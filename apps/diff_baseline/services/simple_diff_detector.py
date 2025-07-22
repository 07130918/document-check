"""
Simple Diff Detector - 差分タイプを分けない単純な差分検出
"""
from typing import List, Dict, Set
from difflib import SequenceMatcher
from ..models import BBoxTextData, DiffResult, ChangeType


class SimpleDiffDetector:
    """差分タイプを分けない単純な差分検出器"""
    
    def __init__(self, similarity_threshold: float = 0.9):
        """
        Args:
            similarity_threshold: テキスト類似度の閾値
        """
        self.similarity_threshold = similarity_threshold
    
    def detect_differences(self, 
                          doc1_bbox_list: List[BBoxTextData], 
                          doc2_bbox_list: List[BBoxTextData]) -> List[DiffResult]:
        """
        単純な差分検出（タイプ分けなし）- 2024年文書の差分のみカウント
        
        Args:
            doc1_bbox_list: 文書1のbbox_text_dataリスト
            doc2_bbox_list: 文書2のbbox_text_dataリスト
            
        Returns:
            差分結果のリスト（すべてDIFFERENCEタイプ）
        """
        # テキストの配列を作成
        texts1 = [bbox['text'] for bbox in doc1_bbox_list]
        texts2 = [bbox['text'] for bbox in doc2_bbox_list]
        
        # シーケンスマッチャーで差分を検出
        matcher = SequenceMatcher(None, texts1, texts2)
        differences = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                # doc2（2024年）側の差分のみを記録
                for j in range(j1, j2):
                    # 対応するdoc1の要素を探す（あれば）
                    doc1_item = None
                    if i1 < i2:
                        # 対応する位置の要素を取得
                        relative_pos = j - j1
                        if i1 + relative_pos < i2:
                            doc1_item = doc1_bbox_list[i1 + relative_pos]
                    
                    diff = DiffResult(
                        change_type=ChangeType.DIFFERENCE,
                        original_bbox=doc1_item,  # 対応する要素があれば設定
                        modified_bbox=doc2_bbox_list[j],
                        page=doc2_bbox_list[j]['page'],
                        confidence=1.0
                    )
                    differences.append(diff)
        
        return differences
    
    def get_diff_summary(self, differences: List[DiffResult]) -> Dict[str, int]:
        """
        差分のサマリーを生成
        
        Args:
            differences: 差分結果のリスト
            
        Returns:
            差分のサマリー
        """
        return {
            'total': len(differences),
            'differences': len(differences)  # すべて同じタイプ
        }