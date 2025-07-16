"""
Output Generator - ハイライト付きファイルの生成
"""
from typing import List, Tuple
from ..models import BBoxTextData, DiffResult, ChangeType, Highlight
from ..handlers import PyMuPDFService, DocxService, PptxService


class OutputGenerator:
    """ハイライト付き出力ファイル生成"""
    
    def __init__(self):
        self.pdf_handler = PyMuPDFService()
        self.docx_handler = DocxService()
        self.pptx_handler = PptxService()
    
    def generate_highlighted_document(self,
                                    original_file: bytes,
                                    file_type: str,
                                    reading_order: List[BBoxTextData],
                                    differences: List[DiffResult]) -> bytes:
        """
        ハイライト付きドキュメントを生成
        
        Args:
            original_file: 元のファイルのバイトデータ
            file_type: ファイルタイプ ("pdf", "docx", "pptx")
            reading_order: 読み順序でソートされたbbox_text_data
            differences: 差分検出結果
            
        Returns:
            ハイライトが追加されたファイルのバイトデータ
        """
        # ハイライト情報を生成
        highlights = []
        
        # 1. 読み順序のハイライト（青色、番号付き）
        reading_highlights = self._create_reading_order_highlights(reading_order)
        highlights.extend(reading_highlights)
        
        # 2. 差分のハイライト（色分け）
        diff_highlights = self._create_diff_highlights(differences)
        highlights.extend(diff_highlights)
        
        # ファイルタイプに応じてハイライトを追加
        file_type = file_type.lower()
        
        if file_type == 'pdf':
            return self.pdf_handler.add_highlights_to_pdf(original_file, highlights)
        elif file_type in ['docx', 'doc']:
            return self.docx_handler.add_highlights_to_docx(original_file, highlights)
        elif file_type in ['pptx', 'ppt']:
            return self.pptx_handler.add_highlights_to_pptx(original_file, highlights)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def _create_reading_order_highlights(self, reading_order: List[BBoxTextData]) -> List[dict]:
        """
        読み順序のハイライトを作成
        
        Args:
            reading_order: 読み順序でソートされたbbox_text_data
            
        Returns:
            ハイライト情報のリスト
        """
        highlights = []
        
        # 文章の開始位置に番号を付ける
        sentence_num = 1
        prev_bbox = None
        
        for i, bbox in enumerate(reading_order):
            # 文章の開始を検出（簡易版）
            is_sentence_start = (i == 0 or 
                               self._is_new_sentence(prev_bbox, bbox) or
                               (i > 0 and reading_order[i-1]['text'].endswith(('。', '！', '？'))))
            
            if is_sentence_start:
                highlight = Highlight(
                    bbox=bbox['bbox'],
                    page=bbox['page'],
                    color='blue',
                    label=str(sentence_num)
                )
                highlights.append(highlight.to_dict())
                sentence_num += 1
            
            prev_bbox = bbox
        
        return highlights
    
    def _is_new_sentence(self, prev_bbox: BBoxTextData, curr_bbox: BBoxTextData) -> bool:
        """文章の区切りを判定（簡易版）"""
        if not prev_bbox:
            return True
        
        # ページが異なる
        if prev_bbox['page'] != curr_bbox['page']:
            return True
        
        # y座標の差が大きい（改行）
        y_diff = abs(curr_bbox['bbox'][1] - prev_bbox['bbox'][1])
        if y_diff > 20:
            return True
        
        return False
    
    def _create_diff_highlights(self, differences: List[DiffResult]) -> List[dict]:
        """
        差分のハイライトを作成
        
        Args:
            differences: 差分検出結果
            
        Returns:
            ハイライト情報のリスト
        """
        highlights = []
        
        for diff in differences:
            if diff.change_type == ChangeType.ADDITION:
                # 追加（緑色）
                if diff.modified_bbox:
                    highlight = Highlight(
                        bbox=diff.modified_bbox['bbox'],
                        page=diff.modified_bbox['page'],
                        color='green'
                    )
                    highlights.append(highlight.to_dict())
            
            elif diff.change_type == ChangeType.DELETION:
                # 削除（赤色）
                if diff.original_bbox:
                    highlight = Highlight(
                        bbox=diff.original_bbox['bbox'],
                        page=diff.original_bbox['page'],
                        color='red'
                    )
                    highlights.append(highlight.to_dict())
            
            elif diff.change_type == ChangeType.MODIFICATION:
                # 修正（黄色）
                if diff.modified_bbox:
                    highlight = Highlight(
                        bbox=diff.modified_bbox['bbox'],
                        page=diff.modified_bbox['page'],
                        color='yellow'
                    )
                    highlights.append(highlight.to_dict())
        
        return highlights
    
    def generate_comparison_report(self,
                                 file1: bytes,
                                 file2: bytes,
                                 file_type: str,
                                 differences: List[DiffResult]) -> Tuple[bytes, bytes]:
        """
        比較レポート付きのファイルを生成（両方のファイルにハイライト）
        
        Args:
            file1: 1つ目のファイル
            file2: 2つ目のファイル
            file_type: ファイルタイプ
            differences: 差分検出結果
            
        Returns:
            ハイライト付きの2つのファイル
        """
        # ファイル1用のハイライト（削除と修正前）
        highlights1 = []
        for diff in differences:
            if diff.change_type == ChangeType.DELETION and diff.original_bbox:
                highlight = Highlight(
                    bbox=diff.original_bbox['bbox'],
                    page=diff.original_bbox['page'],
                    color='red'
                )
                highlights1.append(highlight.to_dict())
            elif diff.change_type == ChangeType.MODIFICATION and diff.original_bbox:
                highlight = Highlight(
                    bbox=diff.original_bbox['bbox'],
                    page=diff.original_bbox['page'],
                    color='yellow'
                )
                highlights1.append(highlight.to_dict())
        
        # ファイル2用のハイライト（追加と修正後）
        highlights2 = []
        for diff in differences:
            if diff.change_type == ChangeType.ADDITION and diff.modified_bbox:
                highlight = Highlight(
                    bbox=diff.modified_bbox['bbox'],
                    page=diff.modified_bbox['page'],
                    color='green'
                )
                highlights2.append(highlight.to_dict())
            elif diff.change_type == ChangeType.MODIFICATION and diff.modified_bbox:
                highlight = Highlight(
                    bbox=diff.modified_bbox['bbox'],
                    page=diff.modified_bbox['page'],
                    color='yellow'
                )
                highlights2.append(highlight.to_dict())
        
        # ハイライトを追加
        file_type = file_type.lower()
        
        if file_type == 'pdf':
            highlighted1 = self.pdf_handler.add_highlights_to_pdf(file1, highlights1)
            highlighted2 = self.pdf_handler.add_highlights_to_pdf(file2, highlights2)
        elif file_type in ['docx', 'doc']:
            highlighted1 = self.docx_handler.add_highlights_to_docx(file1, highlights1)
            highlighted2 = self.docx_handler.add_highlights_to_docx(file2, highlights2)
        elif file_type in ['pptx', 'ppt']:
            highlighted1 = self.pptx_handler.add_highlights_to_pptx(file1, highlights1)
            highlighted2 = self.pptx_handler.add_highlights_to_pptx(file2, highlights2)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        return highlighted1, highlighted2