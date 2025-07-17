"""
PDFハイライトラベルを検証するスクリプト
"""
import fitz  # PyMuPDF
import json
from pathlib import Path

def verify_pdf_highlights():
    """生成されたPDFのハイライトラベルを検証"""
    
    # PDFファイルのパス
    pdf_path = Path("/root/AICE/prj-ms-document-check/apps/llm_docs_diff/output/llm_diff_test/PDFs/2023_reading_order.pdf")
    
    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        return
    
    # PDFを開く
    pdf_document = fitz.open(str(pdf_path))
    
    print(f"=== PDF Highlight Verification ===")
    print(f"PDF: {pdf_path}")
    print(f"Total pages: {len(pdf_document)}")
    print()
    
    # ターゲットBBox（許容誤差を含む）
    target_bbox = [159.26, 171.93, 276.75, 15.47]
    tolerance = 2.0  # ピクセルの許容誤差
    
    # 509番のラベルを探す
    label_509_found = False
    target_bbox_label = None
    
    # 各ページの注釈を確認
    all_labels = []
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        
        # ページ上のすべてのテキストを取得（デバッグ用）
        text_instances = page.get_text("dict")
        
        # ハイライト注釈を探す
        for annot in page.annots():
            if annot.type[0] == 8:  # Highlight annotation
                rect = annot.rect
                
                # 関連するテキストを探す
                nearby_text = None
                for block in text_instances["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                span_rect = fitz.Rect(span["bbox"])
                                if rect.intersects(span_rect):
                                    nearby_text = span["text"]
                                    break
                
                # ラベル付きテキストを探す（ハイライトの近くのテキスト）
                page_text = page.get_text()
                
                # ページ上のすべてのテキストインスタンスから番号を抽出
                words = page.get_text("words")
                for word in words:
                    x0, y0, x1, y1, text, _, _, _ = word
                    
                    # 数字のみのテキストを探す
                    if text.isdigit():
                        label_num = int(text)
                        all_labels.append({
                            "page": page_num,
                            "label": label_num,
                            "bbox": [x0, y0, x1, y1],
                            "nearby_highlight": rect if abs(x0 - rect.x1) < 20 else None
                        })
                        
                        if label_num == 509:
                            label_509_found = True
                            print(f"Found label 509 on page {page_num + 1}:")
                            print(f"  Position: [{x0:.2f}, {y0:.2f}, {x1:.2f}, {y1:.2f}]")
                            print(f"  Nearby text: {nearby_text}")
                        
                        # ターゲットBBoxの近くのラベルを確認
                        if (page_num == 0 and  # ページ1
                            abs(y0 - target_bbox[1]) < tolerance * 10):  # Y座標が近い
                            if abs(x0 - (target_bbox[0] + target_bbox[2])) < 50:  # ラベルは右側にある
                                target_bbox_label = label_num
    
    pdf_document.close()
    
    # 結果を報告
    print("\n=== Analysis Results ===")
    
    if label_509_found:
        print("✓ Label 509 was found in the PDF")
    else:
        print("✗ Label 509 was NOT found in the PDF")
    
    if target_bbox_label:
        print(f"\nThe label for the target element (【団体総合生活補償保険...】) is: {target_bbox_label}")
    else:
        print("\n✗ Could not find a label for the target element")
    
    # ラベルの統計
    if all_labels:
        label_numbers = sorted([item["label"] for item in all_labels])
        print(f"\n=== Label Statistics ===")
        print(f"Total labels found: {len(label_numbers)}")
        print(f"Label range: {min(label_numbers)} - {max(label_numbers)}")
        print(f"First 10 labels: {label_numbers[:10]}")
        print(f"Last 10 labels: {label_numbers[-10:]}")
        
        # ページ1のラベルのみ
        page1_labels = sorted([item["label"] for item in all_labels if item["page"] == 0])
        if page1_labels:
            print(f"\nPage 1 labels ({len(page1_labels)} total):")
            print(f"First 10: {page1_labels[:10]}")
            if len(page1_labels) > 10:
                print(f"Last 10: {page1_labels[-10:]}")

if __name__ == "__main__":
    verify_pdf_highlights()