"""
テキスト前処理ユーティリティ
PDFから抽出したテキストの品質を向上させる
"""
from typing import List, Dict, Any, Tuple
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