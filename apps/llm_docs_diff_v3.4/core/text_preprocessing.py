"""
テキスト前処理ユーティリティ
PDFから抽出したテキストの品質を向上させる
"""
from typing import List, Dict, Any, Tuple, Optional
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """テキスト前処理クラス"""
    
    def __init__(self):
        """初期化"""
        # 日本語の一般的なフォント置換マッピング
        self.font_replacement_map = {
            # 全角英数字を半角に
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
            'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
            'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
            'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
            'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
            'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y',
            'Ｚ': 'Z',
            # 特殊な記号の正規化
            '･': '・', '､': '、', '｡': '。', '（': '(', '）': ')',
            '［': '[', '］': ']', '｛': '{', '｝': '}',
        }
        
        # OCRでよく発生する文字の誤認識パターン
        self.ocr_correction_patterns = [
            (r'[０-９]', self._convert_fullwidth_digit),
            (r'[Ａ-Ｚ]', self._convert_fullwidth_alpha),
            (r'[ａ-ｚ]', self._convert_fullwidth_alpha_lower),
        ]
    
    def preprocess_bbox_list(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """BBoxデータリスト全体の前処理
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            前処理済みのBBoxデータリスト
        """
        processed_list = []
        
        for bbox_data in bbox_list:
            # テキストの前処理
            processed_text = self.preprocess_text(bbox_data["text"])
            
            # 空文字になった場合はスキップ
            if not processed_text.strip():
                continue
            
            # 処理済みデータを作成
            processed_bbox = bbox_data.copy()
            processed_bbox["text"] = processed_text
            processed_bbox["original_text"] = bbox_data["text"]  # 元のテキストも保持
            
            processed_list.append(processed_bbox)
        
        # 重複や分割された文字の結合
        processed_list = self._merge_split_characters(processed_list)
        
        # ノイズの除去
        processed_list = self._remove_noise(processed_list)
        
        logger.info(f"Preprocessed {len(bbox_list)} boxes to {len(processed_list)} boxes")
        return processed_list
    
    def preprocess_text(self, text: str) -> str:
        """個別のテキストの前処理
        
        Args:
            text: 前処理するテキスト
            
        Returns:
            前処理済みのテキスト
        """
        if not text:
            return text
        
        # Unicode正規化（NFC形式に統一）
        text = unicodedata.normalize('NFC', text)
        
        # 文字置換
        for old_char, new_char in self.font_replacement_map.items():
            text = text.replace(old_char, new_char)
        
        # OCR誤認識の修正
        for pattern, correction_func in self.ocr_correction_patterns:
            text = re.sub(pattern, correction_func, text)
        
        # 不要な空白の除去（日本語の場合は単語間スペースを除去）
        if self._contains_japanese(text):
            # 日本語テキストの場合、英数字の前後以外のスペースを除去
            text = self._normalize_japanese_spacing(text)
        else:
            # 英語テキストの場合、連続する空白を1つに
            text = re.sub(r'\s+', ' ', text)
        
        # 制御文字の除去
        text = self._remove_control_characters(text)
        
        return text.strip()
    
    def _merge_split_characters(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分割された文字を結合
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            結合済みのBBoxデータリスト
        """
        if not bbox_list:
            return bbox_list
        
        merged_list = []
        i = 0
        
        while i < len(bbox_list):
            current = bbox_list[i]
            
            # 同じ行で近接する要素をチェック
            if i + 1 < len(bbox_list):
                next_item = bbox_list[i + 1]
                
                # 同じページ、同じ行（Y座標が近い）、X座標が近接
                if (current["page"] == next_item["page"] and
                    abs(current["bbox"][1] - next_item["bbox"][1]) < 5 and  # Y座標の差が5未満
                    next_item["bbox"][0] - (current["bbox"][0] + current["bbox"][2]) < 10):  # X座標の間隔が10未満
                    
                    # 特定のパターンで結合（例：分割された数字や記号）
                    if self._should_merge(current["text"], next_item["text"]):
                        # 結合
                        merged_bbox = current.copy()
                        merged_bbox["text"] = current["text"] + next_item["text"]
                        merged_bbox["bbox"] = [
                            current["bbox"][0],
                            min(current["bbox"][1], next_item["bbox"][1]),
                            next_item["bbox"][0] + next_item["bbox"][2] - current["bbox"][0],
                            max(current["bbox"][3], next_item["bbox"][3])
                        ]
                        merged_list.append(merged_bbox)
                        i += 2  # 2つ分スキップ
                        continue
            
            merged_list.append(current)
            i += 1
        
        return merged_list
    
    def _should_merge(self, text1: str, text2: str) -> bool:
        """2つのテキストを結合すべきか判定
        
        Args:
            text1: 最初のテキスト
            text2: 次のテキスト
            
        Returns:
            結合すべきならTrue
        """
        # 数字の分割（例：「1」「0」→「10」）
        if text1.isdigit() and text2.isdigit():
            return True
        
        # 小数点の分割（例：「3」「.」「14」）
        if text1.isdigit() and text2 == ".":
            return True
        if text1 == "." and text2.isdigit():
            return True
        
        # パーセント記号の分割（例：「100」「%」）
        if text1.isdigit() and text2 == "%":
            return True
        
        # 日付の分割（例：「2023」「/」「12」）
        if text1.isdigit() and text2 in ["/", "-", "."]:
            return True
        
        return False
    
    def _remove_noise(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ノイズ要素を除去
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            ノイズを除去したBBoxデータリスト
        """
        filtered_list = []
        
        for bbox_data in bbox_list:
            text = bbox_data["text"]
            
            # 単一の記号や制御文字のみの要素を除去
            if len(text) == 1 and not text.isalnum() and not self._is_meaningful_symbol(text):
                continue
            
            # 極端に小さいバウンディングボックスを除去（ノイズの可能性）
            if bbox_data["bbox"][2] < 5 or bbox_data["bbox"][3] < 5:
                continue
            
            # ヘッダー・フッターの除去（ページ番号など）
            if self._is_header_footer(bbox_data):
                continue
            
            filtered_list.append(bbox_data)
        
        # 重複テキストの除去
        filtered_list = self._remove_duplicate_text(filtered_list)
        
        return filtered_list
    
    def _is_header_footer(self, bbox_data: Dict[str, Any]) -> bool:
        """ヘッダー・フッターかどうか判定
        
        Args:
            bbox_data: BBoxデータ
            
        Returns:
            ヘッダー・フッターならTrue
        """
        text = bbox_data["text"]
        y_pos = bbox_data["bbox"][1]
        
        # ページ上下の10%以内にある単純なテキスト
        # 一般的なPDFのページサイズ（A4: 842pt）を基準
        if y_pos < 85 or y_pos > 757:  
            # ページ番号パターン
            if re.match(r'^\d+$', text) or re.match(r'^-\s*\d+\s*-$', text):
                return True
            # 日付パターン
            if re.match(r'^\d{4}[/\-年]\d{1,2}[/\-月]\d{1,2}', text):
                return True
        
        return False
    
    def _remove_duplicate_text(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """重複テキストを除去
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            重複を除去したBBoxデータリスト
        """
        seen_texts = {}
        filtered_list = []
        
        for bbox_data in bbox_list:
            text = bbox_data["text"]
            page = bbox_data["page"]
            
            # ページごとに重複をチェック
            key = f"{page}:{text}"
            
            if key not in seen_texts:
                seen_texts[key] = bbox_data
                filtered_list.append(bbox_data)
            else:
                # 同じテキストが既にある場合、より大きいBBoxを優先
                existing = seen_texts[key]
                existing_area = existing["bbox"][2] * existing["bbox"][3]
                current_area = bbox_data["bbox"][2] * bbox_data["bbox"][3]
                
                if current_area > existing_area:
                    # 既存のものを削除して新しいものを追加
                    filtered_list = [item for item in filtered_list if item != existing]
                    filtered_list.append(bbox_data)
                    seen_texts[key] = bbox_data
        
        return filtered_list
    
    def _is_meaningful_symbol(self, char: str) -> bool:
        """意味のある記号かどうか判定
        
        Args:
            char: 判定する文字
            
        Returns:
            意味のある記号ならTrue
        """
        meaningful_symbols = set('。、・！？「」（）[]{}%$¥@#&*+-=/\\|_<>,.;:\'\"')
        return char in meaningful_symbols
    
    def _contains_japanese(self, text: str) -> bool:
        """日本語を含むかどうか判定
        
        Args:
            text: 判定するテキスト
            
        Returns:
            日本語を含むならTrue
        """
        for char in text:
            if '\u3040' <= char <= '\u309F':  # ひらがな
                return True
            if '\u30A0' <= char <= '\u30FF':  # カタカナ
                return True
            if '\u4E00' <= char <= '\u9FFF':  # 漢字
                return True
        return False
    
    def _normalize_japanese_spacing(self, text: str) -> str:
        """日本語テキストのスペースを正規化
        
        Args:
            text: 正規化するテキスト
            
        Returns:
            正規化済みのテキスト
        """
        # 日本語文字間のスペースを除去
        text = re.sub(r'([ぁ-ん])\s+([ぁ-ん])', r'\1\2', text)
        text = re.sub(r'([ァ-ン])\s+([ァ-ン])', r'\1\2', text)
        text = re.sub(r'([一-龯])\s+([一-龯])', r'\1\2', text)
        
        # 日本語と英数字の間は1つのスペースを保持
        text = re.sub(r'([ぁ-んァ-ン一-龯])\s*([a-zA-Z0-9])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z0-9])\s*([ぁ-んァ-ン一-龯])', r'\1 \2', text)
        
        return text
    
    def _remove_control_characters(self, text: str) -> str:
        """制御文字を除去
        
        Args:
            text: 処理するテキスト
            
        Returns:
            制御文字を除去したテキスト
        """
        # 改行とタブは保持、それ以外の制御文字は除去
        return ''.join(char for char in text 
                      if not unicodedata.category(char).startswith('C') 
                      or char in '\n\t')
    
    def _convert_fullwidth_digit(self, match):
        """全角数字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)
    
    def _convert_fullwidth_alpha(self, match):
        """全角英大文字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)
    
    def _convert_fullwidth_alpha_lower(self, match):
        """全角英小文字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)

class TextPreprocessorFixed:
    """ページ番号除去問題を修正したテキスト前処理クラス"""
    
    def __init__(self):
        """初期化"""
        # 日本語の一般的なフォント置換マッピング
        self.font_replacement_map = {
            # 全角英数字を半角に
            'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
            'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
            'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
            'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
            'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y',
            'Ｚ': 'Z',
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
            # 特殊な記号の正規化
            '・': '·', '、': ',', '。': '.', '（': '(', '）': ')',
            '［': '[', '］': ']', '｛': '{', '｝': '}',
        }
        
        # OCRでよく発生する文字の誤認識パターン
        self.ocr_correction_patterns = [
            (r'[０-９]', self._convert_fullwidth_digit),
            (r'[Ａ-Ｚ]', self._convert_fullwidth_alpha),
            (r'[ａ-ｚ]', self._convert_fullwidth_alpha_lower),
        ]
    
    def preprocess_bbox_list(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """BBoxデータリスト全体の前処理（問題のある処理を除外）
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            前処理済みのBBoxデータリスト
        """
        processed_list = []
        
        for bbox_data in bbox_list:
            # テキストの前処理
            processed_text = self.preprocess_text(bbox_data["text"])
            
            # 空文字になった場合はスキップ
            if not processed_text.strip():
                continue
            
            # 処理済みデータを作成
            processed_bbox = bbox_data.copy()
            processed_bbox["text"] = processed_text
            processed_bbox["original_text"] = bbox_data["text"]  # 元のテキストも保持
            
            processed_list.append(processed_bbox)
        
        # 重複や分割された文字の結合（保持）
        processed_list = self._merge_split_characters(processed_list)
        
        # 問題のある前処理を除外：
        # - _remove_noise() を除外
        # - _remove_duplicate_text() を除外  
        # - _is_header_footer() を除外
        
        logger.info(f"Preprocessed {len(bbox_list)} boxes to {len(processed_list)} boxes (fixed version)")
        return processed_list
    
    def preprocess_text(self, text: str) -> str:
        """個別のテキストの前処理（保持）
        
        Args:
            text: 前処理するテキスト
            
        Returns:
            前処理済みのテキスト
        """
        if not text:
            return text
        
        # Unicode正規化（NFC形式に統一）
        text = unicodedata.normalize('NFC', text)
        
        # 文字置換
        for old_char, new_char in self.font_replacement_map.items():
            text = text.replace(old_char, new_char)
        
        # OCR誤認識の修正
        for pattern, correction_func in self.ocr_correction_patterns:
            text = re.sub(pattern, correction_func, text)
        
        # 不要な空白の除去（日本語の場合は単語間スペースを除去）
        if self._contains_japanese(text):
            # 日本語テキストの場合、英数字の前後以外のスペースを除去
            text = self._normalize_japanese_spacing(text)
        else:
            # 英語テキストの場合、連続する空白を1つに
            text = re.sub(r'\s+', ' ', text)
        
        # 制御文字の除去（保持）
        text = self._remove_control_characters(text)
        
        return text.strip()
    
    def _merge_split_characters(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分割された文字を結合（保持）
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            結合済みのBBoxデータリスト
        """
        if not bbox_list:
            return bbox_list
        
        merged_list = []
        i = 0
        
        while i < len(bbox_list):
            current = bbox_list[i]
            
            # 同じ行で近接する要素をチェック
            if i + 1 < len(bbox_list):
                next_item = bbox_list[i + 1]
                
                # 同じページ、同じ行（Y座標が近い）、X座標が近接
                if (current["page"] == next_item["page"] and
                    abs(current["bbox"][1] - next_item["bbox"][1]) < 5 and  # Y座標の差が5未満
                    next_item["bbox"][0] - (current["bbox"][0] + current["bbox"][2]) < 10):  # X座標の間隔が10未満
                    
                    # 特定のパターンで結合（例：分割された数字や記号）
                    if self._should_merge(current["text"], next_item["text"]):
                        # 結合
                        merged_bbox = current.copy()
                        merged_bbox["text"] = current["text"] + next_item["text"]
                        merged_bbox["bbox"] = [
                            current["bbox"][0],
                            min(current["bbox"][1], next_item["bbox"][1]),
                            next_item["bbox"][0] + next_item["bbox"][2] - current["bbox"][0],
                            max(current["bbox"][3], next_item["bbox"][3])
                        ]
                        merged_list.append(merged_bbox)
                        i += 2  # 2つ分スキップ
                        continue
            
            merged_list.append(current)
            i += 1
        
        return merged_list
    
    def _should_merge(self, text1: str, text2: str) -> bool:
        """2つのテキストを結合すべきか判定（保持）"""
        # 数字の分割（例：「1」「0」→「10」）
        if text1.isdigit() and text2.isdigit():
            return True
        
        # 小数点の分割（例：「3」「.」「14」）
        if text1.isdigit() and text2 == ".":
            return True
        if text1 == "." and text2.isdigit():
            return True
        
        # パーセント記号の分割（例：「100」「%」）
        if text1.isdigit() and text2 == "%":
            return True
        
        # 日付の分割（例：「2023」「/」「12」）
        if text1.isdigit() and text2 in ["/", "-", "."]:
            return True
        
        return False
    
    def _contains_japanese(self, text: str) -> bool:
        """日本語を含むかどうか判定（保持）"""
        for char in text:
            if '\u3040' <= char <= '\u309F':  # ひらがな
                return True
            if '\u30A0' <= char <= '\u30FF':  # カタカナ
                return True
            if '\u4E00' <= char <= '\u9FFF':  # 漢字
                return True
        return False
    
    def _normalize_japanese_spacing(self, text: str) -> str:
        """日本語テキストのスペースを正規化（保持）"""
        # 日本語文字間のスペースを除去
        text = re.sub(r'([あ-ん])\s+([あ-ん])', r'\1\2', text)
        text = re.sub(r'([ア-ン])\s+([ア-ン])', r'\1\2', text)
        text = re.sub(r'([一-龯])\s+([一-龯])', r'\1\2', text)
        
        # 日本語と英数字の間は1つのスペースを保持
        text = re.sub(r'([あ-んア-ン一-龯])\s*([a-zA-Z0-9])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z0-9])\s*([あ-んア-ン一-龯])', r'\1 \2', text)
        
        return text
    
    def _remove_control_characters(self, text: str) -> str:
        """制御文字を除去（保持）"""
        # 改行とタブは保持、それ以外の制御文字は除去
        return ''.join(char for char in text 
                      if not unicodedata.category(char).startswith('C') 
                      or char in '\n\t')
    
    def _convert_fullwidth_digit(self, match):
        """全角数字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)
    
    def _convert_fullwidth_alpha(self, match):
        """全角英大文字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)
    
    def _convert_fullwidth_alpha_lower(self, match):
        """全角英小文字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)

def test_preprocessing_comparison():
    """修正版と元版の前処理結果を比較テスト"""
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info("=== 前処理比較テスト開始 ===")
    
    # サンプルデータ（P2ページ番号関連）
    sample_data = [
        {"text": "※家族の範囲はP11をご覧ください。", "bbox": [63.0, 330.8, 127.8, 10.1], "page": 1},
        {"text": "詳細はP64をご覧ください。", "bbox": [58.1, 791.8, 124.1, 11.9], "page": 1},
        {"text": "2024年度商品改定 P3", "bbox": [477.8, 102.5, 91.6, 10.6], "page": 1},
        {"text": "プロの目線でみるメリット P5", "bbox": [477.6, 122.3, 91.7, 10.9], "page": 1},
        {"text": "インフォメーション P9", "bbox": [478.1, 142.2, 91.4, 10.8], "page": 1},
        {"text": "ファミリー P11", "bbox": [491.5, 271.2, 60.9, 9.5], "page": 1},
        {"text": "P13", "bbox": [538.7, 287.2, 14.1, 7.8], "page": 1},
        {"text": "P17、20", "bbox": [544.9, 378.5, 22.9, 8.1], "page": 1}
    ]
    
    # 元の前処理
    original_processor = TextPreprocessor()
    original_result = original_processor.preprocess_bbox_list(sample_data)
    
    # 修正版前処理
    fixed_processor = TextPreprocessorFixed()
    fixed_result = fixed_processor.preprocess_bbox_list(sample_data)
    
    # 比較結果
    logger.info(f"元の前処理: {len(sample_data)}件 → {len(original_result)}件")
    logger.info(f"修正版前処理: {len(sample_data)}件 → {len(fixed_result)}件")
    
    # ページ番号要素の保持状況
    original_page_refs = [item for item in original_result if _contains_page_reference(item['text'])]
    fixed_page_refs = [item for item in fixed_result if _contains_page_reference(item['text'])]
    
    logger.info(f"ページ番号保持: 元版={len(original_page_refs)}件, 修正版={len(fixed_page_refs)}件")
    
    return {
        'original_count': len(original_result),
        'fixed_count': len(fixed_result),
        'original_page_refs': len(original_page_refs),
        'fixed_page_refs': len(fixed_page_refs),
        'improvement': len(fixed_page_refs) - len(original_page_refs)
    }

def _contains_page_reference(text: str) -> bool:
    """テキストがページ番号参照を含むかチェック"""
    import re
    return bool(re.search(r'P\d+', text))


class TextPreprocessorV3_1:
    """v3.1: 前処理でページ番号参照などの重要データを保護する改善版クラス"""
    
    def __init__(self):
        """初期化"""
        # 日本語の一般的なフォント置換マッピング
        self.font_replacement_map = {
            # 全角英数字を半角に
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
            'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
            'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
            'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
            'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
            'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y',
            'Ｚ': 'Z',
            # 特殊な記号の正規化
            '･': '・', '､': '、', '｡': '。', '（': '(', '）': ')',
            '［': '[', '］': ']', '｛': '{', '｝': '}',
        }
        
        # OCRでよく発生する文字の誤認識パターン
        self.ocr_correction_patterns = [
            (r'[０-９]', self._convert_fullwidth_digit),
            (r'[Ａ-Ｚ]', self._convert_fullwidth_alpha),
            (r'[ａ-ｚ]', self._convert_fullwidth_alpha_lower),
        ]
    
    def preprocess_bbox_list(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """BBoxデータリスト全体の前処理（v3.1改善版）
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            前処理済みのBBoxデータリスト
        """
        processed_list = []
        
        for bbox_data in bbox_list:
            # テキストの前処理
            processed_text = self.preprocess_text(bbox_data["text"])
            
            # 空文字になった場合はスキップ
            if not processed_text.strip():
                continue
            
            # 処理済みデータを作成
            processed_bbox = bbox_data.copy()
            processed_bbox["text"] = processed_text
            processed_bbox["original_text"] = bbox_data["text"]  # 元のテキストも保持
            
            processed_list.append(processed_bbox)
        
        # 重複や分割された文字の結合
        processed_list = self._merge_split_characters(processed_list)
        
        # v3.1改善: 保守的なノイズ除去（重要データ保護）
        processed_list = self._remove_noise_conservative(processed_list)
        
        logger.info(f"Preprocessed {len(bbox_list)} boxes to {len(processed_list)} boxes (v3.1)")
        return processed_list
    
    def preprocess_text(self, text: str) -> str:
        """個別のテキストの前処理
        
        Args:
            text: 前処理するテキスト
            
        Returns:
            前処理済みのテキスト
        """
        if not text:
            return text
        
        # Unicode正規化（NFC形式に統一）
        text = unicodedata.normalize('NFC', text)
        
        # 文字置換
        for old_char, new_char in self.font_replacement_map.items():
            text = text.replace(old_char, new_char)
        
        # OCR誤認識の修正
        for pattern, correction_func in self.ocr_correction_patterns:
            text = re.sub(pattern, correction_func, text)
        
        # 不要な空白の除去（日本語の場合は単語間スペースを除去）
        if self._contains_japanese(text):
            # 日本語テキストの場合、英数字の前後以外のスペースを除去
            text = self._normalize_japanese_spacing(text)
        else:
            # 英語テキストの場合、連続する空白を1つに
            text = re.sub(r'\s+', ' ', text)
        
        # 制御文字の除去
        text = self._remove_control_characters(text)
        
        return text.strip()
    
    def _is_page_reference_protected(self, text: str) -> bool:
        """ページ番号参照の保護判定
        
        Args:
            text: 判定するテキスト
            
        Returns:
            ページ番号参照を含む場合はTrue
        """
        # P11をご覧ください、詳細はP64をご覧くださいなどのパターン
        return bool(re.search(r'P\d+', text))
    
    def _is_important_content(self, text: str, bbox_data: Dict[str, Any]) -> bool:
        """重要なコンテンツかどうか判定
        
        Args:
            text: テキスト内容
            bbox_data: BBoxデータ
            
        Returns:
            重要なコンテンツの場合はTrue
        """
        # ページ番号参照は保護
        if self._is_page_reference_protected(text):
            return True
        
        # 英数字を含む短文は保護（"P13"など）
        if len(text) <= 5 and re.search(r'[a-zA-Z0-9]', text):
            return True
        
        # 日本語を含む文章は保護
        if self._contains_japanese(text) and len(text) > 2:
            return True
        
        return False
    
    def _remove_noise_conservative(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """保守的なノイズ除去（v3.1改善版）
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            ノイズを除去したBBoxデータリスト
        """
        filtered_list = []
        
        for bbox_data in bbox_list:
            text = bbox_data["text"]
            
            # 重要なコンテンツは保護
            if self._is_important_content(text, bbox_data):
                filtered_list.append(bbox_data)
                continue
            
            # 単一の意味のない記号のみを除去
            if len(text) == 1 and text in '-_|．':
                continue
            
            # 極端に小さいバウンディングボックスを除去（ノイズの可能性）
            if bbox_data["bbox"][2] < 3 or bbox_data["bbox"][3] < 3:
                continue
            
            # その他は保持
            filtered_list.append(bbox_data)
        
        # v3.1改善: 重複テキスト除去も保守的に実行
        filtered_list = self._remove_duplicate_text_conservative(filtered_list)
        
        return filtered_list
    
    def _is_header_footer_relaxed(self, bbox_data: Dict[str, Any]) -> bool:
        """緩和されたヘッダー・フッター判定（v3.1改善版）
        
        Args:
            bbox_data: BBoxデータ
            
        Returns:
            明らかなヘッダー・フッターのみTrue
        """
        text = bbox_data["text"]
        y_pos = bbox_data["bbox"][1]
        
        # ページ番号参照を含むものは除去しない
        if self._is_page_reference_protected(text):
            return False
        
        # より厳格な条件: ページ上下5%以内かつ単純なパターンのみ
        if y_pos < 42 or y_pos > 800:  # A4サイズの上下5%
            # 単純なページ番号のみを除去対象とする
            if re.match(r'^\s*\d+\s*$', text) or re.match(r'^\s*-\s*\d+\s*-\s*$', text):
                return True
        
        return False
    
    def _remove_duplicate_text_conservative(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """保守的な重複テキスト除去（v3.1改善版）
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            重複を除去したBBoxデータリスト
        """
        # 重要な情報は重複除去の対象外
        protected_items = []
        regular_items = []
        
        for bbox_data in bbox_list:
            if self._is_important_content(bbox_data["text"], bbox_data):
                protected_items.append(bbox_data)
            else:
                regular_items.append(bbox_data)
        
        # 通常のアイテムのみ重複除去を適用
        seen_texts = {}
        filtered_regular = []
        
        for bbox_data in regular_items:
            text = bbox_data["text"]
            page = bbox_data["page"]
            
            # ページごとに重複をチェック（より厳格に）
            key = f"{page}:{text}"
            
            if key not in seen_texts:
                seen_texts[key] = bbox_data
                filtered_regular.append(bbox_data)
            else:
                # 同じテキストが既にある場合、より大きいBBoxを優先
                existing = seen_texts[key]
                existing_area = existing["bbox"][2] * existing["bbox"][3]
                current_area = bbox_data["bbox"][2] * bbox_data["bbox"][3]
                
                if current_area > existing_area:
                    # 既存のものを削除して新しいものを追加
                    filtered_regular = [item for item in filtered_regular if item != existing]
                    filtered_regular.append(bbox_data)
                    seen_texts[key] = bbox_data
        
        # 保護されたアイテムと合併
        return protected_items + filtered_regular
    
    def _merge_split_characters(self, bbox_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分割された文字を結合
        
        Args:
            bbox_list: BBoxデータのリスト
            
        Returns:
            結合済みのBBoxデータリスト
        """
        if not bbox_list:
            return bbox_list
        
        merged_list = []
        i = 0
        
        # ロガー名を明示的に確認・設定
        current_logger = logging.getLogger('apps.llm_docs_diff_v3_3.core.text_preprocessing')
        current_logger.info(f"TextPreprocessorV3_1._merge_split_characters開始: {len(bbox_list)}個のアイテム")
        current_logger.debug(f"現在のロガー名: {current_logger.name}")
        current_logger.debug(f"ロガーレベル: {current_logger.level}")
        current_logger.debug(f"ハンドラー数: {len(current_logger.handlers)}")
        
        logger.debug(f"テキスト結合処理開始: {len(bbox_list)}個のアイテム")
        
        # bbox_listの内容をCSVファイルに出力
        import csv
        import os
        
        # 出力ディレクトリを決定（デバッグ用）
        output_dir = "/home/dev/prj-ms-document-check.worktree/worktree1/debug_output"
        os.makedirs(output_dir, exist_ok=True)
        
        # タイムスタンプ付きファイル名
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"bbox_list_input_{timestamp}.csv"
        csv_path = os.path.join(output_dir, csv_filename)
        
        # CSVファイルに出力
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['順序', 'テキスト', 'ページ', 'X座標', 'Y座標', '幅', '高さ', '元テキスト']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for i, item in enumerate(bbox_list):
                writer.writerow({
                    '順序': i,
                    'テキスト': item.get('text', ''),
                    'ページ': item.get('page', 0),
                    'X座標': item.get('bbox', [0,0,0,0])[0],
                    'Y座標': item.get('bbox', [0,0,0,0])[1],
                    '幅': item.get('bbox', [0,0,0,0])[2],
                    '高さ': item.get('bbox', [0,0,0,0])[3],
                    '元テキスト': item.get('original_text', item.get('text', ''))
                })
        
        logger.info(f"bbox_list入力データCSV出力: {csv_path}")
        
        while i < len(bbox_list):
            current = bbox_list[i]
            
            # 同じ行で近接する要素をチェック
            if i + 1 < len(bbox_list):
                next_item = bbox_list[i + 1]
                
                # 全ての結合候補のログ（INFOレベルで確実出力）
                current_logger.info(f"結合候補[{i}→{i+1}]: '{current['text']}' + '{next_item['text']}'")
                current_logger.info(f"  現在位置: ({current['bbox'][0]:.2f}, {current['bbox'][1]:.2f})")
                current_logger.info(f"  次位置: ({next_item['bbox'][0]:.2f}, {next_item['bbox'][1]:.2f})")
                
                # Y差とX間隔の計算
                y_diff = abs(current["bbox"][1] - next_item["bbox"][1])
                x_gap = next_item["bbox"][0] - (current["bbox"][0] + current["bbox"][2])
                current_logger.info(f"  Y差: {y_diff:.2f}, X間隔: {x_gap:.2f}")
                
                # 同じページ、同じ行（Y座標が近い）、X座標が近接
                proximity_check = (current["page"] == next_item["page"] and
                                 y_diff < 5 and  # Y座標の差が5未満
                                 x_gap < 25)  # X座標の間隔が25未満
                
                # 全ての近接判定結果をログ
                current_logger.info(f"  近接判定: {proximity_check} (同ページ: {current['page'] == next_item['page']}, Y<5: {y_diff < 5}, X<25: {x_gap < 25})")
                
                if proximity_check:
                    merge_decision = self._should_merge(current["text"], next_item["text"])
                    current_logger.info(f"  結合判定: {merge_decision}")
                    
                    # 特定のパターンで結合（例：分割された数字や記号）
                    if merge_decision:
                        # 全ての結合実行をログ
                        current_logger.info(f"テキスト結合実行[{i}→{i+1}]: '{current['text']}' + '{next_item['text']}' = '{current['text'] + next_item['text']}'")
                        
                        # 結合
                        merged_bbox = current.copy()
                        merged_bbox["text"] = current["text"] + next_item["text"]
                        merged_bbox["bbox"] = [
                            current["bbox"][0],
                            min(current["bbox"][1], next_item["bbox"][1]),
                            next_item["bbox"][0] + next_item["bbox"][2] - current["bbox"][0],
                            max(current["bbox"][3], next_item["bbox"][3])
                        ]
                        merged_list.append(merged_bbox)
                        i += 2  # 2つ分スキップ
                        continue
            
            merged_list.append(current)
            i += 1
        
        current_logger.info(f"テキスト結合処理完了: {len(bbox_list)}個 → {len(merged_list)}個")
        logger.debug(f"テキスト結合処理完了: {len(bbox_list)}個 → {len(merged_list)}個")
        return merged_list
    
    def _should_merge(self, text1: str, text2: str) -> bool:
        """2つのテキストを結合すべきか判定
        
        Args:
            text1: 最初のテキスト
            text2: 次のテキスト
            
        Returns:
            結合すべきならTrue
        """
        # 数字の分割（例：「1」「0」→「10」）
        if text1.isdigit() and text2.isdigit():
            return True
        
        # 小数点の分割（例：「3」「.」「14」）
        if text1.isdigit() and text2 == ".":
            return True
        if text1 == "." and text2.isdigit():
            return True
        
        # パーセント記号の分割（例：「100」「%」）
        if text1.isdigit() and text2 == "%":
            return True
        
        # 日付の分割（例：「2023」「/」「12」）
        if text1.isdigit() and text2 in ["/", "-", "."]:
            return True
        
        # 一時的に全部Trueにする
        return True
    
    def _contains_japanese(self, text: str) -> bool:
        """日本語を含むかどうか判定
        
        Args:
            text: 判定するテキスト
            
        Returns:
            日本語を含むならTrue
        """
        for char in text:
            if '\u3040' <= char <= '\u309F':  # ひらがな
                return True
            if '\u30A0' <= char <= '\u30FF':  # カタカナ
                return True
            if '\u4E00' <= char <= '\u9FFF':  # 漢字
                return True
        return False
    
    def _normalize_japanese_spacing(self, text: str) -> str:
        """日本語テキストのスペースを正規化
        
        Args:
            text: 正規化するテキスト
            
        Returns:
            正規化済みのテキスト
        """
        # 日本語文字間のスペースを除去
        text = re.sub(r'([ぁ-ん])\s+([ぁ-ん])', r'\1\2', text)
        text = re.sub(r'([ァ-ン])\s+([ァ-ン])', r'\1\2', text)
        text = re.sub(r'([一-龯])\s+([一-龯])', r'\1\2', text)
        
        # 日本語と英数字の間は1つのスペースを保持
        text = re.sub(r'([ぁ-んァ-ン一-龯])\s*([a-zA-Z0-9])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z0-9])\s*([ぁ-んァ-ン一-龯])', r'\1 \2', text)
        
        return text
    
    def _remove_control_characters(self, text: str) -> str:
        """制御文字を除去
        
        Args:
            text: 処理するテキスト
            
        Returns:
            制御文字を除去したテキスト
        """
        # 改行とタブは保持、それ以外の制御文字は除去
        return ''.join(char for char in text 
                      if not unicodedata.category(char).startswith('C') 
                      or char in '\n\t')
    
    def _convert_fullwidth_digit(self, match):
        """全角数字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)
    
    def _convert_fullwidth_alpha(self, match):
        """全角英大文字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)
    
    def _convert_fullwidth_alpha_lower(self, match):
        """全角英小文字を半角に変換"""
        return chr(ord(match.group(0)) - 0xFEE0)


class StructuredTextPreprocessorV4:
    """v3.4: Document Intelligenceのセクション階層と座標情報を活用した構造化前処理クラス"""
    
    def __init__(self):
        """初期化"""
        # 基本的なテキスト正規化設定
        self.font_replacement_map = {
            # 全角英数字を半角に
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
            'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
            'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
            'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
            'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
            'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y',
            'Ｚ': 'Z',
        }
    
    def preprocess_structured_document(self, di_analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Document Intelligence分析結果を構造化前処理
        
        Args:
            di_analysis_result: Document Intelligence分析結果（セクション・段落・座標情報含む）
            
        Returns:
            構造化された検出単位のリスト
        """
        processed_items = []
        
        if not di_analysis_result.get('sections'):
            logger.warning("セクション情報がありません。fallback処理を実行します。")
            return self._fallback_processing(di_analysis_result)
        
        logger.info(f"構造化前処理開始: {len(di_analysis_result['sections'])}セクション")
        
        # セクションごとに処理
        for section in di_analysis_result['sections']:
            section_items = self._process_section(section)
            processed_items.extend(section_items)
        
        logger.info(f"構造化前処理完了: {len(processed_items)}個の検出単位を生成")
        return processed_items
    
    def _process_section(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """個別セクションの処理
        
        Args:
            section: セクション情報
            
        Returns:
            セクション内の検出単位リスト
        """
        section_items = []
        section_title = section.get('title', 'Unknown Section')
        section_coords = section.get('coordinates')
        
        logger.debug(f"セクション処理: {section_title}")
        
        # v3.4対応: セクションタイトルの座標情報を設定
        section_x, section_y, section_width, section_height = 0, 0, 0, 0
        section_bbox = [0, 0, 0, 0]
        
        if section_coords and isinstance(section_coords, dict):
            section_x = section_coords.get('left', 0)
            section_y = section_coords.get('top', 0)
            section_width = section_coords.get('width', section_coords.get('right', 0) - section_x)
            section_height = section_coords.get('height', section_coords.get('bottom', 0) - section_y)
            section_bbox = [section_x, section_y, section_x + section_width, section_y + section_height]
        
        section_item = {
            'text': section_title,
            'type': 'section_title',
            'page': 2,  # 固定値（Page 2処理）
            'x': section_x,
            'y': section_y,
            'width': section_width,
            'height': section_height,
            'bbox': section_bbox,
            'coordinates': section_coords,  # 元の座標情報を保持
            'section_info': {
                'section_number': section.get('section_number', 0),
                'paragraph_count': section.get('paragraph_count', 0),
                'content_length': section.get('content_length', 0)
            }
        }
        section_items.append(section_item)
        
        # セクション内の段落を処理
        for para in section.get('paragraphs', []):
            para_item = self._process_paragraph(para, section_title)
            if para_item:
                section_items.append(para_item)
        
        return section_items
    
    def _process_paragraph(self, paragraph: Dict[str, Any], section_title: str) -> Optional[Dict[str, Any]]:
        """個別段落の処理
        
        Args:
            paragraph: 段落情報
            section_title: 所属セクションのタイトル
            
        Returns:
            段落の検出単位（Noneの場合はスキップ）
        """
        text = paragraph.get('content', '').strip()
        coords = paragraph.get('coordinates')
        role = paragraph.get('role')
        
        # 空のテキストはスキップ
        if not text:
            return None
        
        # テキストの前処理（基本的な正規化）
        processed_text = self._normalize_text(text)
        
        # 重要度に基づく分類
        importance = self._classify_paragraph_importance(text, role)
        
        # v3.4対応: 座標情報を適切に設定
        x, y, width, height = 0, 0, 0, 0
        bbox = [0, 0, 0, 0]
        
        if coords and isinstance(coords, dict):
            x = coords.get('left', 0)
            y = coords.get('top', 0) 
            width = coords.get('width', coords.get('right', 0) - x)
            height = coords.get('height', coords.get('bottom', 0) - y)
            bbox = [x, y, x + width, y + height]
        
        return {
            'text': processed_text,
            'original_text': text,
            'type': 'paragraph',
            'role': role,
            'importance': importance,
            'page': 2,  # 固定値（Page 2処理）
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'bbox': bbox,
            'coordinates': coords,  # 元の座標情報を保持
            'section_context': {
                'section_title': section_title,
                'paragraph_index': paragraph.get('paragraph_index', 0)
            },
            'length': paragraph.get('length', len(text))
        }
    
    def _normalize_text(self, text: str) -> str:
        """基本的なテキスト正規化
        
        Args:
            text: 正規化するテキスト
            
        Returns:
            正規化済みテキスト
        """
        # Unicode正規化
        import unicodedata
        text = unicodedata.normalize('NFC', text)
        
        # 文字置換
        for old_char, new_char in self.font_replacement_map.items():
            text = text.replace(old_char, new_char)
        
        # 不要な空白の正規化
        import re
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _classify_paragraph_importance(self, text: str, role: Optional[str]) -> str:
        """段落の重要度を分類
        
        Args:
            text: 段落テキスト
            role: 段落の役割
            
        Returns:
            重要度レベル（'high', 'medium', 'low'）
        """
        # 役割に基づく重要度
        if role == 'ParagraphRole.TITLE':
            return 'high'
        elif role == 'ParagraphRole.SECTION_HEADING':
            return 'high'
        elif role == 'ParagraphRole.PAGE_NUMBER':
            return 'low'
        elif role == 'ParagraphRole.FOOTNOTE':
            return 'medium'
        
        # テキスト内容に基づく重要度
        import re
        if re.search(r'P\d+', text):  # ページ参照
            return 'high'
        elif len(text) > 50:  # 長い文章
            return 'high'
        elif len(text) < 5:  # 短いテキスト
            return 'low'
        else:
            return 'medium'
    
    def _extract_page_from_coords(self, coords: Dict[str, Any]) -> int:
        """座標情報からページ番号を推定
        
        Args:
            coords: 座標情報
            
        Returns:
            ページ番号（推定）
        """
        # 今回はPage 2のみなので固定値
        return 2
    
    def _fallback_processing(self, di_analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """セクション情報がない場合のfallback処理
        
        Args:
            di_analysis_result: Document Intelligence分析結果
            
        Returns:
            処理済み検出単位リスト
        """
        logger.info("fallback処理: 段落ベースで処理します")
        
        processed_items = []
        paragraphs = di_analysis_result.get('paragraphs', [])
        
        for para in paragraphs:
            para_item = self._process_paragraph(para, "Unknown Section")
            if para_item:
                processed_items.append(para_item)
        
        return processed_items

class MergeSplitCharacterPreProcessor:
    """分割文字結合前処理器 - セクション内で最大2つまで結合"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_document_analysis(self, doc_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """文書解析結果の分割文字結合処理
        
        Args:
            doc_analysis: Document Intelligence解析結果
            
        Returns:
            結合処理済み解析結果
        """
        
        processed_analysis = doc_analysis.copy()
        sections = processed_analysis.get('sections', [])
        
        self.logger.info(f"分割文字結合処理開始: {len(sections)}セクション")
        
        # 各セクション内で段落の結合処理
        for section_idx, section in enumerate(sections):
            section_title = section.get('title', "")
            if section_title == "追加オプション" or "医療ワイドかんぺき" in section_title:
                paragraphs = section.get('paragraphs', [])
                self.logger.debug(f"結合処理実行: セクション{section_idx+1}『{section.get('title', '')}』: {len(paragraphs)}段落")
                
                # セクション内での段落結合処理
                merged_paragraphs = self._merge_paragraphs_in_section(paragraphs, section_idx)
                section['paragraphs'] = merged_paragraphs
                
                # セクション統計を更新
                section['paragraph_count'] = len(merged_paragraphs)
                section['content_length'] = sum(len(p.get('content', '')) for p in merged_paragraphs)
                section['word_count'] = sum(len(p.get('content', '').split()) for p in merged_paragraphs)
                
                self.logger.info(f"セクション{section_idx+1}結合完了: {len(paragraphs)}段落 → {len(merged_paragraphs)}段落")
            

        return processed_analysis


    def _count_p_number_patterns(self, para_contents_list: List[str]) -> int:
        """para_contents_list内のP数字パターンをカウント
        
        Args:
            para_contents_list: 段落コンテンツリスト
            
        Returns:
            P数字パターンの数
        """
        import re
        
        p_pattern_count = 0
        p_number_pattern = re.compile(r'P\d+', re.IGNORECASE)
        
        for content in para_contents_list:
            if p_number_pattern.search(content):
                p_pattern_count += 1
                self.logger.debug(f"  P数字パターン発見: '{content}'")
        
        return p_pattern_count
    
    def _merge_paragraphs_in_section(self, paragraphs: List[Dict[str, Any]], 
                                   section_idx: int) -> List[Dict[str, Any]]:
        """セクション内の段落結合処理（最大2つまで）
        
        Args:
            paragraphs: 段落リスト
            section_idx: セクション番号
            
        Returns:
            結合処理済み段落リスト
        """
        if not paragraphs:
            return paragraphs
        
        merged_list = []
        i = 0
        
        while i < len(paragraphs):
            current = paragraphs[i]
            
            # 次の段落との結合を検討（最大2つまで）
            if i + 1 < len(paragraphs):
                next_para = paragraphs[i + 1]
                
                # 結合判定
                should_merge = self._should_merge_paragraphs(current, next_para, section_idx)
                
                if should_merge:
                    # 2つの段落を結合
                    merged_para = self._merge_two_paragraphs(current, next_para)
                    merged_list.append(merged_para)
                    
                    self.logger.debug(f"段落結合実行[セクション{section_idx+1}]: "
                                    f"'{current.get('content', '')[:20]}...' + "
                                    f"'{next_para.get('content', '')[:20]}...' = "
                                    f"'{merged_para.get('content', '')[:30]}...'")
                    
                    i += 2  # 2つ分スキップ
                    continue
            
            # 結合しない場合はそのまま追加
            merged_list.append(current)
            i += 1
        
        self.logger.debug(f"セクション{section_idx+1}結合結果: {len(paragraphs)}段落 → {len(merged_list)}段落")
        return merged_list
    
    def _should_merge_paragraphs(self, para1: Dict[str, Any], 
                               para2: Dict[str, Any], section_idx: int) -> bool:
        """2つの段落を結合すべきかを判定
        
        Args:
            para1: 段落1
            para2: 段落2  
            section_idx: セクション番号
            
        Returns:
            結合すべきかどうか
        """
        content1 = para1.get('content', '').strip()
        content2 = para2.get('content', '').strip()
        coords1 = para1.get('coordinates', {})
        coords2 = para2.get('coordinates', {})
        
        # 空の内容はスキップ
        if not content1 or not content2:
            return False
        
        # 座標情報がない場合はスキップ
        if not coords1 or not coords2:
            return False
        
        # ポリゴン座標データから位置情報を取得
        left1, top1, right1, bottom1 = self._extract_position_from_polygon(coords1)
        left2, top2, right2, bottom2 = self._extract_position_from_polygon(coords2)
        
        if left1 is None or left2 is None:
            # ポリゴン座標が取得できない場合はスキップ
            return False
        
        # Y座標の差（同じ行かどうか）
        y_diff = abs(top1 - top2)
        
        # X座標の間隔
        x_gap = left2 - right1
        
        # 近接判定
        is_same_line = y_diff < 0.1  # Y差が0.1インチ未満（同じ行）
        is_close_x = 0 <= x_gap < 0.5  # X間隔が0.5インチ未満で隣接
        
        # 結合判定ロジック
        merge_decision = is_same_line and is_close_x
        
        if merge_decision:
            self.logger.debug(f"結合判定OK[セクション{section_idx+1}]: Y差={y_diff:.3f}, X間隔={x_gap:.3f}")
        
        return merge_decision
    
    def _extract_position_from_polygon(self, coords: Dict[str, Any]) -> Tuple[float, float, float, float]:
        """ポリゴン座標データから位置情報を抽出
        
        Args:
            coords: 座標データ（ポリゴン形式）
            
        Returns:
            (left, top, right, bottom) または (None, None, None, None)
        """
        # boundsが存在する場合はそれを使用
        if 'bounds' in coords:
            bounds = coords['bounds']
            return (
                bounds.get('left', 0),
                bounds.get('top', 0), 
                bounds.get('right', 0),
                bounds.get('bottom', 0)
            )
        
        # raw_coordinatesから直接計算
        raw_coords = coords.get('raw_coordinates', [])
        if len(raw_coords) >= 8:  # 最低4点（x1,y1,x2,y2,x3,y3,x4,y4）
            # raw_coordinatesは [x1, y1, x2, y2, x3, y3, x4, y4] の形式
            x_coords = [raw_coords[i] for i in range(0, len(raw_coords), 2)]
            y_coords = [raw_coords[i] for i in range(1, len(raw_coords), 2)]
            
            left = min(x_coords)
            top = min(y_coords)
            right = max(x_coords)
            bottom = max(y_coords)
            
            return (left, top, right, bottom)
        
        # 従来のleft/top/right/bottomがある場合
        if 'left' in coords and 'top' in coords:
            return (
                coords.get('left', 0),
                coords.get('top', 0),
                coords.get('right', coords.get('left', 0) + coords.get('width', 0)),
                coords.get('bottom', coords.get('top', 0) + coords.get('height', 0))
            )
        
        return (None, None, None, None)
    
    
    def _merge_two_paragraphs(self, para1: Dict[str, Any], 
                            para2: Dict[str, Any]) -> Dict[str, Any]:
        """2つの段落を結合
        
        Args:
            para1: 段落1
            para2: 段落2
            
        Returns:
            結合済み段落
        """
        merged_para = para1.copy()
        
        # テキスト結合
        content1 = para1.get('content', '')
        content2 = para2.get('content', '')
        merged_para['content'] = content1 + content2
        merged_para['length'] = len(merged_para['content'])
        
        # 座標結合（2つを包含する範囲）
        coords1 = para1.get('coordinates', {})
        coords2 = para2.get('coordinates', {})
        
        if coords1 and coords2:
            merged_coords = {
                'left': min(coords1.get('left', 0), coords2.get('left', 0)),
                'top': min(coords1.get('top', 0), coords2.get('top', 0)),
                'right': max(
                    coords1.get('right', coords1.get('left', 0) + coords1.get('width', 0)),
                    coords2.get('right', coords2.get('left', 0) + coords2.get('width', 0))
                ),
                'bottom': max(
                    coords1.get('bottom', coords1.get('top', 0) + coords1.get('height', 0)),
                    coords2.get('bottom', coords2.get('top', 0) + coords2.get('height', 0))
                )
            }
            merged_coords['width'] = merged_coords['right'] - merged_coords['left']
            merged_coords['height'] = merged_coords['bottom'] - merged_coords['top']
            merged_para['coordinates'] = merged_coords
        
        # 重要度は高い方を採用
        importance1 = para1.get('importance', 'low')
        importance2 = para2.get('importance', 'low')
        importance_priority = {'high': 3, 'medium': 2, 'low': 1}
        
        if importance_priority.get(importance2, 1) > importance_priority.get(importance1, 1):
            merged_para['importance'] = importance2
        
        return merged_para
