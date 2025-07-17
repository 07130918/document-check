"""
PDFの詳細検証スクリプト
"""
import fitz  # PyMuPDF
from pathlib import Path

def verify_pdf_detailed():
    """生成されたPDFの詳細を検証"""
    
    # PDFファイルのパス
    pdf_path = Path("/root/AICE/prj-ms-document-check/apps/llm_docs_diff/output/llm_diff_test/PDFs/2023_reading_order.pdf")
    
    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        return
    
    # PDFを開く
    pdf_document = fitz.open(str(pdf_path))
    
    print(f"=== PDF Detailed Analysis ===")
    print(f"PDF: {pdf_path}")
    print(f"Total pages: {len(pdf_document)}")
    print()
    
    # ページ1のみを詳しく調査
    page = pdf_document[0]
    
    # すべてのテキストを取得
    words = page.get_text("words")
    
    print(f"=== Page 1 Analysis ===")
    print(f"Total words on page 1: {len(words)}")
    print()
    
    # 数字のみのテキストを分類
    single_digit_labels = []
    double_digit_labels = []
    triple_digit_labels = []
    large_numbers = []
    text_content = []
    
    for word in words:
        x0, y0, x1, y1, text, _, _, _ = word
        
        if text.isdigit():
            num = int(text)
            if num < 10:
                single_digit_labels.append((num, x0, y0))
            elif num < 100:
                double_digit_labels.append((num, x0, y0))
            elif num < 1000:
                triple_digit_labels.append((num, x0, y0))
            else:
                large_numbers.append((num, x0, y0))
        else:
            text_content.append((text, x0, y0))
    
    print(f"Single digit numbers (1-9): {len(single_digit_labels)}")
    print(f"Double digit numbers (10-99): {len(double_digit_labels)}")
    print(f"Triple digit numbers (100-999): {len(triple_digit_labels)}")
    print(f"Large numbers (1000+): {len(large_numbers)}")
    print(f"Text content: {len(text_content)}")
    print()
    
    # 【団体総合生活補償保険】周辺のテキストを探す
    print("=== Looking for target element area ===")
    target_texts = ["【団体総合生活補償保険（MS&AD型）、GLTD、所得補償保険】", "団体総合生活補償保険", "MS&AD型", "GLTD", "所得補償保険"]
    
    for target in target_texts:
        for text, x, y in text_content:
            if target in text:
                print(f"Found '{text}' at position ({x:.1f}, {y:.1f})")
                
                # 近くの数字を探す
                nearby_numbers = []
                for num, nx, ny in (single_digit_labels + double_digit_labels + triple_digit_labels):
                    if abs(x - nx) < 100 and abs(y - ny) < 50:
                        nearby_numbers.append((num, nx, ny))
                
                if nearby_numbers:
                    print(f"  Nearby numbers: {[(n[0], f'({n[1]:.1f}, {n[2]:.1f})') for n in nearby_numbers]}")
    
    # 1-52の範囲の数字を探す（ページ1の要素数）
    print("\n=== Numbers in expected range (1-52) ===")
    expected_range_numbers = []
    for num, x, y in (single_digit_labels + double_digit_labels):
        if 1 <= num <= 52:
            expected_range_numbers.append((num, x, y))
    
    expected_range_numbers.sort(key=lambda x: x[0])
    print(f"Found {len(expected_range_numbers)} numbers in range 1-52")
    if expected_range_numbers:
        print("First 10:", [(n[0], f'({n[1]:.1f}, {n[2]:.1f})') for n in expected_range_numbers[:10]])
    
    pdf_document.close()

if __name__ == "__main__":
    verify_pdf_detailed()