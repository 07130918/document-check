"""
Azure Document Intelligence用のテキスト処理ユーティリティ
単語レベルのデータを行やフレーズにグループ化
"""
from typing import List, Dict, Any, Tuple, Union
import logging
import re

logger = logging.getLogger(__name__)

def group_azure_words_to_lines(word_list: List[Dict[str, Any]], 
                             line_tolerance: float = 5.0,
                             word_spacing_tolerance: float = 20.0) -> List[Dict[str, Any]]:
    """Azure Document Intelligenceの単語データを行単位にグループ化
    
    Args:
        word_list: 単語レベルのBBoxデータのリスト
        line_tolerance: 同じ行と判定するY座標の許容誤差
        word_spacing_tolerance: 単語間の最大許容間隔
        
    Returns:
        行単位にグループ化されたBBoxデータのリスト
    """
    if not word_list:
        return []
    
    # ページごとにグループ化
    pages = {}
    for word in word_list:
        page = word["page"]
        if page not in pages:
            pages[page] = []
        pages[page].append(word)
    
    grouped_lines = []
    
    # 各ページで行をグループ化
    for page_num in sorted(pages.keys()):
        page_words = pages[page_num]
        
        # Y座標でソート
        page_words.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
        
        current_line = []
        current_y = None
        
        for word in page_words:
            word_y = word["bbox"][1]
            word_x = word["bbox"][0]
            
            if current_line:
                # 前の単語との関係をチェック
                last_word = current_line[-1]
                last_x_end = last_word["bbox"][0] + last_word["bbox"][2]
                
                # 同じ行かどうか判定
                same_line = (
                    abs(word_y - current_y) <= line_tolerance and
                    word_x - last_x_end <= word_spacing_tolerance
                )
                
                if same_line:
                    current_line.append(word)
                else:
                    # 行を確定
                    if current_line:
                        merged_line = merge_words_to_line(current_line, page_num)
                        grouped_lines.append(merged_line)
                    current_line = [word]
                    current_y = word_y
            else:
                current_line = [word]
                current_y = word_y
        
        # 最後の行を追加
        if current_line:
            merged_line = merge_words_to_line(current_line, page_num)
            grouped_lines.append(merged_line)
    
    logger.info(f"Grouped {len(word_list)} words into {len(grouped_lines)} lines")
    return grouped_lines

def merge_words_to_line(words: List[Dict[str, Any]], page: int) -> Dict[str, Any]:
    """単語のリストを1つの行にマージ
    
    Args:
        words: マージする単語のリスト
        page: ページ番号
        
    Returns:
        マージされた行データ
    """
    # テキストを結合（スペースで区切る）
    merged_text = " ".join(word["text"] for word in words)
    
    # 日本語の場合はスペースを除去
    if any(ord(char) > 0x3000 for char in merged_text):
        merged_text = "".join(word["text"] for word in words)
    
    # BBoxを計算
    min_x = min(word["bbox"][0] for word in words)
    min_y = min(word["bbox"][1] for word in words)
    max_x = max(word["bbox"][0] + word["bbox"][2] for word in words)
    max_y = max(word["bbox"][1] + word["bbox"][3] for word in words)
    
    return {
        "text": merged_text,
        "bbox": [min_x, min_y, max_x - min_x, max_y - min_y],
        "page": page,
        "word_count": len(words),
        "is_azure_line": True
    }

def group_lines_to_paragraphs(lines: List[Dict[str, Any]], 
                            paragraph_gap: float = 15.0) -> List[Dict[str, Any]]:
    """行データをパラグラフ単位にグループ化
    
    Args:
        lines: 行データのリスト
        paragraph_gap: パラグラフ間の最小ギャップ
        
    Returns:
        パラグラフ単位にグループ化されたデータのリスト
    """
    if not lines:
        return []
    
    # ページごとに処理
    pages = {}
    for line in lines:
        page = line["page"]
        if page not in pages:
            pages[page] = []
        pages[page].append(line)
    
    paragraphs = []
    
    for page_num in sorted(pages.keys()):
        page_lines = pages[page_num]
        page_lines.sort(key=lambda x: x["bbox"][1])
        
        current_paragraph = []
        last_y_end = None
        
        for line in page_lines:
            line_y = line["bbox"][1]
            
            if current_paragraph and last_y_end:
                # 前の行との間隔をチェック
                gap = line_y - last_y_end
                
                if gap > paragraph_gap:
                    # パラグラフを確定
                    merged_para = merge_lines_to_paragraph(current_paragraph, page_num)
                    paragraphs.append(merged_para)
                    current_paragraph = [line]
                else:
                    current_paragraph.append(line)
            else:
                current_paragraph = [line]
            
            last_y_end = line["bbox"][1] + line["bbox"][3]
        
        # 最後のパラグラフを追加
        if current_paragraph:
            merged_para = merge_lines_to_paragraph(current_paragraph, page_num)
            paragraphs.append(merged_para)
    
    logger.info(f"Grouped {len(lines)} lines into {len(paragraphs)} paragraphs")
    return paragraphs

def merge_lines_to_paragraph(lines: List[Dict[str, Any]], page: int) -> Dict[str, Any]:
    """行のリストを1つのパラグラフにマージ
    
    Args:
        lines: マージする行のリスト
        page: ページ番号
        
    Returns:
        マージされたパラグラフデータ
    """
    # テキストを結合
    merged_text = "\n".join(line["text"] for line in lines)
    
    # BBoxを計算
    min_x = min(line["bbox"][0] for line in lines)
    min_y = min(line["bbox"][1] for line in lines)
    max_x = max(line["bbox"][0] + line["bbox"][2] for line in lines)
    max_y = max(line["bbox"][1] + line["bbox"][3] for line in lines)
    
    total_words = sum(line.get("word_count", 1) for line in lines)
    
    return {
        "text": merged_text,
        "bbox": [min_x, min_y, max_x - min_x, max_y - min_y],
        "page": page,
        "line_count": len(lines),
        "word_count": total_words,
        "is_azure_paragraph": True
    }


def group_japanese_characters_to_words(word_list: List[Any]) -> List[Dict[str, Any]]:
    """Azure Document Intelligenceの日本語文字データを意味的な単語にグループ化
    
    Args:
        word_list: 文字レベルのBBoxデータのリスト（辞書またはBBoxTextDataオブジェクト）
        
    Returns:
        意味的な単語にグループ化されたBBoxデータのリスト
    """
    if not word_list:
        return []
    
    # 入力データを辞書形式に変換
    dict_list = []
    for item in word_list:
        if hasattr(item, 'bbox'):  # BBoxTextDataオブジェクトの場合
            dict_list.append({
                'text': item.text,
                'bbox': item.bbox,
                'page': item.page
            })
        else:  # すでに辞書の場合
            dict_list.append(item)
    
    # ページごとにグループ化
    pages = {}
    for char_data in dict_list:
        page = char_data["page"]
        if page not in pages:
            pages[page] = []
        pages[page].append(char_data)
    
    grouped_words = []
    
    # 各ページで単語をグループ化
    for page_num in sorted(pages.keys()):
        page_chars = pages[page_num]
        
        # 位置でソート（Y座標、次にX座標）
        page_chars.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
        
        # 同じ行のグループを作成
        lines = []
        current_line = []
        current_y = None
        line_tolerance = 5.0  # Y座標の許容誤差
        
        for char in page_chars:
            char_y = char["bbox"][1]
            
            if current_line and current_y is not None:
                if abs(char_y - current_y) <= line_tolerance:
                    current_line.append(char)
                else:
                    lines.append(current_line)
                    current_line = [char]
                    current_y = char_y
            else:
                current_line = [char]
                current_y = char_y
        
        if current_line:
            lines.append(current_line)
        
        # 各行内で意味的な単語にグループ化
        for line in lines:
            # X座標でソート
            line.sort(key=lambda x: x["bbox"][0])
            
            words_in_line = group_line_chars_to_words(line, page_num)
            grouped_words.extend(words_in_line)
    
    logger.info(f"Grouped {len(word_list)} characters into {len(grouped_words)} semantic words")
    return grouped_words


def group_line_chars_to_words(chars: List[Dict[str, Any]], page: int) -> List[Dict[str, Any]]:
    """行内の文字を意味的な単語にグループ化
    
    Args:
        chars: 同じ行の文字データのリスト
        page: ページ番号
        
    Returns:
        意味的な単語にグループ化されたデータのリスト
    """
    if not chars:
        return []
    
    # 文字間の距離の閾値（文字サイズに基づいて動的に計算）
    avg_char_width = sum(c["bbox"][2] for c in chars) / len(chars)
    max_char_gap = avg_char_width * 0.3  # 文字幅の30%以内なら同じ単語
    
    grouped_words = []
    current_word_chars = []
    
    for i, char in enumerate(chars):
        if i == 0:
            current_word_chars = [char]
        else:
            prev_char = chars[i-1]
            prev_x_end = prev_char["bbox"][0] + prev_char["bbox"][2]
            curr_x_start = char["bbox"][0]
            gap = curr_x_start - prev_x_end
            
            # 文字種別をチェック
            prev_text = prev_char["text"]
            curr_text = char["text"]
            
            # 同じ単語として結合するかの判定
            should_merge = False
            
            # 1. 距離が近い場合
            if gap <= max_char_gap:
                should_merge = True
            
            # 2. 数字の連続
            elif prev_text.isdigit() and curr_text.isdigit():
                should_merge = True
            
            # 3. アルファベットの連続
            elif is_alpha(prev_text) and is_alpha(curr_text):
                should_merge = True
            
            # 4. カタカナの連続
            elif is_katakana(prev_text) and is_katakana(curr_text):
                should_merge = True
            
            # 5. ひらがなの連続（助詞を考慮）
            elif is_hiragana(prev_text) and is_hiragana(curr_text):
                # 助詞の後で区切る
                if not is_particle(prev_text):
                    should_merge = True
            
            if should_merge:
                current_word_chars.append(char)
            else:
                # 現在の単語を確定
                if current_word_chars:
                    word = merge_chars_to_word(current_word_chars, page)
                    grouped_words.append(word)
                current_word_chars = [char]
    
    # 最後の単語を追加
    if current_word_chars:
        word = merge_chars_to_word(current_word_chars, page)
        grouped_words.append(word)
    
    return grouped_words


def merge_chars_to_word(chars: List[Dict[str, Any]], page: int) -> Dict[str, Any]:
    """文字のリストを1つの単語にマージ
    
    Args:
        chars: マージする文字のリスト
        page: ページ番号
        
    Returns:
        マージされた単語データ
    """
    # テキストを結合
    merged_text = "".join(char["text"] for char in chars)
    
    # BBoxを計算
    min_x = min(char["bbox"][0] for char in chars)
    min_y = min(char["bbox"][1] for char in chars)
    max_x = max(char["bbox"][0] + char["bbox"][2] for char in chars)
    max_y = max(char["bbox"][1] + char["bbox"][3] for char in chars)
    
    return {
        "text": merged_text,
        "bbox": [min_x, min_y, max_x - min_x, max_y - min_y],
        "page": page,
        "char_count": len(chars),
        "is_semantic_word": True
    }


def is_hiragana(text: str) -> bool:
    """ひらがなかどうかを判定"""
    return all('\u3040' <= char <= '\u309F' for char in text)


def is_katakana(text: str) -> bool:
    """カタカナかどうかを判定"""
    return all('\u30A0' <= char <= '\u30FF' for char in text)


def is_alpha(text: str) -> bool:
    """アルファベットかどうかを判定"""
    return all(char.isalpha() and ord(char) < 128 for char in text)


def is_particle(text: str) -> bool:
    """助詞かどうかを判定"""
    particles = {'を', 'が', 'は', 'に', 'へ', 'と', 'で', 'や', 'の', 'も', 'から', 'まで', 'より'}
    return text in particles