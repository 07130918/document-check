#!/usr/bin/env python3
"""
LLM Diff Test v3 簡易版 - 差分タイプ統一・文字囲み版
"""
import os
import sys
from pathlib import Path

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from llm_docs_diff_v3.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from llm_docs_diff_v3.core.text_preprocessing import TextPreprocessor
from llm_docs_diff_v3.core.simple_diff_detector_v3 import SimpleDiffDetectorV3, SimpleDiffResult
from llm_docs_diff_v3.handlers.output_handler import OutputHandler
from llm_docs_diff_v3.models.bbox_models import ComparisonResult
from llm_docs_diff_v3.core.reading_order_v2 import ReadingOrderEstimatorV2
from llm_docs_diff_v3.services.simple_pdf_generator_v3 import SimplePDFGeneratorV3
from llm_docs_diff_v3.config.settings import settings
import json
import time

# 環境変数の読み込み
load_dotenv()

def main():
    # テストPDFファイル
    pdf1_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    pdf2_path = Path("/root/AICE/prj-ms-document-check/docs/img/2024.pdf")
    
    if not pdf1_path.exists() or not pdf2_path.exists():
        print(f"テストファイルが見つかりません")
        return
    
    # PDFファイルを読み込む
    with open(pdf1_path, "rb") as f:
        pdf1_bytes = f.read()
    with open(pdf2_path, "rb") as f:
        pdf2_bytes = f.read()
    
    # 出力ディレクトリ（v3簡易版専用）
    output_dir = Path("output/llm_diff_test_v3_simple")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    
    # ========== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 ==========
    print("===== LLM Diff Test v3 簡易版 (差分タイプ統一) =====")
    print("\n===== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 =====")
    
    azure_service = AzureDocumentServiceEnhanced()
    text_preprocessor = TextPreprocessor()
    
    print("\n1. 2023年PDFの処理...")
    # 行ベースのデータを取得
    line_bbox_list1 = azure_service.extract_layout_from_lines(pdf1_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list1)}")
    
    # 前処理を適用
    bbox_list1 = text_preprocessor.preprocess_bbox_list(line_bbox_list1)
    print(f"   前処理後: {len(bbox_list1)}")
    
    print("\n2. 2024年PDFの処理...")
    # 行ベースのデータを取得
    line_bbox_list2 = azure_service.extract_layout_from_lines(pdf2_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list2)}")
    
    # 前処理を適用
    bbox_list2 = text_preprocessor.preprocess_bbox_list(line_bbox_list2)
    print(f"   前処理後: {len(bbox_list2)}")
    
    # ========== ステップ2: 読み順序の推定 ==========
    print("\n===== ステップ2: 読み順序の推定 =====")
    
    reading_estimator = ReadingOrderEstimatorV2()
    
    # 読み順序を推定
    ordered_bbox_list1 = reading_estimator.estimate_reading_order(bbox_list1)
    ordered_bbox_list2 = reading_estimator.estimate_reading_order(bbox_list2)
    
    print(f"読み順序推定完了: 文書1={len(ordered_bbox_list1)}要素, 文書2={len(ordered_bbox_list2)}要素")
    
    # ========== ステップ3: 簡易版差分検出（統一タイプ） ==========
    print("\n===== ステップ3: 簡易版差分検出 =====")
    
    diff_detector = SimpleDiffDetectorV3(max_page=4)  # 5ページまで (0-indexed)
    differences = diff_detector.detect_differences(ordered_bbox_list1, ordered_bbox_list2)
    
    print(f"\n検出された差分数: {len(differences)}")
    
    # 差分を辞書形式に変換
    diff_dicts = [diff.to_dict() for diff in differences]
    
    # ========== ステップ4: 文字を囲む形式でPDF生成 ==========
    print("\n===== ステップ4: 文字を囲む形式でPDF生成 =====")
    
    pdf_generator = SimplePDFGeneratorV3()
    pdf_dir = output_dir / "PDFs"
    pdf_dir.mkdir(exist_ok=True)
    
    pdf1_output, pdf2_output = pdf_generator.generate_comparison_pdfs(
        str(pdf1_path),
        str(pdf2_path),
        diff_dicts,
        str(pdf_dir)
    )
    
    print(f"比較用PDF生成完了:")
    print(f"  - {Path(pdf1_output).name}")
    print(f"  - {Path(pdf2_output).name}")
    
    # ========== ステップ5: レポート生成 ==========
    print("\n===== ステップ5: レポート生成 =====")
    
    # 実行時間
    execution_time = time.time() - start_time
    
    # サマリー生成
    summary = diff_detector.get_summary(differences)
    
    # 統計情報
    stats = {
        "version": "v3_simple",
        "execution_time": f"{execution_time:.2f} seconds",
        "total_differences": summary['total_differences'],
        "difference_type": "unified",
        "by_page": summary['by_page']
    }
    
    # レポートディレクトリ
    report_dir = output_dir / "reports"
    report_dir.mkdir(exist_ok=True)
    
    # 統計情報を保存
    with open(report_dir / "v3_simple_statistics.json", 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # 差分CSVを生成
    csv_path = output_dir / "v3_simple_differences.csv"
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("番号,ページ,テキスト,文書\n")
        for i, diff in enumerate(differences):
            if diff.doc1_bbox:
                f.write(f"{i+1},{diff.page_num},{diff.doc1_bbox.get('text', '')},文書1\n")
            if diff.doc2_bbox:
                f.write(f"{i+1},{diff.page_num},{diff.doc2_bbox.get('text', '')},文書2\n")
    
    print(f"\nCSVファイル生成完了: {csv_path.name}")
    
    # 実行レポート
    report_text = f"""# LLM Diff v3 簡易版 実行レポート

## 概要
- バージョン: v3_simple (差分タイプ統一)
- 実行日時: {time.strftime('%Y-%m-%d %H:%M:%S')}
- 実行時間: {execution_time:.2f}秒

## 検出結果
- 総差分数: {summary['total_differences']}件
- 差分タイプ: 統一（すべての差分を同一として扱う）

## ページ別差分数
"""
    for page, count in sorted(summary['by_page'].items()):
        report_text += f"- ページ{page + 1}: {count}件\n"
    
    report_text += f"\n## 出力ファイル\n- 比較用PDF: PDFs/\n- 差分CSV: v3_simple_differences.csv\n- 統計情報: reports/v3_simple_statistics.json\n"""
    
    with open(report_dir / "v3_simple_report.md", 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"\nレポート生成完了: reports/v3_simple_report.md")
    
    print("\n===== 処理完了 =====")
    print(f"総実行時間: {execution_time:.2f}秒")
    print(f"出力ディレクトリ: {output_dir}")

if __name__ == "__main__":
    main()