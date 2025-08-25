#!/usr/bin/env python3
"""
表検出のテストスクリプト
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.llm_docs_diff_v3_3.services.azure_service import AzureDocumentService
from apps.llm_docs_diff_v3_3.config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_table_detection(pdf_path: str):
    """指定されたPDFファイルから表を検出"""
    
    # PDFを読み込む
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # Azure Serviceを初期化
    azure_service = AzureDocumentService()
    
    # 表を抽出
    print(f"\n表の検出を開始: {pdf_path}")
    tables = azure_service.extract_tables(pdf_bytes)
    
    print(f"\n検出された表の数: {len(tables)}")
    
    for i, table in enumerate(tables):
        print(f"\n--- 表 {i+1} ---")
        print(f"ページ: {table['page'] + 1}")
        print(f"サイズ: {table['row_count']}行 × {table['column_count']}列")
        print(f"セル数: {len(table['cells'])}")
        
        # 最初の5セルを表示
        print("\n最初の5セルの内容:")
        for j, cell in enumerate(table['cells'][:5]):
            print(f"  [{cell['row']}, {cell['column']}]: {cell['text'][:50]}...")

if __name__ == "__main__":
    # サンプルデータで表検出をテスト
    test_pdfs = [
        "/root/AICE/prj-ms-document-check/data/sample1/サンプル①2024.pdf",
        "/root/AICE/prj-ms-document-check/data/sample2/サンプル②2024 .pdf",
    ]
    
    for pdf_path in test_pdfs:
        if Path(pdf_path).exists():
            test_table_detection(pdf_path)
            break