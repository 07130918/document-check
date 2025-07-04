#!/usr/bin/env python3
"""
ベースライン評価統合プログラム
読み順序の並び替え → 読み順序評価 → 差分検出評価
"""
import json
import logging
from pathlib import Path
import sys
from datetime import datetime
from typing import List, Dict, Tuple

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.pdf_diff_system.app.modules.reading_order.pdf_text_extractor import PDFTextExtractor
from apps.pdf_diff_system.app.infrastructure.evaluation.annotation_loader import (
    AnnotationDataLoader, AnnotationDiff
)
from apps.pdf_diff_system.app.modules.diff_detection.phrase_based_diff_detector import (
    PhraseBasedDiffDetector
)
from apps.pdf_diff_system.app.domain.models.diff_result import DiffResult, ChangeType
from apps.pdf_diff_system.evaluate_reading_order_with_annotation import (
    ReadingOrderEvaluatorWithAnnotation, ReadingOrderAnnotation
)

# ロギング設定
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BaselineEvaluator:
    """ベースライン評価の統合クラス"""
    
    def __init__(self):
        self.pdf_extractor = PDFTextExtractor()
        self.annotation_loader = AnnotationDataLoader()
        self.diff_detector = PhraseBasedDiffDetector()
        self.reading_order_evaluator = ReadingOrderEvaluatorWithAnnotation()
    
    def evaluate_reading_order(self, pdf_path: Path, annotation_csv_path: Path) -> Dict:
        """読み順序評価を実行"""
        logger.info("読み順序評価を開始...")
        
        # アノテーション読み込み
        annotations = self.reading_order_evaluator.load_reading_order_annotations(annotation_csv_path)
        if not annotations:
            logger.error("読み順序アノテーションの読み込みに失敗")
            return {}
        
        # ページごとにグループ化
        page_annotations = {}
        for ann in annotations:
            if ann.page not in page_annotations:
                page_annotations[ann.page] = []
            page_annotations[ann.page].append(ann)
        
        # 各ページを評価
        results = {
            'evaluation_date': datetime.now().isoformat(),
            'pdf_path': str(pdf_path),
            'annotation_file': str(annotation_csv_path),
            'page_results': []
        }
        
        all_scores = []
        all_match_rates = []
        
        for page_num in sorted(page_annotations.keys()):
            page_anns = sorted(page_annotations[page_num], key=lambda a: a.order_number)
            result = self.reading_order_evaluator.evaluate_page(pdf_path, page_num, page_anns)
            results['page_results'].append(result)
            
            if result['status'] == 'evaluated':
                all_scores.append(result['metrics']['composite_score'])
                all_match_rates.append(result['metrics']['match_rate'])
        
        # サマリー計算
        if all_scores:
            import numpy as np
            results['summary'] = {
                'average_composite_score': float(np.mean(all_scores)),
                'average_match_rate': float(np.mean(all_match_rates)),
                'pages_evaluated': len(all_scores)
            }
        
        return results
    
    def evaluate_diff_detection(self, pdf_2023_path: Path, pdf_2024_path: Path, 
                              annotation_csv_path: Path) -> Dict:
        """差分検出評価を実行"""
        logger.info("差分検出評価を開始...")
        
        # アノテーションデータ読み込み
        annotations = self.annotation_loader.load_annotation_csv(annotation_csv_path)
        annotations = self.annotation_loader.segment_annotation_data(annotations)
        
        # PDFテキスト抽出（読み順序に従って）
        pages_2023 = self.pdf_extractor.extract_pages_text(pdf_2023_path)
        pages_2024 = self.pdf_extractor.extract_pages_text(pdf_2024_path)
        
        # テストケース生成
        test_cases = self.annotation_loader.convert_to_test_cases(annotations, pages_2023, pages_2024)
        
        # 評価実行
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_tn = 0
        
        # 詳細分析用のデータ収集
        detailed_results = []
        
        for test_case in test_cases[:5]:  # 最初の5ケースで評価
            # 差分検出実行
            detected_diffs = self.diff_detector.detect_differences(
                test_case['doc1_text'], 
                test_case['doc2_text']
            )
            
            # 評価
            tp, fp, fn, tn, case_details = self._evaluate_detections_with_details(
                detected_diffs, test_case['ground_truth']
            )
            
            # 詳細結果を保存
            detailed_results.append({
                'case_id': test_case['case_id'],
                'name': test_case['name'],
                'page_number': test_case.get('page_number', 0),
                'doc1_text': test_case['doc1_text'],
                'doc2_text': test_case['doc2_text'],
                'ground_truth': test_case['ground_truth'],
                'detected_diffs': detected_diffs,
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'tn': tn,
                'details': case_details
            })
            
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_tn += tn
        
        # メトリクス計算
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (total_tp + total_tn) / (total_tp + total_fp + total_fn + total_tn) if (total_tp + total_fp + total_fn + total_tn) > 0 else 0
        
        # 詳細分析レポートを生成
        if detailed_results:
            self._generate_detailed_analysis_report(detailed_results)
        
        return {
            'evaluation_date': datetime.now().isoformat(),
            'test_cases_count': len(test_cases[:5]),
            'metrics': {
                'true_positives': total_tp,
                'false_positives': total_fp,
                'false_negatives': total_fn,
                'true_negatives': total_tn,
                'precision': precision,
                'recall': recall,
                'f1_score': f1_score,
                'accuracy': accuracy
            },
            'detailed_results': detailed_results
        }
    
    def _evaluate_detections(self, detected_diffs: List[DiffResult], 
                           ground_truth: List[AnnotationDiff]) -> Tuple[int, int, int, int]:
        """検出結果を評価（部分一致対応）"""
        tp = 0  # True Positives
        fp = 0  # False Positives
        fn = 0  # False Negatives
        tn = 0  # True Negatives
        
        # 検出された差分を評価
        detected_texts = [(d.original_text, d.modified_text) for d in detected_diffs]
        # ground_truthは辞書のリストなので、適切にアクセス
        ground_truth_texts = []
        for g in ground_truth:
            if isinstance(g, dict):
                ground_truth_texts.append((g.get('original_text', ''), g.get('modified_text', '')))
            else:
                # AnnotationDiffオブジェクトの場合
                ground_truth_texts.append((g.before_text, g.after_text))
        
        # True Positives: 正しく検出された差分（部分一致を許可）
        matched_detected = []
        matched_truth = []
        
        for i, detected in enumerate(detected_texts):
            for j, truth in enumerate(ground_truth_texts):
                if j not in matched_truth and self._is_partial_match(detected, truth):
                    tp += 1
                    matched_detected.append(i)
                    matched_truth.append(j)
                    break
        
        # False Positives: 誤検出
        fp = len(detected_texts) - len(matched_detected)
        
        # False Negatives: 検出できなかった差分
        fn = len(ground_truth_texts) - len(matched_truth)
        
        # True Negatives の計算（簡易版）
        if len(detected_diffs) == 0 and len(ground_truth) == 0:
            tn = 1
        
        return tp, fp, fn, tn
    
    def _is_partial_match(self, detected: Tuple[str, str], truth: Tuple[str, str]) -> bool:
        """部分一致判定
        
        アノテーションと検出結果が部分的に一致する場合もTrueを返す
        例: 
        - アノテーション: "iOS 11/12/13/14/15/16" 
        - 検出: "11/12/13/14/15/16"
        """
        det_orig, det_mod = detected
        truth_orig, truth_mod = truth
        
        # Noneや空文字列の処理
        det_orig = det_orig or ''
        det_mod = det_mod or ''
        truth_orig = truth_orig or ''
        truth_mod = truth_mod or ''
        
        # 前後のテキストそれぞれで部分一致を確認
        # 完全一致
        if det_orig == truth_orig and det_mod == truth_mod:
            return True
        
        # 部分一致（どちらかがどちらかに含まれる）
        # 元テキストの部分一致
        orig_match = False
        if det_orig and truth_orig:
            orig_match = (det_orig in truth_orig or truth_orig in det_orig)
        elif not det_orig and not truth_orig:
            orig_match = True
        
        # 変更後テキストの部分一致
        mod_match = False
        if det_mod and truth_mod:
            mod_match = (det_mod in truth_mod or truth_mod in det_mod)
        elif not det_mod and not truth_mod:
            mod_match = True
        
        # 両方が部分一致していればTrue
        return orig_match and mod_match
    
    def _evaluate_detections_with_details(self, detected_diffs: List[DiffResult], 
                           ground_truth: List) -> Tuple[int, int, int, int, Dict]:
        """検出結果を評価し、詳細情報も返す"""
        tp = 0
        fp = 0
        fn = 0
        tn = 0
        
        # 検出された差分を評価
        detected_texts = [(d.original_text, d.modified_text) for d in detected_diffs]
        # ground_truthは辞書のリストなので、適切にアクセス
        ground_truth_texts = []
        ground_truth_items = []
        for g in ground_truth:
            if isinstance(g, dict):
                ground_truth_texts.append((g.get('original_text', ''), g.get('modified_text', '')))
                ground_truth_items.append(g)
            else:
                ground_truth_texts.append((g.before_text, g.after_text))
                ground_truth_items.append({'original_text': g.before_text, 'modified_text': g.after_text})
        
        # マッチング結果を記録
        matched_detected = []
        matched_truth = []
        true_positives = []
        false_positives = []
        false_negatives = []
        
        # True Positives: 正しく検出された差分
        for i, detected in enumerate(detected_texts):
            matched = False
            for j, truth in enumerate(ground_truth_texts):
                if j not in matched_truth and self._is_partial_match(detected, truth):
                    tp += 1
                    matched_detected.append(i)
                    matched_truth.append(j)
                    true_positives.append({
                        'detected': detected_diffs[i],
                        'ground_truth': ground_truth_items[j]
                    })
                    matched = True
                    break
            
            if not matched:
                fp += 1
                false_positives.append(detected_diffs[i])
        
        # False Negatives: 検出できなかった差分
        for j, truth in enumerate(ground_truth_items):
            if j not in matched_truth:
                fn += 1
                false_negatives.append(truth)
        
        # True Negatives の計算（簡易版）
        if len(detected_diffs) == 0 and len(ground_truth) == 0:
            tn = 1
        
        details = {
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives
        }
        
        return tp, fp, fn, tn, details
    
    def generate_integrated_report(self, reading_order_results: Dict, 
                                 diff_detection_results: Dict) -> str:
        """統合評価レポートを生成"""
        report = []
        report.append("# ベースライン統合評価レポート\n")
        report.append(f"評価日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 読み順序評価結果
        report.append("\n## 1. 読み順序評価結果\n")
        if 'summary' in reading_order_results:
            summary = reading_order_results['summary']
            report.append(f"- **平均総合スコア**: {summary['average_composite_score']:.3f}")
            report.append(f"- **平均マッチ率**: {summary['average_match_rate']:.1%}")
            report.append(f"- **評価ページ数**: {summary['pages_evaluated']}")
        
        # 差分検出評価結果
        report.append("\n## 2. 差分検出評価結果\n")
        if 'metrics' in diff_detection_results:
            metrics = diff_detection_results['metrics']
            report.append(f"- **適合率 (Precision)**: {metrics['precision']:.3f}")
            report.append(f"- **再現率 (Recall)**: {metrics['recall']:.3f}")
            report.append(f"- **F1スコア**: {metrics['f1_score']:.3f}")
            report.append(f"- **精度 (Accuracy)**: {metrics['accuracy']:.3f}")
        
        # 総合評価
        report.append("\n## 3. 総合評価\n")
        
        # 読み順序スコアと差分検出F1スコアの平均
        if 'summary' in reading_order_results and 'metrics' in diff_detection_results:
            reading_score = reading_order_results['summary']['average_composite_score']
            diff_f1 = diff_detection_results['metrics']['f1_score']
            overall_score = (reading_score + diff_f1) / 2
            
            report.append(f"- **総合スコア**: {overall_score:.3f}")
            
            if overall_score >= 0.8:
                report.append("- **評価**: 優秀 - 実用レベル")
            elif overall_score >= 0.6:
                report.append("- **評価**: 良好 - 改善余地あり")
            elif overall_score >= 0.4:
                report.append("- **評価**: 可 - 大幅な改善必要")
            else:
                report.append("- **評価**: 不可 - 根本的な見直し必要")
        
        # 改善提案
        report.append("\n## 4. 改善提案\n")
        if 'summary' in reading_order_results:
            if reading_order_results['summary']['average_composite_score'] < 0.8:
                report.append("- 読み順序の改善が必要です")
                report.append("  - PDFレイアウト解析の精度向上")
                report.append("  - ブロック結合ロジックの改善")
        
        if 'metrics' in diff_detection_results:
            if diff_detection_results['metrics']['f1_score'] < 0.6:
                report.append("- 差分検出の改善が必要です")
                report.append("  - トークナイゼーションの最適化")
                report.append("  - 意味的な差分検出の実装")
        
        return '\n'.join(report)
    
    def _generate_detailed_analysis_report(self, detailed_results: List[Dict]):
        """詳細分析レポートを生成"""
        report = []
        report.append("# 差分検出詳細分析レポート（部分一致対応）\n")
        report.append("## 概要")
        report.append("このレポートでは、各ページでの差分検出結果を詳細に分析し、")
        report.append("検出できた差分と検出できなかった差分を具体的に示します。")
        report.append("**部分一致評価を採用**：アノテーションと検出結果が部分的に一致する場合も正解とします。\n")
        
        # 全体統計
        total_tp = sum(r['tp'] for r in detailed_results)
        total_fp = sum(r['fp'] for r in detailed_results)
        total_fn = sum(r['fn'] for r in detailed_results)
        total_detected = sum(len(r['detected_diffs']) for r in detailed_results)
        total_truth = sum(len(r['ground_truth']) for r in detailed_results)
        
        for result in detailed_results:
            page_num = result['page_number']
            report.append(f"\n## {result['name']} (ページ {page_num})\n")
            
            # 検出結果サマリー
            report.append("### 検出結果サマリー")
            report.append(f"- **正解差分数**: {len(result['ground_truth'])}件")
            report.append(f"- **検出差分数**: {len(result['detected_diffs'])}件")
            report.append(f"- **正しく検出 (TP)**: {result['tp']}件")
            report.append(f"- **誤検出 (FP)**: {result['fp']}件")
            report.append(f"- **検出漏れ (FN)**: {result['fn']}件")
            if len(result['ground_truth']) > 0:
                detection_rate = result['tp'] / len(result['ground_truth'])
                report.append(f"- **検出率**: {result['tp']}/{len(result['ground_truth'])} = {detection_rate:.1%}")
            
            # 文書テキスト（最初の100文字のみ表示）
            report.append("\n### 文書テキスト（抜粋）")
            report.append(f"**2023年版**: {result['doc1_text'][:100]}...")
            report.append(f"**2024年版**: {result['doc2_text'][:100]}...")
            
            details = result['details']
            
            # 正しく検出できた差分
            if details['true_positives']:
                report.append("\n### ✅ 正しく検出できた差分")
                for i, tp in enumerate(details['true_positives'][:10], 1):  # 最初の10件
                    detected = tp['detected']
                    truth = tp['ground_truth']
                    report.append(f"{i}. `{detected.original_text}` → `{detected.modified_text}`")
                    if (detected.original_text != truth.get('original_text') or 
                        detected.modified_text != truth.get('modified_text')):
                        report.append(f"   (部分一致: アノテーション `{truth.get('original_text')}` → `{truth.get('modified_text')}`)")
                if len(details['true_positives']) > 10:
                    report.append(f"   ... 他 {len(details['true_positives']) - 10} 件")
            
            # 検出できなかった差分
            if details['false_negatives']:
                report.append("\n### ❌ 検出できなかった差分 (見逃し)")
                for i, fn in enumerate(details['false_negatives'][:10], 1):  # 最初の10件
                    report.append(f"{i}. `{fn.get('original_text', '')}` → `{fn.get('modified_text', '')}`")
                    if 'element_id' in fn:
                        report.append(f"   ({fn.get('element_id', '')} - {fn.get('change_type', '')})")
                if len(details['false_negatives']) > 10:
                    report.append(f"   ... 他 {len(details['false_negatives']) - 10} 件")
            
            # 誤って検出された差分
            if details['false_positives']:
                report.append("\n### ⚠️ 誤って検出された差分 (誤検出)")
                for i, fp in enumerate(details['false_positives'][:10], 1):  # 最初の10件
                    report.append(f"{i}. `{fp.original_text}` → `{fp.modified_text}`")
                if len(details['false_positives']) > 10:
                    report.append(f"   ... 他 {len(details['false_positives']) - 10} 件")
            
            report.append("---")
        
        # 全体サマリー
        report.append("\n## 全体サマリー\n")
        report.append("### 検出性能統計")
        report.append(f"- **全正解差分数**: {total_truth}件")
        report.append(f"- **全検出差分数**: {total_detected}件")
        report.append(f"- **正しく検出 (TP)**: {total_tp}件")
        report.append(f"- **誤検出 (FP)**: {total_fp}件")
        report.append(f"- **検出漏れ (FN)**: {total_fn}件")
        if total_truth > 0:
            report.append(f"- **全体検出率 (Recall)**: {total_tp/total_truth:.1%}")
        if total_detected > 0:
            report.append(f"- **全体適合率 (Precision)**: {total_tp/total_detected:.1%}")
        
        report.append("\n### 分析結果")
        report.append("部分一致評価により、以下のようなケースも正解として扱われます：")
        report.append("- アノテーション「iOS 11/12/13/14/15/16」vs 検出「11/12/13/14/15/16」")
        report.append("- 前後の空白や記号の違い")
        report.append("- 一方が他方に含まれる場合")
        
        # ファイルに保存
        output_path = Path("results/detailed_detection_analysis.md")
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        logger.info(f"詳細分析レポートを保存: {output_path}")


def main():
    """メイン実行関数"""
    logger.info("ベースライン統合評価を開始します...")
    
    # ファイルパス設定
    pdf_2023_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    pdf_2024_path = Path("/root/AICE/prj-ms-document-check/docs/img/2024.pdf")
    reading_order_annotation_path = Path("/root/AICE/prj-ms-document-check/apps/pdf_diff_system/data/reading_order_{㈪2023_MSADグループ_パンフレット} - annotation_template.csv")
    diff_annotation_path = Path("/root/AICE/prj-ms-document-check/apps/pdf_diff_system/data/annotation_MSADグループ_パンフレット_2023and2024_20250627 - annotation_template.csv")
    
    # 評価器初期化
    evaluator = BaselineEvaluator()
    
    # 1. 読み順序評価
    logger.info("\n=== フェーズ1: 読み順序評価 ===")
    reading_order_results = evaluator.evaluate_reading_order(
        pdf_2023_path, reading_order_annotation_path
    )
    
    # 2. 差分検出評価
    logger.info("\n=== フェーズ2: 差分検出評価 ===")
    diff_detection_results = evaluator.evaluate_diff_detection(
        pdf_2023_path, pdf_2024_path, diff_annotation_path
    )
    
    # 3. 統合レポート生成
    logger.info("\n=== 統合レポート生成 ===")
    report = evaluator.generate_integrated_report(
        reading_order_results, diff_detection_results
    )
    
    # 結果保存
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    
    # JSON保存
    results = {
        'reading_order': reading_order_results,
        'diff_detection': diff_detection_results
    }
    json_output = output_dir / "baseline_integrated_results.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # レポート保存
    report_output = output_dir / "baseline_integrated_report.md"
    with open(report_output, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"\n評価完了。結果を保存しました:")
    logger.info(f"- JSON: {json_output}")
    logger.info(f"- レポート: {report_output}")
    
    # コンソールに要約表示
    print("\n" + "="*50)
    print(report)


if __name__ == "__main__":
    main()