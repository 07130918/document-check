# coding: utf-8
"""
Azure Document Intelligence構造化分析サービス (v3.4)
セクション階層、段落役割、座標情報を活用した高度な分析
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class StructuredAzureService:
    """構造化されたAzure Document Intelligence分析サービス"""
    
    def __init__(self):
        """初期化"""
        self.endpoint = os.environ["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"]
        self.key = os.environ["AZURE_DOCUMENT_INTELLIGENCE_KEY"]
    
    def analyze_document_structured(self, pdf_file_path: str, pages: Optional[str] = None) -> Dict[str, Any]:
        """文書の構造化分析を実行
        
        Args:
            pdf_file_path: PDFファイルのパス
            pages: 分析対象ページ（例: "2" または "1-3"）
            
        Returns:
            構造化された分析結果
        """
        from azure.core.credentials import AzureKeyCredential
        from azure.ai.documentintelligence import DocumentIntelligenceClient

        client = DocumentIntelligenceClient(
            endpoint=self.endpoint, 
            credential=AzureKeyCredential(self.key)
        )
        
        logger.info(f"構造化分析開始: {pdf_file_path}")
        
        # PDF文書を分析
        with open(pdf_file_path, "rb") as f:
            document_content = f.read()
        
        analyze_kwargs = {
            "model_id": "prebuilt-layout",
            "body": document_content,
            "content_type": "application/pdf"
        }
        
        if pages:
            analyze_kwargs["pages"] = pages
            logger.info(f"ページ指定: {pages}")
        
        poller = client.begin_analyze_document(**analyze_kwargs)
        result = poller.result()
        
        # 構造化分析の実行
        structured_result = self._extract_structured_information(result)
        
        logger.info(f"構造化分析完了: {structured_result['summary']['total_sections']}セクション, "
                   f"{structured_result['summary']['total_paragraphs']}段落")
        
        return structured_result
    
    def _extract_structured_information(self, result) -> Dict[str, Any]:
        """Document Intelligence結果から構造化情報を抽出
        
        Args:
            result: Azure Document Intelligence分析結果
            
        Returns:
            構造化された情報
        """
        full_content = result.content if hasattr(result, 'content') else ""
        paragraphs = result.paragraphs if hasattr(result, 'paragraphs') else []
        
        # 段落を役割に基づいてセクションに分類
        sections = self._organize_paragraphs_into_sections(paragraphs)
        
        # 構造化結果を作成
        structured_result = {
            "source_file": "",  # 呼び出し元で設定
            "analyzed_at": datetime.now().isoformat(),
            "analysis_type": "structured_v3.4",
            "summary": {
                "total_sections": len(sections),
                "total_paragraphs": len(paragraphs),
                "content_length": len(full_content)
            },
            "sections": sections
        }
        
        return structured_result
    
    def _organize_paragraphs_into_sections(self, paragraphs: List) -> List[Dict[str, Any]]:
        """段落を役割に基づいてセクションに整理
        
        Args:
            paragraphs: 段落リスト
            
        Returns:
            セクションリスト
        """
        sections = []
        current_section = None
        
        for i, para in enumerate(paragraphs):
            role = getattr(para, 'role', None)
            content = para.content.strip()
            
            # 段落のページ番号を取得
            page_number = self._get_paragraph_page_number(para)
            
            # 段落の座標情報を取得
            para_coords = self._get_paragraph_coordinates(para)
            
            # セクション見出しまたはタイトルの場合、新しいセクションを開始
            if (role and str(role) in ['ParagraphRole.TITLE', 'ParagraphRole.SECTION_HEADING']):
                if current_section is not None:
                    sections.append(current_section)
                
                current_section = {
                    "section_number": len(sections) + 1,
                    "title": content,
                    "content_length": 0,
                    "word_count": 0,
                    "paragraph_count": 0,
                    "coordinates": para_coords,
                    "paragraphs": [],
                    "para_contents_list": [],
                    "page": page_number
                }
            
            # 段落情報を作成
            para_info = {
                "content": content,
                "role": str(role) if role else None,
                "length": len(content),
                "paragraph_index": i,
                "coordinates": para_coords,
                "importance": self._classify_paragraph_importance(content, role),
                "page": page_number  # ← ページ番号を追加
            }

            
            # 現在のセクションに段落を追加
            if current_section is not None:
                current_section["paragraphs"].append(para_info)
                current_section["content_length"] += len(content)
                current_section["word_count"] += len(content.split())
                current_section["paragraph_count"] += 1
                current_section["para_contents_list"].append(content)
                
                # セクションの座標を更新（段落を含むように拡張）
                if para_coords and current_section["coordinates"]:
                    current_section["coordinates"] = self._extend_coordinates(
                        current_section["coordinates"], para_coords
                    )
                elif para_coords and not current_section["coordinates"]:
                    current_section["coordinates"] = para_coords
            else:
                # 最初のセクションが見つかる前の段落は「前置き」セクション
                if not sections:
                    sections.append({
                        "section_number": 1,
                        "title": "前置き",
                        "content_length": 0,
                        "word_count": 0,
                        "paragraph_count": 0,
                        "coordinates": para_coords,
                        "paragraphs": [],
                        "para_contents_list": [],
                        "page": page_number
                    })
                
                sections[0]["paragraphs"].append(para_info)
                sections[0]["content_length"] += len(content)
                sections[0]["word_count"] += len(content.split())
                sections[0]["paragraph_count"] += 1
                sections[0]["para_contents_list"].append(content)
                
                if para_coords and sections[0]["coordinates"]:
                    sections[0]["coordinates"] = self._extend_coordinates(
                        sections[0]["coordinates"], para_coords
                    )
                elif para_coords and not sections[0]["coordinates"]:
                    sections[0]["coordinates"] = para_coords
        
        # 最後のセクションを追加
        if current_section is not None:
            sections.append(current_section)

        
        
        return sections
    
    def _get_paragraph_coordinates(self, paragraph) -> Optional[Dict[str, Any]]:
        """段落の座標情報を取得
        
        Args:
            paragraph: 段落オブジェクト
            
        Returns:
            座標情報（ポリゴン形式）
        """
        # スパン情報から座標を取得
        if hasattr(paragraph, 'spans') and paragraph.spans:
            coords_from_spans = self._get_spans_coordinates(paragraph.spans)
            if coords_from_spans:
                logger.debug(f"スパンから座標取得: '{paragraph.content[:30]}...'")
                return coords_from_spans
        
        # bounding_regionsから座標を取得
        if hasattr(paragraph, 'bounding_regions') and paragraph.bounding_regions:
            coords_from_regions = self._get_bounding_regions_coordinates(paragraph.bounding_regions)
            if coords_from_regions:
                logger.debug(f"バウンディングリージョンから座標取得: '{paragraph.content[:30]}...'")
                return coords_from_regions
        
        logger.warning(f"座標取得失敗: '{paragraph.content[:30]}...'")
        return None

    def _get_paragraph_page_number(self, paragraph) -> int:
        """段落のページ番号を取得
        
        Args:
            paragraph: 段落オブジェクト
            
        Returns:
            ページ番号（1ベース）
        """
        # 段落のbounding regionからページ番号を取得
        if hasattr(paragraph, 'bounding_regions') and paragraph.bounding_regions:
            for region in paragraph.bounding_regions:
                if hasattr(region, 'page_number'):
                    return region.page_number
        
        # デフォルト値（最初のページ）
        logger.warning(f"段落のページ番号を取得できませんでした: '{paragraph.content[:30]}...'")
        return 1
    
    def _get_spans_coordinates(self, spans) -> Optional[Dict[str, Any]]:
        """スパン情報から座標を取得"""
        if not spans:
            return None
        
        polygons = []
        for span in spans:
            if hasattr(span, 'polygon') and span.polygon:
                polygon_data = self._extract_polygon_data(span.polygon)
                if polygon_data:
                    polygons.append(polygon_data)
        
        if polygons:
            return self._combine_polygons(polygons)
        
        return None

    def _get_bounding_regions_coordinates(self, bounding_regions) -> Optional[Dict[str, Any]]:
        """バウンディングリージョンから座標を取得"""
        if not bounding_regions:
            return None
        
        polygons = []
        for region in bounding_regions:
            if hasattr(region, 'polygon') and region.polygon:
                polygon_data = self._extract_polygon_data(region.polygon)
                if polygon_data:
                    polygons.append(polygon_data)
        
        if polygons:
            return self._combine_polygons(polygons)
        
        return None

    def _extract_polygon_data(self, polygon) -> Optional[Dict[str, Any]]:
        """ポリゴンデータを抽出して構造化"""
        if not polygon or len(polygon) < 4:
            return None
        
        # ポリゴンが [x1, y1, x2, y2, x3, y3, x4, y4] 形式の場合
        if len(polygon) % 2 != 0:
            logger.warning(f"不正なポリゴンデータ: {polygon}")
            return None
            
        points = []
        for i in range(0, len(polygon), 2):
            if i + 1 < len(polygon):
                points.append({
                    "x": polygon[i],
                    "y": polygon[i + 1]
                })
        
        # 座標の範囲情報も計算（検索や比較で有用）
        x_coords = [point["x"] for point in points]
        y_coords = [point["y"] for point in points]
        
        return {
            "type": "polygon",
            "points": points,
            "raw_coordinates": list(polygon),
            "bounds": {
                "left": min(x_coords),
                "top": min(y_coords),
                "right": max(x_coords),
                "bottom": max(y_coords),
                "width": max(x_coords) - min(x_coords),
                "height": max(y_coords) - min(y_coords)
            }
        }
    
    def _combine_polygons(self, polygons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """複数のポリゴンを結合"""
        if not polygons:
            return None
        
        if len(polygons) == 1:
            return polygons[0]
        
        # すべてのポイントを収集
        all_points = []
        all_raw_coords = []
        
        for polygon in polygons:
            if "points" in polygon:
                all_points.extend(polygon["points"])
            if "raw_coordinates" in polygon:
                all_raw_coords.extend(polygon["raw_coordinates"])
        
        # 統合された境界を計算
        if all_points:
            x_coords = [point["x"] for point in all_points]
            y_coords = [point["y"] for point in all_points]
            
            return {
                "type": "combined_polygon",
                "points": all_points,
                "raw_coordinates": all_raw_coords,
                "bounds": {
                    "left": min(x_coords),
                    "top": min(y_coords),
                    "right": max(x_coords),
                    "bottom": max(y_coords),
                    "width": max(x_coords) - min(x_coords),
                    "height": max(y_coords) - min(y_coords)
                },
                "polygon_count": len(polygons)
            }
        
        return None
    
    def _extend_coordinates(self, coords1: Dict[str, Any], coords2: Dict[str, Any]) -> Dict[str, Any]:
        """2つの座標を結合して拡張された座標を作成"""
        return self._combine_polygons([coords1, coords2])
    
    def _classify_paragraph_importance(self, text: str, role) -> str:
        """段落の重要度を分類"""
        if role and str(role) in ['ParagraphRole.TITLE', 'ParagraphRole.SECTION_HEADING']:
            return 'high'
        elif role and str(role) == 'ParagraphRole.PAGE_NUMBER':
            return 'low'
        
        import re
        if re.search(r'P\d+', text):  # ページ参照
            return 'high'
        elif len(text) > 50:  # 長い文章
            return 'high'
        elif len(text) < 5:  # 短いテキスト
            return 'low'
        else:
            return 'medium'