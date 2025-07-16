#!/usr/bin/env python3
"""
類似度ベース評価プログラム
SequenceMatcherを使用した類似度ベースの差分検出評価
"""
import json
import logging
from pathlib import Path
import sys
from datetime import datetime
from typing import List, Dict, Tuple
from difflib import SequenceMatcher

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.pdf_diff_system_withannotation.app.modules.reading_order.pdf_text_extractor import PDFTextExtractor
from apps.pdf_diff_system_withannotation.app.infrastructure.evaluation.annotation_loader import (
    AnnotationDataLoader, AnnotationDiff
)
from apps.pdf_diff_system_withannotation.app.domain.models.diff_result import DiffResult, ChangeType
from dataclasses import asdict

# ロギング設定
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SimilarityBasedDiffDetector:
    """類似度ベースの差分検出器"""

    def __init__(self, similarity_threshold: float = 0.6):
        self.similarity_threshold = similarity_threshold

    def detect_differences(self, text1: str, text2: str) -> List[DiffResult]:
        """類似度ベースで差分を検出"""
        if text1 == text2:
            return []

        # 行単位で分割
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        # SequenceMatcherで差分検出
        matcher = SequenceMatcher(None, lines1, lines2)
        diffs = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            elif tag == 'replace':
                # 置換された行を一つずつ類似度でチェック
                for i in range(i1, i2):
                    for j in range(j1, j2):
                        similarity = SequenceMatcher(None, lines1[i], lines2[j]).ratio()
                        if similarity >= self.similarity_threshold:
                            # 類似度が閾値以上なら修正として扱う
                            diffs.append(DiffResult(
                                change_type=ChangeType.MODIFICATION,
                                original_text=lines1[i],
                                modified_text=lines2[j],
                                confidence_score=similarity,
                                similarity_score=similarity,
                                detection_method="similarity_based"
                            ))
                        else:
                            # 類似度が低い場合は削除+追加として扱う
                            diffs.append(DiffResult(
                                change_type=ChangeType.DELETION,
                                original_text=lines1[i],
                                modified_text=None,
                                confidence_score=1.0,
                                similarity_score=0.0,
                                detection_method="similarity_based"
                            ))
                            diffs.append(DiffResult(
                                change_type=ChangeType.ADDITION,
                                original_text=None,
                                modified_text=lines2[j],
                                confidence_score=1.0,
                                similarity_score=0.0,
                                detection_method="similarity_based"
                            ))
            elif tag == 'delete':
                for i in range(i1, i2):
                    diffs.append(DiffResult(
                        change_type=ChangeType.DELETION,
                        original_text=lines1[i],
                        modified_text=None,
                        confidence_score=1.0,
                        similarity_score=0.0,
                        detection_method="similarity_based"
                    ))
            elif tag == 'insert':
                for j in range(j1, j2):
                    diffs.append(DiffResult(
                        change_type=ChangeType.ADDITION,
                        original_text=None,
                        modified_text=lines2[j],
                        confidence_score=1.0,
                        similarity_score=0.0,
                        detection_method="similarity_based"
                    ))

        return diffs


class SimilarityBasedEvaluator:
    """類似度ベース評価クラス"""

    def __init__(self, similarity_threshold: float = 0.6):
        self.pdf_extractor = PDFTextExtractor()
        self.annotation_loader = AnnotationDataLoader()
        self.diff_detector = SimilarityBasedDiffDetector(similarity_threshold)
        self.similarity_threshold = similarity_threshold

    def evaluate_diff_detection(self, pdf_2023_path: Path, pdf_2024_path: Path,
                              annotation_csv_path: Path) -> Dict:
        """差分検出評価を実行"""
        logger.info(f"類似度ベース差分検出評価を開始（閾値: {self.similarity_threshold}）...")

        # アノテーションデータ読み込み
        annotations = self.annotation_loader.load_annotation_csv(annotation_csv_path)
        annotations = self.annotation_loader.segment_annotation_data(annotations)

        # PDFテキスト抽出
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

            # 詳細結果を保存（DiffResultをdictに変換）
            detailed_results.append({
                'case_id': test_case['case_id'],
                'name': test_case['name'],
                'page_number': test_case.get('page_number', 0),
                'doc1_text': test_case['doc1_text'],
                'doc2_text': test_case['doc2_text'],
                'ground_truth': test_case['ground_truth'],
                'detected_diffs': [{
                    'change_type': d.change_type.value,
                    'original_text': d.original_text,
                    'modified_text': d.modified_text,
                    'confidence_score': d.confidence_score,
                    'similarity_score': d.similarity_score,
                    'detection_method': d.detection_method
                } for d in detected_diffs],
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

        return {
            'evaluation_date': datetime.now().isoformat(),
            'similarity_threshold': self.similarity_threshold,
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

    def _is_partial_match(self, detected: Tuple[str, str], truth: Tuple[str, str]) -> bool:
        """部分一致判定"""
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
                        'detected': {
                            'change_type': detected_diffs[i].change_type.value,
                            'original_text': detected_diffs[i].original_text,
                            'modified_text': detected_diffs[i].modified_text,
                            'confidence_score': detected_diffs[i].confidence_score,
                            'similarity_score': detected_diffs[i].similarity_score,
                            'detection_method': detected_diffs[i].detection_method
                        },
                        'ground_truth': ground_truth_items[j]
                    })
                    matched = True
                    break

            if not matched:
                fp += 1
                false_positives.append({
                    'change_type': detected_diffs[i].change_type.value,
                    'original_text': detected_diffs[i].original_text,
                    'modified_text': detected_diffs[i].modified_text,
                    'confidence_score': detected_diffs[i].confidence_score,
                    'similarity_score': detected_diffs[i].similarity_score,
                    'detection_method': detected_diffs[i].detection_method
                })

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


def evaluate_multiple_thresholds():
    """複数の閾値で評価を実行"""
    logger.info("複数の閾値で類似度ベース評価を実行...")

    # ファイルパス設定
    pdf_2023_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    pdf_2024_path = Path("/root/AICE/prj-ms-document-check/docs/img/2024.pdf")
    diff_annotation_path = Path("/root/AICE/prj-ms-document-check/apps/pdf_diff_system/data/annotation_MSADグループ_パンフレット_2023and2024_20250627 - annotation_template.csv")

    # 評価する閾値のリスト
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    results = {}

    for threshold in thresholds:
        logger.info(f"\n閾値 {threshold} で評価中...")
        evaluator = SimilarityBasedEvaluator(similarity_threshold=threshold)
        result = evaluator.evaluate_diff_detection(
            pdf_2023_path, pdf_2024_path, diff_annotation_path
        )
        results[f"threshold_{threshold}"] = result

    # 結果保存
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    json_output = output_dir / "similarity_based_evaluation_results.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # サマリーレポート生成
    generate_summary_report(results)

    logger.info(f"\n評価完了。結果を保存しました: {json_output}")


def generate_summary_report(results: Dict):
    """評価結果のサマリーレポートを生成"""
    report = []
    report.append("# 類似度ベース評価結果サマリー\n")
    report.append(f"評価日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    report.append("## 閾値別パフォーマンス比較\n")
    report.append("| 閾値 | TP | FP | FN | TN | Precision | Recall | F1 Score |")
    report.append("|------|----|----|----|----|-----------|--------|----------|")

    for threshold_key, result in sorted(results.items()):
        threshold = result['similarity_threshold']
        metrics = result['metrics']
        report.append(f"| {threshold:.1f} | {metrics['true_positives']} | {metrics['false_positives']} | "
                     f"{metrics['false_negatives']} | {metrics['true_negatives']} | "
                     f"{metrics['precision']:.3f} | {metrics['recall']:.3f} | {metrics['f1_score']:.3f} |")

    # 最適閾値の分析
    report.append("\n## 最適閾値の分析\n")
    best_f1_threshold = max(results.items(), key=lambda x: x[1]['metrics']['f1_score'])
    best_precision_threshold = max(results.items(), key=lambda x: x[1]['metrics']['precision'])
    best_recall_threshold = max(results.items(), key=lambda x: x[1]['metrics']['recall'])

    report.append(f"- **最高F1スコア**: 閾値 {best_f1_threshold[1]['similarity_threshold']} "
                 f"(F1: {best_f1_threshold[1]['metrics']['f1_score']:.3f})")
    report.append(f"- **最高適合率**: 閾値 {best_precision_threshold[1]['similarity_threshold']} "
                 f"(Precision: {best_precision_threshold[1]['metrics']['precision']:.3f})")
    report.append(f"- **最高再現率**: 閾値 {best_recall_threshold[1]['similarity_threshold']} "
                 f"(Recall: {best_recall_threshold[1]['metrics']['recall']:.3f})")

    # ファイルに保存
    output_path = Path("results") / "similarity_based_evaluation_summary.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    logger.info(f"サマリーレポートを保存: {output_path}")


if __name__ == "__main__":
    evaluate_multiple_thresholds()
