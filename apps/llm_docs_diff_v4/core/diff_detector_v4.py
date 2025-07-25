"""
差分検出器 v4 - 改善された位置ベースの差分検出
読み取り順序を正確に考慮し、位置の変化を検出
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import difflib

from apps.llm_docs_diff_v3.models.bbox_models import DiffResult, ChangeType

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """位置情報"""
    page: int
    column: int
    line_index: int
    item_index: int
    x: float
    y: float


class PositionBasedDiffDetector:
    """位置ベースの差分検出器（v4）"""
    
    def __init__(self,
                 position_tolerance: float = 10.0,
                 text_similarity_threshold: float = 0.9,
                 consider_reading_order: bool = True):
        """
        Args:
            position_tolerance: 位置の許容誤差（ピクセル）
            text_similarity_threshold: テキスト類似度の閾値
            consider_reading_order: 読み取り順序を考慮するか
        """
        self.position_tolerance = position_tolerance
        self.text_similarity_threshold = text_similarity_threshold
        self.consider_reading_order = consider_reading_order
    
    def detect_differences(self,
                         doc1_items: List[Dict[str, Any]],
                         doc2_items: List[Dict[str, Any]],
                         doc1_ordered: Optional[List[Dict[str, Any]]] = None,
                         doc2_ordered: Optional[List[Dict[str, Any]]] = None) -> List[DiffResult]:
        """差分を検出"""
        
        # 読み取り順序が提供されていれば使用
        if self.consider_reading_order and doc1_ordered and doc2_ordered:
            doc1_items = doc1_ordered
            doc2_items = doc2_ordered
        
        # 各アイテムに位置情報を付与
        doc1_with_pos = self._add_position_info(doc1_items)
        doc2_with_pos = self._add_position_info(doc2_items)
        
        results = []
        matched_indices2 = set()
        
        # doc1の各アイテムについて処理
        for idx1, (item1, pos1) in enumerate(doc1_with_pos):
            best_match = None
            best_score = 0.0
            best_idx2 = -1
            
            # doc2から最適なマッチを探す
            for idx2, (item2, pos2) in enumerate(doc2_with_pos):
                if idx2 in matched_indices2:
                    continue
                
                # マッチングスコアを計算
                score = self._calculate_match_score(item1, item2, pos1, pos2)
                
                if score > best_score and score >= self.text_similarity_threshold:
                    best_match = item2
                    best_score = score
                    best_idx2 = idx2
            
            if best_match:
                # マッチが見つかった
                matched_indices2.add(best_idx2)
                
                # テキストが完全一致でない場合、または位置が変わった場合は変更として記録
                text1 = item1.get('text', '')
                text2 = best_match.get('text', '')
                if text1 != text2 or self._position_changed(item1, best_match):
                    result = DiffResult(
                        change_type=ChangeType.MODIFICATION,
                        page=item1.get('page', 0),
                        original_bbox=item1,
                        modified_bbox=best_match,
                        semantic_similarity=best_score
                    )
                    results.append(result)
            else:
                # マッチが見つからない = 削除
                result = DiffResult(
                    change_type=ChangeType.DELETION,
                    page=item1.get('page', 0),
                    original_bbox=item1,
                    modified_bbox=None,
                    semantic_similarity=0.0
                )
                results.append(result)
        
        # doc2の未マッチアイテムは追加
        for idx2, (item2, pos2) in enumerate(doc2_with_pos):
            if idx2 not in matched_indices2:
                result = DiffResult(
                    change_type=ChangeType.ADDITION,
                    page=item2.get('page', 0),
                    original_bbox=None,
                    modified_bbox=item2,
                    semantic_similarity=0.0
                )
                results.append(result)
        
        return results
    
    def _add_position_info(self, items: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], PositionInfo]]:
        """各アイテムに位置情報を付与"""
        items_with_pos = []
        
        # ページごとにグループ化
        pages = {}
        for item in items:
            page = item.get('page', 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(item)
        
        # 各ページで処理
        for page_num in sorted(pages.keys()):
            page_items = pages[page_num]
            
            # カラムを検出（簡易版）
            columns = self._detect_columns_simple(page_items)
            
            for col_idx, column_items in enumerate(columns):
                # 行にグループ化
                lines = self._group_into_lines(column_items)
                
                for line_idx, line_items in enumerate(lines):
                    # 行内でソート
                    sorted_line = sorted(line_items, key=lambda x: x['bbox'][0])
                    
                    for item_idx, item in enumerate(sorted_line):
                        pos_info = PositionInfo(
                            page=page_num,
                            column=col_idx,
                            line_index=line_idx,
                            item_index=item_idx,
                            x=item['bbox'][0],
                            y=item['bbox'][1]
                        )
                        items_with_pos.append((item, pos_info))
        
        return items_with_pos
    
    def _detect_columns_simple(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """簡易的なカラム検出"""
        if not items:
            return []
        
        # X座標でグループ化
        x_groups = {}
        for item in items:
            x = item['bbox'][0]
            
            # 既存のグループを探す
            found_group = None
            for group_x in x_groups:
                if abs(x - group_x) < 100:  # 100ピクセル以内なら同じカラム
                    found_group = group_x
                    break
            
            if found_group:
                x_groups[found_group].append(item)
            else:
                x_groups[x] = [item]
        
        # X座標でソート
        sorted_groups = sorted(x_groups.items(), key=lambda x: x[0])
        return [group[1] for group in sorted_groups]
    
    def _group_into_lines(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """アイテムを行にグループ化"""
        if not items:
            return []
        
        # Y座標でソート
        sorted_items = sorted(items, key=lambda x: x['bbox'][1])
        
        lines = []
        current_line = [sorted_items[0]]
        
        for item in sorted_items[1:]:
            # 前のアイテムとY座標を比較
            prev_y = current_line[-1]['bbox'][1]
            prev_h = current_line[-1]['bbox'][3]
            curr_y = item['bbox'][1]
            
            # 同一行判定
            if abs(curr_y - prev_y) < prev_h * 0.5:
                current_line.append(item)
            else:
                lines.append(current_line)
                current_line = [item]
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _calculate_match_score(self, 
                             item1: Dict[str, Any], 
                             item2: Dict[str, Any],
                             pos1: PositionInfo,
                             pos2: PositionInfo) -> float:
        """マッチングスコアを計算"""
        # テキストの類似度
        text1 = item1.get('text', '')
        text2 = item2.get('text', '')
        text_similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # 位置の類似度
        position_score = 1.0
        
        # ページが異なる場合はペナルティ
        if pos1.page != pos2.page:
            position_score *= 0.5
        
        # カラムが異なる場合はペナルティ
        if pos1.column != pos2.column:
            position_score *= 0.8
        
        # 行インデックスの差
        line_diff = abs(pos1.line_index - pos2.line_index)
        if line_diff > 0:
            position_score *= (1.0 / (1.0 + line_diff * 0.1))
        
        # 最終スコア（テキストの重みを高く）
        final_score = text_similarity * 0.8 + position_score * 0.2
        
        return final_score
    
    def _position_changed(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> bool:
        """位置が変化したかチェック"""
        bbox1 = item1['bbox']
        bbox2 = item2['bbox']
        
        # X座標またはY座標の変化をチェック
        x_diff = abs(bbox1[0] - bbox2[0])
        y_diff = abs(bbox1[1] - bbox2[1])
        
        return x_diff > self.position_tolerance or y_diff > self.position_tolerance
    
    def generate_diff_summary(self, diff_results: List[DiffResult]) -> Dict[str, Any]:
        """差分結果のサマリーを生成"""
        summary = {
            'total': len(diff_results),
            'additions': 0,
            'deletions': 0,
            'modifications': 0,
            'by_page': {}
        }
        
        for result in diff_results:
            if result.change_type == ChangeType.ADDITION:
                summary['additions'] += 1
            elif result.change_type == ChangeType.DELETION:
                summary['deletions'] += 1
            elif result.change_type == ChangeType.MODIFICATION:
                summary['modifications'] += 1
            
            # ページごとの統計
            page = result.page
            if page not in summary['by_page']:
                summary['by_page'][page] = {
                    'additions': 0,
                    'deletions': 0,
                    'modifications': 0
                }
            
            if result.change_type == ChangeType.ADDITION:
                summary['by_page'][page]['additions'] += 1
            elif result.change_type == ChangeType.DELETION:
                summary['by_page'][page]['deletions'] += 1
            elif result.change_type == ChangeType.MODIFICATION:
                summary['by_page'][page]['modifications'] += 1
        
        return summary