#!/usr/bin/env python3
"""
表検出の詳細テストスクリプト（ファイル出力版）
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.llm_docs_diff_v3_3.services.azure_service import AzureDocumentService
from apps.llm_docs_diff_v3_3.config.settings import settings
from apps.llm_docs_diff_v3_3.utils.pdf_utils import PDFProcessor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_table_detection_to_file(pdf_path: str, max_pages: int = 9):
    """指定されたPDFファイルから表を検出し、ファイルに出力"""
    
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
    
    # 出力ディレクトリを作成
    output_dir = Path("/root/AICE/prj-ms-document-check/output/table_detection_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON形式で保存
    json_output = output_dir / "tables_9pages.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(tables, f, ensure_ascii=False, indent=2)
    print(f"\nJSON形式で保存: {json_output}")
    
    # テキスト形式で保存（読みやすい形式）
    txt_output = output_dir / "tables_9pages_formatted.txt"
    with open(txt_output, 'w', encoding='utf-8') as f:
        f.write(f"表の検出結果: {pdf_path} (最初の{max_pages}ページ)\n")
        f.write(f"検出された表の数: {len(tables)}\n")
        f.write("="*80 + "\n\n")
        
        for i, table in enumerate(tables):
            f.write(f"表 {i+1}: ページ {table['page'] + 1}\n")
            f.write(f"サイズ: {table['row_count']}行 × {table['column_count']}列\n")
            f.write("-"*80 + "\n")
            
            # 表を再構築
            grid = [['' for _ in range(table['column_count'])] for _ in range(table['row_count'])]
            
            for cell in table['cells']:
                row = cell['row']
                col = cell['column']
                text = cell['text']
                grid[row][col] = text
            
            # 表を出力
            for row_idx, row in enumerate(grid):
                f.write(f"行{row_idx}: ")
                for col_idx, cell in enumerate(row):
                    # タブ区切りで出力
                    f.write(f"[{col_idx}] {cell}\t")
                f.write("\n")
            
            # 結合セル情報
            merged_cells = [cell for cell in table['cells'] 
                          if cell.get('row_span', 1) > 1 or cell.get('column_span', 1) > 1]
            if merged_cells:
                f.write("\n結合セル:\n")
                for cell in merged_cells:
                    f.write(f"  - セル[{cell['row']}, {cell['column']}]: "
                           f"row_span={cell.get('row_span', 1)}, "
                           f"column_span={cell.get('column_span', 1)}\n")
            
            f.write("\n" + "="*80 + "\n\n")
    
    print(f"テキスト形式で保存: {txt_output}")
    
    # CSV形式でも保存（各表を別ファイルに）
    csv_dir = output_dir / "csv_tables"
    csv_dir.mkdir(exist_ok=True)
    
    for i, table in enumerate(tables):
        csv_file = csv_dir / f"table_{i+1}_page{table['page']+1}.csv"
        with open(csv_file, 'w', encoding='utf-8') as f:
            # ヘッダー行
            f.write("row,column,text,row_span,column_span\n")
            
            # データ行
            for cell in table['cells']:
                text = cell['text'].replace('"', '""')  # CSVエスケープ
                f.write(f"{cell['row']},{cell['column']},\"{text}\","
                       f"{cell.get('row_span', 1)},{cell.get('column_span', 1)}\n")
        
        print(f"CSV保存: {csv_file}")
    
    return output_dir

if __name__ == "__main__":
    # サンプルデータで表検出をテスト
    pdf_path = "/root/AICE/prj-ms-document-check/data/sample1/サンプル①2024.pdf"
    
    if Path(pdf_path).exists():
        output_dir = test_table_detection_to_file(pdf_path, max_pages=9)
        print(f"\n出力ファイルは以下のディレクトリに保存されました:")
        print(f"{output_dir}")