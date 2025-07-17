"""
Azure Document Intelligenceサービス
"""
from typing import List, Optional, Dict, Any
import logging
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential

from ..config.settings import settings
from ..models.bbox_models import BBoxTextData

logger = logging.getLogger(__name__)


class AzureDocumentService:
    """Azure Document Intelligenceサービス"""
    
    def __init__(self):
        """初期化"""
        if not settings.USE_AZURE_FOR_OCR:
            logger.info("Azure Document Intelligence is disabled")
            self.client = None
            return
            
        if not settings.AZURE_DOCUMENT_INTELLIGENCE_KEY or not settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT:
            raise ValueError(
                "Azure Document Intelligence credentials are not set. "
                "Please set AZURE_DOCUMENT_INTELLIGENCE_KEY and AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
            )
        
        self.client = DocumentIntelligenceClient(
            endpoint=settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_DOCUMENT_INTELLIGENCE_KEY)
        )
    
    def extract_layout_from_pdf(self, pdf_bytes: bytes) -> List[BBoxTextData]:
        """PDFからレイアウト情報を抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            BBoxTextDataのリスト
        """
        if not self.client:
            raise RuntimeError("Azure Document Intelligence is not configured")
        
        try:
            # Document Intelligenceでレイアウト解析
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                document=pdf_bytes,
                content_type="application/pdf"
            )
            result: AnalyzeResult = poller.result()
            
            bbox_data_list = []
            
            # ページごとに処理
            for page_idx, page in enumerate(result.pages):
                # 単語単位で抽出
                for word in page.words:
                    # バウンディングボックスを正規化
                    # Azure returns points, we need [x, y, width, height]
                    points = word.bounding_regions[0].polygon
                    x_coords = [p.x for p in points]
                    y_coords = [p.y for p in points]
                    
                    x_min = min(x_coords)
                    y_min = min(y_coords)
                    width = max(x_coords) - x_min
                    height = max(y_coords) - y_min
                    
                    bbox_data = BBoxTextData(
                        bbox=[x_min, y_min, width, height],
                        text=word.content,
                        page=page_idx
                    )
                    bbox_data_list.append(bbox_data)
            
            logger.info(f"Extracted {len(bbox_data_list)} words from {len(result.pages)} pages")
            return bbox_data_list
            
        except Exception as e:
            logger.error(f"Azure Document Intelligence extraction failed: {e}")
            raise
    
    def extract_tables(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """PDFから表を抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            表情報のリスト
        """
        if not self.client:
            return []
        
        try:
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                document=pdf_bytes,
                content_type="application/pdf"
            )
            result: AnalyzeResult = poller.result()
            
            tables = []
            for table in result.tables:
                table_info = {
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": [],
                    "page": table.bounding_regions[0].page_number - 1  # 0-indexed
                }
                
                for cell in table.cells:
                    cell_info = {
                        "row": cell.row_index,
                        "column": cell.column_index,
                        "text": cell.content,
                        "row_span": cell.row_span or 1,
                        "column_span": cell.column_span or 1
                    }
                    table_info["cells"].append(cell_info)
                
                tables.append(table_info)
            
            logger.info(f"Extracted {len(tables)} tables")
            return tables
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return []
    
    def extract_key_value_pairs(self, pdf_bytes: bytes) -> Dict[str, str]:
        """PDFからキーバリューペアを抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            キーバリューペアの辞書
        """
        if not self.client:
            return {}
        
        try:
            poller = self.client.begin_analyze_document(
                "prebuilt-document",
                document=pdf_bytes,
                content_type="application/pdf"
            )
            result: AnalyzeResult = poller.result()
            
            key_values = {}
            for kv_pair in result.key_value_pairs:
                if kv_pair.key and kv_pair.value:
                    key = kv_pair.key.content
                    value = kv_pair.value.content
                    key_values[key] = value
            
            logger.info(f"Extracted {len(key_values)} key-value pairs")
            return key_values
            
        except Exception as e:
            logger.error(f"Key-value extraction failed: {e}")
            return {}