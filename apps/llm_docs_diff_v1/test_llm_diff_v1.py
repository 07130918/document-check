#!/usr/bin/env python3
"""
LLM Diff Test v1 - 基本版（単語ベースの抽出）
Azure Document Intelligenceを使用した単語レベルの差分検出
"""
import os
import sys
from pathlib import Path

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from llm_docs_diff.services.azure_service import AzureDocumentService
from llm_docs_diff.core.diff_detector import EnhancedDiffDetector
from llm_docs_diff.handlers.output_handler import OutputHandler
from llm_docs_diff.models.bbox_models import ComparisonResult, ChangeType, DiffResult, BBoxTextData
from llm_docs_diff.core.reading_order import ReadingOrderEstimator
import json

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
    
    # 出力ディレクトリ（v1専用）
    output_dir = Path("output/llm_diff_test_v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ========== ステップ1: Azure Document IntelligenceでPDFから抽出 ==========
    print("===== LLM Diff Test v1 (基本版) =====")
    print("\n===== ステップ1: Azure Document IntelligenceでPDFから抽出 =====")
    
    azure_service = AzureDocumentService()
    
    print("\n1. 2023年PDFの処理...")
    # Azureで抽出（単語レベルのBBoxTextDataのリストが返される）
    bbox_list1 = azure_service.extract_layout_from_pdf(pdf1_bytes)
    print(f"   抽出された要素数: {len(bbox_list1)}")
    
    print("\n2. 2024年PDFの処理...")
    # Azureで抽出
    bbox_list2 = azure_service.extract_layout_from_pdf(pdf2_bytes)
    print(f"   抽出された要素数: {len(bbox_list2)}")
    
    # ========== ステップ2: 読み取り順序の推定 ==========
    print("\n===== ステップ2: 読み取り順序の推定（v1基本版） =====")
    
    # Reading Order Estimator v1を使用
    order_estimator = ReadingOrderEstimator()
    
    # 文書1の読み取り順序を推定
    print("1. 2023年PDFの読み取り順序を推定中...")
    # BBoxTextDataをdict形式に変換
    dict_list1 = [
        {
            'text': item.text,
            'bbox': item.bbox,
            'x': item.bbox[0],
            'y': item.bbox[1],
            'width': item.bbox[2],
            'height': item.bbox[3],
            'page': item.page
        }
        for item in bbox_list1
    ]
    ordered_list1 = order_estimator.estimate_reading_order(dict_list1)
    
    # 文書2の読み取り順序を推定
    print("2. 2024年PDFの読み取り順序を推定中...")
    dict_list2 = [
        {
            'text': item.text,
            'bbox': item.bbox,
            'x': item.bbox[0],
            'y': item.bbox[1],
            'width': item.bbox[2],
            'height': item.bbox[3],
            'page': item.page
        }
        for item in bbox_list2
    ]
    ordered_list2 = order_estimator.estimate_reading_order(dict_list2)
    
    # ========== ステップ3: 差分検出 ==========
    print("\n===== ステップ3: 差分検出（基本版） =====")
    diff_detector = EnhancedDiffDetector()
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
    
    # ========== ステップ4: ComparisonResultオブジェクトの作成 ==========
    print("\n===== ステップ4: 結果オブジェクトの作成 =====")
    
    comparison_result = ComparisonResult(
        diff_results=diff_results,
        reading_order_doc1=ordered_list1,
        reading_order_doc2=ordered_list2,
        metadata={
            "version": "v1_basic",
            "extraction_method": "Azure Document Intelligence (Word-based)",
            "doc1_name": "2023.pdf",
            "doc2_name": "2024.pdf",
            "extraction_info": {
                "doc1_words": len(bbox_list1),
                "doc2_words": len(bbox_list2)
            },
            "total_differences": len(diff_results),
            "statistics": stats
        }
    )
    
    # ========== ステップ5: OutputHandlerによる出力 ==========
    print("\n===== ステップ5: OutputHandlerによる出力 =====")
    
    # OutputHandlerのインスタンス化（出力ディレクトリを指定）
    output_handler = OutputHandler()
    output_handler.output_dir = output_dir
    
    # 結果の保存
    saved_files = output_handler.save_comparison_result(
        result=comparison_result,
        output_name="llm_diff_test_v1",
        pdf1_bytes=pdf1_bytes,
        pdf2_bytes=pdf2_bytes
    )
    
    print("\n保存されたファイル:")
    for file_type, file_path in saved_files.items():
        print(f"- {file_type}: {Path(file_path).name}")
    
    # ========== ステップ6: v1基本統計レポート ==========
    print("\n===== ステップ6: v1基本統計レポートの生成 =====")
    
    v1_stats = {
        "version": "v1_basic",
        "extraction_method": "Azure Document Intelligence (Word-based)",
        "extraction_details": {
            "level": "word",
            "doc1_elements": len(bbox_list1),
            "doc2_elements": len(bbox_list2),
            "description": "単語単位の抽出（Azure標準）"
        },
        "difference_detection": {
            "algorithm": "enhanced diff detector",
            "results": stats,
            "total": len(diff_results)
        },
        "characteristics": [
            "Azure Document Intelligenceの単語レベル抽出",
            "基本的な読み取り順序推定",
            "単純な差分検出アルゴリズム",
            "前処理なし"
        ],
        "known_issues": [
            "日本語文字が個別に抽出される場合がある",
            "レイアウトが複雑な場合、読み取り順序が混在する可能性",
            "差分が多く検出される傾向"
        ]
    }
    
    stats_path = output_dir / "reports" / "v1_statistics.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(v1_stats, f, ensure_ascii=False, indent=2)
    
    print(f"v1統計レポートを保存: {stats_path}")
    
    # デバッグ用：最初の20要素を確認
    print("\n===== デバッグ: 最初の20要素を確認 =====")
    for i, item in enumerate(ordered_list1[:20]):
        print(f"要素{i+1}: {item['text']}")
    
    print("\n===== LLM Diff Test v1 (基本版) 完了！ =====")
    print(f"すべての結果は {output_dir} に保存されました。")

if __name__ == "__main__":
    main()