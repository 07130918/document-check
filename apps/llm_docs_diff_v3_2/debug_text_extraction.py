#!/usr/bin/env python3
"""
抽出したテキストを順番にCSVに保存するデバッグツール（v3-2用）
"""
import csv
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPYTHONPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.llm_docs_diff_v3_2.services.azure_service_enhanced import AzureDocumentServiceEnhanced

def main():
    """sample1のテキスト抽出をデバッグ"""
    # PDFファイルのパス（Dockerコンテナ内のパス）
    pdf_path = Path("/app/data/sample1/サンプル①2024.pdf")
    
    # サービスを初期化
    service = AzureDocumentServiceEnhanced()
    
    # PDFを読み込む
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    # 出力ディレクトリを作成（Dockerコンテナ内のパス）
    output_dir = Path("/app/output/debug_text_extraction")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 通常のOCR
    print("=== v3-2 通常OCR実行中 ===")
    result_normal = service.extract_layout_from_lines(pdf_bytes)
    
    csv_path = output_dir / "sample1_v3-2_normal_text_order.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['index', 'page', 'x', 'y', 'width', 'height', 'text'])
        
        for idx, item in enumerate(result_normal):
            page = item.get('page', 0)
            x = item.get('x', 0)
            y = item.get('y', 0)
            width = item.get('width', 0)
            height = item.get('height', 0)
            text = item.get('text', '')
            
            writer.writerow([idx, page, f"{x:.2f}", f"{y:.2f}", f"{width:.2f}", f"{height:.2f}", text])
    
    print(f"保存完了: {csv_path}")
    print(f"抽出アイテム数: {len(result_normal)}")
    ho_char_count = sum(item.get('text', '').count('補') for item in result_normal)
    print(f"「補」の総文字数: {ho_char_count}")
    
    # ページ分割OCR
    print("\n=== v3-2 ページ分割OCR実行中 ===")
    result_split = service.extract_layout_from_lines_with_split(pdf_bytes)
    
    csv_path = output_dir / "sample1_v3-2_split_text_order.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['index', 'page', 'x', 'y', 'width', 'height', 'text', 'source_region'])
        
        for idx, item in enumerate(result_split):
            page = item.get('page', 0)
            x = item.get('x', 0)
            y = item.get('y', 0)
            width = item.get('width', 0)
            height = item.get('height', 0)
            text = item.get('text', '')
            source_region = item.get('source_region', 'normal')
            
            writer.writerow([idx, page, f"{x:.2f}", f"{y:.2f}", f"{width:.2f}", f"{height:.2f}", text, source_region])
    
    print(f"保存完了: {csv_path}")
    print(f"抽出アイテム数: {len(result_split)}")
    ho_char_count = sum(item.get('text', '').count('補') for item in result_split)
    print(f"「補」の総文字数: {ho_char_count}")

if __name__ == "__main__":
    main()