"""
OCRで抽出したテキストをPDF上にハイライトする機能
"""
import fitz  # PyMuPDF
from typing import List, Dict, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PDFHighlighter:
    """PDFにOCR結果をハイライト表示するクラス"""
    
    def __init__(self):
        self.highlight_color = (1, 1, 0)  # 黄色 (R, G, B)
        self.rect_color = (1, 0, 0)  # 赤色 (R, G, B)
        self.rect_width = 1
    
    def highlight_extracted_texts(self, pdf_bytes: bytes, bbox_list: List[Dict], output_path: str, 
                                show_text: bool = False) -> None:
        """
        OCRで抽出したテキストをPDF上にハイライト
        
        Args:
            pdf_bytes: 元のPDFのバイトデータ
            bbox_list: OCRで抽出したテキストのリスト（bbox情報を含む）
            output_path: 出力PDFファイルパス
            show_text: テキストも表示するかどうか
        """
        try:
            # PDFを開く
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # ページごとにテキストをグループ化
            page_texts = {}
            for item in bbox_list:
                page_num = item.get('page', 0)
                if page_num not in page_texts:
                    page_texts[page_num] = []
                page_texts[page_num].append(item)
            
            # 各ページに対してハイライトを追加
            for page_num, texts in page_texts.items():
                if page_num >= len(doc):
                    logger.warning(f"Page {page_num} not found in PDF")
                    continue
                
                page = doc[page_num]
                
                for text_item in texts:
                    # バウンディングボックスを取得
                    bbox = text_item.get('bbox', [])
                    if len(bbox) >= 4:
                        x, y, width, height = bbox[0], bbox[1], bbox[2], bbox[3]
                        
                        # PyMuPDFのRect形式に変換（x0, y0, x1, y1）
                        rect = fitz.Rect(x, y, x + width, y + height)
                        
                        # ハイライト（透明な黄色の矩形）を追加
                        highlight = page.add_rect_annot(rect)
                        highlight.set_colors(stroke=self.rect_color, fill=self.highlight_color)
                        highlight.set_opacity(0.3)
                        highlight.update()
                        
                        # テキストを表示する場合
                        if show_text:
                            text = text_item.get('text', '')
                            if text:
                                # テキストの上に小さく表示
                                font_size = min(8, height * 0.8)
                                text_point = fitz.Point(x, y - 2)
                                page.insert_text(text_point, text[:20] + "..." if len(text) > 20 else text,
                                               fontsize=font_size, color=(0, 0, 1))
                
                # ページ分割の領域情報があれば表示
                if texts and 'source_region' in texts[0]:
                    regions = set(t.get('source_region', 'normal') for t in texts)
                    if regions != {'normal'}:
                        # ページ分割情報を表示
                        page_rect = page.rect
                        for region in regions:
                            if region == 'top':
                                region_rect = fitz.Rect(0, 0, page_rect.width, page_rect.height / 2)
                                color = (0, 0, 1)  # 青
                            elif region == 'bottom':
                                region_rect = fitz.Rect(0, page_rect.height / 2, page_rect.width, page_rect.height)
                                color = (0, 1, 0)  # 緑
                            else:
                                continue
                            
                            # 領域の境界線を描画
                            shape = page.new_shape()
                            shape.draw_rect(region_rect)
                            shape.finish(color=color, width=2, dashes="[5 5]")
                            shape.commit()
            
            # PDFを保存
            doc.save(output_path)
            doc.close()
            
            logger.info(f"Highlighted PDF saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to create highlighted PDF: {e}")
            raise
    
    def create_comparison_pdf(self, pdf_bytes1: bytes, bbox_list1: List[Dict],
                             pdf_bytes2: bytes, bbox_list2: List[Dict],
                             output_path: str) -> None:
        """
        2つの文書のOCR結果を並べて表示
        
        Args:
            pdf_bytes1: 文書1のPDFバイトデータ
            bbox_list1: 文書1のOCR結果
            pdf_bytes2: 文書2のPDFバイトデータ
            bbox_list2: 文書2のOCR結果
            output_path: 出力PDFファイルパス
        """
        try:
            # 一時的に個別のハイライトPDFを作成
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp1:
                self.highlight_extracted_texts(pdf_bytes1, bbox_list1, tmp1.name)
                tmp1_path = tmp1.name
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp2:
                self.highlight_extracted_texts(pdf_bytes2, bbox_list2, tmp2.name)
                tmp2_path = tmp2.name
            
            # 2つのPDFを読み込む
            doc1 = fitz.open(tmp1_path)
            doc2 = fitz.open(tmp2_path)
            
            # 新しいPDFを作成（ページを横に並べる）
            output_doc = fitz.open()
            
            max_pages = max(len(doc1), len(doc2))
            for page_num in range(max_pages):
                # 新しいページを作成（幅2倍）
                if page_num < len(doc1):
                    page1 = doc1[page_num]
                    page_rect = page1.rect
                else:
                    page_rect = fitz.Rect(0, 0, 595, 842)  # A4サイズ
                
                new_page = output_doc.new_page(width=page_rect.width * 2, height=page_rect.height)
                
                # 左側に文書1を配置
                if page_num < len(doc1):
                    new_page.show_pdf_page(fitz.Rect(0, 0, page_rect.width, page_rect.height), 
                                          doc1, page_num)
                
                # 右側に文書2を配置
                if page_num < len(doc2):
                    page2 = doc2[page_num]
                    new_page.show_pdf_page(fitz.Rect(page_rect.width, 0, page_rect.width * 2, page_rect.height),
                                          doc2, page_num)
                
                # ページ番号とラベルを追加
                new_page.insert_text(fitz.Point(10, 20), f"Document 1 - Page {page_num + 1}", 
                                   fontsize=12, color=(0, 0, 0))
                new_page.insert_text(fitz.Point(page_rect.width + 10, 20), f"Document 2 - Page {page_num + 1}",
                                   fontsize=12, color=(0, 0, 0))
            
            # 保存
            output_doc.save(output_path)
            output_doc.close()
            doc1.close()
            doc2.close()
            
            # 一時ファイルを削除
            import os
            os.unlink(tmp1_path)
            os.unlink(tmp2_path)
            
            logger.info(f"Comparison PDF saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to create comparison PDF: {e}")
            raise