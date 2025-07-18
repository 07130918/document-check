#!/usr/bin/env python3
"""
LLM Diff Test v3 - 内容ベースの差分検出版
位置に依存せず、テキストの移動を認識する改良版
"""
import os
import sys
from pathlib import Path

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from llm_docs_diff_v3.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from llm_docs_diff_v3.core.text_preprocessing import TextPreprocessor
from llm_docs_diff_v3.core.diff_detector_v3 import ContentBasedDiffDetector, DiffResultV3
from llm_docs_diff_v3.handlers.output_handler import OutputHandler
from llm_docs_diff_v3.models.bbox_models import ComparisonResult, ChangeType
from llm_docs_diff_v3.core.reading_order_v2 import ReadingOrderEstimatorV2
from llm_docs_diff_v3.config.settings import settings
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
    
    # 出力ディレクトリ（v3専用）
    output_dir = Path("output/llm_diff_test_v3")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ========== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 ==========
    print("===== LLM Diff Test v3 (内容ベース版) =====")
    print("\n===== ステップ1: Azure Document Intelligenceで階層的にPDFから抽出 =====")
    
    azure_service = AzureDocumentServiceEnhanced()
    text_preprocessor = TextPreprocessor()
    
    print("\n1. 2023年PDFの処理...")
    # PDFのページ数を確認
    import fitz
    pdf_doc = fitz.open(stream=pdf1_bytes, filetype="pdf")
    print(f"   元のPDFページ数: {len(pdf_doc)}ページ")
    pdf_doc.close()
    
    # 階層構造で抽出
    hierarchy1 = azure_service.extract_layout_with_hierarchy(pdf1_bytes)
    print(f"   段落数: {len(hierarchy1['paragraphs'])}")
    print(f"   行数: {len(hierarchy1['lines'])}")
    print(f"   単語数: {len(hierarchy1['words'])}")
    
    # 処理されたページ数を確認
    pages_processed = set()
    for para in hierarchy1.get('paragraphs', []):
        if 'page' in para:
            pages_processed.add(para['page'])
    print(f"   処理されたページ: {sorted(pages_processed)}")
    
    # 行ベースのデータを取得
    line_bbox_list1 = azure_service.extract_layout_from_lines(pdf1_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list1)}")
    
    # 前処理を適用
    bbox_list1 = text_preprocessor.preprocess_bbox_list(line_bbox_list1)
    print(f"   前処理前: {len(line_bbox_list1)} → 前処理後: {len(bbox_list1)}")
    
    print("\n2. 2024年PDFの処理...")
    # PDFのページ数を確認
    pdf_doc = fitz.open(stream=pdf2_bytes, filetype="pdf")
    print(f"   元のPDFページ数: {len(pdf_doc)}ページ")
    pdf_doc.close()
    
    # 階層構造で抽出
    hierarchy2 = azure_service.extract_layout_with_hierarchy(pdf2_bytes)
    print(f"   段落数: {len(hierarchy2['paragraphs'])}")
    print(f"   行数: {len(hierarchy2['lines'])}")
    print(f"   単語数: {len(hierarchy2['words'])}")
    
    # 処理されたページ数を確認
    pages_processed = set()
    for para in hierarchy2.get('paragraphs', []):
        if 'page' in para:
            pages_processed.add(para['page'])
    print(f"   処理されたページ: {sorted(pages_processed)}")
    
    # 行ベースのデータを取得
    line_bbox_list2 = azure_service.extract_layout_from_lines(pdf2_bytes)
    print(f"   行ベースの要素数: {len(line_bbox_list2)}")
    
    # 前処理を適用
    bbox_list2 = text_preprocessor.preprocess_bbox_list(line_bbox_list2)
    print(f"   前処理前: {len(line_bbox_list2)} → 前処理後: {len(bbox_list2)}")
    
    # ========== ステップ2: 読み取り順序の推定（v3では参考情報として使用） ==========
    print("\n===== ステップ2: 読み取り順序の確認（参考情報） =====")
    
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
    
    # ========== ステップ3: 差分検出（v3: 内容ベース） ==========
    print("\n===== ステップ3: 差分検出（内容ベース） =====")
    
    # v3の内容ベース差分検出器を使用
    # TEST_MAX_PAGESから1を引いて0-indexedのページ番号にする
    max_page = settings.TEST_MAX_PAGES - 1 if hasattr(settings, 'TEST_MAX_PAGES') else None
    
    diff_detector = ContentBasedDiffDetector(
        similarity_threshold=0.7,  # 閾値を下げて、より多くのマッチングを許可
        exact_match_bonus=0.2,
        position_weight=0.05,  # 位置の重みを小さく設定
        max_page=max_page  # 最大ページ番号を設定
    )
    
    # 順序付けされたリストではなく、元のリストを使用（位置に依存しないため）
    diff_results = diff_detector.detect_differences(bbox_list1, bbox_list2)
    
    # 差分の統計（移動を別カウント）
    stats = {
        'removed': 0,
        'added': 0,
        'modified': 0,
        'moved': 0
    }
    
    for d in diff_results:
        if hasattr(d, 'movement_info') and d.movement_info and d.movement_info.get('type') == 'movement':
            stats['moved'] += 1
        elif d.change_type == ChangeType.DELETION:
            stats['removed'] += 1
        elif d.change_type == ChangeType.ADDITION:
            stats['added'] += 1
        elif d.change_type == ChangeType.MODIFICATION:
            stats['modified'] += 1
    
    print(f"検出された差分:")
    print(f"- 削除: {stats['removed']}件")
    print(f"- 追加: {stats['added']}件")
    print(f"- 変更: {stats['modified']}件")
    print(f"- 移動: {stats['moved']}件")
    print(f"- 合計: {len(diff_results)}件")
    
    # ========== ステップ4: ComparisonResultオブジェクトの作成 ==========
    print("\n===== ステップ4: 結果オブジェクトの作成 =====")
    
    comparison_result = ComparisonResult(
        diff_results=diff_results,
        reading_order_doc1=ordered_list1,
        reading_order_doc2=ordered_list2,
        metadata={
            "version": "v3_content_based",
            "extraction_method": "Azure Document Intelligence (Line-based)",
            "diff_detection_method": "Content-based (position-independent)",
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
            "statistics": stats,
            "position_weight": 0.05
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
        output_name="llm_diff_test_v3",
        pdf1_bytes=pdf1_bytes,
        pdf2_bytes=pdf2_bytes
    )
    
    print("\n保存されたファイル:")
    for file_type, file_path in saved_files.items():
        print(f"- {file_type}: {Path(file_path).name}")
    
    # ========== ステップ6: v3追加機能 - 移動分析 ==========
    print("\n===== ステップ6: v3追加機能 - 移動分析 =====")
    
    # 移動の詳細分析
    movement_analysis = analyze_movements(diff_results)
    
    # 分析結果の保存
    analysis_path = output_dir / "reports" / "v3_movement_analysis.json"
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(movement_analysis, f, ensure_ascii=False, indent=2)
    
    print(f"移動分析を保存: {analysis_path}")
    
    # 移動の要約を表示
    if movement_analysis["movements"]:
        print("\n検出された移動:")
        for i, move in enumerate(movement_analysis["movements"][:5]):
            print(f"{i+1}. 「{move['text']}」: {move['from']} → {move['to']}")
    
    # ========== ステップ7: v2との比較 ==========
    print("\n===== ステップ7: v2との比較分析 =====")
    
    # v2方式（位置ベース）での差分検出も実行して比較
    from llm_docs_diff_v3.core.diff_detector import EnhancedDiffDetector
    v2_detector = EnhancedDiffDetector()
    v2_diff_results = v2_detector.detect_differences(ordered_list1, ordered_list2)
    
    v2_stats = {
        'removed': sum(1 for d in v2_diff_results if d.change_type == ChangeType.DELETION),
        'added': sum(1 for d in v2_diff_results if d.change_type == ChangeType.ADDITION),
        'modified': sum(1 for d in v2_diff_results if d.change_type == ChangeType.MODIFICATION)
    }
    
    print(f"\nv2（位置ベース）の結果:")
    print(f"- 削除: {v2_stats['removed']}件")
    print(f"- 追加: {v2_stats['added']}件")
    print(f"- 変更: {v2_stats['modified']}件")
    print(f"- 合計: {sum(v2_stats.values())}件")
    
    print(f"\nv3（内容ベース）の改善:")
    print(f"- 偽陽性の削減: {sum(v2_stats.values()) - len(diff_results)}件")
    print(f"- 移動として正しく認識: {stats['moved']}件")
    
    # 統計レポート
    v3_stats = {
        "version": "v3_content_based",
        "extraction_method": "Azure Document Intelligence (Hierarchical)",
        "diff_detection": {
            "method": "Content-based matching",
            "position_weight": 0.05,
            "similarity_threshold": 0.8
        },
        "comparison": {
            "v2_position_based": {
                "total_diffs": sum(v2_stats.values()),
                "breakdown": v2_stats
            },
            "v3_content_based": {
                "total_diffs": len(diff_results),
                "breakdown": stats,
                "improvement": sum(v2_stats.values()) - len(diff_results)
            }
        },
        "improvements_over_v2": [
            "位置に依存しない差分検出",
            "テキストの移動を正しく認識",
            "「も継続」のような位置変更を移動として処理",
            "偽陽性（削除＋追加）の大幅削減",
            "より正確な変更検出"
        ]
    }
    
    stats_path = output_dir / "reports" / "v3_statistics.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(v3_stats, f, ensure_ascii=False, indent=2)
    
    print(f"\nv3統計レポートを保存: {stats_path}")
    
    print("\n===== LLM Diff Test v3 (内容ベース版) 完了！ =====")
    print(f"すべての結果は {output_dir} に保存されました。")

def analyze_movements(diff_results):
    """移動の詳細分析"""
    movements = []
    
    for diff in diff_results:
        if hasattr(diff, 'movement_info') and diff.movement_info and diff.movement_info.get('type') == 'movement':
            movement = {
                "text": diff.original_bbox.get('text', '') if diff.original_bbox else '',
                "from": f"ページ{diff.movement_info['from_position']['page']+1}, Y:{diff.movement_info['from_position']['y']:.1f}",
                "to": f"ページ{diff.movement_info['to_position']['page']+1}, Y:{diff.movement_info['to_position']['y']:.1f}",
                "distance": abs(diff.movement_info['to_position']['y'] - diff.movement_info['from_position']['y'])
            }
            movements.append(movement)
    
    # 移動距離でソート
    movements.sort(key=lambda m: m['distance'], reverse=True)
    
    analysis = {
        "total_movements": len(movements),
        "movements": movements,
        "summary": {
            "same_page_movements": sum(1 for m in movements if "ページ1" in m['from'] and "ページ1" in m['to']),
            "cross_page_movements": sum(1 for m in movements if m['from'].split(',')[0] != m['to'].split(',')[0])
        }
    }
    
    return analysis

if __name__ == "__main__":
    main()