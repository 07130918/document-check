"""
Azure Document Intelligenceサービス（拡張版）
段落、行、単語の階層構造を保持
"""
from typing import List, Optional, Dict, Any, Union
import logging
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential

from ..config.settings import settings
from ..models.bbox_models import BBoxTextData

logger = logging.getLogger(__name__)


class AzureDocumentServiceEnhanced:
    """Azure Document Intelligenceサービス（拡張版）"""
    
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
    
    def extract_layout_with_hierarchy(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """PDFからレイアウト情報を階層構造で抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            階層構造を持つレイアウト情報
            {
                "paragraphs": 段落情報のリスト,
                "lines": 行情報のリスト,
                "words": 単語情報のリスト,
                "raw_result": 生のAnalyzeResult
            }
        """
        if not self.client:
            raise RuntimeError("Azure Document Intelligence is not configured")
        
        try:
            # PDFサイズをチェックし、大きすぎる場合は最初の5ページのみを処理
            from ..utils.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            
            # 有料版では制限なし - 全ページを処理
            logger.info("Processing all pages with Azure Document Intelligence (paid version)")
            
            # Document Intelligenceでレイアウト解析
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                body=pdf_bytes,
                content_type="application/pdf"
            )
            result: AnalyzeResult = poller.result()
            
            # 階層構造で情報を整理
            hierarchy = {
                "paragraphs": self._extract_paragraphs(result),
                "lines": self._extract_lines(result),
                "words": self._extract_words(result),
                "raw_result": result
            }
            
            logger.info(f"Extracted hierarchy: {len(hierarchy['paragraphs'])} paragraphs, "
                       f"{len(hierarchy['lines'])} lines, {len(hierarchy['words'])} words")
            
            return hierarchy
            
        except Exception as e:
            logger.error(f"Azure Document Intelligence extraction failed: {e}")
            raise
    
    def _extract_paragraphs(self, result: AnalyzeResult) -> List[Dict[str, Any]]:
        """段落情報を抽出"""
        paragraphs = []
        
        if hasattr(result, 'paragraphs') and result.paragraphs:
            for idx, para in enumerate(result.paragraphs):
                para_info = {
                    "id": idx,
                    "content": para.content,
                    "page": para.bounding_regions[0].page_number - 1 if para.bounding_regions else 0,
                    "role": getattr(para, 'role', None),
                }
                
                # バウンディングボックスを計算
                if para.bounding_regions and para.bounding_regions[0].polygon:
                    polygon = para.bounding_regions[0].polygon
                    para_info["bbox"] = self._polygon_to_bbox(polygon)
                
                paragraphs.append(para_info)
        
        return paragraphs
    
    def _extract_lines(self, result: AnalyzeResult) -> List[Dict[str, Any]]:
        """行情報を抽出"""
        lines = []
        line_id = 0
        
        for page_idx, page in enumerate(result.pages):
            if hasattr(page, 'lines') and page.lines:
                for line in page.lines:
                    line_info = {
                        "id": line_id,
                        "content": line.content,
                        "page": page_idx,
                    }
                    
                    # バウンディングボックスを計算
                    if hasattr(line, 'polygon') and line.polygon:
                        line_info["bbox"] = self._polygon_to_bbox(line.polygon)
                    
                    lines.append(line_info)
                    line_id += 1
        
        return lines
    
    def _extract_words(self, result: AnalyzeResult) -> List[BBoxTextData]:
        """単語情報を抽出（既存の形式で）"""
        bbox_data_list = []
        
        for page_idx, page in enumerate(result.pages):
            for word in page.words:
                # バウンディングボックスを正規化
                if hasattr(word, 'polygon') and word.polygon:
                    points = word.polygon
                elif hasattr(word, 'bounding_box') and word.bounding_box:
                    points = word.bounding_box
                else:
                    logger.warning(f"Word without polygon or bounding_box: {word.content}")
                    continue
                
                bbox = self._polygon_to_bbox(points)
                
                bbox_data = BBoxTextData(
                    bbox=bbox,
                    text=word.content,
                    page=page_idx
                )
                bbox_data_list.append(bbox_data)
        
        return bbox_data_list
    
    def _polygon_to_bbox(self, polygon: Union[List[float], List[Any]]) -> List[float]:
        """ポリゴンからバウンディングボックスを計算
        
        Args:
            polygon: ポリゴンデータ
            
        Returns:
            [x, y, width, height] 形式のバウンディングボックス
        """
        # ポイントからバウンディングボックスを計算
        if isinstance(polygon, list) and len(polygon) >= 8:
            # [x1,y1,x2,y2,x3,y3,x4,y4] 形式
            x_coords = [polygon[i] for i in range(0, 8, 2)]
            y_coords = [polygon[i] for i in range(1, 8, 2)]
        else:
            # オブジェクトのリストの場合
            x_coords = [p.x if hasattr(p, 'x') else p[0] for p in polygon]
            y_coords = [p.y if hasattr(p, 'y') else p[1] for p in polygon]
        
        x_min = min(x_coords)
        y_min = min(y_coords)
        width = max(x_coords) - x_min
        height = max(y_coords) - y_min
        
        # インチからポイントに変換（1インチ = 72ポイント）
        return [x_min * 72, y_min * 72, width * 72, height * 72]
    
    def extract_layout_from_lines(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """PDFから行ベースでレイアウト情報を抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            行ベースのBBoxデータのリスト
        """
        hierarchy = self.extract_layout_with_hierarchy(pdf_bytes)
        
        # 行データを既存の形式に変換
        line_bbox_list = []
        for line in hierarchy["lines"]:
            if "bbox" in line:
                line_data = {
                    "text": line["content"],
                    "bbox": line["bbox"],
                    "x": line["bbox"][0],
                    "y": line["bbox"][1],
                    "width": line["bbox"][2],
                    "height": line["bbox"][3],
                    "page": line["page"],
                    "is_line": True  # 行データであることを示すフラグ
                }
                line_bbox_list.append(line_data)
        
        return line_bbox_list
    
    def extract_layout_from_paragraphs(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """PDFから段落ベースでレイアウト情報を抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            段落ベースのBBoxデータのリスト
        """
        hierarchy = self.extract_layout_with_hierarchy(pdf_bytes)
        
        # 段落データを既存の形式に変換
        para_bbox_list = []
        for para in hierarchy["paragraphs"]:
            if "bbox" in para:
                para_data = {
                    "text": para["content"],
                    "bbox": para["bbox"],
                    "x": para["bbox"][0],
                    "y": para["bbox"][1],
                    "width": para["bbox"][2],
                    "height": para["bbox"][3],
                    "page": para["page"],
                    "is_paragraph": True,  # 段落データであることを示すフラグ
                    "role": para.get("role")  # 段落の役割（タイトル、本文など）
                }
                para_bbox_list.append(para_data)
        
        return para_bbox_list