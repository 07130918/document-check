#!/usr/bin/env python3
"""
表のバウンディングボックス情報をテスト
"""
import os
import sys
from pathlib import Path

# プロジェクトのルートパスを追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from apps.llm_docs_diff_v3_3.services.azure_service import AzureDocumentService

def test_table_bbox():
    """表のバウンディングボックス情報をテスト"""
    # テスト用PDFを読み込む
    pdf_path = project_root / "data" / "sample1" / "サンプル①2024.pdf"
    
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # 最初の3ページのみ処理
    from apps.llm_docs_diff_v3_3.utils.pdf_utils import PDFProcessor
    pdf_processor = PDFProcessor()
    pdf_bytes = pdf_processor.limit_pdf_pages(pdf_bytes, 3)
    
    # Azure Document Intelligenceで表を抽出
    service = AzureDocumentService()
    tables = service.extract_tables(pdf_bytes)
    
    print(f"抽出された表の数: {len(tables)}")
    for i, table in enumerate(tables):
        print(f"\n表{i+1}:")
        print(f"  ページ: {table['page'] + 1}")
        print(f"  サイズ: {table['row_count']}行 × {table['column_count']}列")
        print(f"  バウンディングボックス: {table.get('bbox', 'なし')}")
        
        # 最初の3つのセルのbbox情報も確認
        cells_with_bbox = [cell for cell in table['cells'][:3] if cell.get('bbox')]
        print(f"  セルのバウンディングボックス: {len(cells_with_bbox)}個/{min(3, len(table['cells']))}個")

if __name__ == "__main__":
    test_table_bbox()