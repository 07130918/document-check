#!/usr/bin/env python3
"""
PDFのテキスト抽出の詳細を確認し、並び替えの影響を分析
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import fitz  # PyMuPDF

def analyze_extraction_methods():
    """異なる抽出方法の比較"""
    pdf_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    
    doc = fitz.open(str(pdf_path))
    page = doc[0]  # 1ページ目
    
    print("=== PDF 1ページ目の詳細分析 ===\n")
    
    # 1. PyMuPDFのget_text("text")による抽出
    print("【1. PyMuPDFのget_text('text')による抽出】")
    print("-" * 80)
    text_simple = page.get_text("text")
    print(text_simple[:500])  # 最初の500文字
    print(f"\n... (全{len(text_simple)}文字)")
    print("-" * 80)
    
    # 2. span単位での抽出と並び替え
    print("\n【2. Span単位での抽出（並び替え前後）】")
    print("-" * 80)
    
    blocks = page.get_text("dict")["blocks"]
    all_spans = []
    
    for block in blocks:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"].strip():
                        all_spans.append({
                            "text": span["text"],
                            "x0": span["bbox"][0],
                            "y0": span["bbox"][1],
                            "x1": span["bbox"][2],
                            "y1": span["bbox"][3]
                        })
    
    # 並び替え前の連結
    print("並び替え前の連結テキスト（最初の500文字）:")
    original_text = "".join([s["text"] for s in all_spans])
    print(original_text[:500])
    
    # 並び替え後の連結
    print("\n並び替え後の連結テキスト（最初の500文字）:")
    sorted_spans = sorted(all_spans, key=lambda s: (round(s["y0"] / 10) * 10, s["x0"]))
    sorted_text = "".join([s["text"] for s in sorted_spans])
    print(sorted_text[:500])
    
    print("-" * 80)
    
    # 3. 行単位での抽出
    print("\n【3. 行単位での抽出（最初の20行）】")
    print("-" * 80)
    
    line_texts = []
    for block in blocks:
        if "lines" in block:
            for line in block["lines"]:
                line_text = ""
                for span in line["spans"]:
                    line_text += span["text"]
                if line_text.strip():
                    line_texts.append({
                        "text": line_text.strip(),
                        "y0": line["bbox"][1],
                        "x0": line["bbox"][0]
                    })
    
    # Y座標でソート
    sorted_lines = sorted(line_texts, key=lambda l: (round(l["y0"] / 10) * 10, l["x0"]))
    
    for i, line in enumerate(sorted_lines[:20]):
        print(f"{i:02d}: {line['text']}")
    
    print("-" * 80)
    
    # 4. 問題点の分析
    print("\n【4. 問題点の分析】")
    print("-" * 80)
    print("1. Span単位の抽出:")
    print("   - 「団」「体」「総」「合」など1文字ずつ分割される")
    print("   - 縦書きテキストも混在")
    print("\n2. 並び替えの影響:")
    print("   - Y座標の10ピクセル丸めで、異なる行が同じグループになる可能性")
    print("   - 縦書きと横書きが混在すると順序が乱れる")
    print("\n3. 文単位の抽出ができない理由:")
    print("   - PDFは文構造を持たない（視覚的な配置のみ）")
    print("   - 句読点での分割などの後処理が必要")
    
    doc.close()

if __name__ == "__main__":
    analyze_extraction_methods()