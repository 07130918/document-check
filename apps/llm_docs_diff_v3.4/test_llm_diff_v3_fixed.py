#!/usr/bin/env python3
"""
LLM Diff Test v3 修正版 - 前処理改善版
"""
import os
import sys
from pathlib import Path
import argparse

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from llm_docs_diff_v3.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from llm_docs_diff_v3.core.text_preprocessing import TextPreprocessorFixed  # 修正版を使用
from llm_docs_diff_v3.core.simple_diff_detector_v3 import SimpleDiffDetectorV3
from llm_docs_diff_v3.handlers.output_handler import OutputHandler
from llm_docs_diff_v3.models.bbox_models import ComparisonResult, DiffResult, ChangeType
from llm_docs_diff_v3.core.reading_order_v2 import ReadingOrderEstimatorV2
from llm_docs_diff_v3.config.settings import settings
import time
from datetime import datetime

# 環境変数の読み込み
load_dotenv()

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description='LLM Diff Test v3 修正版 - 前処理改善')
    parser.add_argument('--dataset', type=str, choices=['dantai', 'sougou'], default='dantai',
                        help='使用するデータセット (dantai: docs/img/2023.pdf & 2024.pdf, sougou: data/sougou/)')
    parser.add_argument('--pdf1', type=str, help='比較元のPDFファイルパス（任意）')
    parser.add_argument('--pdf2', type=str, help='比較先のPDFファイルパス（任意）')
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # データセットに基づいてPDFパスを設定
    if args.pdf1 and args.pdf2:
        # カスタムパスが指定された場合
        pdf1_path = Path(args.pdf1)
        pdf2_path = Path(args.pdf2)
    elif args.dataset == 'sougou':
        # sougouデータセットを使用
        data_dir = Path("data/sougou")
        pdf1_path = data_dir / "サンプル②2024 .pdf"
        pdf2_path = data_dir / "サンプル②2025.pdf"
    else:  # dantai
        # dantaiデータセットを使用（旧default）
        pdf1_path = Path("docs/img/2023.pdf")
        pdf2_path = Path("docs/img/2024.pdf")
    
    if not pdf1_path.exists() or not pdf2_path.exists():
        print(f"エラー: テストファイルが見つかりません")
        if not pdf1_path.exists():
            print(f"  PDF1が存在しません: {pdf1_path}")
        if not pdf2_path.exists():
            print(f"  PDF2が存在しません: {pdf2_path}")
        return
    
    # PDFファイルを読み込む
    with open(pdf1_path, "rb") as f:
        pdf1_bytes = f.read()
    with open(pdf2_path, "rb") as f:
        pdf2_bytes = f.read()
    
    # タイムスタンプ付き出力ディレクトリ（修正版専用）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_output_name = f"llm_diff_test_v3_fixed_{timestamp}"
    
    if args.dataset == 'sougou':
        output_dir = Path(f"output/{base_output_name}/sougou")
    elif args.pdf1 and args.pdf2:
        output_dir = Path(f"output/{base_output_name}/custom")
    else:  # dantai
        output_dir = Path(f"output/{base_output_name}/dantai")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    
    # ========== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 ==========
    print("===== LLM Diff Test v3 修正版（前処理改善） =====")
    print(f"使用するPDFファイル:")
    print(f"  PDF1: {pdf1_path.name}")
    print(f"  PDF2: {pdf2_path.name}")
    print(f"  データセット: {args.dataset}")
    print("\n===== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 =====")
    
    azure_service = AzureDocumentServiceEnhanced()
    text_preprocessor = TextPreprocessorFixed()  # 修正版前処理を使用
    
    print(f"\n1. {pdf1_path.name}の処理...")
    # 行ベースのデータを取得
    line_bbox_list1 = azure_service.extract_layout_from_lines(pdf1_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list1)}")
    
    # 修正版前処理を適用
    bbox_list1 = text_preprocessor.preprocess_bbox_list(line_bbox_list1)
    print(f"   修正版前処理後: {len(bbox_list1)}")
    
    print(f"\n2. {pdf2_path.name}の処理...")
    # 行ベースのデータを取得
    line_bbox_list2 = azure_service.extract_layout_from_lines(pdf2_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list2)}")
    
    # 修正版前処理を適用
    bbox_list2 = text_preprocessor.preprocess_bbox_list(line_bbox_list2)
    print(f"   修正版前処理後: {len(bbox_list2)}")
    
    # ページ番号要素の保持確認
    page_refs_1 = len([item for item in bbox_list1 if 'P' in item.get('text', '') and any(c.isdigit() for c in item.get('text', ''))])
    page_refs_2 = len([item for item in bbox_list2 if 'P' in item.get('text', '') and any(c.isdigit() for c in item.get('text', ''))])
    print(f"\n📄 ページ番号要素保持確認:")
    print(f"   2024年: {page_refs_1}件")
    print(f"   2025年: {page_refs_2}件")
    
    # ========== ステップ2: 読み順序の推定 ==========
    print("\n===== ステップ2: 読み順序の推定 =====")
    
    reading_estimator = ReadingOrderEstimatorV2()
    ordered_bbox_list1 = reading_estimator.estimate_reading_order(bbox_list1)
    ordered_bbox_list2 = reading_estimator.estimate_reading_order(bbox_list2)
    
    print(f"読み順序推定完了: 文書1={len(ordered_bbox_list1)}要素, 文書2={len(ordered_bbox_list2)}要素")
    
    # ========== ステップ3: 簡易版差分検出（統一タイプ） ==========
    print("\n===== ステップ3: 修正版差分検出 =====")
    
    diff_detector = SimpleDiffDetectorV3(max_page=None)  # 全ページ処理
    differences = diff_detector.detect_differences(ordered_bbox_list1, ordered_bbox_list2)
    
    print(f"\n検出された差分数: {len(differences)}")
    
    # ページ番号関連差分のカウント
    page_number_diffs = 0
    for diff in differences:
        doc1_text = diff.doc1_bbox.get('text', '') if diff.doc1_bbox else ''
        doc2_text = diff.doc2_bbox.get('text', '') if diff.doc2_bbox else ''
        if ('P' in doc1_text and any(c.isdigit() for c in doc1_text)) or \
           ('P' in doc2_text and any(c.isdigit() for c in doc2_text)):
            page_number_diffs += 1
    
    print(f"うちページ番号関連: {page_number_diffs}件")
    
    # SimpleDiffResultをDiffResultに変換
    diff_results = []
    for sdiff in differences:
        # 全ての差分をDIFFERENCE型として扱う
        diff_result = DiffResult(
            change_type=ChangeType.MODIFICATION,  # 簡易版では全て変更として扱う
            original_bbox=sdiff.doc1_bbox,
            modified_bbox=sdiff.doc2_bbox,
            page=sdiff.page_num,
            confidence=sdiff.confidence
        )
        diff_results.append(diff_result)
    
    # ========== ステップ4: ComparisonResultを作成 ==========
    print("\n===== ステップ4: 比較結果の作成 =====")
    
    comparison_result = ComparisonResult(
        diff_results=diff_results,  # DiffResultのリストを使用
        reading_order_doc1=ordered_bbox_list1,
        reading_order_doc2=ordered_bbox_list2,
        metadata={
            "doc1_total_words": len(ordered_bbox_list1),
            "doc2_total_words": len(ordered_bbox_list2),
            "total_differences": len(differences),
            "page_number_differences": page_number_diffs,
            "doc1_name": pdf1_path.name,
            "doc2_name": pdf2_path.name,
            "preprocessing_version": "fixed"
        }
    )
    
    # ========== ステップ5: OutputHandlerで全ての出力を生成 ==========
    print("\n===== ステップ5: 出力ファイルの生成 =====")
    
    # 出力ディレクトリを設定で上書き
    settings.OUTPUT_DIR = output_dir
    
    output_handler = OutputHandler()
    saved_files = output_handler.save_comparison_result(
        comparison_result,
        base_output_name,  # タイムスタンプ付きベース名を使用
        pdf1_bytes=pdf1_bytes,
        pdf2_bytes=pdf2_bytes,
        pdf1_name=pdf1_path.name,
        pdf2_name=pdf2_path.name
    )
    
    print("\n生成されたファイル:")
    for key, path in saved_files.items():
        print(f"  - {key}: {Path(path).name}")
    
    end_time = time.time()
    print(f"\n===== 処理完了 =====")
    print(f"総実行時間: {end_time - start_time:.2f}秒")
    print(f"出力ディレクトリ: {output_dir}")
    
    # ページ数を取得（PDF生成後）
    if saved_files.get("side_by_side_pdf"):
        import fitz
        with fitz.open(saved_files["side_by_side_pdf"]) as doc:
            print(f"並列表示PDFのページ数: {len(doc)}ページ")

if __name__ == "__main__":
    main()