"""
Sentence-aware Diff Detector - 文章単位→単語単位の2段階差分検出
"""
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from difflib import SequenceMatcher
from ..models import BBoxTextData, DiffResult, ChangeType
from ..utils import MeCabTokenizer


class SentenceAwareDiffDetector:
    """文章単位で差分を検出してから単語単位で詳細を分析"""
    
    def __init__(self,
                 sentence_similarity_threshold: float = 0.85,
                 word_similarity_threshold: float = 0.9):
        """
        Args:
            sentence_similarity_threshold: 文章類似度の閾値
            word_similarity_threshold: 単語類似度の閾値
        """
        self.sentence_similarity_threshold = sentence_similarity_threshold
        self.word_similarity_threshold = word_similarity_threshold
        self.tokenizer = MeCabTokenizer()
    
    def detect_differences(self, 
                          doc1_bbox_list: List[BBoxTextData], 
                          doc2_bbox_list: List[BBoxTextData]) -> List[DiffResult]:
        """
        2段階差分検出：文章単位→単語単位
        
        Args:
            doc1_bbox_list: 文書1のbbox_text_dataリスト
            doc2_bbox_list: 文書2のbbox_text_dataリスト
            
        Returns:
            差分結果のリスト（単語単位）
        """
        # 1. 文章単位でグループ化
        doc1_sentences = self._group_into_sentences(doc1_bbox_list)
        doc2_sentences = self._group_into_sentences(doc2_bbox_list)
        
        # 2. 文章単位でマッチング
        sentence_matches = self._match_sentences(doc1_sentences, doc2_sentences)
        
        # 3. 差分がある文章のみ単語単位で処理
        differences = []
        
        # 削除された文章
        for sent_idx, sentence1 in enumerate(doc1_sentences):
            if sent_idx not in sentence_matches:
                # 文章全体が削除された場合、単語をMeCabで分割して差分として記録
                word_diffs = self._extract_word_differences_from_sentence(
                    sentence1, None, ChangeType.DELETION
                )
                differences.extend(word_diffs)
        
        # 追加された文章
        matched_indices2 = set(sentence_matches.values())
        for sent_idx, sentence2 in enumerate(doc2_sentences):
            if sent_idx not in matched_indices2:
                # 文章全体が追加された場合、単語をMeCabで分割して差分として記録
                word_diffs = self._extract_word_differences_from_sentence(
                    None, sentence2, ChangeType.ADDITION
                )
                differences.extend(word_diffs)
        
        # 変更された文章（部分的に一致）
        for sent_idx1, sent_idx2 in sentence_matches.items():
            sentence1 = doc1_sentences[sent_idx1]
            sentence2 = doc2_sentences[sent_idx2]
            
            # 文章が完全一致していない場合のみ単語単位で比較
            if not self._are_sentences_identical(sentence1, sentence2):
                word_diffs = self._compare_sentences_word_level(sentence1, sentence2)
                differences.extend(word_diffs)
        
        return differences
    
    def _group_into_sentences(self, bbox_list: List[BBoxTextData]) -> List[List[BBoxTextData]]:
        """
        bbox_listを文章単位にグループ化
        
        Returns:
            文章のリスト（各文章はbboxのリスト）
        """
        if not bbox_list:
            return []
        
        sentences = []
        current_sentence = []
        
        for bbox in bbox_list:
            current_sentence.append(bbox)
            
            # 文末判定（簡易版）
            if bbox['text'] in ['。', '！', '？', '.', '!', '?']:
                sentences.append(current_sentence)
                current_sentence = []
            # 改行や大きな位置変化も文境界とする
            elif len(current_sentence) > 1:
                prev_bbox = current_sentence[-2]
                # Y座標が大きく変わった場合
                if abs(bbox['bbox'][1] - prev_bbox['bbox'][1]) > 30:
                    # 現在の単語を次の文章に回す
                    current_sentence.pop()
                    sentences.append(current_sentence)
                    current_sentence = [bbox]
        
        # 残りの単語も文章として追加
        if current_sentence:
            sentences.append(current_sentence)
        
        return sentences
    
    def _match_sentences(self, 
                        sentences1: List[List[BBoxTextData]], 
                        sentences2: List[List[BBoxTextData]]) -> Dict[int, int]:
        """
        文章単位でマッチング
        
        Returns:
            {sentence1_index: sentence2_index}のマッピング
        """
        matches = {}
        used_indices2 = set()
        
        # 各文章のテキストを結合
        texts1 = [''.join(bbox['text'] for bbox in sent) for sent in sentences1]
        texts2 = [''.join(bbox['text'] for bbox in sent) for sent in sentences2]
        
        # 類似度に基づいてマッチング
        for i, text1 in enumerate(texts1):
            best_match = None
            best_score = 0
            
            for j, text2 in enumerate(texts2):
                if j in used_indices2:
                    continue
                
                similarity = SequenceMatcher(None, text1, text2).ratio()
                
                if similarity > self.sentence_similarity_threshold and similarity > best_score:
                    best_match = j
                    best_score = similarity
            
            if best_match is not None:
                matches[i] = best_match
                used_indices2.add(best_match)
        
        return matches
    
    def _are_sentences_identical(self, 
                                sentence1: List[BBoxTextData], 
                                sentence2: List[BBoxTextData]) -> bool:
        """文章が完全に同一かチェック"""
        text1 = ''.join(bbox['text'] for bbox in sentence1)
        text2 = ''.join(bbox['text'] for bbox in sentence2)
        return text1 == text2
    
    def _extract_word_differences_from_sentence(self,
                                              sentence1: List[BBoxTextData],
                                              sentence2: List[BBoxTextData],
                                              change_type: ChangeType) -> List[DiffResult]:
        """
        文章から単語単位の差分を抽出（MeCab使用）
        """
        differences = []
        
        if change_type == ChangeType.DELETION and sentence1:
            # 削除：sentence1の各単語をMeCabで分割
            for bbox in sentence1:
                words = self.tokenizer.tokenize(bbox['text'])
                if len(words) == 1:
                    # 既に単語単位の場合
                    diff = DiffResult(
                        change_type=ChangeType.DELETION,
                        original_bbox=bbox,
                        modified_bbox=None,
                        page=bbox['page'],
                        confidence=1.0
                    )
                    differences.append(diff)
                else:
                    # 複数単語の場合は分割して処理
                    for word in words:
                        # 簡易的にbboxを作成（実際の位置は推定）
                        word_bbox = {
                            'bbox': bbox['bbox'].copy(),
                            'text': word,
                            'page': bbox['page']
                        }
                        diff = DiffResult(
                            change_type=ChangeType.DELETION,
                            original_bbox=word_bbox,
                            modified_bbox=None,
                            page=bbox['page'],
                            confidence=0.9
                        )
                        differences.append(diff)
        
        elif change_type == ChangeType.ADDITION and sentence2:
            # 追加：sentence2の各単語をMeCabで分割
            for bbox in sentence2:
                words = self.tokenizer.tokenize(bbox['text'])
                if len(words) == 1:
                    diff = DiffResult(
                        change_type=ChangeType.ADDITION,
                        original_bbox=None,
                        modified_bbox=bbox,
                        page=bbox['page'],
                        confidence=1.0
                    )
                    differences.append(diff)
                else:
                    for word in words:
                        word_bbox = {
                            'bbox': bbox['bbox'].copy(),
                            'text': word,
                            'page': bbox['page']
                        }
                        diff = DiffResult(
                            change_type=ChangeType.ADDITION,
                            original_bbox=None,
                            modified_bbox=word_bbox,
                            page=bbox['page'],
                            confidence=0.9
                        )
                        differences.append(diff)
        
        return differences
    
    def _compare_sentences_word_level(self,
                                    sentence1: List[BBoxTextData],
                                    sentence2: List[BBoxTextData]) -> List[DiffResult]:
        """
        部分的に一致する文章を単語レベルで比較
        """
        differences = []
        
        # 文章を単語リストに変換（MeCab使用）
        words1 = []
        for bbox in sentence1:
            tokenized = self.tokenizer.tokenize(bbox['text'])
            for word in tokenized:
                words1.append({
                    'text': word,
                    'original_bbox': bbox,
                    'page': bbox['page']
                })
        
        words2 = []
        for bbox in sentence2:
            tokenized = self.tokenizer.tokenize(bbox['text'])
            for word in tokenized:
                words2.append({
                    'text': word,
                    'original_bbox': bbox,
                    'page': bbox['page']
                })
        
        # 単語レベルでのdiff計算
        matcher = SequenceMatcher(None, 
                                 [w['text'] for w in words1],
                                 [w['text'] for w in words2])
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'delete':
                # 削除された単語
                for i in range(i1, i2):
                    word_data = words1[i]
                    diff = DiffResult(
                        change_type=ChangeType.DELETION,
                        original_bbox={
                            'bbox': word_data['original_bbox']['bbox'],
                            'text': word_data['text'],
                            'page': word_data['page']
                        },
                        modified_bbox=None,
                        page=word_data['page'],
                        confidence=0.95
                    )
                    differences.append(diff)
            
            elif tag == 'insert':
                # 追加された単語
                for j in range(j1, j2):
                    word_data = words2[j]
                    diff = DiffResult(
                        change_type=ChangeType.ADDITION,
                        original_bbox=None,
                        modified_bbox={
                            'bbox': word_data['original_bbox']['bbox'],
                            'text': word_data['text'],
                            'page': word_data['page']
                        },
                        page=word_data['page'],
                        confidence=0.95
                    )
                    differences.append(diff)
            
            elif tag == 'replace':
                # 変更された単語
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    word1 = words1[i]
                    word2 = words2[j]
                    diff = DiffResult(
                        change_type=ChangeType.MODIFICATION,
                        original_bbox={
                            'bbox': word1['original_bbox']['bbox'],
                            'text': word1['text'],
                            'page': word1['page']
                        },
                        modified_bbox={
                            'bbox': word2['original_bbox']['bbox'],
                            'text': word2['text'],
                            'page': word2['page']
                        },
                        page=word1['page'],
                        confidence=0.9
                    )
                    differences.append(diff)
        
        return differences
    
    def get_diff_summary(self, differences: List[DiffResult]) -> Dict[str, int]:
        """
        差分のサマリーを生成
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