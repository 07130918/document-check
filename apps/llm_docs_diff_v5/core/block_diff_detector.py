"""
ブロックベース差分検出
ブロック単位で文書の差分を検出
"""
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from difflib import SequenceMatcher
import numpy as np

from ..models.block_models import (
    Block, BlockType, DocumentStructure, BlockDifference, BoundingBox
)

logger = logging.getLogger(__name__)


class BlockDiffDetector:
    """ブロックベースの差分検出器"""
    
    def __init__(self,
                 position_weight: float = 0.3,
                 content_weight: float = 0.5,
                 type_weight: float = 0.2,
                 similarity_threshold: float = 0.7,
                 position_tolerance: float = 20.0):
        """
        Args:
            position_weight: 位置の類似度の重み
            content_weight: コンテンツの類似度の重み
            type_weight: ブロックタイプの類似度の重み
            similarity_threshold: ブロックが同一とみなされる類似度の閾値
            position_tolerance: 位置の許容誤差（ピクセル）
        """
        self.position_weight = position_weight
        self.content_weight = content_weight
        self.type_weight = type_weight
        self.similarity_threshold = similarity_threshold
        self.position_tolerance = position_tolerance
    
    def detect_differences(self, 
                          doc1: DocumentStructure, 
                          doc2: DocumentStructure) -> List[BlockDifference]:
        """2つの文書構造の差分を検出"""
        differences = []
        
        # ページごとに処理
        max_pages = max(doc1.pages, doc2.pages)
        
        for page_num in range(max_pages):
            blocks1 = doc1.get_blocks_by_page(page_num) if page_num < doc1.pages else []
            blocks2 = doc2.get_blocks_by_page(page_num) if page_num < doc2.pages else []
            
            page_diffs = self._detect_page_differences(blocks1, blocks2, page_num)
            differences.extend(page_diffs)
        
        # 移動検出（異なるページ間）
        moved_diffs = self._detect_moved_blocks(doc1, doc2, differences)
        differences.extend(moved_diffs)
        
        return differences
    
    def _detect_page_differences(self, 
                                blocks1: List[Block], 
                                blocks2: List[Block],
                                page_num: int) -> List[BlockDifference]:
        """ページ内の差分を検出"""
        differences = []
        
        # ブロック間の類似度マトリックスを計算
        similarity_matrix = self._calculate_similarity_matrix(blocks1, blocks2)
        
        # 最適なマッチングを見つける
        matches = self._find_optimal_matches(similarity_matrix)
        
        matched1 = set()
        matched2 = set()
        
        # マッチしたブロックを処理
        for i, j, similarity in matches:
            if similarity >= self.similarity_threshold:
                matched1.add(i)
                matched2.add(j)
                
                # 内容が異なる場合は変更として記録
                if not self._are_blocks_identical(blocks1[i], blocks2[j]):
                    differences.append(BlockDifference(
                        change_type="modified",
                        block1=blocks1[i],
                        block2=blocks2[j],
                        similarity=similarity,
                        details={
                            'content_changed': blocks1[i].text != blocks2[j].text,
                            'position_changed': not self._are_positions_equal(
                                blocks1[i].bbox, blocks2[j].bbox
                            ),
                            'type_changed': blocks1[i].block_type != blocks2[j].block_type
                        }
                    ))
        
        # マッチしなかったブロックを処理
        for i, block1 in enumerate(blocks1):
            if i not in matched1:
                differences.append(BlockDifference(
                    change_type="deleted",
                    block1=block1,
                    block2=None,
                    similarity=0.0
                ))
        
        for j, block2 in enumerate(blocks2):
            if j not in matched2:
                differences.append(BlockDifference(
                    change_type="added",
                    block1=None,
                    block2=block2,
                    similarity=0.0
                ))
        
        return differences
    
    def _calculate_similarity_matrix(self, 
                                   blocks1: List[Block], 
                                   blocks2: List[Block]) -> np.ndarray:
        """ブロック間の類似度マトリックスを計算"""
        n1 = len(blocks1)
        n2 = len(blocks2)
        
        if n1 == 0 or n2 == 0:
            return np.zeros((n1, n2))
        
        matrix = np.zeros((n1, n2))
        
        for i, block1 in enumerate(blocks1):
            for j, block2 in enumerate(blocks2):
                matrix[i, j] = self._calculate_block_similarity(block1, block2)
        
        return matrix
    
    def _calculate_block_similarity(self, block1: Block, block2: Block) -> float:
        """2つのブロックの類似度を計算"""
        # 位置の類似度
        position_sim = self._calculate_position_similarity(block1.bbox, block2.bbox)
        
        # コンテンツの類似度
        content_sim = self._calculate_content_similarity(block1.text, block2.text)
        
        # タイプの類似度
        type_sim = 1.0 if block1.block_type == block2.block_type else 0.0
        
        # 重み付き平均
        total_weight = self.position_weight + self.content_weight + self.type_weight
        similarity = (
            self.position_weight * position_sim +
            self.content_weight * content_sim +
            self.type_weight * type_sim
        ) / total_weight
        
        return similarity
    
    def _calculate_position_similarity(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
        """位置の類似度を計算"""
        # 中心点の距離
        dx = abs(bbox1.center_x - bbox2.center_x)
        dy = abs(bbox1.center_y - bbox2.center_y)
        distance = np.sqrt(dx*dx + dy*dy)
        
        # 距離を類似度に変換（距離が小さいほど類似度が高い）
        position_sim = np.exp(-distance / (2 * self.position_tolerance))
        
        # サイズの類似度も考慮
        size_ratio = min(bbox1.area, bbox2.area) / max(bbox1.area, bbox2.area)
        
        # 組み合わせ
        return 0.7 * position_sim + 0.3 * size_ratio
    
    def _calculate_content_similarity(self, text1: str, text2: str) -> float:
        """コンテンツの類似度を計算"""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # 単純な文字列類似度
        matcher = SequenceMatcher(None, text1, text2)
        return matcher.ratio()
    
    def _find_optimal_matches(self, similarity_matrix: np.ndarray) -> List[Tuple[int, int, float]]:
        """類似度マトリックスから最適なマッチングを見つける"""
        matches = []
        
        if similarity_matrix.size == 0:
            return matches
        
        # 貪欲法で最適なマッチを見つける
        matrix = similarity_matrix.copy()
        
        while matrix.size > 0 and matrix.max() > 0:
            # 最大値の位置を見つける
            i, j = np.unravel_index(matrix.argmax(), matrix.shape)
            max_sim = matrix[i, j]
            
            if max_sim < self.similarity_threshold * 0.5:  # 低すぎる場合は終了
                break
            
            matches.append((i, j, max_sim))
            
            # 使用した行と列を除外
            matrix[i, :] = 0
            matrix[:, j] = 0
        
        return matches
    
    def _are_blocks_identical(self, block1: Block, block2: Block) -> bool:
        """2つのブロックが同一かチェック"""
        return (block1.text == block2.text and
                block1.block_type == block2.block_type and
                self._are_positions_equal(block1.bbox, block2.bbox))
    
    def _are_positions_equal(self, bbox1: BoundingBox, bbox2: BoundingBox) -> bool:
        """2つの位置が等しいかチェック（許容誤差込み）"""
        return (abs(bbox1.x - bbox2.x) <= self.position_tolerance and
                abs(bbox1.y - bbox2.y) <= self.position_tolerance and
                abs(bbox1.width - bbox2.width) <= self.position_tolerance and
                abs(bbox1.height - bbox2.height) <= self.position_tolerance)
    
    def _detect_moved_blocks(self, 
                           doc1: DocumentStructure, 
                           doc2: DocumentStructure,
                           existing_diffs: List[BlockDifference]) -> List[BlockDifference]:
        """移動したブロックを検出"""
        moved_diffs = []
        
        # 削除と追加のペアから移動を検出
        deleted_blocks = [d for d in existing_diffs if d.change_type == "deleted"]
        added_blocks = [d for d in existing_diffs if d.change_type == "added"]
        
        for del_diff in deleted_blocks:
            best_match = None
            best_similarity = 0.0
            
            for add_diff in added_blocks:
                # 異なるページのブロックのみチェック
                if del_diff.block1.page == add_diff.block2.page:
                    continue
                
                # コンテンツの類似度をチェック
                similarity = self._calculate_content_similarity(
                    del_diff.block1.text, 
                    add_diff.block2.text
                )
                
                if similarity > best_similarity and similarity >= 0.8:
                    best_similarity = similarity
                    best_match = add_diff
            
            if best_match:
                # 移動として記録
                moved_diffs.append(BlockDifference(
                    change_type="moved",
                    block1=del_diff.block1,
                    block2=best_match.block2,
                    similarity=best_similarity,
                    details={
                        'from_page': del_diff.block1.page,
                        'to_page': best_match.block2.page,
                        'position_changed': True
                    }
                ))
                
                # 元の削除と追加を除外
                existing_diffs.remove(del_diff)
                existing_diffs.remove(best_match)
                added_blocks.remove(best_match)
        
        return moved_diffs
    
    def generate_summary(self, differences: List[BlockDifference]) -> Dict[str, Any]:
        """差分のサマリーを生成"""
        summary = {
            'total': len(differences),
            'by_type': {},
            'by_page': {},
            'by_block_type': {}
        }
        
        # 変更タイプ別
        for diff in differences:
            change_type = diff.change_type
            summary['by_type'][change_type] = summary['by_type'].get(change_type, 0) + 1
            
            # ページ別
            page = diff.block2.page if diff.block2 else diff.block1.page
            if page not in summary['by_page']:
                summary['by_page'][page] = {}
            summary['by_page'][page][change_type] = \
                summary['by_page'][page].get(change_type, 0) + 1
            
            # ブロックタイプ別
            block_type = (diff.block2.block_type if diff.block2 else diff.block1.block_type).value
            if block_type not in summary['by_block_type']:
                summary['by_block_type'][block_type] = {}
            summary['by_block_type'][block_type][change_type] = \
                summary['by_block_type'][block_type].get(change_type, 0) + 1
        
        return summary