"""
Evaluation framework for annotation-based testing
PDF difference detection algorithm comparison with real data
"""

from .comparison_evaluator import (
    ComparisonEvaluator,
    PerformanceMetrics,
    ABTestResult,
    GroundTruthDiff,
    TestCase
)
from .annotation_loader import AnnotationDataLoader, AnnotationDiff

__all__ = [
    "ComparisonEvaluator",
    "PerformanceMetrics", 
    "ABTestResult",
    "GroundTruthDiff",
    "TestCase",
    "AnnotationDataLoader",
    "AnnotationDiff"
]