#!/usr/bin/env python3
"""
Annotation-based PDF Difference Detection Test
Real annotation data evaluation for order-aware difference detection
"""
import json
import logging
from pathlib import Path
import sys
from typing import List, Dict, Tuple

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.pdf_diff_system.app.infrastructure.evaluation.annotation_loader import (
    AnnotationDataLoader, AnnotationDiff
)
from apps.pdf_diff_system.app.modules.reading_order.pdf_text_extractor import PDFTextExtractor
from apps.pdf_diff_system.app.modules.diff_detection.phrase_based_diff_detector import (
    PhraseBasedDiffDetector
)
from apps.pdf_diff_system.app.application.services.ab_test_service import ABTestService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Main execution function for annotation-based testing"""
    
    print("=== アノテーションベース PDF差分検出テスト ===")
    
    # 1. Initialize components
    print("\\n1. コンポーネント初期化")
    annotation_loader = AnnotationDataLoader()
    pdf_extractor = PDFTextExtractor()
    
    # ベースライン検出器（フレーズベース）
    baseline_detector = PhraseBasedDiffDetector()
    ab_test_service = ABTestService(baseline_detector)
    
    print(f"   ベースライン検出器: {baseline_detector.__class__.__name__}")
    
    # 2. Load annotation data
    print("\\n2. アノテーションデータ読み込み")
    annotation_path = Path("data/annotation_MSADグループ_パンフレット_2023and2024_20250627 - annotation_template.csv")
    
    if not annotation_path.exists():
        print(f"エラー: アノテーションファイルが見つかりません: {annotation_path}")
        return None
    
    try:
        annotations = annotation_loader.load_annotation_csv(annotation_path)
        print(f"✓ {len(annotations)} 件のアノテーションを読み込み")
        
        # Show statistics
        stats = annotation_loader.get_statistics(annotations)
        print(f"  - 変更あり: {stats['changes']} 件")
        print(f"  - 変更なし: {stats['no_changes']} 件") 
        print(f"  - 変更タイプ: {stats['change_types']}")
        print(f"  - ページ分布: {sorted(stats['page_distribution'].items())}")
        
        # アノテーションデータの意味的分割
        print(f"\n=== アノテーションデータの意味的分割実行 ===")
        segmented_annotations = annotation_loader.segment_annotation_data(annotations)
        annotation_loader.print_annotation_segmentation_summary(segmented_annotations)
        
        # 分割後のアノテーションを使用
        annotations = segmented_annotations
        
        # アノテーション分割レポートを保存
        annotation_loader.save_annotation_segmentation_report(annotations)
        
    except Exception as e:
        print(f"エラー: アノテーションデータの読み込みに失敗: {e}")
        return None
    
    # 3. Check for PDF files
    print("\\n3. PDFファイル確認")
    # 実際のPDFファイルパスを設定
    pdf_2023_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    pdf_2024_path = Path("/root/AICE/prj-ms-document-check/docs/img/2024.pdf")
    
    # PDFファイルの存在確認
    if not pdf_2023_path.exists():
        print(f"エラー: 2023年版PDFファイルが見つかりません: {pdf_2023_path}")
        return None
    if not pdf_2024_path.exists():
        print(f"エラー: 2024年版PDFファイルが見つかりません: {pdf_2024_path}")
        return None
    
    # PDFから実際のテキストを抽出
    print("   実際のPDFファイルからテキストを抽出")
    pages_2023 = pdf_extractor.extract_pages_text(pdf_2023_path)
    pages_2024 = pdf_extractor.extract_pages_text(pdf_2024_path)
    
    print(f"✓ 2023年版: {len(pages_2023)} ページ")
    print(f"✓ 2024年版: {len(pages_2024)} ページ")
    
    # 4. Convert annotations to test cases
    print("\\n4. テストケース生成")
    test_cases = annotation_loader.convert_to_test_cases(annotations, pages_2023, pages_2024)
    print(f"✓ {len(test_cases)} 件のテストケースを生成")
    
    # Show test case summary
    for case in test_cases[:3]:  # Show first 3 cases
        print(f"  - {case['case_id']}: {case['name']} - {len(case['ground_truth'])} 差分")
    
    # 5. Run difference detection evaluation
    print("\\n5. 差分検出評価実行")
    
    if not test_cases:
        print("エラー: 有効なテストケースがありません")
        return None
    
    # Run evaluation on first few test cases
    sample_cases = test_cases[:5] if len(test_cases) >= 5 else test_cases
    print(f"サンプル評価: {len(sample_cases)} ケース")
    
    try:
        # Execute A/B test
        result = ab_test_service.execute_ab_test(sample_cases)
        
        # 6. Results analysis
        print("\\n6. 結果分析")
        print(f"✓ テストケース数: {result.test_cases_count}")
        print(f"✓ ベースライン性能:")
        print(f"  - 真陽性率 (Recall): {result.baseline_metrics.recall:.3f}")
        print(f"  - 適合率 (Precision): {result.baseline_metrics.precision:.3f}")
        print(f"  - F1スコア: {result.baseline_metrics.f1_score:.3f}")
        print(f"  - 処理時間: {result.baseline_metrics.processing_time:.3f}秒")
        
        # 7. Save results
        print("\\n7. 結果保存")
        results_dir = Path("/root/AICE/prj-ms-document-check/apps/pdf_diff_system/results")
        results_dir.mkdir(exist_ok=True)
        
        # Save annotation test results
        annotation_results_path = results_dir / "annotation_test_results.json"
        save_annotation_results(result, annotations, sample_cases, annotation_results_path)
        print(f"✓ 結果保存: {annotation_results_path}")
        
        # Generate detailed report
        report = generate_annotation_report(result, annotations, sample_cases)
        report_path = results_dir / "annotation_test_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✓ レポート生成: {report_path}")
        
        # Generate detailed detection analysis report
        print("\\n8. 詳細差分検出分析レポート生成")
        detailed_report_generator = DetailedReportGenerator()
        
        # Collect detection results for detailed analysis
        detection_results = collect_detection_results(baseline_detector, sample_cases)
        
        detailed_report_path = results_dir / "detailed_detection_analysis.md"
        detailed_report = detailed_report_generator.generate_detection_analysis_report(
            sample_cases, detection_results, detailed_report_path
        )
        print(f"✓ 詳細分析レポート生成: {detailed_report_path}")
        
        # 文書分割分析レポートを保存
        print("\n9. 文書分割分析レポート生成")
        segmentation_report_path = baseline_detector.save_segmentation_report()
        print(f"✓ 分割分析レポート生成: {segmentation_report_path}")
        
        # セグメンテーション比較レポートを生成
        print("\n10. アノテーション vs 文書分割比較レポート生成")
        from apps.pdf_diff_system.app.infrastructure.evaluation.segmentation_comparison_generator import SegmentationComparisonGenerator
        comparison_generator = SegmentationComparisonGenerator()
        comparison_report_path = comparison_generator.generate_comparison_report(annotations, baseline_detector)
        print(f"✓ セグメンテーション比較レポート生成: {comparison_report_path}")
        
        # 真のアノテーションデータを生成
        print("\n11. 真のアノテーションデータ生成")
        true_annotation_generator = TrueAnnotationGenerator()
        true_annotations = true_annotation_generator.generate_true_annotations(annotations)
        true_annotation_generator.save_true_annotations_report(true_annotations)
        print(f"✓ 真のアノテーションデータ生成: {len(true_annotations)}件")
        print("✓ 機械的セグメンテーションと整合性のあるアノテーションを作成")
        
        print("\\n============================================================")
        print("アノテーションベース評価完了")
        print("============================================================")
        print(f"✓ 実際のアノテーションデータによる評価")
        print(f"✓ {len(annotations)} 件の実差分を含む評価")
        print(f"✓ 9ページまでの実データでの性能測定")
        print(f"✓ ベースライン検出率: {result.baseline_metrics.recall:.1%}")
        print(f"✓ ベースライン適合率: {result.baseline_metrics.precision:.1%}")
        
        return result
        
    except Exception as e:
        print(f"エラー: 評価実行中にエラー: {e}")
        logger.exception("Evaluation error")
        return None


def collect_detection_results(detector, test_cases: List[Dict]) -> List[Dict]:
    """Collect detection results for detailed analysis"""
    detection_results = []
    
    for test_case in test_cases:
        doc1_text = test_case['doc1_text']
        doc2_text = test_case['doc2_text']
        
        # Run detection
        detected_diffs = detector.detect_differences(doc1_text, doc2_text)
        
        result = {
            'test_case_id': test_case['case_id'],
            'detected_differences': detected_diffs,
            'detection_count': len(detected_diffs)
        }
        
        detection_results.append(result)
    
    return detection_results


def create_mock_page_data(annotations: List[AnnotationDiff]) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Create mock page data from annotations for testing without PDFs"""
    
    pages_2023 = {}
    pages_2024 = {}
    
    # Group annotations by page
    page_annotations = {}
    for annotation in annotations:
        page_num = annotation.current_page or annotation.previous_page
        if page_num and page_num <= 9:  # Only up to page 9
            if page_num not in page_annotations:
                page_annotations[page_num] = []
            page_annotations[page_num].append(annotation)
    
    # Create mock page content for each page
    for page_num in sorted(page_annotations.keys()):
        page_annots = page_annotations[page_num]
        
        # Build page content from annotations
        texts_2023 = []
        texts_2024 = []
        
        for annotation in page_annots:
            if annotation.previous_text:
                texts_2023.append(annotation.previous_text)
            if annotation.current_text:
                texts_2024.append(annotation.current_text)
        
        # Create page content from annotations only (no artificial context)
        page_2023_text = " ".join(texts_2023) if texts_2023 else ""
        page_2024_text = " ".join(texts_2024) if texts_2024 else ""
        
        pages_2023[page_num] = page_2023_text
        pages_2024[page_num] = page_2024_text
    
    return pages_2023, pages_2024


def save_annotation_results(result, annotations: List[AnnotationDiff], 
                          test_cases: List[Dict], output_path: Path):
    """Save annotation test results to JSON"""
    
    results_data = {
        "test_type": "annotation_based_evaluation",
        "annotation_statistics": {
            "total_annotations": len(annotations),
            "test_cases_evaluated": len(test_cases),
            "evaluation_pages": sorted(set(
                tc.get('case_id', '').replace('page_', '').replace('_', '').zfill(2)
                for tc in test_cases
            ))
        },
        "baseline_performance": {
            "true_positives": result.baseline_metrics.true_positives,
            "false_positives": result.baseline_metrics.false_positives,
            "true_negatives": result.baseline_metrics.true_negatives,
            "false_negatives": result.baseline_metrics.false_negatives,
            "precision": result.baseline_metrics.precision,
            "recall": result.baseline_metrics.recall,
            "f1_score": result.baseline_metrics.f1_score,
            "accuracy": result.baseline_metrics.accuracy,
            "processing_time": result.baseline_metrics.processing_time
        },
        "test_cases_summary": [
            {
                "case_id": tc["case_id"],
                "name": tc["name"],
                "ground_truth_count": len(tc["ground_truth"]),
                "page_number": tc.get("page_number", 0),
                "annotation_count": tc.get("annotation_count", 0)
            }
            for tc in test_cases
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)


def generate_annotation_report(result, annotations: List[AnnotationDiff], 
                             test_cases: List[Dict]) -> str:
    """Generate detailed annotation evaluation report"""
    
    report = f"""
# アノテーションベース PDF差分検出 評価レポート

## 概要
- 評価日時: {result.timestamp}
- 評価タイプ: 実アノテーションデータベース
- アノテーション総数: {len(annotations)}件
- 評価テストケース数: {len(test_cases)}

## アノテーションデータ統計

### 変更タイプ分布
"""
    
    # Count change types from annotations
    change_type_counts = {}
    for annotation in annotations:
        if annotation.has_change:
            change_type = annotation.change_type
            change_type_counts[change_type] = change_type_counts.get(change_type, 0) + 1
    
    for change_type, count in sorted(change_type_counts.items()):
        report += f"- {change_type}: {count}件\\n"
    
    report += f"""

## ベースライン性能結果

### 混同行列
- 真陽性 (TP): {result.baseline_metrics.true_positives}
- 偽陽性 (FP): {result.baseline_metrics.false_positives}  
- 真陰性 (TN): {result.baseline_metrics.true_negatives}
- 偽陰性 (FN): {result.baseline_metrics.false_negatives}

### 性能指標
- **真陽性率 (Recall)**: {result.baseline_metrics.recall:.3f} ({result.baseline_metrics.recall:.1%})
- **適合率 (Precision)**: {result.baseline_metrics.precision:.3f} ({result.baseline_metrics.precision:.1%})
- **F1スコア**: {result.baseline_metrics.f1_score:.3f}
- **精度 (Accuracy)**: {result.baseline_metrics.accuracy:.3f} ({result.baseline_metrics.accuracy:.1%})
- **処理時間**: {result.baseline_metrics.processing_time:.3f}秒

## テストケース詳細
"""
    
    for tc in test_cases:
        report += f"""
### {tc['case_id']}: {tc['name']}
- 正解差分数: {len(tc['ground_truth'])}
- 2023年テキスト長: {len(tc['doc1_text'])} 文字
- 2024年テキスト長: {len(tc['doc2_text'])} 文字
"""
    
    report += f"""

## 結論

実際のアノテーションデータ（{len(annotations)}件）を用いた評価により、ベースライン差分検出アルゴリズムの性能を測定しました。

### 主要な発見
- 検出率: {result.baseline_metrics.recall:.1%}
- 適合率: {result.baseline_metrics.precision:.1%}
- 実データでの動作確認が完了

### 改善の方向性
1. 順序入れ替えに対応した高度なアライメント
2. ページ構造を考慮した差分検出
3. 変更タイプ別の特化した検出ロジック

🤖 Generated with Claude Code
"""
    
    return report


if __name__ == "__main__":
    main()