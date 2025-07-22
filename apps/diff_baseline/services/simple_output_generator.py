"""
Simple Output Generator - 文字を囲む形式での差分表示
"""
from typing import List, Tuple, Dict
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
                page.draw_rect(rect, color=(1, 0, 0), width=1.5)
        
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