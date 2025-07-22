"""
差分検出器 v3 簡易版 - 差分タイプを統一
すべての差分を単一タイプとして扱う
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import difflib
from ..models.bbox_models import DiffResult, ChangeType
import logging

logger = logging.getLogger(__name__)


class SimpleChangeType(Enum):
    """変更タイプ（簡易版）"""
    DIFFERENCE = "difference"  # すべての差分を統一


@dataclass
class SimpleDiffResult:
    """差分結果（簡易版）"""
    change_type: SimpleChangeType
    page_num: int
    doc1_bbox: Optional[Dict[str, Any]] = None
    doc2_bbox: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = {
            'change_type': self.change_type.value,
            'page': self.page_num,
            'confidence': self.confidence
        }
        
        if self.doc1_bbox:
            result['doc1_text'] = self.doc1_bbox.get('text', '')
            result['doc1_bbox'] = self.doc1_bbox.get('bbox', [])
        
        if self.doc2_bbox:
            result['doc2_text'] = self.doc2_bbox.get('text', '')
            result['doc2_bbox'] = self.doc2_bbox.get('bbox', [])
        
        return result


class SimpleDiffDetectorV3:
    """内容ベースの差分検出器（簡易版）"""
    
    def __init__(self, 
                 similarity_threshold: float = 0.8,
                 max_page: Optional[int] = None):
        """
        Args:
            similarity_threshold: 類似度の閾値
            max_page: 処理する最大ページ番号（0-indexed）
        """
        self.similarity_threshold = similarity_threshold
        self.max_page = max_page
    
    def detect_differences(self,
                          doc1_data: List[Dict[str, Any]],
                          doc2_data: List[Dict[str, Any]]) -> List[SimpleDiffResult]:
        """
        差分を検出（すべて同じタイプとして）
        2024年文書（文書2）の差分のみをカウント
        
        Args:
            doc1_data: 文書1のデータ
            doc2_data: 文書2のデータ
            
        Returns:
            差分結果のリスト
        """
        # ページ数制限
        if self.max_page is not None:
            doc1_data = [item for item in doc1_data if item.get('page', 0) <= self.max_page]
            doc2_data = [item for item in doc2_data if item.get('page', 0) <= self.max_page]
        
        # テキストのリストを作成
        texts1 = [item.get('text', '') for item in doc1_data]
        texts2 = [item.get('text', '') for item in doc2_data]
        
        # difflibで差分を検出
        matcher = difflib.SequenceMatcher(None, texts1, texts2)
        differences = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                # 2024年文書（doc2）側の差分のみを記録
                for j in range(j1, j2):
                    # 対応する doc1 の要素を探す（あれば）
                    doc1_item = None
                    if i1 < i2:
                        # 対応する位置の要素を取得
                        relative_pos = j - j1
                        if i1 + relative_pos < i2:
                            doc1_item = doc1_data[i1 + relative_pos]
                    
                    diff = SimpleDiffResult(
                        change_type=SimpleChangeType.DIFFERENCE,
                        page_num=doc2_data[j].get('page', 0),
                        doc1_bbox=doc1_item,  # 対応する要素があれば設定
                        doc2_bbox=doc2_data[j],
                        confidence=1.0
                    )
                    differences.append(diff)
        
        return differences
    
    def get_summary(self, differences: List[SimpleDiffResult]) -> Dict[str, Any]:
        """
        差分のサマリーを生成
        
        Args:
            differences: 差分結果のリスト
            
        Returns:
            サマリー情報
        """
        total = len(differences)
        by_page = {}
        
        for diff in differences:
            page = diff.page_num
            if page not in by_page:
                by_page[page] = 0
            by_page[page] += 1
        
        return {
            'total_differences': total,
            'by_page': by_page,
            'difference_type': 'unified'  # 統一タイプであることを明示
        }