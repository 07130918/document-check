"""
テキストグループ化ユーティリティ
斜め文字や複数行にまたがるテキストをグループ化
"""
from typing import List, Dict, Any
import math

def group_text_elements(bbox_list: List[Dict[str, Any]], tolerance: float = 5.0) -> List[Dict[str, Any]]:
    """近接するテキスト要素をグループ化
    
    Args:
        bbox_list: BBoxデータのリスト
        tolerance: グループ化の許容誤差（ピクセル）
        
    Returns:
        グループ化されたBBoxデータのリスト
    """
    if not bbox_list:
        return []
    
    # ソート（ページ番号、Y座標、X座標の順）
    sorted_boxes = sorted(bbox_list, key=lambda x: (x["page"], x["bbox"][1], x["bbox"][0]))
    
    grouped = []
    current_group = []
    
    for box in sorted_boxes:
        if not current_group:
            current_group = [box]
            continue
        
        # 最後の要素と比較
        last_box = current_group[-1]
        
        # 同じページで、Y座標が近く、X座標が連続している場合はグループ化
        if (box["page"] == last_box["page"] and
            abs(box["bbox"][1] - last_box["bbox"][1]) <= tolerance and
            box["bbox"][0] - (last_box["bbox"][0] + last_box["bbox"][2]) <= tolerance * 3):
            current_group.append(box)
        else:
            # グループを確定
            if len(current_group) > 1:
                # 複数要素をマージ
                merged = merge_group(current_group)
                grouped.append(merged)
            else:
                grouped.append(current_group[0])
            
            current_group = [box]
    
    # 最後のグループを追加
    if current_group:
        if len(current_group) > 1:
            merged = merge_group(current_group)
            grouped.append(merged)
        else:
            grouped.append(current_group[0])
    
    return grouped

def merge_group(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    """グループ内の要素をマージ
    
    Args:
        group: マージする要素のリスト
        
    Returns:
        マージされた要素
    """
    # テキストを結合
    merged_text = "".join(box["text"] for box in group)
    
    # BBoxを計算（最小X、最小Y、最大幅、最大高さ）
    min_x = min(box["bbox"][0] for box in group)
    min_y = min(box["bbox"][1] for box in group)
    max_x = max(box["bbox"][0] + box["bbox"][2] for box in group)
    max_y = max(box["bbox"][1] + box["bbox"][3] for box in group)
    
    return {
        "text": merged_text,
        "bbox": [min_x, min_y, max_x - min_x, max_y - min_y],
        "page": group[0]["page"],
        "is_merged": True,
        "original_count": len(group)
    }

def split_by_spreads(pages: Dict[int, List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
    """ページを見開き単位に分割（1ページ目は表紙、以降は2/3、4/5のように見開き）
    
    Args:
        pages: ページ番号をキーとするBBoxデータの辞書
        
    Returns:
        見開き単位のBBoxデータのリスト
    """
    spreads = []
    page_numbers = sorted(pages.keys())
    
    if not page_numbers:
        return spreads
    
    # 最初のページ（表紙）は単独で処理
    if 0 in page_numbers:
        spreads.append(pages[0])
    
    # 残りのページを見開き単位で処理（1/2, 3/4, 5/6...）
    # 0-indexedなので、実際のページ番号は+1
    i = 1
    while i < len(page_numbers):
        current_page_num = page_numbers[i]
        spread = []
        
        # 現在のページを追加
        spread.extend(pages[current_page_num])
        
        # 次のページが存在し、見開きのペアになる場合は追加
        if i + 1 < len(page_numbers):
            next_page_num = page_numbers[i + 1]
            # 0-indexedを考慮して、偶数/奇数のペアをチェック
            # ページ1(index 1)とページ2(index 2)、ページ3(index 3)とページ4(index 4)...
            if (current_page_num % 2 == 1 and next_page_num == current_page_num + 1):
                spread.extend(pages[next_page_num])
                i += 2  # 2ページ分進める
            else:
                i += 1  # 1ページ分進める
        else:
            i += 1  # 1ページ分進める
        
        spreads.append(spread)
    
    return spreads