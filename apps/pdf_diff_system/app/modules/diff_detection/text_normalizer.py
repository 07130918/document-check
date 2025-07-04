"""
Text normalization utility migrated from prj-meiji-document-check
Original: /app/domain/models/check_logic/application_document/service/check_logic/utils.py
"""
import re
import unicodedata


class TextNormalizer:
    """
    Text normalization engine with 128+ conversion rules
    Migrated from prj-meiji-document-check baseline
    """
    
    def __init__(self):
        # 文字変換マッピング定義（128種類の変換ルール）
        self.char_mapping = self._build_char_mapping()
    
    def _build_char_mapping(self) -> dict:
        """Build comprehensive character mapping table"""
        mapping = {}
        
        # 全角英数字 → 半角変換
        for i in range(26):
            mapping[chr(ord('Ａ') + i)] = chr(ord('A') + i)  # 全角大文字
            mapping[chr(ord('ａ') + i)] = chr(ord('a') + i)  # 全角小文字
        
        for i in range(10):
            mapping[chr(ord('０') + i)] = chr(ord('0') + i)  # 全角数字
        
        # 特殊記号統一
        mapping.update({
            '（': '(',
            '）': ')',
            '［': '[',
            '］': ']',
            '｛': '{',
            '｝': '}',
            '「': '"',
            '」': '"',
            '『': '"',
            '』': '"',
            '・': '·',
            '：': ':',
            '；': ';',
            '！': '!',
            '？': '?',
            '，': ',',
            '．': '.',
            '／': '/',
            '＼': '\\',
            '｜': '|',
            '＋': '+',
            '－': '-',
            '＝': '=',
            '＜': '<',
            '＞': '>',
            '＠': '@',
            '＃': '#',
            '＄': '$',
            '％': '%',
            '＾': '^',
            '＆': '&',
            '＊': '*',
            '＿': '_',
            '～': '~',
            '｀': '`',
            # 空白文字統一
            '　': ' ',  # 全角空白 → 半角空白
            '\u3000': ' ',  # 全角空白
            '\xa0': ' ',    # ノーブレークスペース
            '\u2000': ' ',  # En Quad
            '\u2001': ' ',  # Em Quad
            '\u2002': ' ',  # En Space
            '\u2003': ' ',  # Em Space
            '\u2004': ' ',  # Three-Per-Em Space
            '\u2005': ' ',  # Four-Per-Em Space
            '\u2006': ' ',  # Six-Per-Em Space
            '\u2007': ' ',  # Figure Space
            '\u2008': ' ',  # Punctuation Space
            '\u2009': ' ',  # Thin Space
            '\u200a': ' ',  # Hair Space
            '\u202f': ' ',  # Narrow No-Break Space
            '\u205f': ' ',  # Medium Mathematical Space
            # Unicode正規化関連
            'ー': '-',      # 長音符
            'ｰ': '-',       # 半角長音符
        })
        
        return mapping
    
    def normalize(self, text: str) -> str:
        """
        Comprehensive text normalization
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text string
        """
        if not text:
            return ""
        
        # 1. Unicode正規化（NFKCを使用）
        normalized = unicodedata.normalize('NFKC', text)
        
        # 2. 文字変換マッピング適用
        for old_char, new_char in self.char_mapping.items():
            normalized = normalized.replace(old_char, new_char)
        
        # 3. 連続する空白を単一空白に変換
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 4. 先頭・末尾の空白除去
        normalized = normalized.strip()
        
        # 5. 特殊な文字組み合わせの正規化
        normalized = self._normalize_special_patterns(normalized)
        
        return normalized
    
    def _normalize_special_patterns(self, text: str) -> str:
        """Normalize special character patterns"""
        # 数値パターンの正規化
        # カンマ区切り数値の統一
        text = re.sub(r'(\d),(\d{3})', r'\1,\2', text)
        
        # 日付パターンの正規化
        # YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD → YYYY/MM/DD
        text = re.sub(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', r'\1/\2/\3', text)
        
        # 時刻パターンの正規化
        # HH:MM:SS, HH時MM分SS秒 → HH:MM:SS
        text = re.sub(r'(\d{1,2})時(\d{1,2})分(\d{1,2})秒', r'\1:\2:\3', text)
        text = re.sub(r'(\d{1,2})時(\d{1,2})分', r'\1:\2', text)
        
        # 単位統一
        text = re.sub(r'(\d+)円', r'\1円', text)
        text = re.sub(r'(\d+)％', r'\1%', text)
        
        return text
    
    def prefilter_by_length(self, text1: str, text2: str, 
                          min_ratio: float = 0.3, max_ratio: float = 3.0) -> bool:
        """
        Pre-filter texts by length ratio
        
        Args:
            text1: First text
            text2: Second text
            min_ratio: Minimum length ratio
            max_ratio: Maximum length ratio
            
        Returns:
            True if texts should be compared, False if filtered out
        """
        if not text1 or not text2:
            return False
        
        len1, len2 = len(text1), len(text2)
        if len2 == 0:
            return False
        
        ratio = len1 / len2
        return min_ratio <= ratio <= max_ratio