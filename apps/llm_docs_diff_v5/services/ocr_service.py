"""
Azure Document Intelligence OCRサービス
"""
import logging
import os
from typing import Any, Optional, List, Dict
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

from ..config.settings import settings

logger = logging.getLogger(__name__)


class AzureOCRService:
    """Azure Document IntelligenceのOCRサービス"""
    
    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None):
        """
        Args:
            endpoint: Azure Document IntelligenceのエンドポイントURL
            api_key: APIキー
        """
        self.endpoint = endpoint or settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
        self.api_key = api_key or settings.AZURE_DOCUMENT_INTELLIGENCE_KEY
        
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure Document Intelligence credentials not provided. "
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY environment variables."
            )
        
        self.client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key)
        )
    
    def extract_text_from_pdf(self, pdf_path: str) -> Any:
        """PDFからテキストと構造情報を抽出"""
        logger.info(f"Extracting text from PDF: {pdf_path}")
        
        try:
            # PDFファイルを読み込む
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # Document Intelligenceで解析
            # prebuilt-readモデルを使用（OCRに特化）
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-read",
                body=pdf_content
            )
            
            # 結果を待つ
            result = poller.result()
            
            logger.info(f"Successfully extracted text from {len(result.pages)} pages")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise
    
    def extract_layout_from_pdf(self, pdf_path: str, max_pages: Optional[int] = None) -> Any:
        """PDFからレイアウト情報を含む詳細な構造を抽出"""
        logger.info(f"Extracting layout from PDF: {pdf_path}")
        
        try:
            # PDFファイルを読み込む
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # ファイルサイズをチェック
            file_size_mb = len(pdf_content) / (1024 * 1024)
            logger.info(f"PDF file size: {file_size_mb:.2f} MB")
            
            # max_pagesが明示的に指定されている場合のみページ数を制限
            if max_pages:
                logger.info(f"Limiting PDF to {max_pages} pages")
                pdf_content = self._limit_pdf_pages(pdf_content, max_pages)
                new_size_mb = len(pdf_content) / (1024 * 1024)
                logger.info(f"Reduced PDF size: {new_size_mb:.2f} MB")
            
            # レイアウトモデルを使用（より詳細な構造情報）
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=pdf_content
            )
            
            # 結果を待つ
            result = poller.result()
            
            logger.info(f"Successfully extracted layout from {len(result.pages)} pages")
            logger.info(f"Found {len(result.paragraphs) if hasattr(result, 'paragraphs') else 0} paragraphs")
            logger.info(f"Found {len(result.tables) if hasattr(result, 'tables') else 0} tables")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting layout from PDF: {e}")
            raise
    
    def _limit_pdf_pages(self, pdf_bytes: bytes, max_pages: int) -> bytes:
        """PDFを指定ページ数に制限"""
        try:
            import fitz  # PyMuPDF
            
            # 元のPDFを開く
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # 新しいPDFを作成
            new_pdf = fitz.open()
            
            # 指定ページ数まで複製
            if len(pdf_document) > max_pages:
                new_pdf.insert_pdf(pdf_document, from_page=0, to_page=max_pages-1)
            else:
                new_pdf.insert_pdf(pdf_document)
            
            # バイトデータとして取得
            new_pdf_bytes = new_pdf.tobytes()
            
            # クリーンアップ
            new_pdf.close()
            pdf_document.close()
            
            return new_pdf_bytes
            
        except Exception as e:
            logger.error(f"Error limiting PDF pages: {e}")
            # エラーの場合は元のPDFを返す
            return pdf_bytes
    
    def extract_layout_from_pdf_in_chunks(self, pdf_path: str, pages_per_chunk: int = 2) -> Any:
        """PDFを分割してレイアウト情報を抽出"""
        logger.info(f"Extracting layout from PDF in chunks: {pdf_path}")
        
        try:
            import fitz  # PyMuPDF
            
            # PDFファイルを開く
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            pdf_document.close()
            
            logger.info(f"Total pages in PDF: {total_pages}")
            
            # 結果を格納するための疑似的な結果オブジェクト
            combined_result = type('CombinedResult', (), {
                'pages': [],
                'paragraphs': [],
                'tables': []
            })()
            
            # ページをチャンクに分けて処理
            for start_page in range(0, total_pages, pages_per_chunk):
                end_page = min(start_page + pages_per_chunk, total_pages)
                logger.info(f"Processing pages {start_page + 1} to {end_page}")
                
                # チャンクのPDFを作成
                chunk_pdf_bytes = self._extract_page_range(pdf_path, start_page, end_page)
                
                # チャンクを処理
                try:
                    # レイアウトモデルを使用
                    poller = self.client.begin_analyze_document(
                        model_id="prebuilt-layout",
                        body=chunk_pdf_bytes
                    )
                    
                    # 結果を待つ
                    chunk_result = poller.result()
                    
                    # ページ番号を調整して結果を結合
                    if hasattr(chunk_result, 'pages'):
                        for page in chunk_result.pages:
                            # ページ番号を調整
                            adjusted_page = type(page.__class__.__name__, (), {})()
                            for attr in dir(page):
                                if not attr.startswith('_'):
                                    try:
                                        value = getattr(page, attr)
                                        if attr == 'page_number':
                                            setattr(adjusted_page, attr, value + start_page)
                                        else:
                                            setattr(adjusted_page, attr, value)
                                    except:
                                        pass
                            combined_result.pages.append(adjusted_page)
                    
                    # パラグラフも結合
                    if hasattr(chunk_result, 'paragraphs'):
                        for para in chunk_result.paragraphs:
                            # ページ番号を含むbounding_regionsを調整
                            if hasattr(para, 'bounding_regions'):
                                for region in para.bounding_regions:
                                    if hasattr(region, 'page_number'):
                                        region.page_number += start_page
                            combined_result.paragraphs.append(para)
                    
                    # テーブルも結合
                    if hasattr(chunk_result, 'tables'):
                        for table in chunk_result.tables:
                            # ページ番号を含むbounding_regionsを調整
                            if hasattr(table, 'bounding_regions'):
                                for region in table.bounding_regions:
                                    if hasattr(region, 'page_number'):
                                        region.page_number += start_page
                            combined_result.tables.append(table)
                    
                    logger.info(f"Successfully processed chunk: pages {start_page + 1}-{end_page}")
                    
                except Exception as e:
                    logger.error(f"Error processing chunk {start_page + 1}-{end_page}: {e}")
                    # エラーが発生してもその他のチャンクは処理を続ける
            
            logger.info(f"Successfully extracted layout from {len(combined_result.pages)} pages total")
            logger.info(f"Found {len(combined_result.paragraphs)} paragraphs total")
            logger.info(f"Found {len(combined_result.tables)} tables total")
            
            return combined_result
            
        except Exception as e:
            logger.error(f"Error extracting layout from PDF in chunks: {e}")
            raise
    
    def _extract_page_range(self, pdf_path: str, start_page: int, end_page: int) -> bytes:
        """PDFから特定のページ範囲を抽出"""
        try:
            import fitz  # PyMuPDF
            
            # 元のPDFを開く
            pdf_document = fitz.open(pdf_path)
            
            # 新しいPDFを作成
            new_pdf = fitz.open()
            
            # 指定ページ範囲を複製
            new_pdf.insert_pdf(pdf_document, from_page=start_page, to_page=end_page - 1)
            
            # バイトデータとして取得
            pdf_bytes = new_pdf.tobytes()
            
            # クリーンアップ
            new_pdf.close()
            pdf_document.close()
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error extracting page range: {e}")
            raise