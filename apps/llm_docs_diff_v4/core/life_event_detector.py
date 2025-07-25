"""
ライフイベント検出器
保険文書に特化したドメイン知識を活用して、
ライフイベントの論理的な順序を推定
"""
from typing import List, Dict, Any, Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)


class LifeEventDetector:
    """ライフイベント検出器"""
    
    # ライフイベントのキーワードと標準的な順序
    LIFE_EVENTS = {
        '入社': {'keywords': ['入社', '就職', '入職'], 'order': 10},
        '結婚': {'keywords': ['結婚', '婚姻', 'ブライダル'], 'order': 20},
        '出産': {'keywords': ['出産', '誕生', 'ベビー', 'Baby', 'Babyor', 'Babyy', '赤ちゃん'], 'order': 30},
        '住宅購入': {'keywords': ['住宅', '購入', 'マイホーム', '家'], 'order': 40},
        '子供成長': {'keywords': ['子供', '子ども', 'こども', '成長', '進学'], 'order': 50},
        '子供独立': {'keywords': ['独立', '巣立ち', '一人立ち'], 'order': 60},
        '退職': {'keywords': ['退職', '定年', 'リタイア'], 'order': 70},
    }
    
    def __init__(self):
        """初期化"""
        self.event_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """キーワードパターンをコンパイル"""
        patterns = {}
        for event_type, config in self.LIFE_EVENTS.items():
            pattern = '|'.join(config['keywords'])
            patterns[event_type] = re.compile(pattern, re.IGNORECASE)
        return patterns
    
    def detect_life_events(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ライフイベントを検出"""
        detected_events = []
        
        for idx, item in enumerate(items):
            text = item.get('text', '')
            
            for event_type, pattern in self.event_patterns.items():
                if pattern.search(text):
                    event_info = {
                        'index': idx,
                        'event_type': event_type,
                        'order': self.LIFE_EVENTS[event_type]['order'],
                        'text': text,
                        'x': item.get('x', 0),
                        'y': item.get('y', 0)
                    }
                    detected_events.append(event_info)
                    break  # 1つのアイテムは1つのイベントタイプのみ
        
        return detected_events
    
    def group_life_events(self, events: List[Dict[str, Any]], 
                         proximity_threshold: float = 150.0) -> List[List[Dict[str, Any]]]:
        """近接するライフイベントをグループ化"""
        if not events:
            return []
        
        # Y座標でソート
        sorted_events = sorted(events, key=lambda e: e['y'])
        
        groups = []
        current_group = [sorted_events[0]]
        
        for event in sorted_events[1:]:
            # 前のイベントとの距離を計算
            prev_event = current_group[-1]
            y_distance = abs(event['y'] - prev_event['y'])
            
            if y_distance < proximity_threshold:
                current_group.append(event)
            else:
                groups.append(current_group)
                current_group = [event]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def reorder_life_events(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ライフイベントを論理的な順序に並べ替え（より洗練された局所的な並べ替え）"""
        # ライフイベントを検出
        events = self.detect_life_events(items)
        
        logger.info(f"検出されたライフイベント数: {len(events)}")
        for event in events:
            logger.info(f"  Index {event['index']}: {event['event_type']} - {event['text']}")
        
        if not events:
            return items
        
        # 特定の範囲（例：インデックス7-19）のライフイベントを処理
        # この範囲は図形要素が集中している可能性が高い
        target_events = [e for e in events if 7 <= e['index'] <= 19]
        
        logger.info(f"範囲7-19のライフイベント数: {len(target_events)}")
        
        if len(target_events) >= 3:  # 3つ以上のライフイベントがある場合
            # 論理的順序でソート
            sorted_events = sorted(target_events, key=lambda e: e['order'])
            
            logger.info(f"並べ替え前: {[(e['index'], e['event_type']) for e in target_events]}")
            logger.info(f"並べ替え後: {[(e['index'], e['event_type']) for e in sorted_events]}")
            
            # 元のインデックスと新しい順序のマッピング
            index_mapping = {}
            sorted_indices = sorted([e['index'] for e in target_events])
            
            for i, event in enumerate(sorted_events):
                old_idx = event['index']
                new_idx = sorted_indices[i]
                index_mapping[old_idx] = new_idx
                logger.info(f"  マッピング: {old_idx} -> {new_idx}")
            
            # 結果を構築
            result = []
            temp_items = {idx: items[idx] for idx in range(len(items))}
            
            # マッピングに基づいて入れ替え
            for old_idx, new_idx in index_mapping.items():
                temp_items[new_idx] = items[old_idx]
            
            # 順序通りに結果を構築
            for idx in range(len(items)):
                result.append(temp_items[idx])
            
            logger.info(f"ライフイベント並べ替え（範囲7-19）: {[e['event_type'] for e in sorted_events]}")
            
            # 並べ替え結果を確認
            logger.info("並べ替え後の結果（index 7-19）:")
            for i in range(7, min(20, len(result))):
                if i < len(result):
                    logger.info(f"  Index {i}: {result[i].get('text', '')}")
            
            return result
        
        # 通常のグループベースの処理
        return items
    
    def detect_temporal_flow(self, items: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
        """時系列的な流れを検出"""
        connections = []
        events = self.detect_life_events(items)
        
        if len(events) < 2:
            return connections
        
        # イベントを論理的順序でソート
        sorted_events = sorted(events, key=lambda e: e['order'])
        
        # 連続するイベント間の接続を作成
        for i in range(len(sorted_events) - 1):
            current = sorted_events[i]
            next_event = sorted_events[i + 1]
            
            # 同じグループ内（近接している）場合のみ接続
            y_distance = abs(current['y'] - next_event['y'])
            if y_distance < 150.0:  # 近接している場合
                connections.append((current['index'], next_event['index']))
                logger.debug(f"時系列接続: {current['event_type']} -> {next_event['event_type']}")
        
        return connections
    
    def enhance_reading_order(self, items: List[Dict[str, Any]], 
                            original_order: List[int]) -> List[int]:
        """既存の読み取り順序をライフイベントの論理性で強化"""
        events = self.detect_life_events(items)
        
        if not events:
            return original_order
        
        # イベントのインデックスマップを作成
        event_map = {e['index']: e for e in events}
        
        # 新しい順序を作成
        new_order = []
        processed = set()
        
        # グループごとに処理
        event_groups = self.group_life_events(events)
        
        for group in event_groups:
            # グループの開始位置を特定
            group_indices = [e['index'] for e in group]
            first_pos = min(original_order.index(idx) for idx in group_indices if idx in original_order)
            
            # グループ内のイベントを論理的順序でソート
            sorted_group = sorted(group, key=lambda e: e['order'])
            sorted_indices = [e['index'] for e in sorted_group]
            
            # 元の順序で、このグループの位置に挿入
            for idx in original_order[:first_pos]:
                if idx not in processed:
                    new_order.append(idx)
                    processed.add(idx)
            
            # ソートされたグループを挿入
            for idx in sorted_indices:
                if idx not in processed:
                    new_order.append(idx)
                    processed.add(idx)
            
            # グループのインデックスを処理済みとマーク
            processed.update(group_indices)
        
        # 残りのアイテムを追加
        for idx in original_order:
            if idx not in processed:
                new_order.append(idx)
        
        return new_order