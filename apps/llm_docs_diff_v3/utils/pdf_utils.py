"""
PDF処理ユーティリティ
"""
import fitz  # PyMuPDF
import logging
from typing import List, Optional, Tuple
import io

from ..models.bbox_models import BBoxTextData
from ..core.text_preprocessing import TextPreprocessor

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF処理クラス"""
    
    def __init__(self):
        """初期化"""
        self.text_preprocessor = TextPreprocessor()
    
    def extract_bbox_data(self, pdf_bytes: bytes, preprocess: bool = True) -> List[BBoxTextData]:
        """PDFからBBoxデータを抽出
        
        Args:
            pdf_bytes: PDFのバイトデータ
            preprocess: テキスト前処理を行うかどうか
            
        Returns:
            BBoxTextDataのリスト
        """
        bbox_data_list = []
        
        try:
            # バイトデータからPDFを開く
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # 各ページを処理
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # テキストを単語単位で抽出
                words = page.get_text("words")
                
                for word_info in words:
                    # word_info: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                    x0, y0, x1, y1, text, _, _, _ = word_info
                    
                    # 空白文字のみの単語はスキップ
                    if not text.strip():
                        continue
                    
                    bbox_data = {
                        "bbox": [x0, y0, x1 - x0, y1 - y0],  # [x, y, width, height]
                        "text": text,
                        "page": page_num
                    }
                    bbox_data_list.append(bbox_data)
            
            pdf_document.close()
            logger.info(f"Extracted {len(bbox_data_list)} words from PDF")
            
            # 前処理を適用
            if preprocess:
                logger.info("Applying text preprocessing...")
                bbox_data_list = self.text_preprocessor.preprocess_bbox_list(bbox_data_list)
            
            # BBoxTextDataオブジェクトに変換
            bbox_objects = []
            for bbox_dict in bbox_data_list:
                bbox_obj = BBoxTextData(
                    bbox=bbox_dict["bbox"],
                    text=bbox_dict["text"],
                    page=bbox_dict["page"]
                )
                bbox_objects.append(bbox_obj)
            
            logger.info(f"Converted to {len(bbox_objects)} BBoxTextData objects")
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise
        
        return bbox_data_list  # 一時的に辞書のリストを返す
    
    def create_highlighted_pdf(self, pdf_bytes: bytes, 
                             highlights: List[dict]) -> bytes:
        """ハイライト付きPDFを作成
        
        Args:
            pdf_bytes: 元のPDFのバイトデータ
            highlights: ハイライト情報のリスト
            
        Returns:
            ハイライト付きPDFのバイトデータ
        """
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # 色の定義
            color_map = {
                "red": (1, 0, 0),
                "green": (0, 1, 0),
                "yellow": (1, 1, 0),
                "blue": (0, 0, 1)
            }
            
            # ページごとにハイライトをグループ化
            page_highlights = {}
            for highlight in highlights:
                page = highlight.get("page", 0)
                if page not in page_highlights:
                    page_highlights[page] = []
                page_highlights[page].append(highlight)
            
            # 各ページにハイライトを適用
            for page_num, page_hl_list in page_highlights.items():
                if page_num >= len(pdf_document):
                    logger.warning(f"Page {page_num} is out of range (total pages: {len(pdf_document)})")
                    continue
                
                page = pdf_document[page_num]
                logger.debug(f"Processing page {page_num} with {len(page_hl_list)} highlights")
                
                for highlight in page_hl_list:
                    bbox = highlight.get("bbox", [])
                    if len(bbox) != 4:
                        continue
                    
                    # [x, y, width, height] を [x0, y0, x1, y1] に変換
                    x, y, w, h = bbox
                    rect = fitz.Rect(x, y, x + w, y + h)
                    
                    # 色を取得
                    color = color_map.get(highlight.get("color", "yellow"), (1, 1, 0))
                    
                    # ハイライトを追加（透過度を設定）
                    try:
                        highlight_annot = page.add_highlight_annot(rect)
                        highlight_annot.set_colors(stroke=color)
                        highlight_annot.set_opacity(0.3)  # 透過度30%に設定
                        highlight_annot.update()
                    except Exception as e:
                        logger.debug(f"Failed to add highlight at {rect}: {e}")
                    
                    # ラベルがある場合はテキスト注釈を追加
                    label = highlight.get("label")
                    if label:
                        # ラベルの位置も調整（右側に配置）
                        text_point = fitz.Point(x + w + 5, y + h / 2)
                        page.insert_text(
                            text_point,
                            label,
                            fontsize=12,
                            color=(0, 0, 1),  # 青色
                            fontname="helv"  # PyMuPDFの標準フォント
                        )
            
            # PDFをバイトデータに変換
            output_buffer = io.BytesIO()
            pdf_document.save(output_buffer)
            pdf_document.close()
            
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to create highlighted PDF: {e}")
            raise
    
    def get_page_count(self, pdf_bytes: bytes) -> int:
        """PDFのページ数を取得
        
        Args:
            pdf_bytes: PDFのバイトデータ
            
        Returns:
            ページ数
        """
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(pdf_document)
            pdf_document.close()
            return page_count
        except Exception as e:
            logger.error(f"Failed to get page count: {e}")
            return 0
    
    def extract_page_images(self, pdf_bytes: bytes, page_num: int) -> List[bytes]:
        """指定ページから画像を抽出
        
        Args:
            pdf_bytes: PDFのバイトデータ
            page_num: ページ番号（0-indexed）
            
        Returns:
            画像データのリスト
        """
        images = []
        
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            if page_num >= len(pdf_document):
                pdf_document.close()
                return images
            
            page = pdf_document[page_num]
            image_list = page.get_images()
            
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                pix = fitz.Pixmap(pdf_document, xref)
                
                if pix.n - pix.alpha < 4:  # GRAY or RGB
                    img_data = pix.tobytes("png")
                    images.append(img_data)
                else:  # CMYK
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_data = pix.tobytes("png")
                    images.append(img_data)
                
                pix = None
            
            pdf_document.close()
            
        except Exception as e:
            logger.error(f"Failed to extract images: {e}")
        
        return images
    
    def limit_pdf_pages(self, pdf_bytes: bytes, max_pages: int) -> bytes:
        """PDFを指定ページ数に制限
        
        Args:
            pdf_bytes: 元のPDFのバイトデータ
            max_pages: 最大ページ数
            
        Returns:
            制限されたPDFのバイトデータ
        """
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # 新しいPDFドキュメントを作成
            new_pdf = fitz.open()
            
            # 指定ページ数まで複製（PDFの構造を保持する別の方法）
            if len(pdf_document) > max_pages:
                # ページ範囲を指定して一度に挿入
                new_pdf.insert_pdf(pdf_document, from_page=0, to_page=max_pages-1)
            else:
                # 全ページを挿入
                new_pdf.insert_pdf(pdf_document)
            
            # バイトデータに変換（deflateオプションを追加）
            output_buffer = io.BytesIO()
            new_pdf.save(output_buffer, deflate=True, garbage=3, clean=True)
            
            pdf_document.close()
            new_pdf.close()
            
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to limit PDF pages: {e}")
            # エラーの場合は元のPDFを返す
            return pdf_bytes