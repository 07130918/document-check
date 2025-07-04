"""
A/B Testing Framework for PDF Difference Detection
Comparison evaluator for baseline vs improved algorithms
"""
import json
import time
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import statistics
import csv

# デバッグログ設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# from ..baseline import SequenceMatcherDiffDetector, DiffResult


@dataclass
class GroundTruthDiff:
    """Ground truth difference annotation"""
    change_type: str  # "addition", "deletion", "modification"
    original_text: Optional[str]
    modified_text: Optional[str]
    sentence_id: int  # 文章単位のID（アノテーション対応）
    importance: str = "normal"  # "high", "normal", "low"


@dataclass
class TestCase:
    """Single test case for A/B testing"""
    case_id: str
    name: str
    difficulty: str  # "easy", "medium", "hard"
    doc1_text: str
    doc2_text: str
    ground_truth: List[GroundTruthDiff]
    description: str = ""


@dataclass
class PerformanceMetrics:
    """Performance evaluation metrics"""
    # 混同行列指標
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    
    # 計算指標
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    
    # 性能指標
    processing_time: float
    memory_usage_mb: float
    
    # その他
    total_differences: int
    detected_differences: int
    method_name: str


@dataclass
class ABTestResult:
    """A/B test comparison result"""
    baseline_metrics: PerformanceMetrics
    improved_metrics: PerformanceMetrics
    statistical_significance: Dict[str, Any]
    improvement_summary: Dict[str, float]
    test_cases_count: int
    timestamp: str


class StatisticalAnalyzer:
    """Statistical significance testing"""
    
    def perform_t_test(self, baseline_scores: List[float], 
                      improved_scores: List[float]) -> Dict[str, Any]:
        """Perform t-test for statistical significance"""
        try:
            from scipy import stats
            
            # t検定実行
            t_stat, p_value = stats.ttest_rel(improved_scores, baseline_scores)
            
            # 効果量計算（Cohen's d）
            pooled_std = statistics.stdev(baseline_scores + improved_scores)
            cohens_d = (statistics.mean(improved_scores) - statistics.mean(baseline_scores)) / pooled_std
            
            return {
                "t_statistic": float(t_stat),
                "p_value": float(p_value),
                "cohens_d": float(cohens_d),
                "is_significant": p_value < 0.05,
                "effect_size": "large" if abs(cohens_d) >= 0.8 else "medium" if abs(cohens_d) >= 0.5 else "small"
            }
        except ImportError:
            # scipy が利用できない場合のフォールバック
            return self._simple_statistical_test(baseline_scores, improved_scores)
    
    def _simple_statistical_test(self, baseline_scores: List[float], 
                                improved_scores: List[float]) -> Dict[str, Any]:
        """Simple statistical analysis without scipy"""
        baseline_mean = statistics.mean(baseline_scores)
        improved_mean = statistics.mean(improved_scores)
        
        improvement_rate = (improved_mean - baseline_mean) / baseline_mean if baseline_mean > 0 else 0
        
        return {
            "baseline_mean": baseline_mean,
            "improved_mean": improved_mean,
            "improvement_rate": improvement_rate,
            "is_significant": improvement_rate > 0.1,  # 10%以上の改善を有意とする
            "effect_size": "large" if improvement_rate > 0.3 else "medium" if improvement_rate > 0.1 else "small"
        }


class ComparisonEvaluator:
    """
    A/B Testing evaluation framework
    Compares baseline vs improved algorithms
    """
    
    def __init__(self, baseline_detector=None):
        self.baseline_detector = baseline_detector
        self.statistical_analyzer = StatisticalAnalyzer()
        self.test_results = []
    
    def run_ab_test(self, test_cases: List[TestCase], 
                    improved_detector=None) -> ABTestResult:
        """
        Run A/B test comparing baseline vs improved algorithm
        
        Args:
            test_cases: List of test cases to evaluate
            improved_detector: Improved algorithm detector (if available)
            
        Returns:
            A/B test results with statistical analysis
        """
        print(f"A/Bテスト開始: {len(test_cases)}ケースで評価")
        
        baseline_results = []
        improved_results = []
        
        for i, test_case in enumerate(test_cases):
            # Handle both dict and object formats
            case_name = test_case.get('name') if isinstance(test_case, dict) else test_case.name
            print(f"テストケース {i+1}/{len(test_cases)}: {case_name}")
            
            # ベースライン評価
            baseline_metrics = self._evaluate_detector(
                self.baseline_detector, test_case, "baseline"
            )
            baseline_results.append(baseline_metrics)
            
            # 改良版評価（利用可能な場合）
            if improved_detector:
                improved_metrics = self._evaluate_detector(
                    improved_detector, test_case, "improved"
                )
                improved_results.append(improved_metrics)
            else:
                # 改良版が未実装の場合、ベースラインと同じ結果を使用
                improved_results.append(baseline_metrics)
        
        # 統計的有意性分析
        statistical_significance = self._analyze_statistical_significance(
            baseline_results, improved_results
        )
        
        # 改善サマリー計算
        improvement_summary = self._calculate_improvement_summary(
            baseline_results, improved_results
        )
        
        # 結果生成
        result = ABTestResult(
            baseline_metrics=self._aggregate_metrics(baseline_results, "baseline"),
            improved_metrics=self._aggregate_metrics(improved_results, "improved"),
            statistical_significance=statistical_significance,
            improvement_summary=improvement_summary,
            test_cases_count=len(test_cases),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        return result
    
    def _evaluate_detector(self, detector, test_case, 
                          method_name: str):
        """Evaluate single detector on test case"""
        start_time = time.time()
        
        # Handle both dict and object formats
        if isinstance(test_case, dict):
            doc1_text = test_case['doc1_text']
            doc2_text = test_case['doc2_text']
            ground_truth = test_case['ground_truth']
        else:
            doc1_text = test_case.doc1_text
            doc2_text = test_case.doc2_text
            ground_truth = test_case.ground_truth
        
        # 差分検出実行
        detected_diffs = detector.detect_differences(doc1_text, doc2_text)
        
        end_time = time.time()
        
        # 混同行列計算
        confusion_matrix = self._calculate_confusion_matrix(
            detected_diffs, ground_truth
        )
        
        # メトリクス計算
        metrics = self._calculate_performance_metrics(
            confusion_matrix,
            processing_time=end_time - start_time,
            detected_count=len(detected_diffs),
            total_count=len(ground_truth),
            method_name=method_name
        )
        
        return metrics
    
    def _calculate_confusion_matrix(self, detected_diffs, ground_truth) -> Dict[str, int]:
        """Calculate confusion matrix for difference detection"""
        logger.debug(f"=== 混同行列計算開始 ===")
        logger.debug(f"検出された差分数: {len(detected_diffs)}")
        logger.debug(f"正解データ数: {len(ground_truth)}")
        
        tp = fp = tn = fn = 0
        
        # 検出された差分をセットに変換
        detected_texts = set()
        for i, diff in enumerate(detected_diffs):
            logger.debug(f"検出差分 {i+1}: {diff}")
            if hasattr(diff, 'original_text') and hasattr(diff, 'modified_text'):
                if diff.original_text and diff.modified_text:
                    detected_texts.add((diff.original_text.strip(), diff.modified_text.strip()))
            else:
                logger.warning(f"検出差分にoriginal_text/modified_textが存在しません: {diff}")
        
        # Ground truthをセットに変換  
        ground_truth_texts = set()
        for i, gt in enumerate(ground_truth):
            logger.debug(f"正解データ {i+1}: {gt}")
            # dict形式の場合の処理
            if isinstance(gt, dict):
                original = gt.get('original_text', '')
                modified = gt.get('modified_text', '')
                if original and modified:
                    # 句点を統一して正規化
                    orig_norm = self._normalize_for_comparison(original)
                    mod_norm = self._normalize_for_comparison(modified)
                    ground_truth_texts.add((orig_norm, mod_norm))
            # オブジェクト形式の場合の処理  
            elif hasattr(gt, 'original_text') and hasattr(gt, 'modified_text'):
                if gt.original_text and gt.modified_text:
                    orig_norm = self._normalize_for_comparison(gt.original_text)
                    mod_norm = self._normalize_for_comparison(gt.modified_text)
                    ground_truth_texts.add((orig_norm, mod_norm))
            else:
                logger.warning(f"正解データの形式が不正です: {gt}")
        
        logger.debug(f"検出テキストペア: {detected_texts}")
        logger.debug(f"正解テキストペア: {ground_truth_texts}")
        
        # True Positives: 正しく検出された差分
        tp = len(detected_texts.intersection(ground_truth_texts))
        
        # False Positives: 誤って検出された差分
        fp = len(detected_texts - ground_truth_texts)
        
        # False Negatives: 検出されなかった差分
        fn = len(ground_truth_texts - detected_texts)
        
        logger.debug(f"TP: {tp}, FP: {fp}, FN: {fn}")
        logger.debug(f"交集合: {detected_texts.intersection(ground_truth_texts)}")
        logger.debug(f"誤検出: {detected_texts - ground_truth_texts}")
        logger.debug(f"見逃し: {ground_truth_texts - detected_texts}")
        logger.debug(f"=== 混同行列計算終了 ===\n")
        
        # True Negatives: 差分なしを正しく判定（簡略化）
        tn = max(0, len(ground_truth) - tp - fp - fn)
        
        return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}
    
    def _normalize_for_comparison(self, text: str) -> str:
        """比較用のテキスト正規化"""
        if not text:
            return ""
        # スペースと句点を除去して正規化
        normalized = text.strip()
        # 最後の句点を除去
        normalized = normalized.rstrip('。．.')
        return normalized
    
    def _calculate_performance_metrics(self, confusion_matrix: Dict[str, int],
                                     processing_time: float, detected_count: int,
                                     total_count: int, method_name: str) -> PerformanceMetrics:
        """Calculate performance metrics from confusion matrix"""
        tp = confusion_matrix["tp"]
        fp = confusion_matrix["fp"]
        tn = confusion_matrix["tn"]
        fn = confusion_matrix["fn"]
        
        # 精度指標計算
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0.0
        
        return PerformanceMetrics(
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            processing_time=processing_time,
            memory_usage_mb=0.0,  # 実装時に実際の値を設定
            total_differences=total_count,
            detected_differences=detected_count,
            method_name=method_name
        )
    
    def _analyze_statistical_significance(self, baseline_results, improved_results) -> Dict[str, Any]:
        """Analyze statistical significance of improvements"""
        baseline_recalls = [m.recall for m in baseline_results]
        improved_recalls = [m.recall for m in improved_results]
        
        baseline_precisions = [m.precision for m in baseline_results]
        improved_precisions = [m.precision for m in improved_results]
        
        baseline_times = [m.processing_time for m in baseline_results]
        improved_times = [m.processing_time for m in improved_results]
        
        return {
            "recall": self.statistical_analyzer.perform_t_test(baseline_recalls, improved_recalls),
            "precision": self.statistical_analyzer.perform_t_test(baseline_precisions, improved_precisions),
            "processing_time": self.statistical_analyzer.perform_t_test(baseline_times, improved_times)
        }
    
    def _calculate_improvement_summary(self, baseline_results, improved_results) -> Dict[str, float]:
        """Calculate improvement summary statistics"""
        baseline_avg_recall = statistics.mean([m.recall for m in baseline_results])
        improved_avg_recall = statistics.mean([m.recall for m in improved_results])
        
        baseline_avg_precision = statistics.mean([m.precision for m in baseline_results])
        improved_avg_precision = statistics.mean([m.precision for m in improved_results])
        
        baseline_avg_time = statistics.mean([m.processing_time for m in baseline_results])
        improved_avg_time = statistics.mean([m.processing_time for m in improved_results])
        
        return {
            "recall_improvement": (improved_avg_recall - baseline_avg_recall) / baseline_avg_recall if baseline_avg_recall > 0 else 0,
            "precision_improvement": (improved_avg_precision - baseline_avg_precision) / baseline_avg_precision if baseline_avg_precision > 0 else 0,
            "time_improvement": (baseline_avg_time - improved_avg_time) / baseline_avg_time if baseline_avg_time > 0 else 0,
            "baseline_recall": baseline_avg_recall,
            "improved_recall": improved_avg_recall,
            "baseline_precision": baseline_avg_precision,
            "improved_precision": improved_avg_precision
        }
    
    def _aggregate_metrics(self, results, method_name: str):
        """Aggregate metrics across all test cases"""
        if not results:
            return PerformanceMetrics(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, method_name)
        
        total_tp = sum(r.true_positives for r in results)
        total_fp = sum(r.false_positives for r in results)
        total_tn = sum(r.true_negatives for r in results)
        total_fn = sum(r.false_negatives for r in results)
        
        avg_precision = statistics.mean([r.precision for r in results])
        avg_recall = statistics.mean([r.recall for r in results])
        avg_f1 = statistics.mean([r.f1_score for r in results])
        avg_accuracy = statistics.mean([r.accuracy for r in results])
        
        total_time = sum(r.processing_time for r in results)
        avg_memory = statistics.mean([r.memory_usage_mb for r in results])
        
        return PerformanceMetrics(
            true_positives=total_tp,
            false_positives=total_fp,
            true_negatives=total_tn,
            false_negatives=total_fn,
            precision=avg_precision,
            recall=avg_recall,
            f1_score=avg_f1,
            accuracy=avg_accuracy,
            processing_time=total_time,
            memory_usage_mb=avg_memory,
            total_differences=sum(r.total_differences for r in results),
            detected_differences=sum(r.detected_differences for r in results),
            method_name=method_name
        )
    
    def save_results(self, result: ABTestResult, output_path: Path):
        """Save A/B test results to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2)
        
        print(f"A/Bテスト結果を保存: {output_path}")
    
    def generate_report(self, result: ABTestResult) -> str:
        """Generate human-readable A/B test report"""
        report = f"""
# A/Bテスト結果レポート

## 概要
- テストケース数: {result.test_cases_count}
- 実行日時: {result.timestamp}

## 性能比較

### ベースライン (prj-meiji-document-check)
- 真陽性率 (Recall): {result.baseline_metrics.recall:.3f}
- 適合率 (Precision): {result.baseline_metrics.precision:.3f}
- F1スコア: {result.baseline_metrics.f1_score:.3f}
- 処理時間: {result.baseline_metrics.processing_time:.2f}秒

### 改良版
- 真陽性率 (Recall): {result.improved_metrics.recall:.3f}
- 適合率 (Precision): {result.improved_metrics.precision:.3f}
- F1スコア: {result.improved_metrics.f1_score:.3f}
- 処理時間: {result.improved_metrics.processing_time:.2f}秒

## 改善サマリー
- 真陽性率改善: {result.improvement_summary['recall_improvement']*100:+.1f}%
- 適合率改善: {result.improvement_summary['precision_improvement']*100:+.1f}%
- 処理時間改善: {result.improvement_summary['time_improvement']*100:+.1f}%

## 統計的有意性
- 真陽性率: p値 = {result.statistical_significance['recall'].get('p_value', 'N/A')}
- 適合率: p値 = {result.statistical_significance['precision'].get('p_value', 'N/A')}
- 処理時間: p値 = {result.statistical_significance['processing_time'].get('p_value', 'N/A')}

## 結論
統計的有意性（p < 0.05）: {'達成' if any(s.get('is_significant', False) for s in result.statistical_significance.values()) else '未達成'}
実用的改善（>10%）: {'達成' if any(abs(v) > 0.1 for k, v in result.improvement_summary.items() if 'improvement' in k) else '未達成'}
"""
        return report