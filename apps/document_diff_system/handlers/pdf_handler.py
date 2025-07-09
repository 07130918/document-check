"""
PDF Handler using PyMuPDF
"""
from typing import List
import fitz  # PyMuPDF
from ..models import BBoxTextData
from ..utils import MeCabTokenizer


class PyMuPDFService:
    """PyMuPDFを使用したPDF処理サービス"""
    
    def __init__(self):
        self.tokenizer = MeCabTokenizer()
    
    def extract_bbox_data(self, pdf_bytes: bytes, max_pages: int = None) -> List[BBoxTextData]:
        """
        PDFからbbox_text_dataを抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            max_pages: 処理する最大ページ数（デフォルト: None = 全ページ）
            
        Returns:
            bbox_text_dataのリスト
        """
        bbox_data_list = []
        
        # PDFを開く
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            # ページ数の制限
            pages_to_process = len(doc) if max_pages is None else min(len(doc), max_pages)
            
            for page_num in range(pages_to_process):
                page = doc[page_num]
                # get_text("words")で単語単位の情報を取得
                # 戻り値: [(x0, y0, x1, y1, "word", block_no, line_no, word_no), ...]
                words = page.get_text("words")
                
                for word in words:
                    x0, y0, x1, y1 = word[:4]
                    text = word[4]
                    
                    # MeCabで単語分割
                    mecab_words = self.tokenizer.tokenize_with_positions(text)
                    
                    for mecab_word, start_pos, end_pos in mecab_words:
                        # 単語の相対的な位置を計算
                        word_ratio = start_pos / len(text) if text else 0
                        word_width_ratio = (end_pos - start_pos) / len(text) if text else 1
                        
                        # 新しいbboxを計算
                        width = x1 - x0
                        new_x0 = x0 + width * word_ratio
                        new_width = width * word_width_ratio
                        
                        bbox = [new_x0, y0, new_width, y1 - y0]
                        
                        bbox_data = BBoxTextData(
                            bbox=bbox,
                            text=mecab_word,
                            page=page_num
                        )
                        bbox_data_list.append(bbox_data)
        
        finally:
            doc.close()
        
        return bbox_data_list
    
    def add_highlights_to_pdf(self, pdf_bytes: bytes, highlights: List[dict]) -> bytes:
        """
        PDFにハイライトを追加
        
        Args:
            pdf_bytes: 元のPDFバイトデータ
            highlights: ハイライト情報のリスト
            
        Returns:
            ハイライトが追加されたPDFのバイトデータ
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            for highlight in highlights:
                page_num = highlight['page']
                if page_num >= len(doc):
                    continue
                    
                page = doc[page_num]
                bbox = highlight['bbox']
                color = self._get_color_rgb(highlight['color'])
                
                # 矩形領域を作成
                rect = fitz.Rect(bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3])
                
                # ハイライト注釈を追加
                annot = page.add_highlight_annot(rect)
                annot.set_colors(stroke=color)
                # 透過度を80%に設定（opacity = 0.2）
                annot.set_opacity(0.2)
                annot.update()
                
                # ラベルがある場合はテキスト注釈も追加
                if highlight.get('label'):
                    text_point = fitz.Point(bbox[0], bbox[1] - 5)
                    page.insert_text(text_point, highlight['label'], 
                                   fontsize=10, color=(0, 0, 1))  # 青色
            
            # PDFをバイトデータとして保存
            return doc.tobytes()
        
        finally:
            doc.close()
    
    def _get_color_rgb(self, color_name: str) -> tuple:
        """色名をRGB値に変換"""
        colors = {
            'red': (1, 0, 0),
            'green': (0, 1, 0),
            'yellow': (1, 1, 0),
            'blue': (0, 0, 1)
        }
        return colors.get(color_name, (0, 0, 0))
    
    def add_reading_order_numbers(self, pdf_bytes: bytes, reading_order_info: List[dict]) -> bytes:
        """
        PDFに読み順序番号を追加
        
        Args:
            pdf_bytes: 元のPDFバイトデータ
            reading_order_info: 読み順序情報のリスト
                各要素: {'page': int, 'bbox': [x, y, w, h], 'order': int, 'text': str}
            
        Returns:
            読み順序番号が追加されたPDFのバイトデータ
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            for item in reading_order_info:
                page_num = item['page']
                if page_num >= len(doc):
                    continue
                    
                page = doc[page_num]
                bbox = item['bbox']
                order = item['order']
                
                # 番号を表示する位置（bboxの左上）
                number_point = fitz.Point(bbox[0] - 20, bbox[1])
                
                # 番号を挿入（円で囲む）
                # 円の中心
                circle_center = fitz.Point(bbox[0] - 15, bbox[1] + 5)
                circle_radius = 8
                
                # 円を描画
                shape = page.new_shape()
                shape.draw_circle(circle_center, circle_radius)
                shape.finish(fill=(0.9, 0.9, 1.0), color=(0, 0, 1), width=1)
                shape.commit()
                
                # 番号を挿入
                page.insert_text(
                    fitz.Point(circle_center.x - 4, circle_center.y + 3),
                    str(order),
                    fontsize=10,
                    color=(0, 0, 1)  # 青色
                )
                
                # オプション：文章の範囲を薄い青でハイライト
                rect = fitz.Rect(bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3])
                annot = page.add_highlight_annot(rect)
                annot.set_colors(stroke=(0.5, 0.5, 1))  # 薄い青
                annot.set_opacity(0.1)  # とても薄く
                annot.update()
            
            return doc.tobytes()
        
        finally:
            doc.close()