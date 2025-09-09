"""
Reading Order Estimator v2 - 同一行内の要素を適切にグループ化
"""
from typing import List, Dict, Any, Tuple


class ReadingOrderEstimatorV2:
    """改良版の読み取り順序推定システム"""
    
    def __init__(self, 
                 line_height_ratio: float = 0.5,
                 max_word_gap_ratio: float = 3.0):
        """
        Args:
            line_height_ratio: 同一行と判定する高さの比率（文字高さに対して）
            max_word_gap_ratio: 同一行内の最大単語間隔（文字幅に対して）
        """
        self.line_height_ratio = line_height_ratio
        self.max_word_gap_ratio = max_word_gap_ratio
    
    def estimate_reading_order(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """読み取り順序を推定（同一行を保持）"""
        if not bbox_list:
            return []
        
        # ページごとに処理
        pages = {}
        for item in bbox_list:
            page = item['page']
            if page not in pages:
                pages[page] = []
            pages[page].append(item)
        
        ordered_list = []
        
        for page_num in sorted(pages.keys()):
            page_items = pages[page_num]
            
            # 行にグループ化
            lines = self._group_into_lines(page_items)
            
            # 行をY座標でソート（上から下）
            sorted_lines = sorted(lines, key=lambda line: self._get_line_y(line))
            
            # 各行内でX座標でソート（左から右）
            for line in sorted_lines:
                sorted_line = sorted(line, key=lambda item: item['x'])
                ordered_list.extend(sorted_line)
        
        return ordered_list
    
    def _group_into_lines(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """アイテムを行にグループ化"""
        if not items:
            return []
        
        # Y座標でソート
        sorted_items = sorted(items, key=lambda item: item['y'])
        
        lines = []
        current_line = [sorted_items[0]]
        current_line_y = sorted_items[0]['y']
        current_line_height = sorted_items[0]['height']
        
        for i in range(1, len(sorted_items)):
            item = sorted_items[i]
            
            # 同一行判定（Y座標の差が文字高さの比率以内）
            y_diff = abs(item['y'] - current_line_y)
            height_threshold = max(current_line_height, item['height']) * self.line_height_ratio
            
            if y_diff <= height_threshold:
                # 同一行として追加
                current_line.append(item)
                # 行の代表Y座標と高さを更新
                current_line_y = sum(it['y'] for it in current_line) / len(current_line)
                current_line_height = max(it['height'] for it in current_line)
            else:
                # 新しい行を開始
                lines.append(current_line)
                current_line = [item]
                current_line_y = item['y']
                current_line_height = item['height']
        
        # 最後の行を追加
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _get_line_y(self, line: List[Dict[str, Any]]) -> float:
        """行の代表Y座標を取得"""
        return sum(item['y'] for item in line) / len(line)
    
    def _should_merge_lines(self, line1: List[Dict[str, Any]], line2: List[Dict[str, Any]]) -> bool:
        """2つの行をマージすべきか判定"""
        # 行の平均Y座標を計算
        y1 = self._get_line_y(line1)
        y2 = self._get_line_y(line2)
        
        # 行の平均高さを計算
        height1 = sum(item['height'] for item in line1) / len(line1)
        height2 = sum(item['height'] for item in line2) / len(line2)
        avg_height = (height1 + height2) / 2
        
        # Y座標の差が平均高さの半分以下ならマージ
        return abs(y2 - y1) <= avg_height * self.line_height_ratio