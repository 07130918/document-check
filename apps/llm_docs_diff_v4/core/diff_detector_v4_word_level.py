"""
差分検出器 v4 - 単語レベルの位置ベース差分検出
各単語の位置変化を個別に検出し、すべての位置の違いを記録
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import difflib

from apps.llm_docs_diff_v3.models.bbox_models import DiffResult, ChangeType

logger = logging.getLogger(__name__)


@dataclass
class WordPositionInfo:
    """単語の位置情報"""
    page: int
    x: float
    y: float
    width: float
    height: float
    line_index: int
    word_index_in_line: int
    

class WordLevelDiffDetector:
    """単語レベルの位置ベース差分検出器"""
    
    def __init__(self,
                 position_tolerance: float = 5.0,  # 単語レベルなのでより厳密に
                 text_similarity_threshold: float = 0.8,  # 部分一致も考慮
                 detect_all_position_changes: bool = True):
        """
        Args:
            position_tolerance: 位置の許容誤差（ピクセル）
            text_similarity_threshold: テキスト類似度の閾値
            detect_all_position_changes: すべての位置変化を検出するか
        """
        self.position_tolerance = position_tolerance
        self.text_similarity_threshold = text_similarity_threshold
        self.detect_all_position_changes = detect_all_position_changes
    
    def detect_differences(self,
                         doc1_words: List[Dict[str, Any]],
                         doc2_words: List[Dict[str, Any]]) -> List[DiffResult]:
        """単語レベルで差分を検出
        
        Args:
            doc1_words: 文書1の単語リスト（Azureから抽出）
            doc2_words: 文書2の単語リスト（Azureから抽出）
        
        Returns:
            単語レベルの差分結果リスト
        """
        # 各単語に詳細な位置情報を付与
        doc1_with_pos = self._add_word_position_info(doc1_words)
        doc2_with_pos = self._add_word_position_info(doc2_words)
        
        results = []
        matched_indices2 = set()
        
        # doc1の各単語について処理
        for idx1, (word1, pos1) in enumerate(doc1_with_pos):
            best_match = None
            best_score = 0.0
            best_idx2 = -1
            best_pos2 = None
            
            # doc2から最適なマッチを探す
            for idx2, (word2, pos2) in enumerate(doc2_with_pos):
                if idx2 in matched_indices2:
                    continue
                
                # 単語レベルのマッチングスコアを計算
                score = self._calculate_word_match_score(word1, word2, pos1, pos2)
                
                if score > best_score and score >= self.text_similarity_threshold:
                    best_match = word2
                    best_score = score
                    best_idx2 = idx2
                    best_pos2 = pos2
            
            if best_match:
                # マッチが見つかった
                matched_indices2.add(best_idx2)
                
                # テキストが異なるか、位置が変わった場合は変更として記録
                text1 = word1.get('text', '').strip()
                text2 = best_match.get('text', '').strip()
                position_changed = self._word_position_changed(pos1, best_pos2)
                
                if text1 != text2 or (self.detect_all_position_changes and position_changed):
                    # 変更タイプを詳細に分類してLLM説明に記録
                    if text1 != text2 and position_changed:
                        change_detail = "text_and_position"
                        llm_explanation = f"Text changed from '{text1}' to '{text2}' and position moved by ({best_pos2.x - pos1.x:.1f}, {best_pos2.y - pos1.y:.1f})"
                    elif text1 != text2:
                        change_detail = "text_only"
                        llm_explanation = f"Text changed from '{text1}' to '{text2}'"
                    else:
                        change_detail = "position_only"
                        llm_explanation = f"Position moved by ({best_pos2.x - pos1.x:.1f}, {best_pos2.y - pos1.y:.1f})"
                    
                    result = DiffResult(
                        change_type=ChangeType.MODIFICATION,
                        page=word1.get('page', 0),
                        original_bbox=word1,
                        modified_bbox=best_match,
                        semantic_similarity=best_score,
                        llm_explanation=llm_explanation
                    )
                    results.append(result)
            else:
                # マッチが見つからない = 削除された単語
                result = DiffResult(
                    change_type=ChangeType.DELETION,
                    page=word1.get('page', 0),
                    original_bbox=word1,
                    modified_bbox=None,
                    semantic_similarity=0.0,
                    llm_explanation=f"Word '{word1.get('text', '')}' was deleted"
                )
                results.append(result)
        
        # doc2の未マッチ単語は追加
        for idx2, (word2, pos2) in enumerate(doc2_with_pos):
            if idx2 not in matched_indices2:
                result = DiffResult(
                    change_type=ChangeType.ADDITION,
                    page=word2.get('page', 0),
                    original_bbox=None,
                    modified_bbox=word2,
                    semantic_similarity=0.0,
                    llm_explanation=f"Word '{word2.get('text', '')}' was added"
                )
                results.append(result)
        
        return results
    
    def _add_word_position_info(self, words: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], WordPositionInfo]]:
        """各単語に詳細な位置情報を付与"""
        words_with_pos = []
        
        # ページごとにグループ化
        pages = {}
        for word in words:
            page = word.get('page', 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(word)
        
        # 各ページで処理
        for page_num in sorted(pages.keys()):
            page_words = pages[page_num]
            
            # 行にグループ化
            lines = self._group_words_into_lines(page_words)
            
            for line_idx, line_words in enumerate(lines):
                # 行内でX座標順にソート
                sorted_line = sorted(line_words, key=lambda w: w['bbox'][0])
                
                for word_idx, word in enumerate(sorted_line):
                    bbox = word['bbox']
                    pos_info = WordPositionInfo(
                        page=page_num,
                        x=bbox[0],
                        y=bbox[1],
                        width=bbox[2],
                        height=bbox[3],
                        line_index=line_idx,
                        word_index_in_line=word_idx
                    )
                    words_with_pos.append((word, pos_info))
        
        return words_with_pos
    
    def _group_words_into_lines(self, words: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """単語を行にグループ化"""
        if not words:
            return []
        
        # Y座標でソート
        sorted_words = sorted(words, key=lambda w: w['bbox'][1])
        
        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0]['bbox'][1]
        current_height = sorted_words[0]['bbox'][3]
        
        for word in sorted_words[1:]:
            word_y = word['bbox'][1]
            word_height = word['bbox'][3]
            
            # 同一行判定（より厳密に）
            y_overlap = abs(word_y - current_y) < min(current_height, word_height) * 0.5
            
            if y_overlap:
                current_line.append(word)
                # 行の代表Y座標を更新（平均値）
                current_y = sum(w['bbox'][1] for w in current_line) / len(current_line)
            else:
                lines.append(current_line)
                current_line = [word]
                current_y = word_y
                current_height = word_height
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _calculate_word_match_score(self, 
                                  word1: Dict[str, Any], 
                                  word2: Dict[str, Any],
                                  pos1: WordPositionInfo,
                                  pos2: WordPositionInfo) -> float:
        """単語レベルのマッチングスコアを計算"""
        # テキストの類似度（大文字小文字を無視）
        text1 = word1.get('text', '').strip().lower()
        text2 = word2.get('text', '').strip().lower()
        
        # 完全一致なら高スコア
        if text1 == text2:
            text_similarity = 1.0
        else:
            # 部分一致も考慮
            text_similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # 位置の類似度（単語レベルなのでより厳密に）
        position_score = 1.0
        
        # ページが異なる場合は大幅にペナルティ
        if pos1.page != pos2.page:
            position_score *= 0.3
        
        # 位置の差を計算
        x_diff = abs(pos1.x - pos2.x)
        y_diff = abs(pos1.y - pos2.y)
        
        # 位置の差に基づくペナルティ（指数関数的に減衰）
        position_penalty = 1.0 / (1.0 + (x_diff + y_diff) / 100.0)
        position_score *= position_penalty
        
        # 行インデックスの差
        if pos1.page == pos2.page:
            line_diff = abs(pos1.line_index - pos2.line_index)
            if line_diff > 0:
                position_score *= (1.0 / (1.0 + line_diff * 0.2))
        
        # 最終スコア（単語レベルなのでテキストの重みをさらに高く）
        final_score = text_similarity * 0.9 + position_score * 0.1
        
        return final_score
    
    def _word_position_changed(self, pos1: WordPositionInfo, pos2: WordPositionInfo) -> bool:
        """単語の位置が変化したかチェック"""
        # ページが異なる
        if pos1.page != pos2.page:
            return True
        
        # X座標またはY座標の変化をチェック
        x_diff = abs(pos1.x - pos2.x)
        y_diff = abs(pos1.y - pos2.y)
        
        return x_diff > self.position_tolerance or y_diff > self.position_tolerance
    
    def generate_word_diff_summary(self, diff_results: List[DiffResult]) -> Dict[str, Any]:
        """単語レベルの差分結果サマリーを生成"""
        summary = {
            'total_word_changes': len(diff_results),
            'word_additions': 0,
            'word_deletions': 0,
            'word_modifications': 0,
            'text_changes': 0,
            'position_changes': 0,
            'text_and_position_changes': 0,
            'by_page': {}
        }
        
        for result in diff_results:
            if result.change_type == ChangeType.ADDITION:
                summary['word_additions'] += 1
            elif result.change_type == ChangeType.DELETION:
                summary['word_deletions'] += 1
            elif result.change_type == ChangeType.MODIFICATION:
                summary['word_modifications'] += 1
                
                # LLM説明から変更タイプを判定
                llm_explanation = getattr(result, 'llm_explanation', '')
                if 'Text changed' in llm_explanation and 'position moved' in llm_explanation:
                    summary['text_and_position_changes'] += 1
                elif 'Text changed' in llm_explanation:
                    summary['text_changes'] += 1
                elif 'Position moved' in llm_explanation:
                    summary['position_changes'] += 1
            
            # ページごとの統計
            page = result.page
            if page not in summary['by_page']:
                summary['by_page'][page] = {
                    'word_additions': 0,
                    'word_deletions': 0,
                    'word_modifications': 0,
                    'position_changes': 0
                }
            
            if result.change_type == ChangeType.ADDITION:
                summary['by_page'][page]['word_additions'] += 1
            elif result.change_type == ChangeType.DELETION:
                summary['by_page'][page]['word_deletions'] += 1
            elif result.change_type == ChangeType.MODIFICATION:
                summary['by_page'][page]['word_modifications'] += 1
                llm_explanation = getattr(result, 'llm_explanation', '')
                if 'position moved' in llm_explanation:
                    summary['by_page'][page]['position_changes'] += 1
        
        return summary