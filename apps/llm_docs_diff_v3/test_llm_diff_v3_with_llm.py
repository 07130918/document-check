#!/usr/bin/env python3
"""
LLM Diff Test v3 with LLM - LLMを使用した差分検出
"""
import os
import sys
from pathlib import Path
import argparse

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from llm_docs_diff_v3.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from llm_docs_diff_v3.services.llm_service import LLMService
from llm_docs_diff_v3.core.text_preprocessing import TextPreprocessor
from llm_docs_diff_v3.core.simple_diff_detector_v3 import SimpleDiffDetectorV3
from llm_docs_diff_v3.handlers.output_handler import OutputHandler
from llm_docs_diff_v3.models.bbox_models import ComparisonResult, DiffResult, ChangeType
from llm_docs_diff_v3.core.reading_order_v2 import ReadingOrderEstimatorV2
from llm_docs_diff_v3.config.settings import settings
import time
import logging

# 環境変数の読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description='LLM Diff Test v3 with LLM - 文書差分検出')
    parser.add_argument('--dataset', type=str, choices=['dantai', 'sample1', 'sample2', 'sample3', 'sample4', 'sample5'], default='dantai',
                        help='使用するデータセット')
    parser.add_argument('--use-llm-order', action='store_true',
                        help='LLMで読み順序を推定する')
    parser.add_argument('--use-llm-summary', action='store_true',
                        help='LLMで差分を要約する')
    parser.add_argument('--analyze-structure', action='store_true',
                        help='LLMで文書構造を解析する')
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # データセットに基づいてPDFパスを設定
    # プロジェクトルートからの相対パス
    base_path = Path(__file__).parent.parent.parent
    
    if args.dataset == 'dantai':
        data_dir = base_path / "data" / "dantaihoken"
        pdf1_path = data_dir / "2023.pdf"
        pdf2_path = data_dir / "2024.pdf"
    elif args.dataset == 'sample1':
        data_dir = base_path / "data" / "sample1"
        pdf1_path = data_dir / "サンプル①2024後半.pdf"
        pdf2_path = data_dir / "サンプル①2025後半.pdf"
    elif args.dataset == 'sample2':
        data_dir = base_path / "data" / "sample2"
        pdf1_path = data_dir / "サンプル②2024 .pdf"
        pdf2_path = data_dir / "サンプル②2025.pdf"
    elif args.dataset == 'sample3':
        data_dir = base_path / "data" / "sample3"
        pdf1_path = data_dir / "サンプル③2023.pdf"
        pdf2_path = data_dir / "サンプル③2024.pdf"
    elif args.dataset == 'sample4':
        data_dir = base_path / "data" / "sample4"
        pdf1_path = data_dir / "サンプル④2024_アノテーション.pdf"
        pdf2_path = data_dir / "サンプル④2025_アノテーション.pdf"
    else:  # sample5
        data_dir = base_path / "data" / "sample5"
        pdf1_path = data_dir / "サンプル⑤2024_アノテーション.pdf"
        pdf2_path = data_dir / "サンプル⑤2025_アノテーション.pdf"
    
    if not pdf1_path.exists() or not pdf2_path.exists():
        print(f"エラー: テストファイルが見つかりません")
        return
    
    # PDFファイルを読み込む
    with open(pdf1_path, "rb") as f:
        pdf1_bytes = f.read()
    with open(pdf2_path, "rb") as f:
        pdf2_bytes = f.read()
    
    # 出力ディレクトリ
    output_dir = Path(f"output/llm_diff_test_v3_llm/{args.dataset}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    
    # ========== ステップ1: Azure Document Intelligenceで抽出 ==========
    print("===== LLM Diff Test v3 with LLM =====")
    print(f"使用するPDFファイル:")
    print(f"  PDF1: {pdf1_path.name}")
    print(f"  PDF2: {pdf2_path.name}")
    print(f"  データセット: {args.dataset}")
    print(f"  LLM使用設定:")
    print(f"    - 読み順序推定: {args.use_llm_order}")
    print(f"    - 差分要約: {args.use_llm_summary}")
    print(f"    - 文書構造解析: {args.analyze_structure}")
    
    azure_service = AzureDocumentServiceEnhanced()
    text_preprocessor = TextPreprocessor()
    llm_service = LLMService()
    
    print(f"\n1. {pdf1_path.name}の処理...")
    line_bbox_list1 = azure_service.extract_layout_from_lines(pdf1_bytes)
    bbox_list1 = text_preprocessor.preprocess_bbox_list(line_bbox_list1)
    print(f"   要素数: {len(bbox_list1)}")
    
    print(f"\n2. {pdf2_path.name}の処理...")
    line_bbox_list2 = azure_service.extract_layout_from_lines(pdf2_bytes)
    bbox_list2 = text_preprocessor.preprocess_bbox_list(line_bbox_list2)
    print(f"   要素数: {len(bbox_list2)}")
    
    # ========== ステップ2: 読み取り順序の推定 ==========
    print("\n===== ステップ2: 読み取り順序の推定 =====")
    
    if args.use_llm_order:
        print("LLMを使用して読み順序を推定中...")
        
        # 文書1
        print(f"1. {pdf1_path.name}の読み順序をLLMで推定中...")
        try:
            order_indices1 = llm_service.estimate_reading_order(bbox_list1, 
                                                               page_layout_description="保険関連文書",
                                                               is_spread=False)
            # インデックスに従って並び替え
            ordered_list1 = [bbox_list1[i] for i in order_indices1 if i < len(bbox_list1)]
            print(f"   LLMによる推定成功: {len(ordered_list1)}要素")
        except Exception as e:
            logger.error(f"LLM推定エラー: {e}")
            print("   LLM推定失敗、ルールベースに切り替え")
            order_estimator = ReadingOrderEstimatorV2()
            ordered_list1 = order_estimator.estimate_reading_order(bbox_list1)
        
        # 文書2
        print(f"2. {pdf2_path.name}の読み順序をLLMで推定中...")
        try:
            order_indices2 = llm_service.estimate_reading_order(bbox_list2,
                                                               page_layout_description="保険関連文書",
                                                               is_spread=False)
            ordered_list2 = [bbox_list2[i] for i in order_indices2 if i < len(bbox_list2)]
            print(f"   LLMによる推定成功: {len(ordered_list2)}要素")
        except Exception as e:
            logger.error(f"LLM推定エラー: {e}")
            print("   LLM推定失敗、ルールベースに切り替え")
            order_estimator = ReadingOrderEstimatorV2()
            ordered_list2 = order_estimator.estimate_reading_order(bbox_list2)
    else:
        print("ルールベースで読み順序を推定中...")
        order_estimator = ReadingOrderEstimatorV2()
        ordered_list1 = order_estimator.estimate_reading_order(bbox_list1)
        ordered_list2 = order_estimator.estimate_reading_order(bbox_list2)
    
    # ========== ステップ3: 文書構造解析（オプション） ==========
    if args.analyze_structure:
        print("\n===== 文書構造解析（LLM） =====")
        
        print("文書1の構造を解析中...")
        try:
            structure1 = llm_service.analyze_document_structure(ordered_list1)
            print(f"文書1のタイプ: {structure1.get('document_type', '不明')}")
            print(f"主要セクション: {', '.join(structure1.get('sections', []))}")
            print(f"要約: {structure1.get('summary', 'なし')}")
        except Exception as e:
            logger.error(f"構造解析エラー: {e}")
        
        print("\n文書2の構造を解析中...")
        try:
            structure2 = llm_service.analyze_document_structure(ordered_list2)
            print(f"文書2のタイプ: {structure2.get('document_type', '不明')}")
            print(f"主要セクション: {', '.join(structure2.get('sections', []))}")
            print(f"要約: {structure2.get('summary', 'なし')}")
        except Exception as e:
            logger.error(f"構造解析エラー: {e}")
    
    # ========== ステップ4: 差分検出 ==========
    print("\n===== ステップ4: 差分検出 =====")
    diff_detector = SimpleDiffDetectorV3()
    diff_results = diff_detector.detect_differences(ordered_list1, ordered_list2)
    
    # 差分の統計
    stats = {
        'removed': sum(1 for d in diff_results if d.change_type == ChangeType.DELETION),
        'added': sum(1 for d in diff_results if d.change_type == ChangeType.ADDITION),
        'modified': sum(1 for d in diff_results if d.change_type == ChangeType.MODIFICATION)
    }
    
    print(f"検出された差分:")
    print(f"- 削除: {stats['removed']}件")
    print(f"- 追加: {stats['added']}件")
    print(f"- 変更: {stats['modified']}件")
    print(f"- 合計: {len(diff_results)}件")
    
    # ========== ステップ5: 差分の要約（オプション） ==========
    if args.use_llm_summary and len(diff_results) > 0:
        print("\n===== 差分の要約（LLM） =====")
        try:
            # SimpleDiffResultをDiffResultに変換
            converted_results = []
            for dr in diff_results[:20]:  # 最初の20件のみ
                # DiffResultに変換
                diff_result = DiffResult(
                    change_type=ChangeType.MODIFICATION,  # すべて変更として扱う
                    original_bbox=dr.doc1_bbox,
                    modified_bbox=dr.doc2_bbox,
                    page=dr.page_num,
                    confidence=dr.confidence
                )
                converted_results.append(diff_result)
            
            key_changes = llm_service.summarize_changes(converted_results)
            print("主要な変更点:")
            for i, change in enumerate(key_changes, 1):
                print(f"  {i}. {change}")
        except Exception as e:
            logger.error(f"要約エラー: {e}")
            print("差分の要約に失敗しました")
    
    # ========== ステップ6: 結果の出力 ==========
    print("\n===== ステップ6: 結果の出力 =====")
    
    # SimpleDiffResultをDiffResultに変換してComparisonResultを作成
    converted_diff_results = []
    for dr in diff_results:
        # DiffResultに変換
        diff_result = DiffResult(
            change_type=ChangeType.MODIFICATION,  # すべて変更として扱う
            original_bbox=dr.doc1_bbox,
            modified_bbox=dr.doc2_bbox,
            page=dr.page_num,
            confidence=dr.confidence
        )
        converted_diff_results.append(diff_result)
    
    # ComparisonResultを作成
    comparison_result = ComparisonResult(
        diff_results=converted_diff_results,
        reading_order_doc1=ordered_list1,
        reading_order_doc2=ordered_list2,
        llm_analysis=None,  # 必要に応じて設定
        execution_time=time.time() - start_time,
        metadata={
            "file1": str(pdf1_path),
            "file2": str(pdf2_path),
            "doc1_pages": max(b["page"] for b in ordered_list1) + 1 if ordered_list1 else 0,
            "doc2_pages": max(b["page"] for b in ordered_list2) + 1 if ordered_list2 else 0,
            "total_differences": len(diff_results),
            "llm_used": {
                "reading_order": args.use_llm_order,
                "summary": args.use_llm_summary,
                "structure_analysis": args.analyze_structure
            }
        }
    )
    
    # 出力ハンドラーでPDFとレポートを生成
    output_handler = OutputHandler()
    output_handler.save_all_outputs(
        comparison_result=comparison_result,
        pdf1_bytes=pdf1_bytes,
        pdf2_bytes=pdf2_bytes,
        pdf1_path=pdf1_path,
        pdf2_path=pdf2_path,
        output_dir=output_dir
    )
    
    print(f"\n処理完了！実行時間: {comparison_result.execution_time:.2f}秒")
    print(f"結果は {output_dir} に保存されました")

if __name__ == "__main__":
    main()