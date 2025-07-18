"""
改善された出力ハンドラー（読み順序の可視化を改善）
"""
from pathlib import Path
from typing import List, Dict, Any

def create_improved_reading_order_pdf(pdf_bytes: bytes, 
                                    original_order: List[Dict],
                                    estimated_order: List[Dict],
                                    pdf_processor) -> bytes:
    """読み順序を改善した方法で可視化
    
    Args:
        pdf_bytes: 元のPDFバイトデータ
        original_order: 元の順序のBBoxデータ
        estimated_order: 推定された順序のBBoxデータ
        pdf_processor: PDFProcessorインスタンス
        
    Returns:
        ハイライト付きPDFのバイトデータ
    """
    # 元の順序のインデックスマップを作成
    original_index_map = {}
    for idx, bbox_data in enumerate(original_order):
        key = (bbox_data["text"], bbox_data["page"], tuple(bbox_data["bbox"]))
        original_index_map[key] = idx + 1  # 1-indexed
    
    highlights = []
    
    # 推定順序でハイライトを作成
    for new_idx, bbox_data in enumerate(estimated_order):
        # 元の順序での番号を探す
        key = (bbox_data["text"], bbox_data["page"], tuple(bbox_data["bbox"]))
        original_idx = original_index_map.get(key, "?")
        
        # 10個ごとに番号を表示（重なりを避けるため）
        show_label = (new_idx % 10 == 0)
        
        # ラベルには「新順序 (元順序)」の形式で表示
        if show_label:
            label = f"{new_idx + 1} ({original_idx})"
        else:
            label = None
        
        highlights.append({
            "bbox": bbox_data["bbox"],
            "page": bbox_data["page"],
            "color": "blue",
            "label": label
        })
    
    # PDFを作成
    return pdf_processor.create_highlighted_pdf(pdf_bytes, highlights)


def create_comparison_visualization(pdf_bytes: bytes,
                                  original_order: List[Dict],
                                  estimated_order: List[Dict],
                                  pdf_processor) -> bytes:
    """元の順序と推定順序を並べて表示（最初のページのみ）
    
    最初のページに、元の順序と推定順序を並べて表示し、
    順序の変化を矢印で示す
    """
    import fitz
    
    # 新しいPDFドキュメントを作成
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)  # A4横
    
    # フォント設定
    fontsize = 10
    line_height = 15
    
    # 左側: 元の順序
    x_left = 50
    y_start = 50
    page.insert_text((x_left, y_start), "元の順序", fontsize=14, fontname="helv")
    
    # 右側: 推定順序
    x_right = 450
    page.insert_text((x_right, y_start), "推定順序", fontsize=14, fontname="helv")
    
    # 最初の30個の要素を表示
    y = y_start + 30
    max_items = min(30, len(original_order), len(estimated_order))
    
    for i in range(max_items):
        if i < len(original_order):
            orig = original_order[i]
            text = f"{i+1}. {orig['text'][:30]}..."
            page.insert_text((x_left, y), text, fontsize=fontsize)
        
        if i < len(estimated_order):
            est = estimated_order[i]
            text = f"{i+1}. {est['text'][:30]}..."
            page.insert_text((x_right, y), text, fontsize=fontsize)
            
            # 元の順序での位置を探す
            for j, orig in enumerate(original_order):
                if (orig["text"] == est["text"] and 
                    orig["page"] == est["page"] and 
                    orig["bbox"] == est["bbox"]):
                    if j != i:  # 順序が変わっている場合
                        # 矢印を描く
                        color = (1, 0, 0) if j > i else (0, 0, 1)  # 赤：下がった、青：上がった
                        page.draw_line((x_left + 350, y_start + 30 + j * line_height - 5),
                                     (x_right - 10, y - 5),
                                     color=color, width=0.5)
                    break
        
        y += line_height
    
    # PDFをバイトデータに変換
    pdf_bytes = doc.tobytes()
    doc.close()
    
    return pdf_bytes