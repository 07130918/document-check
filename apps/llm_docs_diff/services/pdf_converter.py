"""
PDF変換サービス
"""
from abc import ABC, abstractmethod
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PDFConverter(ABC):
    """PDF変換の抽象基底クラス"""
    
    @abstractmethod
    def convert_to_pdf(self, file_bytes: bytes, file_type: str) -> bytes:
        """ファイルをPDFに変換"""
        pass


class LibreOfficePDFConverter(PDFConverter):
    """LibreOfficeを使用したPDF変換"""
    
    def __init__(self, libreoffice_path: str = "libreoffice"):
        """初期化
        
        Args:
            libreoffice_path: LibreOfficeの実行パス
        """
        self.libreoffice_path = libreoffice_path
        self._check_libreoffice()
    
    def _check_libreoffice(self):
        """LibreOfficeがインストールされているか確認"""
        try:
            subprocess.run([self.libreoffice_path, "--version"], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning(
                "LibreOffice not found. Please install LibreOffice for "
                "Word/PowerPoint to PDF conversion."
            )
    
    def convert_to_pdf(self, file_bytes: bytes, file_type: str) -> bytes:
        """LibreOfficeを使用してPDFに変換
        
        Args:
            file_bytes: 変換するファイルのバイトデータ
            file_type: ファイルタイプ (docx, pptx など)
            
        Returns:
            PDFのバイトデータ
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # 入力ファイルを一時保存
            input_file = os.path.join(temp_dir, f"input.{file_type}")
            with open(input_file, 'wb') as f:
                f.write(file_bytes)
            
            try:
                # LibreOfficeでPDFに変換
                cmd = [
                    self.libreoffice_path,
                    '--headless',
                    '--convert-to', 'pdf',
                    '--outdir', temp_dir,
                    input_file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise RuntimeError(
                        f"LibreOffice conversion failed: {result.stderr}"
                    )
                
                # 変換されたPDFを読み込み
                pdf_file = os.path.join(temp_dir, "input.pdf")
                if not os.path.exists(pdf_file):
                    raise FileNotFoundError(
                        f"Converted PDF not found at {pdf_file}"
                    )
                
                with open(pdf_file, 'rb') as f:
                    return f.read()
                    
            except Exception as e:
                logger.error(f"PDF conversion failed: {e}")
                raise


class SpirePDFConverter(PDFConverter):
    """Spire.Doc/Spire.Presentationを使用したPDF変換（商用）"""
    
    def __init__(self):
        """初期化"""
        self._check_spire()
    
    def _check_spire(self):
        """Spireライブラリがインストールされているか確認"""
        try:
            if hasattr(self, '_spire_doc_available'):
                return
            
            # Spire.Docのチェック
            try:
                import spire.doc
                self._spire_doc_available = True
            except ImportError:
                self._spire_doc_available = False
                logger.warning("Spire.Doc not available for Word conversion")
            
            # Spire.Presentationのチェック
            try:
                import spire.presentation
                self._spire_presentation_available = True
            except ImportError:
                self._spire_presentation_available = False
                logger.warning("Spire.Presentation not available for PowerPoint conversion")
                
        except Exception as e:
            logger.error(f"Error checking Spire libraries: {e}")
            self._spire_doc_available = False
            self._spire_presentation_available = False
    
    def convert_to_pdf(self, file_bytes: bytes, file_type: str) -> bytes:
        """Spireライブラリを使用してPDFに変換
        
        Args:
            file_bytes: 変換するファイルのバイトデータ
            file_type: ファイルタイプ (docx, pptx)
            
        Returns:
            PDFのバイトデータ
        """
        import io
        
        if file_type == 'docx':
            if not self._spire_doc_available:
                raise RuntimeError("Spire.Doc is not available")
            
            from spire.doc import Document, FileFormat
            
            doc = Document()
            doc.LoadFromStream(io.BytesIO(file_bytes))
            
            output_stream = io.BytesIO()
            doc.SaveToStream(output_stream, FileFormat.PDF)
            return output_stream.getvalue()
            
        elif file_type == 'pptx':
            if not self._spire_presentation_available:
                raise RuntimeError("Spire.Presentation is not available")
            
            from spire.presentation import Presentation, FileFormat
            
            ppt = Presentation()
            ppt.LoadFromStream(io.BytesIO(file_bytes))
            
            output_stream = io.BytesIO()
            ppt.SaveToStream(output_stream, FileFormat.PDF)
            return output_stream.getvalue()
            
        else:
            raise ValueError(f"Unsupported file type: {file_type}")


class PDFConverterFactory:
    """PDF変換器のファクトリクラス"""
    
    @staticmethod
    def create_converter(converter_type: str = "libreoffice") -> PDFConverter:
        """PDF変換器を作成
        
        Args:
            converter_type: 変換器のタイプ ("libreoffice" or "spire")
            
        Returns:
            PDFConverterインスタンス
        """
        if converter_type == "libreoffice":
            return LibreOfficePDFConverter()
        elif converter_type == "spire":
            return SpirePDFConverter()
        else:
            raise ValueError(f"Unknown converter type: {converter_type}")