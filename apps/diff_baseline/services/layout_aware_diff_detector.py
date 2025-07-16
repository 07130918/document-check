"""
Layout-aware Diff Detector - レイアウト変更に強い差分検出
"""
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
from difflib import SequenceMatcher
from ..models import BBoxTextData, DiffResult, ChangeType


class LayoutAwareDiffDetector:
    """レイアウト変更に強い差分検出器"""
    
    def __init__(self,
                 text_similarity_threshold: float = 0.9,
                 context_window: int = 5):
        """
        Args:
            text_similarity_threshold: テキスト類似度の閾値
            context_window: 文脈を考慮する単語数
        """
        self.text_similarity_threshold = text_similarity_threshold
        self.context_window = context_window
    
    def detect_differences(self, 
                          doc1_bbox_list: List[BBoxTextData], 
                          doc2_bbox_list: List[BBoxTextData]) -> List[DiffResult]:
        """
        レイアウト変更を考慮した差分検出
        
        Args:
            doc1_bbox_list: 文書1のbbox_text_dataリスト
            doc2_bbox_list: 文書2のbbox_text_dataリスト
            
        Returns:
            差分結果のリスト
        """
        # 1. テキストベースでのマッチング
        text_matches = self._find_text_matches(doc1_bbox_list, doc2_bbox_list)
        
        # 2. コンテキストを考慮したマッチングの精緻化
        refined_matches = self._refine_matches_with_context(
            doc1_bbox_list, doc2_bbox_list, text_matches
        )
        
        # 3. 差分の生成
        differences = self._generate_differences(
            doc1_bbox_list, doc2_bbox_list, refined_matches
        )
        
        return differences
    
    def _find_text_matches(self, 
                          doc1: List[BBoxTextData], 
                          doc2: List[BBoxTextData]) -> Dict[int, int]:
        """
        テキスト内容に基づくマッチングを見つける
        
        Returns:
            {doc1_index: doc2_index}のマッピング
        """
        matches = {}
        used_indices2 = set()
        
        # テキストをキーとしたインデックスマップを作成
        text_map2 = defaultdict(list)
        for j, bbox2 in enumerate(doc2):
            text_map2[bbox2['text']].append(j)
        
        # 完全一致を優先的に処理
        for i, bbox1 in enumerate(doc1):
            text1 = bbox1['text']
            if text1 in text_map2:
                candidates = [j for j in text_map2[text1] if j not in used_indices2]
                if candidates:
                    # 最も近いページのものを選択
                    best_j = min(candidates, 
                               key=lambda j: abs(doc2[j]['page'] - bbox1['page']))
                    matches[i] = best_j
                    used_indices2.add(best_j)
        
        # 部分一致を処理
        unmatched1 = [i for i in range(len(doc1)) if i not in matches]
        unmatched2 = [j for j in range(len(doc2)) if j not in used_indices2]
        
        for i in unmatched1:
            bbox1 = doc1[i]
            best_match = None
            best_score = 0
            
            for j in unmatched2:
                bbox2 = doc2[j]
                
                # テキストの類似度を計算
                similarity = SequenceMatcher(None, bbox1['text'], bbox2['text']).ratio()
                
                if similarity > self.text_similarity_threshold and similarity > best_score:
                    best_match = j
                    best_score = similarity
            
            if best_match is not None:
                matches[i] = best_match
                unmatched2.remove(best_match)
        
        return matches
    
    def _refine_matches_with_context(self,
                                   doc1: List[BBoxTextData],
                                   doc2: List[BBoxTextData],
                                   initial_matches: Dict[int, int]) -> Dict[int, int]:
        """
        コンテキストを考慮してマッチングを精緻化
        """
        refined_matches = initial_matches.copy()
        
        # 文脈スコアを計算
        for i, j in list(initial_matches.items()):
            context_score = self._calculate_context_score(
                doc1, doc2, i, j, initial_matches
            )
            
            # 文脈スコアが低い場合は、より良いマッチを探す
            if context_score < 0.5:
                better_match = self._find_better_match_with_context(
                    doc1, doc2, i, initial_matches
                )
                if better_match is not None and better_match != j:
                    refined_matches[i] = better_match
        
        return refined_matches
    
    def _calculate_context_score(self,
                               doc1: List[BBoxTextData],
                               doc2: List[BBoxTextData],
                               idx1: int,
                               idx2: int,
                               matches: Dict[int, int]) -> float:
        """
        周辺の単語のマッチング状況から文脈スコアを計算
        """
        score = 0
        count = 0
        
        # 前後の単語を確認
        for offset in range(-self.context_window, self.context_window + 1):
            if offset == 0:
                continue
            
            neighbor1_idx = idx1 + offset
            if 0 <= neighbor1_idx < len(doc1) and neighbor1_idx in matches:
                neighbor2_idx = matches[neighbor1_idx]
                expected_neighbor2_idx = idx2 + offset
                
                # 期待される位置に近いほど高スコア
                if neighbor2_idx == expected_neighbor2_idx:
                    score += 1.0
                elif abs(neighbor2_idx - expected_neighbor2_idx) <= 2:
                    score += 0.5
                
                count += 1
        
        return score / count if count > 0 else 0.5
    
    def _find_better_match_with_context(self,
                                      doc1: List[BBoxTextData],
                                      doc2: List[BBoxTextData],
                                      idx1: int,
                                      matches: Dict[int, int]) -> Optional[int]:
        """
        文脈を考慮してより良いマッチを探す
        """
        text1 = doc1[idx1]['text']
        best_idx2 = None
        best_score = 0
        
        # 同じテキストを持つ全ての候補を評価
        for idx2, bbox2 in enumerate(doc2):
            if bbox2['text'] == text1:
                context_score = self._calculate_context_score(
                    doc1, doc2, idx1, idx2, matches
                )
                if context_score > best_score:
                    best_score = context_score
                    best_idx2 = idx2
        
        return best_idx2
    
    def _generate_differences(self,
                            doc1: List[BBoxTextData],
                            doc2: List[BBoxTextData],
                            matches: Dict[int, int]) -> List[DiffResult]:
        """
        マッチング結果から差分を生成
        """
        differences = []
        matched_indices2 = set(matches.values())
        
        # 削除された要素
        for i, bbox1 in enumerate(doc1):
            if i not in matches:
                diff = DiffResult(
                    change_type=ChangeType.DELETION,
                    original_bbox=bbox1,
                    modified_bbox=None,
                    page=bbox1['page'],
                    confidence=1.0
                )
                differences.append(diff)
        
        # 追加された要素
        for j, bbox2 in enumerate(doc2):
            if j not in matched_indices2:
                diff = DiffResult(
                    change_type=ChangeType.ADDITION,
                    original_bbox=None,
                    modified_bbox=bbox2,
                    page=bbox2['page'],
                    confidence=1.0
                )
                differences.append(diff)
        
        # 位置が変更された要素（レイアウト変更）は追加しない
        # テキストが同じでマッチしている場合は差分として扱わない
        
        return differences
    
    def get_layout_changes(self,
                          doc1: List[BBoxTextData],
                          doc2: List[BBoxTextData],
                          matches: Dict[int, int]) -> List[Dict]:
        """
        レイアウト変更の検出（位置が大きく変わった要素）
        
        Returns:
            レイアウト変更情報のリスト
        """
        layout_changes = []
        
        for i, j in matches.items():
            bbox1 = doc1[i]
            bbox2 = doc2[j]
            
            # 位置の変化を計算
            dx = abs(bbox2['bbox'][0] - bbox1['bbox'][0])
            dy = abs(bbox2['bbox'][1] - bbox1['bbox'][1])
            
            # ページが変わった、または位置が大きく変わった場合
            if bbox1['page'] != bbox2['page'] or dx > 50 or dy > 50:
                layout_changes.append({
                    'text': bbox1['text'],
                    'old_position': {
                        'page': bbox1['page'],
                        'x': bbox1['bbox'][0],
                        'y': bbox1['bbox'][1]
                    },
                    'new_position': {
                        'page': bbox2['page'],
                        'x': bbox2['bbox'][0],
                        'y': bbox2['bbox'][1]
                    },
                    'distance': (dx**2 + dy**2)**0.5
                })
        
        return layout_changes
    
    def get_diff_summary(self, differences: List[DiffResult]) -> Dict[str, int]:
        """
        差分のサマリーを生成
        
        Args:
            differences: 差分結果のリスト
            
        Returns:
            差分のサマリー
        """
        summary = {
            'total': len(differences),
            'additions': 0,
            'deletions': 0,
            'modifications': 0
        }
        
        for diff in differences:
            if diff.change_type.value == 'addition':
                summary['additions'] += 1
            elif diff.change_type.value == 'deletion':
                summary['deletions'] += 1
            elif diff.change_type.value == 'modification':
                summary['modifications'] += 1
        
        return summary