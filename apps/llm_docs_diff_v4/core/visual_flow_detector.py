"""
ビジュアルフロー検出器
図形要素間の視覚的な流れ（矢印、線、配置パターン）を検出し、
論理的な読み取り順序を推定する
"""
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.cluster import DBSCAN
import logging

logger = logging.getLogger(__name__)


class VisualFlowDetector:
    """ビジュアルフロー検出器"""
    
    def __init__(self,
                 proximity_threshold: float = 50.0,
                 alignment_tolerance: float = 10.0,
                 arrow_keywords: List[str] = None):
        """
        Args:
            proximity_threshold: 要素間の近接性の閾値
            alignment_tolerance: 整列判定の許容誤差
            arrow_keywords: 矢印を示すキーワード
        """
        self.proximity_threshold = proximity_threshold
        self.alignment_tolerance = alignment_tolerance
        self.arrow_keywords = arrow_keywords or ['→', '➡', '▶', '⇒']
    
    def detect_visual_groups(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """視覚的にグループ化された要素を検出"""
        if not items:
            return []
        
        # 座標データを抽出
        positions = np.array([[item['x'], item['y']] for item in items])
        
        # DBSCANでクラスタリング
        clustering = DBSCAN(eps=self.proximity_threshold, min_samples=2)
        labels = clustering.fit_predict(positions)
        
        # グループごとに分類
        groups = {}
        for idx, label in enumerate(labels):
            if label == -1:  # ノイズ点は個別グループ
                groups[f'single_{idx}'] = [items[idx]]
            else:
                if label not in groups:
                    groups[label] = []
                groups[label].append(items[idx])
        
        return list(groups.values())
    
    def detect_flow_pattern(self, group: List[Dict[str, Any]]) -> str:
        """グループ内のフローパターンを検出"""
        if len(group) < 2:
            return 'single'
        
        # 座標を抽出
        positions = [(item['x'], item['y']) for item in group]
        
        # 水平整列をチェック
        y_coords = [pos[1] for pos in positions]
        if max(y_coords) - min(y_coords) < self.alignment_tolerance:
            return 'horizontal'
        
        # 垂直整列をチェック
        x_coords = [pos[0] for pos in positions]
        if max(x_coords) - min(x_coords) < self.alignment_tolerance:
            return 'vertical'
        
        # 円形配置をチェック
        if self._is_circular_arrangement(positions):
            return 'circular'
        
        # 階層的配置をチェック
        if self._is_hierarchical_arrangement(positions):
            return 'hierarchical'
        
        return 'mixed'
    
    def _is_circular_arrangement(self, positions: List[Tuple[float, float]]) -> bool:
        """円形配置かどうかを判定"""
        if len(positions) < 4:
            return False
        
        # 重心を計算
        center_x = sum(pos[0] for pos in positions) / len(positions)
        center_y = sum(pos[1] for pos in positions) / len(positions)
        
        # 各点の重心からの距離
        distances = [
            np.sqrt((pos[0] - center_x)**2 + (pos[1] - center_y)**2)
            for pos in positions
        ]
        
        # 距離の標準偏差が小さければ円形
        std_dev = np.std(distances)
        mean_dist = np.mean(distances)
        
        return std_dev / mean_dist < 0.2 if mean_dist > 0 else False
    
    def _is_hierarchical_arrangement(self, positions: List[Tuple[float, float]]) -> bool:
        """階層的配置かどうかを判定"""
        # Y座標でソート
        sorted_positions = sorted(positions, key=lambda p: p[1])
        
        # レベルごとにグループ化
        levels = []
        current_level = [sorted_positions[0]]
        
        for pos in sorted_positions[1:]:
            if abs(pos[1] - current_level[0][1]) < self.alignment_tolerance:
                current_level.append(pos)
            else:
                levels.append(current_level)
                current_level = [pos]
        
        if current_level:
            levels.append(current_level)
        
        # 3レベル以上あれば階層的とみなす
        return len(levels) >= 3
    
    def detect_arrow_connections(self, items: List[Dict[str, Any]], 
                               azure_features: Optional[Dict[str, Any]] = None) -> List[Tuple[int, int]]:
        """矢印による接続を検出"""
        connections = []
        
        # Azure特徴量から矢印や線を探す
        if azure_features:
            # 図形要素から矢印を検出
            figures = azure_features.get('figures', [])
            for figure in figures:
                if any(keyword in str(figure.get('caption', {}).get('content', '')) 
                      for keyword in self.arrow_keywords):
                    # 矢印の始点と終点を推定
                    connection = self._estimate_arrow_connection(figure, items)
                    if connection:
                        connections.append(connection)
        
        # テキスト内の矢印記号も検出
        for i, item in enumerate(items):
            text = item.get('text', '')
            if any(keyword in text for keyword in self.arrow_keywords):
                # 前後の要素との接続を推定
                if i > 0:
                    connections.append((i-1, i))
                if i < len(items) - 1:
                    connections.append((i, i+1))
        
        return connections
    
    def _estimate_arrow_connection(self, arrow_figure: Dict[str, Any], 
                                 items: List[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
        """矢印図形から接続を推定"""
        # 矢印の境界ボックス
        arrow_bbox = arrow_figure.get('boundingRegions', [{}])[0].get('polygon', [])
        if len(arrow_bbox) < 4:
            return None
        
        # 矢印の開始点と終了点を推定（簡易版）
        # 左端と右端のポイントを使用
        start_x = min(p['x'] for p in arrow_bbox)
        end_x = max(p['x'] for p in arrow_bbox)
        
        # 最も近い要素を探す
        start_idx = None
        end_idx = None
        min_start_dist = float('inf')
        min_end_dist = float('inf')
        
        for idx, item in enumerate(items):
            item_center_x = item['x'] + item['width'] / 2
            
            # 開始点に最も近い要素
            start_dist = abs(item_center_x - start_x)
            if start_dist < min_start_dist and start_dist < self.proximity_threshold:
                min_start_dist = start_dist
                start_idx = idx
            
            # 終了点に最も近い要素
            end_dist = abs(item_center_x - end_x)
            if end_dist < min_end_dist and end_dist < self.proximity_threshold:
                min_end_dist = end_dist
                end_idx = idx
        
        if start_idx is not None and end_idx is not None and start_idx != end_idx:
            return (start_idx, end_idx)
        
        return None
    
    def reorder_by_visual_flow(self, items: List[Dict[str, Any]], 
                             azure_features: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """視覚的な流れに基づいて並び替え"""
        if len(items) <= 1:
            return items
        
        # 視覚的グループを検出
        groups = self.detect_visual_groups(items)
        
        # 各グループのフローパターンを検出
        reordered_items = []
        
        for group in groups:
            pattern = self.detect_flow_pattern(group)
            
            if pattern == 'horizontal':
                # 左から右へ
                group.sort(key=lambda x: x['x'])
            elif pattern == 'vertical':
                # 上から下へ
                group.sort(key=lambda x: x['y'])
            elif pattern == 'circular':
                # 円形の場合は時計回りに並べる
                group = self._sort_circular(group)
            elif pattern == 'hierarchical':
                # 階層的な場合は上から下、各レベルで左から右
                group = self._sort_hierarchical(group)
            else:
                # その他の場合は位置ベース
                group.sort(key=lambda x: (x['y'], x['x']))
            
            reordered_items.extend(group)
        
        # 矢印による接続を考慮
        connections = self.detect_arrow_connections(reordered_items, azure_features)
        if connections:
            reordered_items = self._apply_connections(reordered_items, connections)
        
        return reordered_items
    
    def _sort_circular(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """円形配置の要素を時計回りにソート"""
        # 重心を計算
        center_x = sum(item['x'] for item in items) / len(items)
        center_y = sum(item['y'] for item in items) / len(items)
        
        # 角度でソート
        def angle(item):
            return np.arctan2(item['y'] - center_y, item['x'] - center_x)
        
        # 12時の位置（上）から開始するように調整
        sorted_items = sorted(items, key=angle)
        
        # 最も上にある要素を先頭に
        top_idx = min(range(len(sorted_items)), 
                     key=lambda i: sorted_items[i]['y'])
        
        return sorted_items[top_idx:] + sorted_items[:top_idx]
    
    def _sort_hierarchical(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """階層的配置の要素をソート"""
        # Y座標でグループ化
        levels = {}
        for item in items:
            y_level = round(item['y'] / self.alignment_tolerance) * self.alignment_tolerance
            if y_level not in levels:
                levels[y_level] = []
            levels[y_level].append(item)
        
        # 各レベルを左から右にソート
        sorted_items = []
        for y_level in sorted(levels.keys()):
            level_items = sorted(levels[y_level], key=lambda x: x['x'])
            sorted_items.extend(level_items)
        
        return sorted_items
    
    def _apply_connections(self, items: List[Dict[str, Any]], 
                         connections: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
        """接続情報を使って並び替え"""
        # グラフとして扱い、トポロジカルソートを適用
        # 簡易実装：接続順に並べる
        
        visited = set()
        result = []
        
        # 開始ノードを探す（入次数が0のノード）
        in_degree = {i: 0 for i in range(len(items))}
        for _, end in connections:
            in_degree[end] += 1
        
        # 入次数が0のノードから開始
        queue = [i for i in range(len(items)) if in_degree[i] == 0]
        
        while queue:
            current = queue.pop(0)
            if current not in visited:
                visited.add(current)
                result.append(items[current])
                
                # 接続先を追加
                for start, end in connections:
                    if start == current and end not in visited:
                        queue.append(end)
        
        # 未訪問のノードを追加
        for i in range(len(items)):
            if i not in visited:
                result.append(items[i])
        
        return result