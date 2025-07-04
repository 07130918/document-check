#!/usr/bin/env python3
"""
PDF1ページ目のテキスト抽出結果を確認するスクリプト
"""
import sys
from pathlib import Path
import json

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.pdf_diff_system.app.modules.reading_order.pdf_text_extractor import PDFTextExtractor

def test_page1_extraction():
    """1ページ目の抽出結果を詳細に出力"""
    pdf_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    
    extractor = PDFTextExtractor()
    
    print("=== PDF 1ページ目のテキスト抽出テスト ===\n")
    
    # 1. 通常のテキスト抽出（extract_pages_text）
    print("【1. 通常のテキスト抽出結果（extract_pages_text）】")
    print("-" * 80)
    pages_text = extractor.extract_pages_text(pdf_path, max_pages=1)
    page1_text = pages_text.get(1, "")
    print(page1_text)
    print(f"\n文字数: {len(page1_text)}")
    print("-" * 80)
    
    # 2. レイアウト付きテキスト抽出（メソッドが存在しない場合はスキップ）
    print("\n【2. レイアウト付きテキスト抽出結果】")
    print("-" * 80)
    print("（extract_page_with_layoutメソッドは存在しません）")
    print("-" * 80)
    
    # 3. テキストブロック抽出（extract_text_blocks）
    print("\n【3. テキストブロック単位の抽出結果（extract_text_blocks）】")
    print("-" * 80)
    text_blocks = extractor.extract_text_blocks(pdf_path, 1)
    for i, block in enumerate(text_blocks[:20]):  # 最初の20ブロックのみ表示
        print(f"Block {i:02d}: Y={block['y0']:6.1f}, X={block['x0']:6.1f} | {block['text'][:50]}...")
    print(f"\n総ブロック数: {len(text_blocks)}")
    print("-" * 80)
    
    # 4. 並び替え前後の比較（PyMuPDFの生データ）
    print("\n【4. 並び替え前後の比較】")
    print("-" * 80)
    
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        
        # 生のspan取得
        blocks = page.get_text("dict")["blocks"]
        raw_spans = []
        
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["text"].strip():
                            raw_spans.append({
                                "text": span["text"],
                                "x0": span["bbox"][0],
                                "y0": span["bbox"][1],
                                "x1": span["bbox"][2],
                                "y1": span["bbox"][3]
                            })
        
        # 並び替え前（出現順）
        print("並び替え前（最初の10個）:")
        for i, span in enumerate(raw_spans[:10]):
            print(f"  {i:02d}: Y={span['y0']:6.1f}, X={span['x0']:6.1f} | {span['text']}")
        
        # 並び替え後（Y→X順）
        sorted_spans = sorted(raw_spans, key=lambda s: (round(s["y0"] / 10) * 10, s["x0"]))
        print("\n並び替え後（最初の10個）:")
        for i, span in enumerate(sorted_spans[:10]):
            print(f"  {i:02d}: Y={span['y0']:6.1f}, X={span['x0']:6.1f} | {span['text']}")
        
        doc.close()
        
    except Exception as e:
        print(f"エラー: {e}")
    
    print("-" * 80)

if __name__ == "__main__":
    test_page1_extraction()