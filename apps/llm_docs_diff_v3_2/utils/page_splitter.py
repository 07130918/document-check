"""
ページ分割ユーティリティ
1ページを4分割（左上、右上、左下、右下）してOCR精度を向上させる
"""
import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Any
import logging
from pathlib import Path
import io

logger = logging.getLogger(__name__)


class PageSplitter:
    """ページを上下2分割してOCR処理の精度を向上させるクラス"""
    
    def __init__(self, overlap_ratio: float = 0.1, scale_factor: float = 2.0, 
                 dedup_distance_threshold: float = 10.0):
        """
        初期化
        
        Args:
            overlap_ratio: 領域の重複率（0.1 = 10%）
            scale_factor: 拡大倍率（2.0 = 2倍）
            dedup_distance_threshold: 重複除去の距離閾値（ポイント単位）
        """
        self.overlap_ratio = overlap_ratio
        self.scale_factor = scale_factor
        self.dedup_distance_threshold = dedup_distance_threshold
    
    def split_page_to_regions(self, pdf_bytes: bytes, page_num: int) -> List[Dict[str, Any]]:
        """
        PDFの指定ページを上下2分割して画像として抽出
        
        Args:
            pdf_bytes: PDFのバイトデータ
            page_num: ページ番号（0ベース）
            
        Returns:
            分割された領域の情報リスト
            [{
                'image_bytes': bytes,  # PNG画像データ
                'region': {
                    'x': float,  # 元のページでのX座標
                    'y': float,  # 元のページでのY座標
                    'width': float,  # 幅
                    'height': float,  # 高さ
                    'quadrant': str  # 'top', 'bottom'
                }
            }]
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if page_num >= len(doc):
                raise ValueError(f"Page {page_num} does not exist in PDF")
            
            page = doc[page_num]
            page_rect = page.rect
            
            # ページの幅と高さ
            page_width = page_rect.width
            page_height = page_rect.height
            
            # 重複を考慮した分割サイズ（上下のみ）
            overlap_y = page_height * self.overlap_ratio
            
            # 各領域の高さ（重複を含む）
            region_height = page_height / 2 + overlap_y
            
            # 2つの領域を定義（上下分割）
            regions = [
                {
                    'quadrant': 'top',
                    'x': 0,
                    'y': 0,
                    'width': page_width,
                    'height': region_height
                },
                {
                    'quadrant': 'bottom',
                    'x': 0,
                    'y': page_height / 2 - overlap_y,
                    'width': page_width,
                    'height': region_height
                }
            ]
            
            # 各領域を画像として抽出
            result = []
            for region in regions:
                # クリップ領域を設定
                clip_rect = fitz.Rect(
                    region['x'],
                    region['y'],
                    min(region['x'] + region['width'], page_width),
                    min(region['y'] + region['height'], page_height)
                )
                
                # 拡大して画像を取得
                mat = fitz.Matrix(self.scale_factor, self.scale_factor)
                pix = page.get_pixmap(matrix=mat, clip=clip_rect)
                
                # PNG形式でバイトデータに変換
                img_bytes = pix.tobytes("png")
                
                result.append({
                    'image_bytes': img_bytes,
                    'region': region,
                    'page_num': page_num,
                    'original_width': page_width,
                    'original_height': page_height
                })
                
                logger.info(f"Extracted {region['quadrant']} region from page {page_num}")
            
            doc.close()
            return result
            
        except Exception as e:
            logger.error(f"Failed to split page {page_num}: {e}")
            raise
    
    def transform_coordinates(self, bbox: List[float], region: Dict[str, Any]) -> List[float]:
        """
        分割領域の座標を元のページ座標に変換
        
        Args:
            bbox: 分割領域内での座標 [x, y, width, height]（ピクセル座標）
            region: 分割領域の情報
            
        Returns:
            元のページでの座標 [x, y, width, height]（ポイント座標）
        """
        # PyMuPDFのデフォルトDPIは72
        # scale_factorで拡大した画像のピクセル座標を元に戻す
        dpi = 72.0
        
        # ピクセル座標をポイント座標に変換
        # bbox内の座標は拡大された画像内のピクセル座標
        x_in_region = bbox[0] / self.scale_factor  # 拡大を戻す
        y_in_region = bbox[1] / self.scale_factor
        width = bbox[2] / self.scale_factor
        height = bbox[3] / self.scale_factor
        
        # 領域の開始位置を加算
        x = x_in_region + region['x']
        y = y_in_region + region['y']
        
        return [x, y, width, height]
    
    def merge_ocr_results(self, region_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        2つの領域のOCR結果をマージして重複を除去
        
        Args:
            region_results: 各領域のOCR結果
            [{
                'region': Dict,  # 領域情報
                'text_items': List[Dict]  # OCR結果
            }]
            
        Returns:
            マージされたOCR結果
        """
        all_items = []
        
        for result in region_results:
            region = result['region']
            
            for item in result['text_items']:
                # 座標を元のページ座標に変換
                original_bbox = self.transform_coordinates(
                    item['bbox'],
                    region
                )
                
                # 元のアイテムをコピーして座標を更新
                merged_item = item.copy()
                merged_item['bbox'] = original_bbox
                merged_item['x'] = original_bbox[0]
                merged_item['y'] = original_bbox[1]
                merged_item['width'] = original_bbox[2]
                merged_item['height'] = original_bbox[3]
                merged_item['source_region'] = region['quadrant']
                
                all_items.append(merged_item)
        
        # 重複除去（同じテキストで位置が近いものを除去）
        unique_items = self._remove_duplicates(all_items, self.dedup_distance_threshold)
        
        return unique_items
    
    def _remove_duplicates(self, items: List[Dict[str, Any]], 
                          distance_threshold: float = 10.0) -> List[Dict[str, Any]]:
        """
        重複するテキストアイテムを除去
        
        Args:
            items: テキストアイテムのリスト
            distance_threshold: 重複とみなす距離の閾値
            
        Returns:
            重複を除去したリスト
        """
        if not items:
            return []
        
        # テキストと位置でソート
        sorted_items = sorted(items, key=lambda x: (x['text'], x['x'], x['y']))
        
        unique_items = []
        
        for item in sorted_items:
            # 既存のアイテムと比較
            is_duplicate = False
            
            for unique_item in unique_items:
                # 同じテキストで位置が近い場合は重複とみなす
                if (item['text'] == unique_item['text'] and
                    abs(item['x'] - unique_item['x']) < distance_threshold and
                    abs(item['y'] - unique_item['y']) < distance_threshold):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_items.append(item)
        
        
        logger.info(f"Removed {len(items) - len(unique_items)} duplicate items in total")
        
        return unique_items