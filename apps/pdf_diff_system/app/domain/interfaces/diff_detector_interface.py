"""
Domain Interfaces - 差分検出器インターフェース
"""
from abc import ABC, abstractmethod
from typing import List

from ..models.diff_result import DiffResult


class DiffDetectorInterface(ABC):
    """差分検出器インターフェース"""
    
    @abstractmethod
    def detect_differences(self, doc1_text: str, doc2_text: str) -> List[DiffResult]:
        """
        差分検出を実行
        
        Args:
            doc1_text: 元文書テキスト
            doc2_text: 比較文書テキスト
            
        Returns:
            検出された差分のリスト
        """
        pass
    
    @abstractmethod
    def measure_performance(self, doc1_text: str, doc2_text: str) -> dict:
        """
        性能測定を実行
        
        Args:
            doc1_text: 元文書テキスト
            doc2_text: 比較文書テキスト
            
        Returns:
            性能メトリクス
        """
        pass