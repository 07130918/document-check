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
from ..core.table_merger import TableMerger

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
            # PDFサイズをチェックし、大きすぎる場合は最初の5ページのみを処理
            from ..utils.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            
            # テスト用に最大ページ数を制限
            max_pages = getattr(settings, 'TEST_MAX_PAGES', 5)
            if max_pages:
                logger.info(f"Limiting PDF to {max_pages} pages for Azure processing")
                pdf_bytes = pdf_processor.limit_pdf_pages(pdf_bytes, max_pages)
            
            # Document Intelligenceでレイアウト解析
            # 新しいAPIでは、bodyパラメータとしてバイトデータを渡す
            # High Resolution機能を有効化（バイナリ形式を維持）
            features = []
            if settings.USE_HIGH_RESOLUTION_OCR:
                # Azure Document Intelligenceの正しいfeature名を使用
                features.append("ocr.highResolution")
                logger.info("Azure Document Intelligence: High Resolution OCR enabled")
            else:
                logger.info("Azure Document Intelligence: Standard resolution OCR")
            
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                body=pdf_bytes,
                content_type="application/pdf",
                features=features if features else None,  # High Resolution OCRを有効化
                locale="ja-JP"  # 日本語を明示的に指定
            )
            result: AnalyzeResult = poller.result()
            
            bbox_data_list = []
            
            # ページごとに処理
            for page_idx, page in enumerate(result.pages):
                # 単語単位で抽出
                for word in page.words:
                    # バウンディングボックスを正規化
                    # Azure returns polygon points, we need [x, y, width, height]
                    # 新しいAPIでは word.polygon を使用
                    if hasattr(word, 'polygon') and word.polygon:
                        points = word.polygon
                    elif hasattr(word, 'bounding_box') and word.bounding_box:
                        # bounding_box形式の場合 - 8つの数値のリスト [x1,y1,x2,y2,x3,y3,x4,y4]
                        points = word.bounding_box
                    else:
                        logger.warning(f"Word without polygon or bounding_box: {word.content}")
                        continue
                    
                    # ポイントからバウンディングボックスを計算
                    # Azureは8つの数値（4つの頂点のx,y座標）を返す
                    if isinstance(points, list) and len(points) >= 8:
                        # [x1,y1,x2,y2,x3,y3,x4,y4] 形式
                        x_coords = [points[i] for i in range(0, 8, 2)]
                        y_coords = [points[i] for i in range(1, 8, 2)]
                    else:
                        # オブジェクトのリストの場合
                        x_coords = [p.x if hasattr(p, 'x') else p[0] for p in points]
                        y_coords = [p.y if hasattr(p, 'y') else p[1] for p in points]
                    
                    x_min = min(x_coords)
                    y_min = min(y_coords)
                    width = max(x_coords) - x_min
                    height = max(y_coords) - y_min
                    
                    # インチからポイントに変換（1インチ = 72ポイント）
                    bbox_data = BBoxTextData(
                        bbox=[x_min * 72, y_min * 72, width * 72, height * 72],
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
            # PDFサイズをチェックし、大きすぎる場合は最初のNページのみを処理
            from ..utils.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            
            # テスト用に最大ページ数を制限
            max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
            if max_pages:
                logger.info(f"Limiting PDF to {max_pages} pages for table extraction")
                pdf_bytes = pdf_processor.limit_pdf_pages(pdf_bytes, max_pages)
            
            # 表抽出のオプションを追加
            # features: テーブル抽出機能を明示的に有効化
            features = []
            
            # 高解像度OCRを有効化（テーブル内の小さな文字の認識精度向上）
            if settings.USE_HIGH_RESOLUTION_OCR:
                features.append("ocr.highResolution")
                logger.info("Table extraction: High Resolution OCR enabled")
            
            # テーブル抽出を明示的に有効化
            # 注：tablesフィーチャーは、featuresパラメータではなくモデル自体に含まれている
            
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                body=pdf_bytes,
                content_type="application/pdf",
                features=features if features else None,  # 高解像度OCRオプション
                locale="ja"  # 日本語文書として明示的に指定
            )
            result: AnalyzeResult = poller.result()
            
            tables = []
            logger.info(f"Azure detected {len(result.tables)} tables in the document")
            
            for table_idx, table in enumerate(result.tables):
                logger.info(f"Processing table {table_idx}: {table.row_count}x{table.column_count}")
                
                # テーブルのセル内容をデバッグ出力
                if table_idx < 5:  # 最初の5つのテーブルのみ詳細ログ
                    logger.debug(f"Table {table_idx} cells:")
                    for cell in table.cells[:10]:  # 最初の10セルのみ
                        logger.debug(f"  Cell[{cell.row_index}][{cell.column_index}]: '{cell.content}' "
                                   f"(kind: {getattr(cell, 'kind', 'unknown')}, "
                                   f"row_span: {cell.row_span or 1}, "
                                   f"col_span: {cell.column_span or 1})")
                
                # バウンディングボックス情報を取得
                bounding_region = table.bounding_regions[0] if table.bounding_regions else None
                bbox = None
                
                if bounding_region and hasattr(bounding_region, 'polygon') and bounding_region.polygon:
                    # polygonから最小・最大座標を計算
                    points = bounding_region.polygon
                    if isinstance(points, list) and len(points) >= 8:
                        x_coords = [points[i] for i in range(0, len(points), 2)]
                        y_coords = [points[i] for i in range(1, len(points), 2)]
                        # bboxをインチ単位で保存（ハンドラーで変換）
                        bbox = [
                            min(x_coords),  # x
                            min(y_coords),  # y
                            (max(x_coords) - min(x_coords)),  # width
                            (max(y_coords) - min(y_coords))   # height
                        ]
                        logger.debug(f"  Calculated bbox: {bbox}")
                    else:
                        logger.warning(f"  Invalid polygon points: {points}")
                
                table_info = {
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": [],
                    "page": bounding_region.page_number - 1 if bounding_region else 0,  # 0-indexed
                    "bbox": bbox  # バウンディングボックス情報を追加
                }
                
                for cell in table.cells:
                    cell_bbox = None
                    if hasattr(cell, 'bounding_regions') and cell.bounding_regions:
                        cell_region = cell.bounding_regions[0]
                        if hasattr(cell_region, 'polygon') and cell_region.polygon:
                            points = cell_region.polygon
                            if len(points) >= 8:
                                x_coords = [points[i] for i in range(0, len(points), 2)]
                                y_coords = [points[i] for i in range(1, len(points), 2)]
                                # bboxをインチ単位で保存（ハンドラーで変換）
                                cell_bbox = [
                                    min(x_coords),
                                    min(y_coords),
                                    (max(x_coords) - min(x_coords)),
                                    (max(y_coords) - min(y_coords))
                                ]
                    
                    cell_info = {
                        "row": cell.row_index,
                        "column": cell.column_index,
                        "text": cell.content,
                        "row_span": cell.row_span or 1,
                        "column_span": cell.column_span or 1,
                        "bbox": cell_bbox,  # セルのバウンディングボックス
                        "kind": getattr(cell, 'kind', 'content')  # セルの種類（columnHeader, content等）
                    }
                    table_info["cells"].append(cell_info)
                
                tables.append(table_info)
            
            logger.info(f"Extracted {len(tables)} tables before merging")
            
            # 表の結合処理を実行（設定により有効/無効を切り替え可能）
            if getattr(settings, 'ENABLE_TABLE_MERGING', True):
                merger = TableMerger(
                    vertical_distance_threshold=getattr(settings, 'TABLE_MERGE_VERTICAL_THRESHOLD', 0.05),
                    horizontal_overlap_threshold=getattr(settings, 'TABLE_MERGE_HORIZONTAL_THRESHOLD', 0.8),
                    column_match_threshold=getattr(settings, 'TABLE_MERGE_COLUMN_THRESHOLD', 0.7)
                )
                
                # 表を結合
                merged_tables = merger.merge_tables(tables)
                logger.info(f"After merging: {len(merged_tables)} tables")
                
                # デバッグ情報を出力
                merge_count = len(tables) - len(merged_tables)
                if merge_count > 0:
                    logger.info(f"Merged {merge_count} table pairs")
                    for table in merged_tables:
                        if table.get('is_merged'):
                            logger.debug(f"Merged table on page {table['page']}: "
                                       f"{table['merge_info']['original_table_count']} tables combined, "
                                       f"final size: {table['row_count']}x{table['column_count']}")
                
                return merged_tables
            else:
                logger.info("Table merging is disabled")
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
            # prebuilt-documentモデルは廃止されたため、prebuilt-layoutを使用
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                body=pdf_bytes,
                content_type="application/pdf",
                features=["keyValuePairs"] if hasattr(self.client, 'api_version') else None
            )
            result: AnalyzeResult = poller.result()
            
            key_values = {}
            # key_value_pairsが存在する場合のみ処理
            if hasattr(result, 'key_value_pairs') and result.key_value_pairs:
                for kv_pair in result.key_value_pairs:
                    if kv_pair.key and kv_pair.value:
                        key = kv_pair.key.content
                        value = kv_pair.value.content
                        key_values[key] = value
            
            logger.info(f"Extracted {len(key_values)} key-value pairs")
            return key_values
            
        except Exception as e:
            logger.error(f"Key-value extraction failed: {e}")
            logger.debug(f"Error details: {type(e).__name__}: {e}")
            return {}