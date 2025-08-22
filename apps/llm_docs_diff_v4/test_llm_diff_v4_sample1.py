#!/usr/bin/env python3
"""
LLM Diff Test v4 - 拡張版（階層構造 + 読み取り順序） - サンプル1テスト用
視覚的な流れと階層構造を考慮した最新版
"""
import os
import sys
from pathlib import Path
import time
import argparse

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.llm_docs_diff_v4.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from apps.llm_docs_diff_v4.core.text_preprocessing import TextPreprocessor
from apps.llm_docs_diff_v4.core.diff_detector_v4 import PositionBasedDiffDetector
from apps.llm_docs_diff_v4.handlers.output_handler import OutputHandler
from apps.llm_docs_diff_v4.models.bbox_models import BBoxTextData
from apps.llm_docs_diff_v4.core.reading_order_v4 import ReadingOrderEstimatorV4
import json

def main():
    # サンプル1のPDFパスを設定
    base_path = Path(__file__).parent.parent.parent
    data_dir = base_path / "data" / "sample1"
    pdf1_path = data_dir / "サンプル①2024.pdf"
    pdf2_path = data_dir / "サンプル①2025.pdf"
    
    if not pdf1_path.exists() or not pdf2_path.exists():
        print(f"エラー: テストファイルが見つかりません")
        if not pdf1_path.exists():
            print(f"  PDF1が存在しません: {pdf1_path}")
        if not pdf2_path.exists():
            print(f"  PDF2が存在しません: {pdf2_path}")
        return
    
    print(f"PDF1: {pdf1_path}")
    print(f"PDF2: {pdf2_path}")
    
    # 実行時間計測開始
    start_time = time.time()
    
    # PDFファイルを読み込む
    with open(pdf1_path, "rb") as f:
        pdf1_bytes = f.read()
    with open(pdf2_path, "rb") as f:
        pdf2_bytes = f.read()
    
    # 出力ディレクトリ（v4専用、サンプル1用）
    output_dir = Path("output/llm_diff_test_v4/sample1")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Azure Document Intelligenceサービス（拡張版）を初期化
    azure_service = AzureDocumentServiceEnhanced()
    
    # PDFから階層構造でレイアウト情報を抽出
    print("Azure Document Intelligenceで文書を解析中（階層構造）...")
    
    # 階層構造の抽出
    hierarchy1 = azure_service.extract_layout_with_hierarchy(pdf1_bytes)
    hierarchy2 = azure_service.extract_layout_with_hierarchy(pdf2_bytes)
    
    print(f"PDF1から {len(hierarchy1['paragraphs'])} 段落、{len(hierarchy1['lines'])} 行、{len(hierarchy1['words'])} 単語を抽出")
    print(f"PDF2から {len(hierarchy2['paragraphs'])} 段落、{len(hierarchy2['lines'])} 行、{len(hierarchy2['words'])} 単語を抽出")
    
    # 読み取り順序を推定（V4版）
    print("高度な読み取り順序を推定中...")
    reading_order_estimator = ReadingOrderEstimatorV4()
    
    # 段落レベルの読み取り順序
    ordered_paragraphs1 = reading_order_estimator.estimate_reading_order(hierarchy1["paragraphs"])
    ordered_paragraphs2 = reading_order_estimator.estimate_reading_order(hierarchy2["paragraphs"])
    
    # デバッグ情報を保存
    debug_dir = output_dir / "debug"
    debug_dir.mkdir(exist_ok=True)
    
    # 階層構造データを保存
    with open(debug_dir / "hierarchy1.json", "w", encoding="utf-8") as f:
        # raw_resultを除外してJSON保存
        save_data = {
            "paragraphs": hierarchy1["paragraphs"],
            "lines": hierarchy1["lines"],
            "words": [{"text": w["text"] if isinstance(w, dict) else w.text, 
                       "bbox": w["bbox"] if isinstance(w, dict) else w.bbox, 
                       "page": w["page"] if isinstance(w, dict) else w.page} for w in hierarchy1["words"]]
        }
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    with open(debug_dir / "hierarchy2.json", "w", encoding="utf-8") as f:
        save_data = {
            "paragraphs": hierarchy2["paragraphs"],
            "lines": hierarchy2["lines"],
            "words": [{"text": w["text"] if isinstance(w, dict) else w.text, 
                       "bbox": w["bbox"] if isinstance(w, dict) else w.bbox, 
                       "page": w["page"] if isinstance(w, dict) else w.page} for w in hierarchy2["words"]]
        }
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    # 読み取り順序情報を保存
    with open(debug_dir / "ordered_paragraphs1.json", "w", encoding="utf-8") as f:
        json.dump(ordered_paragraphs1, f, ensure_ascii=False, indent=2)
    with open(debug_dir / "ordered_paragraphs2.json", "w", encoding="utf-8") as f:
        json.dump(ordered_paragraphs2, f, ensure_ascii=False, indent=2)
    
    # 差分検出器を初期化（V4版）
    detector = PositionBasedDiffDetector()
    
    # 差分検出を実行
    print("階層構造を考慮した差分を検出中...")
    # 段落レベルの差分を検出
    diff_results = detector.detect_differences(
        hierarchy1["paragraphs"], 
        hierarchy2["paragraphs"],
        ordered_paragraphs1, 
        ordered_paragraphs2
    )
    
    # 実行時間を計測
    elapsed_time = time.time() - start_time
    
    # 結果の統計情報を表示
    from apps.llm_docs_diff_v4.models.bbox_models import ChangeType
    additions = [d for d in diff_results if d.change_type == ChangeType.ADDITION]
    deletions = [d for d in diff_results if d.change_type == ChangeType.DELETION]
    modifications = [d for d in diff_results if d.change_type == ChangeType.MODIFICATION]
    
    print(f"\n検出された差分（段落レベル）:")
    print(f"  追加: {len(additions)}個")
    print(f"  削除: {len(deletions)}個")
    print(f"  変更: {len(modifications)}個")
    
    print(f"\n実行時間: {elapsed_time:.2f}秒")
    
    # ComparisonResult形式に変換
    from apps.llm_docs_diff_v4.models.bbox_models import ComparisonResult
    comparison_result = ComparisonResult(
        diff_results=diff_results,
        reading_order_doc1=hierarchy1["words"],
        reading_order_doc2=hierarchy2["words"]
    )
    
    # 出力ハンドラーを使用して結果を保存
    output_handler = OutputHandler(output_dir)
    saved_files = output_handler.save_all_outputs(
        comparison_result, 
        ordered_paragraphs1,
        ordered_paragraphs2,
        pdf1_bytes,
        pdf2_bytes
    )
    print(f"\n結果を保存しました:")
    for file_type, file_path in saved_files.items():
        print(f"  - {file_type}: {file_path}")

if __name__ == "__main__":
    main()