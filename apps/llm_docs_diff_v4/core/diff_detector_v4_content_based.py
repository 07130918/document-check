"""
差分検出器 v4 - 内容ベースの単語レベル差分検出
位置の違いは無視し、テキスト内容の変化のみを検出
"""
from typing import List, Dict, Any, Set
from collections import Counter
import logging

from apps.llm_docs_diff_v3.models.bbox_models import DiffResult, ChangeType

logger = logging.getLogger(__name__)


class ContentBasedDiffDetector:
    """内容ベースの単語レベル差分検出器"""
    
    def __init__(self):
        """初期化"""
        pass
    
    def detect_differences(self,
                         doc1_words: List[Dict[str, Any]],
                         doc2_words: List[Dict[str, Any]]) -> List[DiffResult]:
        """内容ベースで単語レベルの差分を検出（位置情報も保持）
        
        Args:
            doc1_words: 文書1の単語リスト（位置情報付き）
            doc2_words: 文書2の単語リスト（位置情報付き）
        
        Returns:
            単語レベルの差分結果リスト（内容の変化のみ、位置情報付き）
        """
        # 単語を正規化してグループ化（位置情報も保持）
        doc1_word_map = self._create_word_position_map(doc1_words)
        doc2_word_map = self._create_word_position_map(doc2_words)
        
        # すべての単語を収集
        all_words = set(doc1_word_map.keys()) | set(doc2_word_map.keys())
        
        results = []
        
        # 各単語について差分を検出
        for word in sorted(all_words):
            doc1_positions = doc1_word_map.get(word, [])
            doc2_positions = doc2_word_map.get(word, [])
            
            count1 = len(doc1_positions)
            count2 = len(doc2_positions)
            
            if count1 > count2:
                # 削除された単語（回数が減った）
                # 削除された分の位置情報を使用
                for i in range(count1 - count2):
                    if i < len(doc1_positions):
                        word_info = doc1_positions[i]
                        result = DiffResult(
                            change_type=ChangeType.DELETION,
                            page=word_info.get('page', 0),
                            original_bbox=word_info,
                            modified_bbox=None,
                            semantic_similarity=0.0,
                            llm_explanation=f"Word '{word}' was deleted (appears {count1}x → {count2}x)"
                        )
                        results.append(result)
                    
            elif count2 > count1:
                # 追加された単語（回数が増えた）
                # 追加された分の位置情報を使用
                for i in range(count2 - count1):
                    if i < len(doc2_positions):
                        word_info = doc2_positions[i]
                        result = DiffResult(
                            change_type=ChangeType.ADDITION,
                            page=word_info.get('page', 0),
                            original_bbox=None,
                            modified_bbox=word_info,
                            semantic_similarity=0.0,
                            llm_explanation=f"Word '{word}' was added (appears {count1}x → {count2}x)"
                        )
                        results.append(result)
        
        return results
    
    def _create_word_position_map(self, words: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """単語を正規化してグループ化し、位置情報を保持"""
        word_map = {}
        
        for word_info in words:
            text = word_info.get('text', '').strip().lower()
            if text:
                if text not in word_map:
                    word_map[text] = []
                # 位置情報を含む完全な単語情報を保存
                word_map[text].append(word_info)
        
        return word_map
    
    def _find_word_info(self, words: List[Dict[str, Any]], target_word: str) -> Dict[str, Any]:
        """単語リストから特定の単語情報を見つける"""
        for word in words:
            if word.get('text', '').strip().lower() == target_word.lower():
                return word
        return {}
    
    def detect_phrase_differences(self,
                                doc1_words: List[Dict[str, Any]],
                                doc2_words: List[Dict[str, Any]],
                                phrase_length: int = 3) -> List[DiffResult]:
        """フレーズレベルの差分を検出（n-gram）
        
        Args:
            doc1_words: 文書1の単語リスト
            doc2_words: 文書2の単語リスト
            phrase_length: フレーズの長さ（デフォルト3単語）
        
        Returns:
            フレーズレベルの差分結果リスト
        """
        # 単語リストをテキストのみのリストに変換
        doc1_texts = [w.get('text', '').strip() for w in doc1_words if w.get('text', '').strip()]
        doc2_texts = [w.get('text', '').strip() for w in doc2_words if w.get('text', '').strip()]
        
        # n-gramを生成
        doc1_ngrams = self._generate_ngrams(doc1_texts, phrase_length)
        doc2_ngrams = self._generate_ngrams(doc2_texts, phrase_length)
        
        # n-gramの出現回数をカウント
        doc1_counter = Counter(doc1_ngrams)
        doc2_counter = Counter(doc2_ngrams)
        
        # すべてのn-gramを収集
        all_ngrams = set(doc1_counter.keys()) | set(doc2_counter.keys())
        
        results = []
        
        # 各n-gramについて差分を検出
        for ngram in sorted(all_ngrams):
            count1 = doc1_counter.get(ngram, 0)
            count2 = doc2_counter.get(ngram, 0)
            
            if count1 > count2:
                # 削除されたフレーズ
                phrase = ' '.join(ngram)
                for _ in range(count1 - count2):
                    result = DiffResult(
                        change_type=ChangeType.DELETION,
                        page=0,  # フレーズレベルではページ特定が困難
                        original_bbox={'text': phrase},
                        modified_bbox=None,
                        semantic_similarity=0.0,
                        llm_explanation=f"Phrase '{phrase}' was deleted (appears {count1}x → {count2}x)"
                    )
                    results.append(result)
                    
            elif count2 > count1:
                # 追加されたフレーズ
                phrase = ' '.join(ngram)
                for _ in range(count2 - count1):
                    result = DiffResult(
                        change_type=ChangeType.ADDITION,
                        page=0,  # フレーズレベルではページ特定が困難
                        original_bbox=None,
                        modified_bbox={'text': phrase},
                        semantic_similarity=0.0,
                        llm_explanation=f"Phrase '{phrase}' was added (appears {count1}x → {count2}x)"
                    )
                    results.append(result)
        
        return results
    
    def _generate_ngrams(self, words: List[str], n: int) -> List[tuple]:
        """単語リストからn-gramを生成"""
        ngrams = []
        for i in range(len(words) - n + 1):
            ngrams.append(tuple(words[i:i+n]))
        return ngrams
    
    def generate_content_diff_summary(self, diff_results: List[DiffResult]) -> Dict[str, Any]:
        """内容ベースの差分結果サマリーを生成"""
        summary = {
            'total_content_changes': len(diff_results),
            'words_added': 0,
            'words_deleted': 0,
            'unique_words_added': set(),
            'unique_words_deleted': set(),
            'most_frequent_additions': [],
            'most_frequent_deletions': []
        }
        
        added_words = []
        deleted_words = []
        
        for result in diff_results:
            if result.change_type == ChangeType.ADDITION:
                summary['words_added'] += 1
                if result.modified_bbox:
                    word = result.modified_bbox.get('text', '').strip()
                    if word:
                        added_words.append(word)
                        summary['unique_words_added'].add(word)
                        
            elif result.change_type == ChangeType.DELETION:
                summary['words_deleted'] += 1
                if result.original_bbox:
                    word = result.original_bbox.get('text', '').strip()
                    if word:
                        deleted_words.append(word)
                        summary['unique_words_deleted'].add(word)
        
        # 最も頻繁に追加/削除された単語を集計
        if added_words:
            added_counter = Counter(added_words)
            summary['most_frequent_additions'] = added_counter.most_common(10)
        
        if deleted_words:
            deleted_counter = Counter(deleted_words)
            summary['most_frequent_deletions'] = deleted_counter.most_common(10)
        
        # セットを文字列に変換（JSON化のため）
        summary['unique_words_added'] = list(summary['unique_words_added'])
        summary['unique_words_deleted'] = list(summary['unique_words_deleted'])
        
        return summary