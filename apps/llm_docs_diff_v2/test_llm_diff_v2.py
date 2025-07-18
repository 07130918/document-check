#!/usr/bin/env python3
"""
LLM Diff Test v2 - Azure Document Intelligence行ベース版
段落・行レベルの階層構造を活用した改良版
"""
import os
import sys
from pathlib import Path

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from llm_docs_diff_v2.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from llm_docs_diff_v2.core.text_preprocessing import TextPreprocessor
from llm_docs_diff_v2.core.diff_detector import EnhancedDiffDetector
from llm_docs_diff_v2.handlers.output_handler import OutputHandler
from llm_docs_diff_v2.models.bbox_models import ComparisonResult, ChangeType, DiffResult, BBoxTextData
from llm_docs_diff_v2.core.reading_order_v2 import ReadingOrderEstimatorV2
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
    
    # 出力ディレクトリ（v2専用）
    output_dir = Path("output/llm_diff_test_v2")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ========== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 ==========
    print("===== LLM Diff Test v2 (Azure行ベース版) =====")
    print("\n===== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 =====")
    
    azure_service = AzureDocumentServiceEnhanced()
    text_preprocessor = TextPreprocessor()
    
    print("\n1. 2023年PDFの処理...")
    # 階層構造で抽出
    hierarchy1 = azure_service.extract_layout_with_hierarchy(pdf1_bytes)
    print(f"   段落数: {len(hierarchy1['paragraphs'])}")
    print(f"   行数: {len(hierarchy1['lines'])}")
    print(f"   単語数: {len(hierarchy1['words'])}")
    
    # 行ベースのデータを取得
    line_bbox_list1 = azure_service.extract_layout_from_lines(pdf1_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list1)}")
    
    # 前処理を適用（行レベルでは前処理は最小限に）
    bbox_list1 = text_preprocessor.preprocess_bbox_list(line_bbox_list1)
    print(f"   前処理前: {len(line_bbox_list1)} → 前処理後: {len(bbox_list1)}")
    
    print("\n2. 2024年PDFの処理...")
    # 階層構造で抽出
    hierarchy2 = azure_service.extract_layout_with_hierarchy(pdf2_bytes)
    print(f"   段落数: {len(hierarchy2['paragraphs'])}")
    print(f"   行数: {len(hierarchy2['lines'])}")
    print(f"   単語数: {len(hierarchy2['words'])}")
    
    # 行ベースのデータを取得
    line_bbox_list2 = azure_service.extract_layout_from_lines(pdf2_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list2)}")
    
    # 前処理を適用
    bbox_list2 = text_preprocessor.preprocess_bbox_list(line_bbox_list2)
    print(f"   前処理前: {len(line_bbox_list2)} → 前処理後: {len(bbox_list2)}")
    
    # ========== ステップ2: 読み取り順序の推定（行ベースでは通常不要だが一応実行） ==========
    print("\n===== ステップ2: 読み取り順序の確認 =====")
    
    # 行データは既に正しい順序になっているはずだが、念のため確認
    order_estimator = ReadingOrderEstimatorV2(
        line_height_ratio=0.5,
        max_word_gap_ratio=3.0
    )
    
    # 文書1の読み取り順序を確認
    print("1. 2023年PDFの読み取り順序を確認中...")
    ordered_list1 = order_estimator.estimate_reading_order(bbox_list1)
    
    # 文書2の読み取り順序を確認
    print("2. 2024年PDFの読み取り順序を確認中...")
    ordered_list2 = order_estimator.estimate_reading_order(bbox_list2)
    
    # ========== ステップ3: 差分検出 ==========
    print("\n===== ステップ3: 差分検出（行ベース） =====")
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
            "version": "v2_line_based",
            "extraction_method": "Azure Document Intelligence (Line-based)",
            "doc1_name": "2023.pdf",
            "doc2_name": "2024.pdf",
            "hierarchy_info": {
                "doc1": {
                    "paragraphs": len(hierarchy1['paragraphs']),
                    "lines": len(hierarchy1['lines']),
                    "words": len(hierarchy1['words'])
                },
                "doc2": {
                    "paragraphs": len(hierarchy2['paragraphs']),
                    "lines": len(hierarchy2['lines']),
                    "words": len(hierarchy2['words'])
                }
            },
            "extraction_level": "line",
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
        output_name="llm_diff_test_v2",
        pdf1_bytes=pdf1_bytes,
        pdf2_bytes=pdf2_bytes
    )
    
    print("\n保存されたファイル:")
    for file_type, file_path in saved_files.items():
        print(f"- {file_type}: {Path(file_path).name}")
    
    # ========== ステップ6: v2追加機能 - 階層情報の詳細分析 ==========
    print("\n===== ステップ6: v2追加機能 - 階層情報の詳細分析 =====")
    
    # 行レベルの詳細分析
    line_analysis = analyze_line_differences(diff_results, hierarchy1, hierarchy2)
    
    # 分析結果の保存
    analysis_path = output_dir / "reports" / "v2_line_analysis.json"
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(line_analysis, f, ensure_ascii=False, indent=2)
    
    print(f"行レベル分析を保存: {analysis_path}")
    
    # ========== ステップ7: 段落レベルとの比較 ==========
    print("\n===== ステップ7: 段落レベルとの比較分析 =====")
    
    # 段落ベースでも抽出してみる
    para_bbox_list1 = azure_service.extract_layout_from_paragraphs(pdf1_bytes)
    para_bbox_list2 = azure_service.extract_layout_from_paragraphs(pdf2_bytes)
    
    print(f"\n段落ベースの要素数:")
    print(f"- 2023年: {len(para_bbox_list1)}段落")
    print(f"- 2024年: {len(para_bbox_list2)}段落")
    
    # 段落の最初の5つを表示
    print("\n2023年の最初の5段落:")
    for i, para in enumerate(para_bbox_list1[:5]):
        print(f"{i+1}. {para['text'][:50]}...")
    
    print("\n2024年の最初の5段落:")
    for i, para in enumerate(para_bbox_list2[:5]):
        print(f"{i+1}. {para['text'][:50]}...")
    
    # 統計レポート
    v2_stats = {
        "version": "v2_line_based",
        "extraction_method": "Azure Document Intelligence (Hierarchical)",
        "comparison": {
            "word_level": {
                "doc1": len(hierarchy1['words']),
                "doc2": len(hierarchy2['words']),
                "description": "文字単位（最も詳細だが、レイアウトが混在しやすい）"
            },
            "line_level": {
                "doc1": len(hierarchy1['lines']),
                "doc2": len(hierarchy2['lines']),
                "description": "行単位（視覚的な行を保持、レイアウトの混在を防ぐ）"
            },
            "paragraph_level": {
                "doc1": len(hierarchy1['paragraphs']),
                "doc2": len(hierarchy2['paragraphs']),
                "description": "段落単位（論理的な文章のまとまりを保持）"
            }
        },
        "difference_detection": {
            "level": "line",
            "results": stats,
            "total": len(diff_results)
        },
        "improvements_over_v1": [
            "Azure Document Intelligenceの階層構造を活用",
            "行レベルでの抽出により「団体保険制度」と「役員・従業員...」の混在を防止",
            "段落レベルの情報も取得可能",
            "より正確なレイアウト認識",
            "論理的な文書構造の保持"
        ]
    }
    
    stats_path = output_dir / "reports" / "v2_statistics.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(v2_stats, f, ensure_ascii=False, indent=2)
    
    print(f"\nv2統計レポートを保存: {stats_path}")
    
    # デバッグ用：特定の行の内容を確認
    print("\n===== デバッグ: 「団体保険制度」周辺の行を確認 =====")
    for i, line in enumerate(ordered_list1[:20]):
        if "団体" in line['text'] or "役員" in line['text']:
            print(f"行{i+1}: {line['text']}")
    
    print("\n===== LLM Diff Test v2 (Azure行ベース版) 完了！ =====")
    print(f"すべての結果は {output_dir} に保存されました。")

def analyze_line_differences(diff_results, hierarchy1, hierarchy2):
    """行レベルの差分を詳細分析"""
    analysis = {
        "extraction_level": "line",
        "line_changes": {
            "total_lines_doc1": len(hierarchy1['lines']),
            "total_lines_doc2": len(hierarchy2['lines']),
            "changed_lines": len(diff_results)
        },
        "paragraph_mapping": {
            "doc1_paragraphs": len(hierarchy1['paragraphs']),
            "doc2_paragraphs": len(hierarchy2['paragraphs'])
        },
        "sample_differences": []
    }
    
    # 最初の10個の差分をサンプルとして保存
    for diff in diff_results[:10]:
        sample = {
            "type": diff.change_type.value,
            "page": diff.page
        }
        
        if diff.change_type == ChangeType.MODIFICATION:
            if hasattr(diff.original_bbox, 'text'):
                sample["before"] = diff.original_bbox.text
            else:
                sample["before"] = diff.original_bbox.get('text', '')
                
            if hasattr(diff.modified_bbox, 'text'):
                sample["after"] = diff.modified_bbox.text
            else:
                sample["after"] = diff.modified_bbox.get('text', '')
        
        elif diff.change_type == ChangeType.DELETION:
            if hasattr(diff.original_bbox, 'text'):
                sample["text"] = diff.original_bbox.text
            else:
                sample["text"] = diff.original_bbox.get('text', '')
        
        elif diff.change_type == ChangeType.ADDITION:
            if hasattr(diff.modified_bbox, 'text'):
                sample["text"] = diff.modified_bbox.text
            else:
                sample["text"] = diff.modified_bbox.get('text', '')
        
        analysis["sample_differences"].append(sample)
    
    return analysis

if __name__ == "__main__":
    main()