"""
Simple Output Generator - 文字を囲む形式での差分表示
"""
from typing import List, Tuple, Dict, Optional
from ..models import BBoxTextData, DiffResult, ChangeType
from ..handlers import PyMuPDFService, DocxService, PptxService


class SimpleOutputGenerator:
    """文字を囲む形式での出力ファイル生成"""
    
    def __init__(self):
        self.pdf_handler = PyMuPDFService()
        self.docx_handler = DocxService()
        self.pptx_handler = PptxService()
    
    def generate_comparison_report(self,
                                 file1: bytes,
                                 file2: bytes,
                                 file_type: str,
                                 doc1_bboxes: List[BBoxTextData],
                                 doc2_bboxes: List[BBoxTextData],
                                 differences: List[DiffResult]) -> Tuple[bytes, bytes]:
        """
        比較レポート付きのファイルを生成（文字を囲む形式）
        
        Args:
            file1: 1つ目のファイル
            file2: 2つ目のファイル
            file_type: ファイルタイプ
            doc1_bboxes: 文書1の全bbox
            doc2_bboxes: 文書2の全bbox
            differences: 差分検出結果
            
        Returns:
            差分表示付きの2つのファイル
        """
        # 差分のbboxを抽出
        diff_bboxes1 = []  # 文書1の差分位置
        diff_bboxes2 = []  # 文書2の差分位置
        
        for diff in differences:
            if diff.change_type == ChangeType.DIFFERENCE:
                if diff.original_bbox:
                    diff_bboxes1.append(diff.original_bbox)
                if diff.modified_bbox:
                    diff_bboxes2.append(diff.modified_bbox)
        
        # ファイルタイプに応じて処理
        file_type = file_type.lower()
        
        if file_type == 'pdf':
            # PDFの場合、文字を囲む四角形を追加
            highlighted1 = self._add_text_boxes_to_pdf(file1, diff_bboxes1)
            highlighted2 = self._add_text_boxes_to_pdf(file2, diff_bboxes2)
        elif file_type in ['docx', 'doc']:
            # Word文書の場合、該当テキストに枠線を追加
            highlighted1 = self._add_text_boxes_to_docx(file1, diff_bboxes1)
            highlighted2 = self._add_text_boxes_to_docx(file2, diff_bboxes2)
        elif file_type in ['pptx', 'ppt']:
            # PowerPointの場合、該当テキストに枠線を追加
            highlighted1 = self._add_text_boxes_to_pptx(file1, diff_bboxes1)
            highlighted2 = self._add_text_boxes_to_pptx(file2, diff_bboxes2)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        return highlighted1, highlighted2
    
    def _add_text_boxes_to_pdf(self, pdf_bytes: bytes, diff_bboxes: List[BBoxTextData]) -> bytes:
        """PDFに文字を囲む四角形を追加"""
        import fitz  # PyMuPDF
        
        # PDFを開く
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # 各ページの差分に枠線を追加
        for bbox_data in diff_bboxes:
            page_num = bbox_data['page']
            if page_num < len(pdf_document):
                page = pdf_document[page_num]
                
                # bboxの座標を取得
                x, y, width, height = bbox_data['bbox']
                
                # PyMuPDFの座標系に変換（左上が原点）
                rect = fitz.Rect(x, y, x + width, y + height)
                
                # 赤い枠線を描画（塗りつぶしなし）
                page.draw_rect(rect, color=(1, 0, 0), width=2.0, fill=None)
        
        # PDFをバイト列として取得
        return pdf_document.tobytes()
    
    def _add_text_boxes_to_docx(self, docx_bytes: bytes, diff_bboxes: List[BBoxTextData]) -> bytes:
        """Word文書に文字を囲む枠線を追加（簡易実装）"""
        # 現在は元のファイルをそのまま返す
        # TODO: python-docxを使用して実装
        return docx_bytes
    
    def _add_text_boxes_to_pptx(self, pptx_bytes: bytes, diff_bboxes: List[BBoxTextData]) -> bytes:
        """PowerPointに文字を囲む枠線を追加（簡易実装）"""
        # 現在は元のファイルをそのまま返す
        # TODO: python-pptxを使用して実装
        return pptx_bytes
    
    def generate_diff_csv(self, differences: List[DiffResult], output_path: str):
        """差分をCSV形式で出力（単純化版）"""
        import csv
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['番号', 'ページ', 'テキスト', 'タイプ'])
            
            for i, diff in enumerate(differences):
                if diff.original_bbox:
                    writer.writerow([
                        i + 1,
                        diff.original_bbox['page'],
                        diff.original_bbox['text'],
                        '文書1の差分'
                    ])
                if diff.modified_bbox:
                    writer.writerow([
                        i + 1,
                        diff.modified_bbox['page'],
                        diff.modified_bbox['text'],
                        '文書2の差分'
                    ])
    
    def generate_side_by_side_pdf(self, 
                                  file1: bytes, 
                                  file2: bytes,
                                  diff_bboxes1: List[BBoxTextData],
                                  diff_bboxes2: List[BBoxTextData],
                                  max_pages: Optional[int] = None) -> bytes:
        """
        2つのPDFを並べて表示する新しいPDFを生成
        注: file1とfile2は既にハイライト（赤枠）が追加されたPDFである必要があります
        
        Args:
            file1: 1つ目のPDFファイル（ハイライト付き）
            file2: 2つ目のPDFファイル（ハイライト付き）
            diff_bboxes1: 文書1の差分位置（未使用）
            diff_bboxes2: 文書2の差分位置（未使用）
            max_pages: 最大ページ数（Noneの場合は全ページ）
            
        Returns:
            並列表示されたPDFのバイト列
        """
        import fitz  # PyMuPDF
        
        # PDFを開く
        pdf1 = fitz.open(stream=file1, filetype="pdf")
        pdf2 = fitz.open(stream=file2, filetype="pdf")
        
        # 新しいPDFを作成
        output_pdf = fitz.open()
        
        # ページ数を決定
        if max_pages is None:
            max_pages = max(len(pdf1), len(pdf2))
        else:
            max_pages = min(max_pages, max(len(pdf1), len(pdf2)))
        
        # 各ページを処理
        for page_idx in range(max_pages):
            # 左右のページを取得
            left_page = pdf1[page_idx] if page_idx < len(pdf1) else None
            right_page = pdf2[page_idx] if page_idx < len(pdf2) else None
            
            if left_page is None and right_page is None:
                continue
            
            # ページサイズを計算（A4の2倍幅）
            page_width = 595 * 2 + 20  # A4幅 * 2 + 間隔
            page_height = 842  # A4高さ
            
            # 新しいページを作成
            new_page = output_pdf.new_page(width=page_width, height=page_height)
            
            # 左側のページを配置
            if left_page:
                # ページラベルを追加
                label_rect = fitz.Rect(10, 10, 300, 30)
                new_page.insert_textbox(label_rect, f"2023年版 - ページ {page_idx + 1}",
                                      fontsize=12, fontname="helv", 
                                      color=(0, 0, 0))
                
                # ページコンテンツを配置（ハイライト付きPDFをそのまま表示）
                left_rect = fitz.Rect(0, 40, 595, page_height)
                new_page.show_pdf_page(left_rect, pdf1, page_idx)
            
            # 右側のページを配置
            if right_page:
                # ページラベルを追加
                label_rect = fitz.Rect(615, 10, 915, 30)
                new_page.insert_textbox(label_rect, f"2024年版 - ページ {page_idx + 1}",
                                      fontsize=12, fontname="helv", 
                                      color=(0, 0, 0))
                
                # ページコンテンツを配置（ハイライト付きPDFをそのまま表示）
                right_rect = fitz.Rect(615, 40, 615 + 595, page_height)
                new_page.show_pdf_page(right_rect, pdf2, page_idx)
        
        # PDFをバイト列として返す
        return output_pdf.tobytes()