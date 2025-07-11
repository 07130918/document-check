"""
Reading Order Estimator - 文章単位での読み順序推定
"""
from typing import List, Dict, Tuple
from ..models import BBoxTextData


class ReadingOrderEstimator:
    """座標ベースの読み順序推定システム"""
    
    def __init__(self, 
                 line_threshold: float = 5.0,
                 column_threshold: float = 50.0,
                 paragraph_threshold: float = 15.0):
        """
        Args:
            line_threshold: 同一行判定の閾値
            column_threshold: カラム分離の閾値
            paragraph_threshold: 段落分離の閾値
        """
        self.line_threshold = line_threshold
        self.column_threshold = column_threshold
        self.paragraph_threshold = paragraph_threshold
    
    def estimate_reading_order(self, bbox_data_list: List[BBoxTextData]) -> List[BBoxTextData]:
        """
        読み順序を推定（文章単位）
        
        Args:
            bbox_data_list: bbox_text_dataのリスト
            
        Returns:
            読み順序でソートされたbbox_text_dataのリスト
        """
        if not bbox_data_list:
            return []
        
        # ページごとに処理
        pages = self._group_by_page(bbox_data_list)
        ordered_data = []
        
        for page_num in sorted(pages.keys()):
            page_data = pages[page_num]
            
            # 単語を文章にグルーピング
            sentences = self._group_into_sentences(page_data)
            
            # 文章単位で読み順序をソート
            ordered_sentences = self._sort_sentences(sentences)
            
            # 文章内の単語を元の順序で追加
            for sentence in ordered_sentences:
                ordered_data.extend(sentence)
        
        return ordered_data
    
    def _group_by_page(self, bbox_list: List[BBoxTextData]) -> Dict[int, List[BBoxTextData]]:
        """ページごとにグルーピング"""
        pages = {}
        for bbox_data in bbox_list:
            page = bbox_data['page']
            if page not in pages:
                pages[page] = []
            pages[page].append(bbox_data)
        return pages
    
    def _group_into_sentences(self, page_data: List[BBoxTextData]) -> List[List[BBoxTextData]]:
        """
        単語を文章にグルーピング
        
        Args:
            page_data: 1ページ分のbbox_text_data
            
        Returns:
            文章ごとにグループ化されたリスト
        """
        if not page_data:
            return []
        
        # y座標でソートしてから処理
        sorted_data = sorted(page_data, key=lambda d: (d['bbox'][1], d['bbox'][0]))
        
        sentences = []
        current_sentence = [sorted_data[0]]
        
        for i in range(1, len(sorted_data)):
            prev_bbox = sorted_data[i-1]
            curr_bbox = sorted_data[i]
            
            # 文章の区切り判定
            if self._is_sentence_break(prev_bbox, curr_bbox):
                sentences.append(current_sentence)
                current_sentence = [curr_bbox]
            else:
                current_sentence.append(curr_bbox)
        
        # 最後の文章を追加
        if current_sentence:
            sentences.append(current_sentence)
        
        return sentences
    
    def _is_sentence_break(self, prev_bbox: BBoxTextData, curr_bbox: BBoxTextData) -> bool:
        """
        文章の区切りかどうかを判定
        
        Args:
            prev_bbox: 前の単語のbbox
            curr_bbox: 現在の単語のbbox
            
        Returns:
            文章の区切りならTrue
        """
        # y座標の差
        y_diff = abs(curr_bbox['bbox'][1] - prev_bbox['bbox'][1])
        
        # x座標（左端の位置）
        prev_right = prev_bbox['bbox'][0] + prev_bbox['bbox'][2]
        curr_left = curr_bbox['bbox'][0]
        x_diff = curr_left - prev_right
        
        # 段落変更（大きなy座標の差）
        if y_diff > self.paragraph_threshold:
            return True
        
        # 異なる行で、かつカラムが異なる
        if y_diff > self.line_threshold and x_diff > self.column_threshold:
            return True
        
        # 句読点での区切り
        if prev_bbox['text'].endswith(('。', '！', '？')):
            return True
        
        # 同一行でも大きな間隔がある場合
        if y_diff <= self.line_threshold and x_diff > self.column_threshold * 2:
            return True
        
        return False
    
    def _sort_sentences(self, sentences: List[List[BBoxTextData]]) -> List[List[BBoxTextData]]:
        """
        文章を読み順序でソート（明治プロジェクトのアルゴリズムを参考に改良）
        
        Args:
            sentences: 文章のリスト
            
        Returns:
            ソートされた文章のリスト
        """
        if not sentences:
            return []
        
        # 各文章の代表座標を計算（最初の単語の座標を使用）
        sentence_positions = []
        for sentence in sentences:
            if sentence:
                first_word = sentence[0]
                # (y座標, x座標, 文章)のタプル
                sentence_positions.append((
                    first_word['bbox'][1],
                    first_word['bbox'][0],
                    sentence
                ))
        
        # Y軸でソート
        sentence_positions.sort(key=lambda x: x[0])
        
        # Y軸の近接グループ化（3.2ピクセル以内は同じ行として扱う）
        y_groups = []
        y_threshold = 3.2  # 明治プロジェクトと同じ閾値
        
        for pos in sentence_positions:
            y_coord = pos[0]
            added_to_group = False
            
            # 既存のグループに追加できるか確認
            for group in y_groups:
                if group and abs(group[0][0] - y_coord) < y_threshold:
                    group.append(pos)
                    added_to_group = True
                    break
            
            # 新しいグループを作成
            if not added_to_group:
                y_groups.append([pos])
        
        # 各グループ内でX軸ソート
        ordered_sentences = []
        for group in y_groups:
            # X座標でソート
            group.sort(key=lambda x: x[1])
            # 文章を追加
            ordered_sentences.extend([item[2] for item in group])
        
        return ordered_sentences
    
    def _detect_columns(self, sentence_positions: List[Tuple[float, float, List]]) -> List[List[Tuple]]:
        """
        カラムレイアウトを検出
        
        Args:
            sentence_positions: (y, x, sentence)のタプルのリスト
            
        Returns:
            カラムごとに分けられたリスト
        """
        if not sentence_positions:
            return []
        
        # x座標でクラスタリング
        columns = []
        for pos in sentence_positions:
            x = pos[1]
            
            # 既存のカラムに割り当て
            assigned = False
            for column in columns:
                if column:
                    column_x = sum(p[1] for p in column) / len(column)
                    if abs(x - column_x) < self.column_threshold:
                        column.append(pos)
                        assigned = True
                        break
            
            # 新しいカラムを作成
            if not assigned:
                columns.append([pos])
        
        # x座標順にカラムをソート
        columns.sort(key=lambda c: sum(p[1] for p in c) / len(c))
        
        return columns
    
    def get_sentence_reading_order(self, bbox_data_list: List[BBoxTextData]) -> List[dict]:
        """
        文章単位の読み順序情報を取得（番号付けのため）
        
        Args:
            bbox_data_list: bbox_text_dataのリスト
            
        Returns:
            読み順序情報のリスト
            各要素: {'page': int, 'bbox': [x, y, w, h], 'order': int, 'text': str}
        """
        if not bbox_data_list:
            return []
        
        # ページごとに処理
        pages = self._group_by_page(bbox_data_list)
        reading_order_info = []
        global_order = 1
        
        for page_num in sorted(pages.keys()):
            page_data = pages[page_num]
            
            # 単語を文章にグルーピング
            sentences = self._group_into_sentences(page_data)
            
            # 文章単位で読み順序をソート
            ordered_sentences = self._sort_sentences(sentences)
            
            # 各文章の情報を記録
            for sentence in ordered_sentences:
                if sentence:
                    # 文章全体のbboxを計算
                    min_x = min(word['bbox'][0] for word in sentence)
                    min_y = min(word['bbox'][1] for word in sentence)
                    max_x = max(word['bbox'][0] + word['bbox'][2] for word in sentence)
                    max_y = max(word['bbox'][1] + word['bbox'][3] for word in sentence)
                    
                    # 文章のテキスト
                    sentence_text = ''.join(word['text'] for word in sentence)
                    
                    reading_order_info.append({
                        'page': page_num,
                        'bbox': [min_x, min_y, max_x - min_x, max_y - min_y],
                        'order': global_order,
                        'text': sentence_text
                    })
                    
                    global_order += 1
        
        return reading_order_info
    
    def get_original_order_info(self, bbox_data_list: List[BBoxTextData]) -> List[dict]:
        """
        順序変換前（元の抽出順序）の情報を取得
        
        Args:
            bbox_data_list: bbox_text_dataのリスト
            
        Returns:
            元の順序情報のリスト
            各要素: {'page': int, 'bbox': [x, y, w, h], 'order': int, 'text': str}
        """
        if not bbox_data_list:
            return []
        
        # ページごとに処理
        pages = self._group_by_page(bbox_data_list)
        original_order_info = []
        
        for page_num in sorted(pages.keys()):
            page_data = pages[page_num]
            
            # 単語を文章にグルーピング（元の順序を保持）
            sentences = self._group_into_sentences_original_order(page_data)
            
            # 元の順序で番号付け
            for i, sentence in enumerate(sentences):
                if sentence:
                    # 文章全体のbboxを計算
                    min_x = min(word['bbox'][0] for word in sentence)
                    min_y = min(word['bbox'][1] for word in sentence)
                    max_x = max(word['bbox'][0] + word['bbox'][2] for word in sentence)
                    max_y = max(word['bbox'][1] + word['bbox'][3] for word in sentence)
                    
                    # 文章のテキスト
                    sentence_text = ''.join(word['text'] for word in sentence)
                    
                    original_order_info.append({
                        'page': page_num,
                        'bbox': [min_x, min_y, max_x - min_x, max_y - min_y],
                        'order': len(original_order_info) + 1,  # 1から始まる連番
                        'text': sentence_text
                    })
        
        return original_order_info
    
    def _group_into_sentences_original_order(self, page_data: List[BBoxTextData]) -> List[List[BBoxTextData]]:
        """
        単語を文章にグルーピング（元の順序を保持）
        
        Args:
            page_data: 1ページ分のbbox_text_data
            
        Returns:
            文章ごとにグループ化されたリスト（元の順序のまま）
        """
        if not page_data:
            return []
        
        # 元の順序のまま処理（ソートしない）
        sentences = []
        current_sentence = [page_data[0]]
        
        for i in range(1, len(page_data)):
            prev_bbox = page_data[i-1]
            curr_bbox = page_data[i]
            
            # 文章の区切り判定
            if self._is_sentence_break(prev_bbox, curr_bbox):
                sentences.append(current_sentence)
                current_sentence = [curr_bbox]
            else:
                current_sentence.append(curr_bbox)
        
        # 最後の文章を追加
        if current_sentence:
            sentences.append(current_sentence)
        
        return sentences