#!/usr/bin/env python3
"""
表検出の詳細テストスクリプト（9ページまで）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.llm_docs_diff_v3_3.services.azure_service import AzureDocumentService
from apps.llm_docs_diff_v3_3.config.settings import settings
from apps.llm_docs_diff_v3_3.utils.pdf_utils import PDFProcessor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_table_detection_detailed(pdf_path: str, max_pages: int = 9):
    """指定されたPDFファイルから表を検出し、詳細を出力"""
    
    # PDFを読み込む
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # 9ページまでに制限
    pdf_processor = PDFProcessor()
    pdf_bytes = pdf_processor.limit_pdf_pages(pdf_bytes, max_pages)
    
    # Azure Serviceを初期化
    azure_service = AzureDocumentService()
    
    # 表を抽出
    print(f"\n表の検出を開始: {pdf_path} (最初の{max_pages}ページ)")
    tables = azure_service.extract_tables(pdf_bytes)
    
    print(f"\n検出された表の数: {len(tables)}")
    
    # 各表の詳細を出力
    for i, table in enumerate(tables):
        print(f"\n{'='*80}")
        print(f"表 {i+1}: ページ {table['page'] + 1}")
        print(f"サイズ: {table['row_count']}行 × {table['column_count']}列")
        print(f"{'='*80}")
        
        # 表を再構築して表示
        # 空の表を作成
        grid = [['' for _ in range(table['column_count'])] for _ in range(table['row_count'])]
        
        # セルを配置
        for cell in table['cells']:
            row = cell['row']
            col = cell['column']
            text = cell['text']
            # 長いテキストは省略
            if len(text) > 50:
                text = text[:47] + "..."
            grid[row][col] = text
        
        # 表を表示
        # 各列の最大幅を計算
        col_widths = [0] * table['column_count']
        for row in grid:
            for col_idx, cell in enumerate(row):
                col_widths[col_idx] = max(col_widths[col_idx], len(cell))
        
        # ヘッダー行を表示
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        
        # 各行を表示
        for row_idx, row in enumerate(grid):
            row_str = "|"
            for col_idx, cell in enumerate(row):
                # セルを左寄せで表示
                row_str += f" {cell:<{col_widths[col_idx]}} |"
            print(row_str)
            
            # 最初の行の後に区切り線
            if row_idx == 0:
                print("+" + "+".join("=" * (w + 2) for w in col_widths) + "+")
        
        # 表の終わり
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        
        # セルの結合情報があれば表示
        merged_cells = [cell for cell in table['cells'] if cell.get('row_span', 1) > 1 or cell.get('column_span', 1) > 1]
        if merged_cells:
            print("\n結合セル:")
            for cell in merged_cells:
                print(f"  - [{cell['row']}, {cell['column']}]: row_span={cell.get('row_span', 1)}, column_span={cell.get('column_span', 1)}")

if __name__ == "__main__":
    # サンプルデータで表検出をテスト
    pdf_path = "/root/AICE/prj-ms-document-check/data/sample1/サンプル①2024.pdf"
    
    if Path(pdf_path).exists():
        test_table_detection_detailed(pdf_path, max_pages=9)