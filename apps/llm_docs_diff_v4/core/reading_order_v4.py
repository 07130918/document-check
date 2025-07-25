"""
Reading Order Estimator v4 - カラム検出と論理的な読み取り順序
複数カラムのレイアウトに対応し、より正確な読み取り順序を推定
"""
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.cluster import DBSCAN
import logging
from apps.llm_docs_diff_v4.core.reading_order_llm import LLMReadingOrderEstimator
from apps.llm_docs_diff_v4.core.life_event_detector import LifeEventDetector
from apps.llm_docs_diff_v4.core.visual_flow_detector import VisualFlowDetector

logger = logging.getLogger(__name__)


class ReadingOrderEstimatorV4:
    """高度な読み取り順序推定システム"""
    
    def __init__(self, 
                 line_height_ratio: float = 0.5,
                 column_gap_threshold: float = 50.0,
                 min_column_width: float = 100.0,
                 same_line_tolerance: float = 5.0,
                 use_llm: bool = False,
                 openai_api_key: Optional[str] = None):
        """
        Args:
            line_height_ratio: 同一行と判定する高さの比率
            column_gap_threshold: カラム間の最小ギャップ
            min_column_width: カラムの最小幅
            same_line_tolerance: 同一行判定のY座標許容差
            use_llm: LLMを使用するかどうか
            openai_api_key: OpenAI APIキー
        """
        self.line_height_ratio = line_height_ratio
        self.column_gap_threshold = column_gap_threshold
        self.min_column_width = min_column_width
        self.same_line_tolerance = same_line_tolerance
        self.use_llm = use_llm
        
        # LLM推定器の初期化
        if use_llm:
            self.llm_estimator = LLMReadingOrderEstimator(api_key=openai_api_key)
        else:
            self.llm_estimator = None
        
        # ライフイベント検出器とビジュアルフロー検出器の初期化
        self.life_event_detector = LifeEventDetector()
        self.visual_flow_detector = VisualFlowDetector()
    
    def estimate_reading_order(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """読み取り順序を推定（カラム対応）"""
        if not bbox_list:
            return []
        
        # ページごとに処理
        pages = self._group_by_page(bbox_list)
        ordered_list = []
        
        for page_num in sorted(pages.keys()):
            page_items = pages[page_num]
            logger.info(f"Processing page {page_num} with {len(page_items)} items")
            
            # カラムを検出
            columns = self._detect_columns(page_items)
            logger.info(f"Detected {len(columns)} columns on page {page_num}")
            
            # 各カラムを処理
            for col_idx, column_items in enumerate(columns):
                logger.debug(f"  Column {col_idx}: {len(column_items)} items")
                
                # カラム内で行にグループ化
                lines = self._group_into_lines_advanced(column_items)
                
                # 行をY座標でソート
                sorted_lines = sorted(lines, key=lambda line: self._get_line_center_y(line))
                
                # 各行内でX座標でソート
                for line in sorted_lines:
                    # bbox形式を確認
                    if line and 'bbox' in line[0]:
                        sorted_line = sorted(line, key=lambda item: item['bbox'][0])
                    else:
                        sorted_line = sorted(line, key=lambda item: item.get('x', 0))
                    ordered_list.extend(sorted_line)
        
        # ライフイベントの論理的順序を適用
        ordered_list = self._apply_life_event_ordering(ordered_list)
        
        return ordered_list
    
    def _apply_life_event_ordering(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ライフイベントの論理的順序を適用"""
        logger.info("ライフイベント順序の適用を開始")
        
        # 各ページごとに処理
        pages = self._group_by_page(items)
        reordered_list = []
        
        for page_num in sorted(pages.keys()):
            page_items = pages[page_num]
            logger.info(f"ページ {page_num} のアイテム数: {len(page_items)}")
            
            # ライフイベントを検出して並べ替え
            reordered_page = self.life_event_detector.reorder_life_events(page_items)
            reordered_list.extend(reordered_page)
        
        logger.info(f"並べ替え後の総アイテム数: {len(reordered_list)}")
        return reordered_list
    
    def _group_by_page(self, bbox_list: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """ページごとにアイテムをグループ化"""
        pages = {}
        for item in bbox_list:
            page = item.get('page', 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(item)
        return pages
    
    def _detect_columns(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """カラムを検出（X座標のクラスタリング）"""
        if not items:
            return []
        
        # X座標の範囲を取得
        x_positions = []
        for item in items:
            # bbox形式とx,y形式の両方に対応
            if 'bbox' in item:
                x = item['bbox'][0]
            else:
                x = item.get('x', 0)
            x_positions.append([x])  # DBSCANは2D配列を期待
        
        if len(set(x[0] for x in x_positions)) < 2:
            # すべて同じX座標の場合は単一カラム
            return [items]
        
        # DBSCANでX座標をクラスタリング
        x_array = np.array(x_positions)
        clustering = DBSCAN(
            eps=self.column_gap_threshold, 
            min_samples=3
        ).fit(x_array)
        
        # クラスタごとにアイテムをグループ化
        clusters = {}
        for idx, label in enumerate(clustering.labels_):
            if label == -1:  # ノイズは最も近いクラスタに割り当て
                label = self._find_nearest_cluster(
                    x_positions[idx][0], 
                    clusters, 
                    clustering.labels_, 
                    x_positions
                )
            
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(items[idx])
        
        # クラスタをX座標でソート（左から右）
        sorted_clusters = sorted(
            clusters.items(), 
            key=lambda x: self._get_cluster_center_x(x[1])
        )
        
        # カラムのリストを返す
        columns = [cluster[1] for cluster in sorted_clusters]
        
        # 小さすぎるカラムをマージ
        columns = self._merge_small_columns(columns)
        
        return columns
    
    def _find_nearest_cluster(self, x: float, clusters: Dict, labels: np.ndarray, 
                            x_positions: List[List[float]]) -> int:
        """最も近いクラスタを見つける"""
        min_distance = float('inf')
        nearest_label = 0
        
        for idx, label in enumerate(labels):
            if label != -1:
                distance = abs(x - x_positions[idx][0])
                if distance < min_distance:
                    min_distance = distance
                    nearest_label = label
        
        return nearest_label
    
    def _get_cluster_center_x(self, items: List[Dict[str, Any]]) -> float:
        """クラスタの中心X座標を取得"""
        x_values = []
        for item in items:
            if 'bbox' in item:
                x_values.append(item['bbox'][0])
            else:
                x_values.append(item.get('x', 0))
        return sum(x_values) / len(x_values) if x_values else 0
    
    def _merge_small_columns(self, columns: List[List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
        """小さすぎるカラムを隣接カラムにマージ"""
        if len(columns) <= 1:
            return columns
        
        merged = []
        skip_next = False
        
        for i in range(len(columns)):
            if skip_next:
                skip_next = False
                continue
            
            column = columns[i]
            
            # カラムの幅を計算
            x_min = min(item['bbox'][0] for item in column)
            x_max = max(item['bbox'][0] + item['bbox'][2] for item in column)
            width = x_max - x_min
            
            if width < self.min_column_width and i < len(columns) - 1:
                # 次のカラムとマージ
                next_column = columns[i + 1]
                merged.append(column + next_column)
                skip_next = True
            else:
                merged.append(column)
        
        return merged
    
    def _group_into_lines_advanced(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """アイテムを行にグループ化（改良版）"""
        if not items:
            return []
        
        # Y座標でソート
        def get_y(item):
            if 'bbox' in item:
                return item['bbox'][1]
            else:
                return item.get('y', 0)
        
        sorted_items = sorted(items, key=get_y)
        
        lines = []
        current_line = [sorted_items[0]]
        
        for i in range(1, len(sorted_items)):
            item = sorted_items[i]
            
            # 現在の行との重なりをチェック
            if self._items_on_same_line(current_line[-1], item):
                current_line.append(item)
            else:
                # 新しい行を開始
                lines.append(current_line)
                current_line = [item]
        
        # 最後の行を追加
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _items_on_same_line(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> bool:
        """2つのアイテムが同一行にあるか判定"""
        # Y座標とheightを取得
        if 'bbox' in item1:
            y1 = item1['bbox'][1]
            h1 = item1['bbox'][3]
        else:
            y1 = item1.get('y', 0)
            h1 = item1.get('height', 0)
        
        if 'bbox' in item2:
            y2 = item2['bbox'][1]
            h2 = item2['bbox'][3]
        else:
            y2 = item2.get('y', 0)
            h2 = item2.get('height', 0)
        
        # アイテムの中心Y座標
        center_y1 = y1 + h1 / 2
        center_y2 = y2 + h2 / 2
        
        # 中心Y座標の差が許容範囲内か
        center_diff = abs(center_y2 - center_y1)
        avg_height = (h1 + h2) / 2
        
        # より厳密な同一行判定
        if center_diff <= self.same_line_tolerance:
            return True
        
        # 高さの比率を考慮した判定
        if center_diff <= avg_height * self.line_height_ratio:
            # Y座標の重なりもチェック
            overlap = min(y1 + h1, y2 + h2) - max(y1, y2)
            if overlap > 0:
                overlap_ratio = overlap / min(h1, h2)
                return overlap_ratio > 0.5
        
        return False
    
    def _get_line_center_y(self, line: List[Dict[str, Any]]) -> float:
        """行の中心Y座標を取得"""
        y_values = []
        for item in line:
            if 'bbox' in item:
                y = item['bbox'][1]
                h = item['bbox'][3]
            else:
                y = item.get('y', 0)
                h = item.get('height', 0)
            y_values.append(y + h / 2)
        return sum(y_values) / len(y_values) if y_values else 0
    
    def debug_reading_order(self, bbox_list: List[Dict[str, Any]], output_path: str):
        """読み取り順序をデバッグ出力"""
        ordered = self.estimate_reading_order(bbox_list)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("Index,Page,Text,X,Y,Width,Height,Column\n")
            
            for idx, item in enumerate(ordered):
                bbox = item['bbox']
                text = item.get('text', '').replace('\n', ' ')
                page = item.get('page', 0)
                
                # どのカラムに属するか推定
                column = self._estimate_column_index(item, bbox_list)
                
                f.write(f"{idx},{page},\"{text}\",{bbox[0]:.1f},{bbox[1]:.1f},"
                       f"{bbox[2]:.1f},{bbox[3]:.1f},{column}\n")
    
    def _estimate_column_index(self, item: Dict[str, Any], all_items: List[Dict[str, Any]]) -> int:
        """アイテムがどのカラムに属するか推定"""
        page = item.get('page', 0)
        page_items = [it for it in all_items if it.get('page', 0) == page]
        
        if not page_items:
            return 0
        
        columns = self._detect_columns(page_items)
        
        for col_idx, column in enumerate(columns):
            if item in column:
                return col_idx
        
        return -1
    
    def estimate_reading_order_with_azure(self, 
                                        bbox_list: List[Dict[str, Any]], 
                                        azure_result: Any = None,
                                        azure_hierarchy: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Azure Document Intelligenceの情報を使用して読み取り順序を推定
        
        Args:
            bbox_list: テキスト要素のリスト
            azure_result: Azure Document Intelligenceの完全な結果
            azure_hierarchy: Azure階層データ（代替）
            
        Returns:
            並び替えられたテキスト要素のリスト
        """
        if not self.use_llm or not self.llm_estimator:
            # LLMを使用しない場合は通常の処理
            return self.estimate_reading_order(bbox_list)
        
        if azure_result:
            # Azure結果がある場合はLLMで処理
            ordered_list = []
            pages = self._group_by_page(bbox_list)
            
            for page_num in sorted(pages.keys()):
                page_items = pages[page_num]
                logger.info(f"Processing page {page_num} with LLM")
                
                # LLMで各ページを処理
                page_ordered = self.llm_estimator.estimate_reading_order_with_llm(
                    page_items, azure_result, page_num
                )
                ordered_list.extend(page_ordered)
            
            # ライフイベントの論理的順序を適用
            ordered_list = self._apply_life_event_ordering(ordered_list)
            
            return ordered_list
        
        elif azure_hierarchy:
            # 階層データがある場合
            ordered_list = self.llm_estimator.process_with_azure_features(bbox_list, azure_hierarchy)
            
            # ライフイベントの論理的順序を適用
            ordered_list = self._apply_life_event_ordering(ordered_list)
            
            return ordered_list
        
        else:
            # Azure情報がない場合は通常の処理
            logger.warning("No Azure information provided. Using standard ordering.")
            return self.estimate_reading_order(bbox_list)