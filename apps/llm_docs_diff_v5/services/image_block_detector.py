"""
画像ベースのブロック検出サービス
PDFを画像に変換し、視覚的にブロックを識別
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw
import cv2
import fitz  # PyMuPDF
from pathlib import Path
import uuid

from ..models.block_models import (
    Block, BlockType, BoundingBox, TextElement, DocumentStructure
)

logger = logging.getLogger(__name__)


class ImageBlockDetector:
    """画像ベースのブロック検出器"""
    
    def __init__(self,
                 dpi: int = 150,
                 min_block_area: int = 5000,  # 大きなブロックのみ検出
                 merge_threshold: int = 30,   # より積極的にマージ
                 text_kernel_size: Tuple[int, int] = (10, 5),  # より大きなカーネル
                 box_min_area: int = 10000,   # 大きなボックスのみ
                 enable_box_detection: bool = True):
        """
        Args:
            dpi: PDF→画像変換時の解像度
            min_block_area: 最小ブロック面積（ピクセル）
            merge_threshold: ブロックマージの距離閾値（ピクセル）
            text_kernel_size: テキスト検出用カーネルサイズ
            box_min_area: ボックス検出の最小面積
            enable_box_detection: ボックス検出を有効にするか
        """
        self.dpi = dpi
        self.min_block_area = min_block_area
        self.merge_threshold = merge_threshold
        self.text_kernel_size = text_kernel_size
        self.box_min_area = box_min_area
        self.enable_box_detection = enable_box_detection
    
    def detect_blocks_from_pdf(self, pdf_path: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        """PDFから画像ベースでブロックを検出"""
        logger.info(f"Detecting blocks from PDF: {pdf_path}")
        
        pdf_doc = fitz.open(pdf_path)
        all_blocks = []
        
        # ページ数を制限
        total_pages = len(pdf_doc)
        pages_to_process = min(total_pages, max_pages) if max_pages else total_pages
        
        for page_num in range(pages_to_process):
            logger.info(f"Processing page {page_num + 1}")
            
            # PDFページを画像に変換
            page_image = self._pdf_page_to_image(pdf_doc, page_num)
            
            # 画像からブロックを検出
            page_blocks = self._detect_blocks_in_image(page_image, page_num)
            
            all_blocks.extend(page_blocks)
        
        pdf_doc.close()
        logger.info(f"Detected {len(all_blocks)} blocks total")
        
        return all_blocks
    
    def _pdf_page_to_image(self, pdf_doc: fitz.Document, page_num: int) -> np.ndarray:
        """PDFページを画像に変換"""
        page = pdf_doc[page_num]
        
        # 画像に変換
        mat = fitz.Matrix(self.dpi / 72.0, self.dpi / 72.0)
        pix = page.get_pixmap(matrix=mat)
        
        # PILイメージに変換
        img_data = pix.tobytes("png")
        pil_image = Image.open(io.BytesIO(img_data))
        
        # NumPy配列に変換
        img_array = np.array(pil_image)
        
        return img_array
    
    def _detect_blocks_in_image(self, image: np.ndarray, page_num: int) -> List[Dict[str, Any]]:
        """画像からブロックを検出（マルチステージアプローチ）"""
        logger.info(f"Detecting blocks in page {page_num + 1}")
        
        # グレースケールに変換
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        all_blocks = []
        
        # ステージ1: ボックス/境界線検出
        if self.enable_box_detection:
            box_blocks = self._detect_boxes(gray, image, page_num)
            all_blocks.extend(box_blocks)
            logger.info(f"Detected {len(box_blocks)} box blocks")
        
        # ステージ2: テキスト領域検出
        text_blocks = self._detect_text_regions(gray, image, page_num, all_blocks)
        all_blocks.extend(text_blocks)
        logger.info(f"Detected {len(text_blocks)} text blocks")
        
        # ブロックをY座標でソート（上から下へ）
        all_blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))
        
        # 重複を除去（ボックス内のテキストブロックなど）
        filtered_blocks = self._filter_overlapping_blocks(all_blocks)
        
        # 近接するブロックを適切にマージ（複数パス）
        merged_blocks = filtered_blocks
        for i in range(3):  # 最大3回マージを繰り返す
            prev_count = len(merged_blocks)
            merged_blocks = self._merge_nearby_blocks(merged_blocks)
            if len(merged_blocks) == prev_count:
                break  # マージが発生しなければ終了
            logger.info(f"Merge pass {i+1}: {prev_count} -> {len(merged_blocks)} blocks")
        
        logger.info(f"Final block count for page {page_num + 1}: {len(merged_blocks)}")
        
        return merged_blocks
    
    def _detect_boxes(self, gray: np.ndarray, original: np.ndarray, page_num: int) -> List[Dict[str, Any]]:
        """ボックス/境界線を検出"""
        blocks = []
        
        # より感度の高いエッジ検出（低い閾値で細かい境界線も検出）
        edges = cv2.Canny(gray, 30, 100, apertureSize=3)
        
        # 線を繋げるための軽い膨張（より小さなカーネル）
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        # 輪郭検出（階層情報も取得）
        contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # 輪郭を近似
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # 矩形または矩形に近い形状（4〜6頂点）を処理
            if 4 <= len(approx) <= 6:
                x, y, w, h = cv2.boundingRect(approx)
                
                # 小さすぎる矩形は無視
                if w * h < self.box_min_area:
                    continue
                
                # アスペクト比をチェック（極端に細長いものは除外）
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 0.05 or aspect_ratio > 20:
                    continue
                
                # ページ全体に近いサイズの矩形は除外
                page_area = original.shape[0] * original.shape[1]
                if w * h > page_area * 0.8:
                    continue
                
                # ボックスブロックとして追加
                block_info = {
                    'page': page_num,
                    'bbox': [x, y, w, h],
                    'image': original[y:y+h, x:x+w],
                    'block_id': str(uuid.uuid4()),
                    'block_type': 'box',
                    'contour': contour
                }
                blocks.append(block_info)
        
        return blocks
    
    def _detect_text_regions(self, gray: np.ndarray, original: np.ndarray, 
                           page_num: int, existing_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """テキスト領域を検出"""
        blocks = []
        
        # アダプティブ閾値処理（より大きなブロックサイズで粗い検出）
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 21, 2)  # ブロックサイズを大きく変更
        
        # ノイズ除去
        denoised = cv2.morphologyEx(binary, cv2.MORPH_OPEN, 
                                    cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
        
        # テキスト用の小さなカーネル
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, self.text_kernel_size)
        
        # 強い膨張処理（大きなブロックを形成）
        dilated = cv2.dilate(denoised, kernel, iterations=3)
        
        # 輪郭検出
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # 小さすぎるブロックは無視
            if w * h < self.min_block_area:
                continue
            
            # 既存のボックス内にあるかチェック
            if self._is_inside_existing_block(x, y, w, h, existing_blocks):
                continue
            
            # テキストブロックとして追加
            block_info = {
                'page': page_num,
                'bbox': [x, y, w, h],
                'image': original[y:y+h, x:x+w],
                'block_id': str(uuid.uuid4()),
                'block_type': 'text',
                'contour': contour
            }
            blocks.append(block_info)
        
        return blocks
    
    def _is_inside_existing_block(self, x: int, y: int, w: int, h: int, 
                                existing_blocks: List[Dict[str, Any]]) -> bool:
        """指定された領域が既存のブロック内にあるかチェック"""
        for block in existing_blocks:
            bx, by, bw, bh = block['bbox']
            # 完全に含まれているかチェック
            if (x >= bx and y >= by and 
                x + w <= bx + bw and y + h <= by + bh):
                return True
        return False
    
    def _filter_overlapping_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """重複するブロックをフィルタリング"""
        if not blocks:
            return blocks
        
        filtered = []
        used = set()
        
        # ボックスブロックを優先
        sorted_blocks = sorted(blocks, key=lambda b: (
            0 if b.get('block_type') == 'box' else 1,
            -b['bbox'][2] * b['bbox'][3]  # 面積の大きい順
        ))
        
        for i, block1 in enumerate(sorted_blocks):
            if i in used:
                continue
            
            # 他のブロックと重複をチェック
            is_duplicate = False
            for j, block2 in enumerate(sorted_blocks[i+1:], i+1):
                if j in used:
                    continue
                
                # 重複率を計算
                overlap_ratio = self._calculate_overlap_ratio(
                    block1['bbox'], block2['bbox']
                )
                
                # 高い重複率の場合、小さい方を削除
                if overlap_ratio > 0.8:
                    if block1['bbox'][2] * block1['bbox'][3] < block2['bbox'][2] * block2['bbox'][3]:
                        is_duplicate = True
                        break
                    else:
                        used.add(j)
            
            if not is_duplicate:
                filtered.append(block1)
        
        return filtered
    
    def _calculate_overlap_ratio(self, bbox1: List[int], bbox2: List[int]) -> float:
        """2つのバウンディングボックスの重複率を計算"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # 交差領域を計算
        x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
        
        intersection = x_overlap * y_overlap
        
        # 各領域の面積
        area1 = w1 * h1
        area2 = w2 * h2
        
        # 小さい方の領域に対する重複率
        min_area = min(area1, area2)
        
        return intersection / min_area if min_area > 0 else 0
    
    def _merge_nearby_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """近接するブロックをマージ"""
        if not blocks:
            return blocks
        
        merged = []
        used = set()
        
        for i, block1 in enumerate(blocks):
            if i in used:
                continue
            
            # マージ候補を探す
            merge_group = [block1]
            
            for j, block2 in enumerate(blocks[i+1:], i+1):
                if j in used:
                    continue
                
                # 近接しているかチェック
                if self._are_blocks_nearby(block1['bbox'], block2['bbox']):
                    merge_group.append(block2)
                    used.add(j)
            
            # マージ実行
            if len(merge_group) > 1:
                merged_block = self._merge_block_group(merge_group)
                merged.append(merged_block)
            else:
                merged.append(block1)
        
        return merged
    
    def _are_blocks_nearby(self, bbox1: List[int], bbox2: List[int]) -> bool:
        """2つのブロックが近接しているかチェック（視覚的グループを形成）"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # 水平方向の距離
        h_distance = max(0, max(x1 - (x2 + w2), x2 - (x1 + w1)))
        
        # 垂直方向の距離
        v_distance = max(0, max(y1 - (y2 + h2), y2 - (y1 + h1)))
        
        # より寛容な条件：視覚的に関連する要素をグループ化
        # 1. 垂直方向に150ピクセル以内で水平方向に重なっている（同じ列）
        if v_distance <= 150 and h_distance == 0:
            return True
        
        # 2. 両方向とも100ピクセル以内（近接する要素）
        if h_distance <= 100 and v_distance <= 100:
            return True
        
        # 3. 水平方向に近く、垂直方向にもある程度近い（同じセクション）
        if h_distance <= 50 and v_distance <= 200:
            return True
        
        # 4. 設定された閾値以内
        return h_distance <= self.merge_threshold and v_distance <= self.merge_threshold * 2
    
    def _merge_block_group(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """ブロックグループをマージ"""
        # バウンディングボックスを計算
        min_x = min(b['bbox'][0] for b in blocks)
        min_y = min(b['bbox'][1] for b in blocks)
        max_x = max(b['bbox'][0] + b['bbox'][2] for b in blocks)
        max_y = max(b['bbox'][1] + b['bbox'][3] for b in blocks)
        
        # 画像を結合（簡略化：最初のブロックの画像を使用）
        # 実際には全ブロックを含む画像を切り出すべき
        page_num = blocks[0]['page']
        
        # マージされたブロックのタイプを決定
        block_types = [b.get('block_type', 'text') for b in blocks]
        merged_type = 'merged' if len(set(block_types)) > 1 else block_types[0]
        
        merged = {
            'page': page_num,
            'bbox': [min_x, min_y, max_x - min_x, max_y - min_y],
            'image': blocks[0]['image'],  # 簡略化
            'block_id': str(uuid.uuid4()),
            'block_type': merged_type,
            'original_blocks': blocks
        }
        
        return merged
    
    def visualize_blocks(self, image: np.ndarray, blocks: List[Dict[str, Any]], 
                        output_path: Optional[str] = None) -> np.ndarray:
        """ブロックを可視化（ブロックタイプ別に色分け）"""
        vis_image = image.copy()
        
        # カラー画像でない場合は変換
        if len(vis_image.shape) == 2:
            vis_image = cv2.cvtColor(vis_image, cv2.COLOR_GRAY2RGB)
        
        # ブロックタイプ別の色
        type_colors = {
            'box': (255, 0, 0),      # 赤: ボックス
            'text': (0, 255, 0),     # 緑: テキスト
            'merged': (0, 0, 255),   # 青: マージされたブロック
            'default': (128, 128, 128)  # グレー: その他
        }
        
        for i, block in enumerate(blocks):
            x, y, w, h = block['bbox']
            block_type = block.get('block_type', 'default')
            color = type_colors.get(block_type, type_colors['default'])
            
            # 矩形を描画
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 2)
            
            # ブロック情報を描画
            label = f"B{i+1}"
            if block_type != 'default':
                label += f"-{block_type[:3].upper()}"
            
            # ラベルの背景を描画
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv2.rectangle(vis_image, (x, y - 20), (x + text_size[0], y), color, -1)
            
            # ラベルテキストを描画
            cv2.putText(vis_image, label, (x + 2, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 保存
        if output_path:
            cv2.imwrite(output_path, cv2.cvtColor(vis_image, cv2.COLOR_RGB2BGR))
        
        return vis_image


import io  # 忘れていたインポートを追加