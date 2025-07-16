"""
MeCab Tokenizer for Japanese text processing
"""
import os
import MeCab
from typing import List, Dict, Tuple

# MeCabの設定
os.environ['MECABRC'] = '/etc/mecabrc'


class MeCabTokenizer:
    """MeCabを使用した日本語単語分割"""
    
    def __init__(self):
        """MeCabの初期化"""
        try:
            self.tagger = MeCab.Tagger()
            # parseToNodeを一度実行して初期化
            self.tagger.parseToNode("")
        except Exception as e:
            print(f"MeCab initialization error: {e}")
            self.tagger = None
    
    def tokenize(self, text: str) -> List[str]:
        """
        テキストを単語に分割
        
        Args:
            text: 分割するテキスト
            
        Returns:
            単語のリスト
        """
        if not self.tagger or not text:
            return [text] if text else []
        
        words = []
        try:
            node = self.tagger.parseToNode(text)
            while node:
                if node.surface:
                    words.append(node.surface)
                node = node.next
        except Exception as e:
            print(f"MeCab tokenization error: {e}")
            # フォールバック: スペースで分割
            words = text.split()
        
        return words
    
    def tokenize_with_positions(self, text: str) -> List[Tuple[str, int, int]]:
        """
        テキストを単語に分割し、元のテキスト内での位置情報も返す
        
        Args:
            text: 分割するテキスト
            
        Returns:
            (単語, 開始位置, 終了位置)のリスト
        """
        if not self.tagger or not text:
            return [(text, 0, len(text))] if text else []
        
        words_with_pos = []
        current_pos = 0
        
        try:
            node = self.tagger.parseToNode(text)
            while node:
                if node.surface:
                    # 元のテキスト内での位置を探す
                    start = text.find(node.surface, current_pos)
                    if start != -1:
                        end = start + len(node.surface)
                        words_with_pos.append((node.surface, start, end))
                        current_pos = end
                node = node.next
        except Exception as e:
            print(f"MeCab tokenization error: {e}")
            # フォールバック
            words_with_pos = [(text, 0, len(text))]
        
        return words_with_pos
    
    def is_content_word(self, word: str) -> bool:
        """
        内容語（名詞、動詞、形容詞など）かどうかを判定
        
        Args:
            word: 判定する単語
            
        Returns:
            内容語ならTrue
        """
        if not self.tagger or not word:
            return True
        
        try:
            node = self.tagger.parseToNode(word)
            while node:
                if node.surface == word:
                    features = node.feature.split(',')
                    pos = features[0]
                    # 内容語: 名詞、動詞、形容詞、副詞
                    return pos in ['名詞', '動詞', '形容詞', '副詞']
                node = node.next
        except:
            pass
        
        return True