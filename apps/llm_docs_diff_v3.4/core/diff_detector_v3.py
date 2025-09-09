"""
差分検出器 v3 - 位置に依存しない差分検出
テキストの移動を認識し、真の追加・削除・変更のみを検出
"""
from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import difflib
from models.bbox_models import DiffResult, ChangeType
import logging

logger = logging.getLogger(__name__)


class ChangeTypeV3(Enum):
    """変更タイプ（v3拡張版）"""
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    MOVEMENT = "movement"  # 新規: 移動


class DiffResultV3(DiffResult):
    """差分結果（v3拡張版）"""
    def __init__(self, *args, movement_info: Optional[Dict[str, Any]] = None, **kwargs):
        # spatial_similarityを取り除く（v3では使用しない）
        kwargs.pop('spatial_similarity', None)
        super().__init__(*args, **kwargs)
        self.movement_info = movement_info


class ContentBasedDiffDetector:
    """内容ベースの差分検出器"""
    
    def __init__(self, 
                 similarity_threshold: float = 0.8,
                 exact_match_bonus: float = 0.2,
                 position_weight: float = 0.1,
                 max_page: Optional[int] = None):
        """
        Args:
            similarity_threshold: 類似度の閾値
            exact_match_bonus: 完全一致時のボーナススコア
            position_weight: 位置の重み（0.0で位置を完全に無視）
            max_page: 処理する最大ページ番号（0-indexed）
        """
        self.similarity_threshold = similarity_threshold
        self.exact_match_bonus = exact_match_bonus
        self.position_weight = position_weight
        self.max_page = max_page
    
    def detect_differences(self, 
                          doc1_items: List[Dict[str, Any]], 
                          doc2_items: List[Dict[str, Any]]) -> List[DiffResultV3]:
        """内容ベースで差分を検出"""
        
        # max_pageが指定されている場合、アイテムをフィルタリング
        if self.max_page is not None:
            doc1_items = [item for item in doc1_items if item.get('page', 0) <= self.max_page]
            doc2_items = [item for item in doc2_items if item.get('page', 0) <= self.max_page]
            logger.info(f"Filtering items to pages 0-{self.max_page}")
        
        # テキストでグループ化
        doc1_by_text = self._group_by_text(doc1_items)
        doc2_by_text = self._group_by_text(doc2_items)
        
        results = []
        
        # 完全一致するテキストを先に処理（移動の検出）
        matched_texts = set(doc1_by_text.keys()) & set(doc2_by_text.keys())
        logger.info(f"完全一致テキスト検出: {len(matched_texts)}件")
        
        for text in matched_texts:
            items1 = doc1_by_text[text]
            items2 = doc2_by_text[text]
            
            # ログ出力: 完全一致したテキストと両方の座標
            logger.debug(f"完全一致: '{text}'")
            for item1 in items1:
                logger.debug(f"  2024年: ({item1.get('x', 0):.2f}, {item1.get('y', 0):.2f}) page {item1.get('page', 0)}")
            for item2 in items2:
                logger.debug(f"  2025年: ({item2.get('x', 0):.2f}, {item2.get('y', 0):.2f}) page {item2.get('page', 0)}")
            
            # 移動距離も計算して表示
            if len(items1) == 1 and len(items2) == 1:
                distance = ((items1[0].get('x', 0) - items2[0].get('x', 0))**2 + 
                           (items1[0].get('y', 0) - items2[0].get('y', 0))**2)**0.5
                logger.debug(f"  移動距離: {distance:.2f}px, 移動判定: {self._is_moved(items1[0], items2[0])}")
            
            # 同じテキストが両方の文書にある場合
            if len(items1) == 1 and len(items2) == 1:
                # 位置が大きく変わった場合は移動として記録
                if self._is_moved(items1[0], items2[0]):
                    result = DiffResultV3(
                        change_type=ChangeType.MODIFICATION,  # 互換性のため
                        page=items1[0]['page'],
                        original_bbox=items1[0],
                        modified_bbox=items2[0],
                        semantic_similarity=1.0,
                        movement_info={
                            'type': 'movement',
                            'from_position': self._get_position_info(items1[0]),
                            'to_position': self._get_position_info(items2[0])
                        }
                    )
                    results.append(result)
            
            # 完全一致したものは処理済みとしてマーク
            del doc1_by_text[text]
            del doc2_by_text[text]
        
        # 残りのアイテムで類似度ベースのマッチング
        doc1_remaining = []
        for items in doc1_by_text.values():
            doc1_remaining.extend(items)
        
        doc2_remaining = []
        for items in doc2_by_text.values():
            doc2_remaining.extend(items)
        
        # 類似度マトリクスを計算
        similarity_matrix = self._calculate_similarity_matrix(doc1_remaining, doc2_remaining)
        
        # P24専用デバッグ: 類似度分析
        self._log_p24_similarity_analysis(doc1_remaining, doc2_remaining, similarity_matrix)
        
        # 最適なマッチングを見つける
        matches = self._find_best_matches(similarity_matrix, self.similarity_threshold)
        
        logger.info(f"類似度マッチング: {len(matches)}件のペアを検出")
        
        # マッチしたペアを処理
        matched_indices1 = set()
        matched_indices2 = set()
        
        for idx1, idx2, similarity in matches:
            item1 = doc1_remaining[idx1]
            item2 = doc2_remaining[idx2]
            
            # ログ出力: マッチしたペアの詳細
            logger.debug(f"マッチ: '{item1.get('text', '')}' -> '{item2.get('text', '')}' (類似度: {similarity:.3f})")
            
            # 変更として記録
            result = DiffResultV3(
                change_type=ChangeType.MODIFICATION,
                page=item1['page'],
                original_bbox=item1,
                modified_bbox=item2,
                semantic_similarity=similarity
            )
            results.append(result)
            
            matched_indices1.add(idx1)
            matched_indices2.add(idx2)
        
        # マッチしなかったアイテムを削除・追加として処理
        for idx, item in enumerate(doc1_remaining):
            if idx not in matched_indices1:
                # 削除
                result = DiffResultV3(
                    change_type=ChangeType.DELETION,
                    page=item['page'],
                    original_bbox=item,
                    modified_bbox=None,
                    semantic_similarity=0.0
                )
                results.append(result)
        
        for idx, item in enumerate(doc2_remaining):
            if idx not in matched_indices2:
                # 追加
                result = DiffResultV3(
                    change_type=ChangeType.ADDITION,
                    page=item['page'],
                    original_bbox=None,
                    modified_bbox=item,
                    semantic_similarity=0.0
                )
                results.append(result)
        
        # 結果をソート（ページ順、Y座標順）
        results.sort(key=lambda r: (
            r.page,
            r.original_bbox.get('y', 0) if r.original_bbox else r.modified_bbox.get('y', 0)
        ))
        
        logger.info(f"Detected {len(results)} differences (content-based)")
        return results
    
    def _group_by_text(self, items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """テキストでグループ化"""
        groups = {}
        for item in items:
            text = item.get('text', '').strip()
            if text:
                if text not in groups:
                    groups[text] = []
                groups[text].append(item)
        return groups
    
    def _is_moved(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> bool:
        """アイテムが移動したかどうかを判定"""
        # ページが違う場合は移動
        if item1.get('page', 0) != item2.get('page', 0):
            return True
        
        # 同じページ内での大きな位置変化を検出
        y_diff = abs(item1.get('y', 0) - item2.get('y', 0))
        height = max(item1.get('height', 1), item2.get('height', 1))
        
        # Y座標の差が高さの3倍以上なら移動とみなす
        return y_diff > height * 3
    
    def _get_position_info(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """位置情報を取得"""
        return {
            'page': item.get('page', 0),
            'x': item.get('x', 0),
            'y': item.get('y', 0)
        }
    
    def _calculate_similarity_matrix(self, 
                                   items1: List[Dict[str, Any]], 
                                   items2: List[Dict[str, Any]]) -> List[List[float]]:
        """類似度マトリクスを計算"""
        matrix = []
        
        for item1 in items1:
            row = []
            for item2 in items2:
                # テキストの類似度を計算
                text_sim = self._calculate_text_similarity(
                    item1.get('text', ''), 
                    item2.get('text', '')
                )
                
                # 位置の類似度を計算（重みを小さく）
                pos_sim = self._calculate_spatial_similarity(item1, item2)
                
                # 総合類似度
                total_sim = (1 - self.position_weight) * text_sim + self.position_weight * pos_sim
                
                row.append(total_sim)
            matrix.append(row)
        
        return matrix
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """テキストの類似度を計算"""
        if not text1 or not text2:
            return 0.0
        
        # 完全一致
        if text1 == text2:
            return 1.0
        
        # 前後に文字が追加されただけの場合（例：「継続できます」→「♡ 継続できます」）
        if text1 in text2 or text2 in text1:
            # 包含関係の場合、長さの比率を考慮
            shorter = min(len(text1), len(text2))
            longer = max(len(text1), len(text2))
            if shorter / longer > 0.8:  # 80%以上が共通なら高い類似度
                return 0.95
            else:
                return 0.9
        
        # 数字の変更パターンを検出（例：P34→P35、令和5年→令和6年）
        # 共通部分を抽出して比較
        import re
        # 数字を除いたパターンで比較
        pattern1 = re.sub(r'\d+', '###', text1)
        pattern2 = re.sub(r'\d+', '###', text2)
        
        if pattern1 == pattern2:
            # 構造は同じで数字だけが違う場合
            return 0.85
        
        # 編集距離ベースの類似度
        similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # 類似度が0.5以上で、かつ共通の重要な部分を含む場合はボーナス
        if similarity > 0.5:
            # 日本語の場合の共通部分チェック
            # 「または」などの共通キーワードを探す
            common_keywords = ['または', 'ページ', '保険', '手続', '加入', '年度']
            keyword_count = sum(1 for keyword in common_keywords if keyword in text1 and keyword in text2)
            
            if keyword_count >= 1:  # 共通キーワードがある
                similarity = min(similarity + 0.15, 1.0)
            
            # 文字n-gramによる類似度も考慮（日本語対応）
            def get_ngrams(text, n=2):
                return set(text[i:i+n] for i in range(len(text)-n+1))
            
            bigrams1 = get_ngrams(text1, 2)
            bigrams2 = get_ngrams(text2, 2)
            if bigrams1 and bigrams2:
                bigram_similarity = len(bigrams1 & bigrams2) / max(len(bigrams1), len(bigrams2))
                if bigram_similarity > 0.5:
                    similarity = max(similarity, 0.7 + bigram_similarity * 0.2)
        
        return similarity
    
    def _calculate_spatial_similarity(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> float:
        """空間的類似度を計算"""
        # ページが違う場合
        if item1.get('page', 0) != item2.get('page', 0):
            return 0.0
        
        # 座標の差を計算
        x_diff = abs(item1.get('x', 0) - item2.get('x', 0))
        y_diff = abs(item1.get('y', 0) - item2.get('y', 0))
        
        # 正規化（ページサイズで割るべきだが、簡易的に固定値を使用）
        max_distance = 1000.0  # 仮定: ページの対角線長
        distance = (x_diff ** 2 + y_diff ** 2) ** 0.5
        
        return max(0.0, 1.0 - distance / max_distance)
    
    def _find_best_matches(self, 
                          similarity_matrix: List[List[float]], 
                          threshold: float) -> List[Tuple[int, int, float]]:
        """最適なマッチングを見つける"""
        matches = []
        used_rows = set()
        used_cols = set()
        
        # 類似度の高い順にペアを作成
        candidates = []
        for i, row in enumerate(similarity_matrix):
            for j, sim in enumerate(row):
                if sim >= threshold:
                    candidates.append((i, j, sim))
        
        # 類似度の降順でソート
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        # 貪欲法で最適なマッチングを選択
        for i, j, sim in candidates:
            if i not in used_rows and j not in used_cols:
                matches.append((i, j, sim))
                used_rows.add(i)
                used_cols.add(j)
        
        return matches
    
    def _log_p24_similarity_analysis(self, doc1_remaining: List[Dict[str, Any]], 
                                   doc2_remaining: List[Dict[str, Any]], 
                                   similarity_matrix: List[List[float]]) -> None:
        """P24専用の類似度分析ログ"""
        
        # P24を含むアイテムを検索
        p24_indices = []
        for i, item in enumerate(doc1_remaining):
            if 'P24' in item.get('text', ''):
                p24_indices.append(i)
        
        if not p24_indices:
            return
        
        logger.info(f"P24分析: {len(p24_indices)}件のP24アイテムを発見")
        
        for p24_idx in p24_indices:
            p24_text = doc1_remaining[p24_idx].get('text', '')
            p24_pos = (doc1_remaining[p24_idx].get('x', 0), doc1_remaining[p24_idx].get('y', 0))
            
            logger.debug(f"P24アイテム[{p24_idx}]: '{p24_text}' at {p24_pos}")
            
            # 2025年の候補との類似度を分析
            candidates = []
            for j, item2 in enumerate(doc2_remaining):
                similarity = similarity_matrix[p24_idx][j] if p24_idx < len(similarity_matrix) and j < len(similarity_matrix[p24_idx]) else 0.0
                text2 = item2.get('text', '')
                pos2 = (item2.get('x', 0), item2.get('y', 0))
                candidates.append((j, text2, similarity, pos2))
            
            # 類似度順でソート
            candidates.sort(key=lambda x: x[2], reverse=True)
            
            logger.debug(f"P24[{p24_idx}]の類似度ランキング (上位5位):")
            for rank, (j, text2, sim, pos2) in enumerate(candidates[:5]):
                logger.debug(f"  {rank+1}位: '{text2}' at {pos2} (類似度: {sim:.3f})")
                
                # P26やP30への詳細分析
                if 'P26' in text2 or 'P30' in text2:
                    text_sim = self._calculate_text_similarity(p24_text, text2)
                    pos_sim = self._calculate_spatial_similarity(doc1_remaining[p24_idx], doc2_remaining[j])
                    total_sim = (1 - self.position_weight) * text_sim + self.position_weight * pos_sim
                    
                    logger.info(f"詳細分析 '{p24_text}' -> '{text2}': テキスト類似度={text_sim:.3f}, 位置類似度={pos_sim:.3f}, 総合={total_sim:.3f}")
        
        logger.debug("=" * 50)