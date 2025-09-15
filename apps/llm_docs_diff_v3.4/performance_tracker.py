# coding: utf-8
"""
Performance tracker for measuring execution time of each processing step
"""

import time
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
from datetime import datetime
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Performance tracking class for measuring execution time"""
    
    def __init__(self):
        """Initialize the performance tracker"""
        self.timings: Dict[str, List[float]] = {}
        self.current_stack: List[Dict[str, Any]] = []
        self.detailed_timings: List[Dict[str, Any]] = []
        
    def start_timing(self, operation_name: str, details: Optional[Dict[str, Any]] = None) -> float:
        """Start timing an operation
        
        Args:
            operation_name: Name of the operation
            details: Optional additional details about the operation
            
        Returns:
            Start time
        """
        start_time = time.time()
        
        # スタックに追加
        self.current_stack.append({
            'name': operation_name,
            'start_time': start_time,
            'details': details or {}
        })
        
        logger.debug(f"開始: {operation_name}")
        return start_time
    
    def end_timing(self, operation_name: str) -> float:
        """End timing an operation
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Elapsed time in seconds
        """
        end_time = time.time()
        
        # スタックから対応する開始時刻を取得
        if not self.current_stack:
            logger.warning(f"タイミングスタックが空です: {operation_name}")
            return 0.0
        
        # スタックから最後の要素を取得
        timing_info = self.current_stack.pop()
        
        # 名前の確認
        if timing_info['name'] != operation_name:
            logger.warning(f"タイミング名の不一致: 期待={timing_info['name']}, 実際={operation_name}")
        
        elapsed_time = end_time - timing_info['start_time']
        
        # 記録を保存
        if operation_name not in self.timings:
            self.timings[operation_name] = []
        self.timings[operation_name].append(elapsed_time)
        
        # 詳細記録を保存
        self.detailed_timings.append({
            'operation': operation_name,
            'start_time': datetime.fromtimestamp(timing_info['start_time']).isoformat(),
            'end_time': datetime.fromtimestamp(end_time).isoformat(),
            'elapsed_seconds': elapsed_time,
            'details': timing_info.get('details', {})
        })
        
        logger.debug(f"完了: {operation_name} ({elapsed_time:.3f}秒)")
        return elapsed_time
    
    def measure(self, operation_name: str):
        """Context manager for measuring operation time
        
        Usage:
            with tracker.measure("operation_name"):
                # code to measure
        """
        class TimingContext:
            def __init__(self, tracker, name):
                self.tracker = tracker
                self.name = name
                
            def __enter__(self):
                self.tracker.start_timing(self.name)
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.tracker.end_timing(self.name)
                return False
        
        return TimingContext(self, operation_name)
    
    def time_function(self, operation_name: Optional[str] = None):
        """Decorator for measuring function execution time
        
        Args:
            operation_name: Optional custom operation name
            
        Usage:
            @tracker.time_function()
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                name = operation_name or func.__name__
                self.start_timing(name)
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    self.end_timing(name)
            return wrapper
        return decorator
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all timings
        
        Returns:
            Dictionary containing timing statistics
        """
        summary = {}
        
        for operation, times in self.timings.items():
            if times:
                summary[operation] = {
                    'count': len(times),
                    'total_seconds': sum(times),
                    'average_seconds': sum(times) / len(times),
                    'min_seconds': min(times),
                    'max_seconds': max(times)
                }
        
        # 合計時間でソート
        sorted_summary = dict(sorted(
            summary.items(),
            key=lambda x: x[1]['total_seconds'],
            reverse=True
        ))
        
        return sorted_summary
    
    def print_summary(self):
        """Print timing summary to console"""
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print("処理時間サマリー")
        print("="*80)
        
        total_time = sum(stat['total_seconds'] for stat in summary.values())
        
        for operation, stats in summary.items():
            percentage = (stats['total_seconds'] / total_time * 100) if total_time > 0 else 0
            print(f"\n{operation}:")
            print(f"  実行回数: {stats['count']}回")
            print(f"  合計時間: {stats['total_seconds']:.3f}秒 ({percentage:.1f}%)")
            print(f"  平均時間: {stats['average_seconds']:.3f}秒")
            print(f"  最小時間: {stats['min_seconds']:.3f}秒")
            print(f"  最大時間: {stats['max_seconds']:.3f}秒")
        
        print(f"\n全体処理時間: {total_time:.3f}秒")
        print("="*80)
    
    def save_to_file(self, output_path: Optional[Path] = None):
        """Save timing data to file
        
        Args:
            output_path: Optional output file path
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"performance_report_{timestamp}.json")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': self.get_summary(),
            'detailed_timings': self.detailed_timings
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"パフォーマンスレポート保存: {output_path}")
        return output_path
    
    def get_bottlenecks(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """Get the top N bottleneck operations
        
        Args:
            top_n: Number of top bottlenecks to return
            
        Returns:
            List of bottleneck operations
        """
        summary = self.get_summary()
        
        bottlenecks = []
        for operation, stats in list(summary.items())[:top_n]:
            bottlenecks.append({
                'operation': operation,
                'total_seconds': stats['total_seconds'],
                'count': stats['count'],
                'average_seconds': stats['average_seconds']
            })
        
        return bottlenecks
    
    def reset(self):
        """Reset all timing data"""
        self.timings.clear()
        self.current_stack.clear()
        self.detailed_timings.clear()
        logger.debug("パフォーマンストラッカーをリセットしました")


# グローバルトラッカーインスタンス
global_tracker = PerformanceTracker()


def get_global_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance
    
    Returns:
        Global PerformanceTracker instance
    """
    return global_tracker