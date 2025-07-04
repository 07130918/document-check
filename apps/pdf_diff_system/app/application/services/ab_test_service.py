"""
Application Service - A/Bテストサービス (アノテーション対応版)
"""
from typing import List
from pathlib import Path

from ...domain.interfaces.diff_detector_interface import DiffDetectorInterface
from ...infrastructure.evaluation.comparison_evaluator import (
    ComparisonEvaluator,
    ABTestResult
)


class ABTestService:
    """A/Bテストアプリケーションサービス (アノテーションデータ用)"""
    
    def __init__(self, baseline_detector: DiffDetectorInterface):
        self.baseline_detector = baseline_detector
        self.evaluator = ComparisonEvaluator(baseline_detector)
    
    def execute_ab_test(self, test_cases: List, 
                       improved_detector: DiffDetectorInterface = None) -> ABTestResult:
        """A/Bテスト実行"""
        return self.evaluator.run_ab_test(test_cases, improved_detector)
    
    def save_results(self, result: ABTestResult, output_path: Path):
        """結果保存"""
        self.evaluator.save_results(result, output_path)
    
    def generate_report(self, result: ABTestResult) -> str:
        """レポート生成"""
        return self.evaluator.generate_report(result)