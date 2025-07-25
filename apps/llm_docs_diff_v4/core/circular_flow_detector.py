"""
円形フロー検出器
保険文書でよく見られる円形配置のライフイベント図を検出し、
適切な読み取り順序を推定する
"""
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class CircularFlowDetector:
    """円形フロー検出器"""
    
    def __init__(self, 
                 center_tolerance: float = 50.0,
                 radius_tolerance: float = 30.0,
                 min_items_for_circle: int = 5):
        """
        Args:
            center_tolerance: 中心点の許容誤差
            radius_tolerance: 半径の許容誤差
            min_items_for_circle: 円形と判定する最小要素数
        """
        self.center_tolerance = center_tolerance
        self.radius_tolerance = radius_tolerance
        self.min_items_for_circle = min_items_for_circle
    
    def detect_circular_arrangement(self, items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """円形配置を検出"""
        if len(items) < self.min_items_for_circle:
            return None
        
        # 各アイテムの中心座標を計算
        positions = []
        for item in items:
            x = item.get('x', 0) + item.get('width', 0) / 2
            y = item.get('y', 0) + item.get('height', 0) / 2
            positions.append((x, y))
        
        # 重心を計算
        center_x = sum(p[0] for p in positions) / len(positions)
        center_y = sum(p[1] for p in positions) / len(positions)
        
        # 各点の重心からの距離
        distances = []
        for x, y in positions:
            dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            distances.append(dist)
        
        # 平均半径と標準偏差
        mean_radius = np.mean(distances)
        std_radius = np.std(distances)
        
        # 円形判定：標準偏差が小さい場合
        if mean_radius > 0 and std_radius / mean_radius < 0.3:
            return {
                'center': (center_x, center_y),
                'radius': mean_radius,
                'std_deviation': std_radius,
                'items': items
            }
        
        return None
    
    def sort_circular_items(self, items: List[Dict[str, Any]], 
                          center: Tuple[float, float]) -> List[Dict[str, Any]]:
        """円形配置のアイテムを時計回りにソート"""
        # 各アイテムの角度を計算
        items_with_angle = []
        
        for item in items:
            # アイテムの中心座標
            x = item.get('x', 0) + item.get('width', 0) / 2
            y = item.get('y', 0) + item.get('height', 0) / 2
            
            # 中心からの角度（ラジアン）
            angle = np.arctan2(y - center[1], x - center[0])
            
            # 12時の位置を0度として調整（通常は3時が0度）
            adjusted_angle = (angle + np.pi/2) % (2 * np.pi)
            
            items_with_angle.append((item, adjusted_angle))
        
        # 角度でソート
        sorted_items = sorted(items_with_angle, key=lambda x: x[1])
        
        return [item for item, _ in sorted_items]
    
    def detect_life_cycle_pattern(self, items: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """ライフサイクルパターンを検出（入社→結婚→出産→...→退職）"""
        # キーワードとその典型的な順序
        life_cycle_keywords = {
            '入社': 1,
            '就職': 1,
            '結婚': 2,
            '婚姻': 2,
            '出産': 3,
            'ベビー': 3,
            'Baby': 3,
            '住宅': 4,
            '購入': 4,
            'マイホーム': 4,
            '子供': 5,
            '子ども': 5,
            '独立': 6,
            '退職': 7,
            '定年': 7
        }
        
        # ライフサイクル要素を検出
        life_cycle_items = []
        for idx, item in enumerate(items):
            text = item.get('text', '')
            for keyword, order in life_cycle_keywords.items():
                if keyword in text:
                    life_cycle_items.append({
                        'item': item,
                        'index': idx,
                        'order': order,
                        'keyword': keyword
                    })
                    break
        
        if len(life_cycle_items) >= 3:  # 3つ以上のライフイベントがある場合
            return life_cycle_items
        
        return None
    
    def reorder_circular_flow(self, items: List[Dict[str, Any]], 
                            start_index: int = 0,
                            end_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """指定範囲内で円形フローを検出して並べ替え"""
        if end_index is None:
            end_index = len(items)
        
        # 指定範囲のアイテムを取得
        target_items = items[start_index:end_index]
        
        # 円形配置を検出
        circle_info = self.detect_circular_arrangement(target_items)
        
        if circle_info:
            # 円形配置が検出された場合
            center = circle_info['center']
            sorted_items = self.sort_circular_items(target_items, center)
            
            # ライフサイクルパターンも確認
            life_cycle = self.detect_life_cycle_pattern(sorted_items)
            
            if life_cycle:
                # ライフサイクルの開始点を見つける
                start_orders = [lc['order'] for lc in life_cycle]
                min_order = min(start_orders)
                
                # 最小順序のアイテムから開始するように調整
                start_item_idx = None
                for i, item in enumerate(sorted_items):
                    for lc in life_cycle:
                        if lc['item'] == item and lc['order'] == min_order:
                            start_item_idx = i
                            break
                    if start_item_idx is not None:
                        break
                
                if start_item_idx is not None:
                    # 開始点から並べ替え
                    sorted_items = sorted_items[start_item_idx:] + sorted_items[:start_item_idx]
                    logger.info(f"円形ライフサイクルパターンを検出: 開始={life_cycle[0]['keyword']}")
            
            # 結果を構築
            result = items[:start_index] + sorted_items + items[end_index:]
            return result
        
        # 円形配置が検出されなかった場合は元のまま
        return items
    
    def find_circular_groups(self, items: List[Dict[str, Any]], 
                           proximity_threshold: float = 200.0) -> List[List[int]]:
        """近接するアイテムから円形グループを検出"""
        # Y座標でグループ化
        y_groups = defaultdict(list)
        
        for idx, item in enumerate(items):
            y = item.get('y', 0)
            # 近い Y座標をグループ化
            group_key = int(y / proximity_threshold)
            y_groups[group_key].append(idx)
        
        # 各グループで円形配置を検出
        circular_groups = []
        
        for indices in y_groups.values():
            if len(indices) >= self.min_items_for_circle:
                group_items = [items[i] for i in indices]
                if self.detect_circular_arrangement(group_items):
                    circular_groups.append(indices)
        
        return circular_groups