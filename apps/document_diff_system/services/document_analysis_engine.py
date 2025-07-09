"""
Document Analysis Engine - Extract bbox_text_data from various document formats
"""
from typing import List, Dict, Union
import fitz  # PyMuPDF
from pathlib import Path
from ..models import BBoxTextData
from ..handlers import PyMuPDFService, DocxService, PptxService


class DocumentAnalysisEngine:
    """文書解析エンジン - PDF/Word/PowerPointからbbox_text_dataを抽出"""
    
    def __init__(self, max_pages: int = None):
        self.pdf_service = PyMuPDFService()
        self.docx_service = DocxService()
        self.pptx_service = PptxService()
        self.max_pages = max_pages
    
    def extract_bbox_text_data(self, file_bytes: bytes, file_type: str) -> List[BBoxTextData]:
        """
        ファイルからbbox_text_dataリストを抽出
        
        Args:
            file_bytes: ファイルのバイトデータ
            file_type: ファイルタイプ ("pdf", "docx", "pptx")
            
        Returns:
            bbox_text_dataのリスト
        """
        file_type = file_type.lower()
        
        if file_type == 'pdf':
            return self.pdf_service.extract_bbox_data(file_bytes, max_pages=self.max_pages)
        elif file_type in ['docx', 'doc']:
            return self.docx_service.extract_bbox_data(file_bytes)
        elif file_type in ['pptx', 'ppt']:
            return self.pptx_service.extract_bbox_data(file_bytes)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def process_pages(self, bbox_data_list: List[BBoxTextData]) -> Dict[int, List[BBoxTextData]]:
        """
        bbox_text_dataをページ単位で処理
        
        Args:
            bbox_data_list: bbox_text_dataのリスト
            
        Returns:
            ページ番号をキーとする辞書
        """
        pages = {}
        for bbox_data in bbox_data_list:
            page = bbox_data['page']
            if page not in pages:
                pages[page] = []
            pages[page].append(bbox_data)
        return pages
    
    def extract_from_file(self, file_path: Union[str, Path]) -> List[BBoxTextData]:
        """
        ファイルパスからbbox_text_dataを抽出（ユーティリティメソッド）
        
        Args:
            file_path: ファイルパス
            
        Returns:
            bbox_text_dataのリスト
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # ファイルタイプを拡張子から判定
        file_type = file_path.suffix.lower().lstrip('.')
        
        # ファイルを読み込み
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        
        return self.extract_bbox_text_data(file_bytes, file_type)