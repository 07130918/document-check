"""
LLM Diff Test v4 - Azure Document Intelligenceの全特徴量を使用
"""
import os
import sys
from pathlib import Path
import time
import logging
import argparse
from dotenv import load_dotenv

# ログ設定
logging.basicConfig(level=logging.DEBUG)

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parents[2]
sys.path.insert(0, str(project_root))

from apps.llm_docs_diff_v4.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from apps.llm_docs_diff_v4.services.azure_service_cached import AzureDocumentServiceCached
from apps.llm_docs_diff_v4.core.text_preprocessing import TextPreprocessor
from apps.llm_docs_diff_v4.utils.pdf_utils import PDFProcessor

from apps.llm_docs_diff_v4.core.reading_order_v4 import ReadingOrderEstimatorV4
from apps.llm_docs_diff_v4.core.diff_detector_v4 import PositionBasedDiffDetector
from apps.llm_docs_diff_v4.models.bbox_models import ComparisonResult
from apps.llm_docs_diff_v4.handlers.output_handler import OutputHandler

# 環境変数の読み込み
load_dotenv()

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description='LLM Diff Test v4 - 文書差分検出（LLM最適化版）')
    parser.add_argument('--dataset', type=str, choices=['default', 'sougou'], default='default',
                        help='使用するデータセット (default: docs/img/2023.pdf & 2024.pdf, sougou: data/sougou/)')
    parser.add_argument('--pdf1', type=str, help='比較元のPDFファイルパス（任意）')
    parser.add_argument('--pdf2', type=str, help='比較先のPDFファイルパス（任意）')
    return parser.parse_args()


def extract_line_data(hierarchy):
    """階層データから行データを抽出（テキスト付き）"""
    lines = []
    for line in hierarchy.get('lines', []):
        bbox = line.get('bbox', [0, 0, 0, 0])
        # 'content'フィールドまたは'text'フィールドを使用
        text = line.get('content', line.get('text', ''))
        
        if isinstance(bbox, list) and len(bbox) >= 4:
            lines.append({
                'x': bbox[0],
                'y': bbox[1],
                'width': bbox[2],
                'height': bbox[3],
                'text': text,
                'page': line.get('page', 0),
                'bbox': bbox
            })
    return lines


def main():
    start_time = time.time()
    args = parse_arguments()
    
    # データセットに基づいてPDFパスを設定
    if args.pdf1 and args.pdf2:
        # カスタムパスが指定された場合
        pdf1_path = Path(args.pdf1)
        pdf2_path = Path(args.pdf2)
    elif args.dataset == 'sougou':
        # sougouデータセットを使用
        data_dir = project_root / "data" / "sougou"
        pdf1_path = data_dir / "サンプル②2024 .pdf"
        pdf2_path = data_dir / "サンプル②2025.pdf"
    else:
        # デフォルトのテストデータを使用
        pdf1_path = project_root / "docs" / "img" / "2023.pdf"
        pdf2_path = project_root / "docs" / "img" / "2024.pdf"
    
    # ファイルの存在確認
    if not pdf1_path.exists() or not pdf2_path.exists():
        print(f"エラー: テストファイルが見つかりません")
        if not pdf1_path.exists():
            print(f"  PDF1が存在しません: {pdf1_path}")
        if not pdf2_path.exists():
            print(f"  PDF2が存在しません: {pdf2_path}")
        return
    
    # 出力ディレクトリ（データセットごとに分ける）
    if args.dataset == 'sougou':
        output_dir = project_root / "output" / "llm_diff_test_v4" / "sougou"
    elif args.pdf1 and args.pdf2:
        output_dir = project_root / "output" / "llm_diff_test_v4" / "custom"
    else:
        output_dir = project_root / "output" / "llm_diff_test_v4" / "default"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # PDFを読み込み
    with open(pdf1_path, "rb") as f:
        pdf1_bytes = f.read()
    with open(pdf2_path, "rb") as f:
        pdf2_bytes = f.read()
    
    # ========== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 ==========
    print("===== LLM Diff Test v4 =====")
    print(f"使用するPDFファイル:")
    print(f"  PDF1: {pdf1_path.name}")
    print(f"  PDF2: {pdf2_path.name}")
    print(f"  データセット: {args.dataset}")
    print("\n===== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 =====")
    
    azure_service = AzureDocumentServiceCached()
    text_preprocessor = TextPreprocessor()
    
    print(f"\n1. {pdf1_path.name}の処理...")
    # バッチ処理で階層構造を抽出
    hierarchy1 = azure_service.extract_layout_with_hierarchy_batch(pdf1_bytes)
    print(f"   段落数: {len(hierarchy1['paragraphs'])}")
    print(f"   行数: {len(hierarchy1['lines'])}")
    print(f"   単語数: {len(hierarchy1['words'])}")
    
    # 生のAzure結果も保持（LLM用）
    print("   Azure完全結果を取得中...")
    azure_result1 = azure_service.get_cached_result(pdf1_bytes)  # キャッシュから取得
    
    # 行データを抽出
    lines1 = extract_line_data(hierarchy1)
    # 前処理を適用
    bbox_list1 = text_preprocessor.preprocess_bbox_list(lines1)
    print(f"   前処理前: {len(lines1)} → 前処理後: {len(bbox_list1)}")
    
    print(f"\n2. {pdf2_path.name}の処理...")
    # バッチ処理で階層構造を抽出
    hierarchy2 = azure_service.extract_layout_with_hierarchy_batch(pdf2_bytes)
    print(f"   段落数: {len(hierarchy2['paragraphs'])}")
    print(f"   行数: {len(hierarchy2['lines'])}")
    print(f"   単語数: {len(hierarchy2['words'])}")
    
    # 生のAzure結果も保持（LLM用）
    print("   Azure完全結果を取得中...")
    azure_result2 = azure_service.get_cached_result(pdf2_bytes)  # キャッシュから取得
    
    # 行データを抽出
    lines2 = extract_line_data(hierarchy2)
    # 前処理を適用
    bbox_list2 = text_preprocessor.preprocess_bbox_list(lines2)
    print(f"   前処理前: {len(lines2)} → 前処理後: {len(bbox_list2)}")
    
    # ========== ステップ2: 読み取り順序の推定（LLM使用） ==========
    print("\n===== ステップ2: 読み取り順序の推定（LLMとAzure特徴量） =====")
    
    # OpenAI APIキーの確認
    openai_api_key = os.getenv("OPENAI_API_KEY")
    use_llm = bool(openai_api_key)
    
    if use_llm:
        print("✓ OpenAI APIキーが設定されています。LLMを使用します。")
    else:
        print("✗ OpenAI APIキーが設定されていません。通常のアルゴリズムを使用します。")
    
    order_estimator = ReadingOrderEstimatorV4(
        line_height_ratio=0.5,
        column_gap_threshold=50.0,
        min_column_width=100.0,
        same_line_tolerance=5.0,
        use_llm=use_llm,
        openai_api_key=openai_api_key
    )
    
    # 文書1の読み取り順序を推定
    print(f"\n1. {pdf1_path.name}の読み取り順序を推定中...")
    if azure_result1:
        print("   LLMにAzure特徴量を入力して処理中...")
        ordered_list1 = order_estimator.estimate_reading_order_with_azure(
            bbox_list1, azure_result=azure_result1
        )
    else:
        print("   Azure結果が取得できなかったため、階層データで処理中...")
        ordered_list1 = order_estimator.estimate_reading_order_with_azure(
            bbox_list1, azure_hierarchy=hierarchy1
        )
    print(f"   順序付き要素数: {len(ordered_list1)}")
    
    # 文書2の読み取り順序を推定
    print(f"\n2. {pdf2_path.name}の読み取り順序を推定中...")
    if azure_result2:
        print("   LLMにAzure特徴量を入力して処理中...")
        ordered_list2 = order_estimator.estimate_reading_order_with_azure(
            bbox_list2, azure_result=azure_result2
        )
    else:
        print("   Azure結果が取得できなかったため、階層データで処理中...")
        ordered_list2 = order_estimator.estimate_reading_order_with_azure(
            bbox_list2, azure_hierarchy=hierarchy2
        )
    print(f"   順序付き要素数: {len(ordered_list2)}")
    
    # デバッグ：読み取り順序の保存
    order_estimator.debug_reading_order(ordered_list1, output_dir / "2023_reading_order_debug.csv")
    order_estimator.debug_reading_order(ordered_list2, output_dir / "2024_reading_order_debug.csv")
    
    # ========== ステップ3: 差分検出（v4位置ベース） ==========
    print("\n===== ステップ3: 差分検出（v4位置ベース） =====")
    
    diff_detector = PositionBasedDiffDetector(
        position_tolerance=10.0,
        text_similarity_threshold=0.9,
        consider_reading_order=True
    )
    
    # 差分を検出
    diff_results = diff_detector.detect_differences(
        bbox_list1, bbox_list2,
        ordered_list1, ordered_list2
    )
    
    # サマリーを生成
    summary = diff_detector.generate_diff_summary(diff_results)
    print(f"検出された差分:")
    print(f"- 削除: {summary['deletions']}件")
    print(f"- 追加: {summary['additions']}件")
    print(f"- 変更: {summary['modifications']}件")
    print(f"- 合計: {summary['total']}件")
    
    # ========== ステップ4: 結果の出力 ==========
    print("\n===== ステップ4: 結果の出力 =====")
    
    output_handler = OutputHandler(output_dir)
    
    # ComparisonResultオブジェクトを作成
    comparison_result = ComparisonResult(
        diff_results=diff_results,
        reading_order_doc1=ordered_list1,
        reading_order_doc2=ordered_list2
    )
    
    # すべての出力を保存
    saved_files = output_handler.save_all_outputs(
        comparison_result=comparison_result,
        ordered_list1=ordered_list1,
        ordered_list2=ordered_list2,
        pdf1_bytes=pdf1_bytes,
        pdf2_bytes=pdf2_bytes
    )
    
    print("\n保存されたファイル:")
    for key, path in saved_files.items():
        if path:
            print(f"- {key}: {path.name}")
    
    # ========== ステップ5: サンプル出力 ==========
    print("\n===== ステップ5: サンプル出力 =====")
    
    # 差分の例を表示
    print("\n差分の例（最初の5件）:")
    for i, diff in enumerate(diff_results[:5]):
        change_type = diff.change_type.value
        page = diff.page + 1
        
        if diff.original_bbox:
            text = diff.original_bbox.get('text', '')[:50]
        elif diff.modified_bbox:
            text = diff.modified_bbox.get('text', '')[:50]
        else:
            text = "No text"
        
        print(f"{i+1}. [{change_type}] ページ{page}: {text}...")
    
    # ページごとの差分を表示
    if summary.get('by_page'):
        print("\nページごとの差分詳細:")
        for page, stats in summary['by_page'].items():
            print(f"  ページ{page+1}: 追加{stats['additions']}, "
                  f"削除{stats['deletions']}, 変更{stats['modifications']}")
    
    # LLM使用状況を表示
    if use_llm:
        print("\n✓ LLMによる読み取り順序最適化が実行されました")
        print("  - Azure Document Intelligenceの全特徴量を使用")
        print("  - 矢印、図形、段落構造を考慮した順序付け")
    else:
        print("\n✗ LLMは使用されませんでした（通常のアルゴリズム）")
    
    # 実行時間
    end_time = time.time()
    print(f"\n===== LLM Diff Test v4 完了！ =====")
    print(f"総処理時間: {end_time - start_time:.1f}秒")
    print(f"すべての結果は {output_dir} に保存されました。")


if __name__ == "__main__":
    main()