"""
BBox Based Diff Detector - 単語単位の差分検出
"""
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
from ..models import BBoxTextData, DiffResult, ChangeType


class BBoxBasedDiffDetector:
    """BBoxベースの差分検出器（単語単位）"""
    
    def __init__(self,
                 position_threshold: float = 50.0,
                 similarity_threshold: float = 0.8):
        """
        Args:
            position_threshold: 位置の近さを判定する閾値
            similarity_threshold: 文字列の類似度閾値
        """
        self.position_threshold = position_threshold
        self.similarity_threshold = similarity_threshold
    
    def detect_differences(self, 
                          doc1_bbox_list: List[BBoxTextData], 
                          doc2_bbox_list: List[BBoxTextData]) -> List[DiffResult]:
        """
        文書間の差分を検出（単語単位）
        
        Args:
            doc1_bbox_list: 文書1のbbox_text_dataリスト
            doc2_bbox_list: 文書2のbbox_text_dataリスト
            
        Returns:
            差分結果のリスト
        """
        differences = []
        
        # ページごとに処理
        doc1_pages = self._group_by_page(doc1_bbox_list)
        doc2_pages = self._group_by_page(doc2_bbox_list)
        
        all_pages = set(doc1_pages.keys()) | set(doc2_pages.keys())
        
        for page in sorted(all_pages):
            page1_data = doc1_pages.get(page, [])
            page2_data = doc2_pages.get(page, [])
            
            # ページ内の差分を検出
            page_diffs = self._detect_page_differences(page1_data, page2_data)
            differences.extend(page_diffs)
        
        return differences
    
    def _group_by_page(self, bbox_list: List[BBoxTextData]) -> Dict[int, List[BBoxTextData]]:
        """ページごとにグルーピング"""
        pages = {}
        for bbox_data in bbox_list:
            page = bbox_data['page']
            if page not in pages:
                pages[page] = []
            pages[page].append(bbox_data)
        return pages
    
    def _detect_page_differences(self, 
                               page1_data: List[BBoxTextData], 
                               page2_data: List[BBoxTextData]) -> List[DiffResult]:
        """
        1ページ内の差分を検出
        
        Args:
            page1_data: ページ1のbbox_text_data
            page2_data: ページ2のbbox_text_data
            
        Returns:
            差分結果のリスト
        """
        differences = []
        
        # マッチング済みのインデックスを記録
        matched_indices1 = set()
        matched_indices2 = set()
        
        # 1. 位置と内容が近い単語をマッチング（修正の検出）
        for i, bbox1 in enumerate(page1_data):
            if i in matched_indices1:
                continue
                
            best_match = None
            best_score = 0
            best_j = -1
            
            for j, bbox2 in enumerate(page2_data):
                if j in matched_indices2:
                    continue
                
                # 位置の近さと文字列の類似度を計算
                score = self._calculate_match_score(bbox1, bbox2)
                
                if score > best_score and score > self.similarity_threshold:
                    best_match = bbox2
                    best_score = score
                    best_j = j
            
            if best_match:
                # マッチが見つかった場合
                matched_indices1.add(i)
                matched_indices2.add(best_j)
                
                # テキストが異なる場合は修正として記録
                if bbox1['text'] != best_match['text']:
                    diff = DiffResult(
                        change_type=ChangeType.MODIFICATION,
                        original_bbox=bbox1,
                        modified_bbox=best_match,
                        page=bbox1['page'],
                        confidence=best_score
                    )
                    differences.append(diff)
        
        # 2. マッチしなかった要素を削除・追加として記録
        for i, bbox1 in enumerate(page1_data):
            if i not in matched_indices1:
                # 削除
                diff = DiffResult(
                    change_type=ChangeType.DELETION,
                    original_bbox=bbox1,
                    modified_bbox=None,
                    page=bbox1['page'],
                    confidence=1.0
                )
                differences.append(diff)
        
        for j, bbox2 in enumerate(page2_data):
            if j not in matched_indices2:
                # 追加
                diff = DiffResult(
                    change_type=ChangeType.ADDITION,
                    original_bbox=None,
                    modified_bbox=bbox2,
                    page=bbox2['page'],
                    confidence=1.0
                )
                differences.append(diff)
        
        return differences
    
    def _calculate_match_score(self, bbox1: BBoxTextData, bbox2: BBoxTextData) -> float:
        """
        2つのbboxのマッチングスコアを計算
        
        Args:
            bbox1: 1つ目のbbox
            bbox2: 2つ目のbbox
            
        Returns:
            マッチングスコア (0.0 - 1.0)
        """
        # 位置の距離を計算
        x1, y1 = bbox1['bbox'][0], bbox1['bbox'][1]
        x2, y2 = bbox2['bbox'][0], bbox2['bbox'][1]
        
        distance = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        
        # 距離が閾値を超える場合はマッチしない
        if distance > self.position_threshold:
            return 0.0
        
        # 位置スコア（距離が近いほど高い）
        position_score = 1.0 - (distance / self.position_threshold)
        
        # テキストの類似度
        text_similarity = SequenceMatcher(None, bbox1['text'], bbox2['text']).ratio()
        
        # 総合スコア（位置と文字列の重み付け平均）
        total_score = position_score * 0.3 + text_similarity * 0.7
        
        return total_score
    
    def get_diff_summary(self, differences: List[DiffResult]) -> Dict[str, int]:
        """
        差分の要約を生成
        
        Args:
            differences: 差分結果のリスト
            
        Returns:
            変更タイプごとの件数
        """
        summary = {
            'additions': 0,
            'deletions': 0,
            'modifications': 0,
            'total': len(differences)
        }
        
        for diff in differences:
            if diff.change_type == ChangeType.ADDITION:
                summary['additions'] += 1
            elif diff.change_type == ChangeType.DELETION:
                summary['deletions'] += 1
            elif diff.change_type == ChangeType.MODIFICATION:
                summary['modifications'] += 1
        
        return summary