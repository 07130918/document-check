"""
MeCab-based Japanese Tokenizer
日本語形態素解析を用いた単語分割処理
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    import MeCab
    HAS_MECAB = True
except ImportError:
    HAS_MECAB = False

logger = logging.getLogger(__name__)


@dataclass
class Token:
    """MeCab解析結果のトークン"""
    surface: str          # 表層形（実際の文字）
    part_of_speech: str   # 品詞
    base_form: str        # 基本形
    reading: str          # 読み
    position: int         # 文章内位置
    
    def __str__(self):
        return f"{self.surface}({self.part_of_speech})"
    
    def __eq__(self, other):
        """完全一致判定用の等価性比較"""
        if not isinstance(other, Token):
            return False
        return self.surface == other.surface and self.base_form == other.base_form


class MeCabTokenizer:
    """MeCab日本語トークナイザー"""
    
    def __init__(self, mecab_dicdir: Optional[str] = None):
        if not HAS_MECAB:
            raise ImportError("MeCab is not installed. Please install mecab-python3.")
        
        try:
            # UTF-8辞書を使用
            dicdir = mecab_dicdir or "/var/lib/mecab/dic/ipadic-utf8"
            args = f"-r /dev/null -d {dicdir}"
            self.tagger = MeCab.Tagger(args)
            logger.info(f"MeCab initialized with dictionary: {dicdir}")
        except Exception as e:
            logger.error(f"Failed to initialize MeCab: {e}")
            raise
    
    def tokenize(self, text: str) -> List[Token]:
        """
        MeCab形態素解析による日本語テキストのトークン化
        
        Args:
            text: 解析対象テキスト
            
        Returns:
            トークンのリスト
        """
        if not text.strip():
            return []
        
        result = []
        node = self.tagger.parseToNode(text)
        position = 0
        
        while node:
            if node.surface and node.surface.strip():
                features = node.feature.split(',')
                
                # 品詞情報の取得
                part_of_speech = features[0] if len(features) > 0 else "unknown"
                base_form = features[6] if len(features) > 6 and features[6] != '*' else node.surface
                reading = features[7] if len(features) > 7 and features[7] != '*' else node.surface
                
                token = Token(
                    surface=node.surface,
                    part_of_speech=part_of_speech,
                    base_form=base_form,
                    reading=reading,
                    position=position
                )
                result.append(token)
                position += len(node.surface)
            
            node = node.next
        
        return result
    
    def tokenize_simple(self, text: str) -> List[str]:
        """
        シンプルな表層形のみの分割
        
        Args:
            text: 解析対象テキスト
            
        Returns:
            表層形のリスト
        """
        tokens = self.tokenize(text)
        return [token.surface for token in tokens]
    
    def split_sentences(self, text: str) -> List[str]:
        """
        文章単位分割（アノテーション単位に対応）
        
        Args:
            text: 分割対象テキスト
            
        Returns:
            文章のリスト
        """
        import re
        
        # 句点・感嘆符・疑問符・改行等で文章を分割
        sentences = re.split(r'[。！？\n]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def normalize_for_comparison(self, tokens: List[Token]) -> List[str]:
        """
        比較用の正規化処理
        
        Args:
            tokens: トークンリスト
            
        Returns:
            正規化された表層形リスト
        """
        normalized = []
        for token in tokens:
            # 記号・空白は除外
            if token.part_of_speech not in ['記号', '空白']:
                normalized.append(token.surface.lower())
        return normalized
    
    def create_word_pairs(self, tokens1: List[Token], tokens2: List[Token]) -> List[Dict]:
        """
        2つのトークンリストから単語ペアを作成
        
        Args:
            tokens1: 文書1のトークン
            tokens2: 文書2のトークン
            
        Returns:
            単語ペア情報のリスト
        """
        pairs = []
        
        # 位置ベースでペアを作成
        max_len = max(len(tokens1), len(tokens2))
        
        for i in range(max_len):
            token1 = tokens1[i] if i < len(tokens1) else None
            token2 = tokens2[i] if i < len(tokens2) else None
            
            pair_info = {
                'index': i,
                'token1': token1,
                'token2': token2,
                'match_type': self._determine_match_type(token1, token2)
            }
            pairs.append(pair_info)
        
        return pairs
    
    def _determine_match_type(self, token1: Optional[Token], token2: Optional[Token]) -> str:
        """マッチタイプの判定"""
        if token1 is None and token2 is None:
            return 'both_none'
        elif token1 is None:
            return 'addition'
        elif token2 is None:
            return 'deletion'
        elif token1 == token2:
            return 'exact_match'
        elif token1.base_form == token2.base_form:
            return 'base_form_match'
        else:
            return 'different'
    
    def get_statistics(self, text: str) -> Dict:
        """テキストの統計情報を取得"""
        tokens = self.tokenize(text)
        
        stats = {
            'total_tokens': len(tokens),
            'unique_surfaces': len(set(token.surface for token in tokens)),
            'unique_base_forms': len(set(token.base_form for token in tokens)),
            'pos_distribution': {}
        }
        
        # 品詞分布の計算
        for token in tokens:
            pos = token.part_of_speech
            stats['pos_distribution'][pos] = stats['pos_distribution'].get(pos, 0) + 1
        
        return stats


def test_mecab_tokenizer():
    """MeCabTokenizerのテスト"""
    try:
        tokenizer = MeCabTokenizer()
        
        # テストテキスト
        test_texts = [
            "令和5年度",
            "令和6年度", 
            "約1.8万人",
            "約1.6万人",
            "iOS 11/12/13/14/15/16",
            "iOS 11/12/13/14/15/16/17"
        ]
        
        print("=== MeCabTokenizer テスト ===")
        for text in test_texts:
            tokens = tokenizer.tokenize(text)
            simple = tokenizer.tokenize_simple(text)
            print(f"Text: {text}")
            print(f"  Tokens: {[str(token) for token in tokens]}")
            print(f"  Simple: {simple}")
            print()
        
        # 差分比較テスト
        print("=== 差分比較テスト ===")
        tokens1 = tokenizer.tokenize("令和5年度")
        tokens2 = tokenizer.tokenize("令和6年度")
        pairs = tokenizer.create_word_pairs(tokens1, tokens2)
        
        for pair in pairs:
            print(f"Index {pair['index']}: {pair['token1']} -> {pair['token2']} ({pair['match_type']})")
        
        return True
        
    except Exception as e:
        print(f"MeCabTokenizer test failed: {e}")
        return False


if __name__ == "__main__":
    test_mecab_tokenizer()