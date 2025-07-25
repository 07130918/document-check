"""
LLMを使用したブロック抽出サービス
画像ベースのブロック検出とLLMによる読み順序決定を統合
"""
import logging
from typing import List, Dict, Any, Optional
import uuid
import numpy as np

from .image_block_detector import ImageBlockDetector
from .llm_reading_order import LLMReadingOrderService
from .ocr_service import AzureOCRService
from ..models.block_models import (
    Block, BlockType, LayoutRole, BoundingBox, 
    TextElement, DocumentStructure
)

logger = logging.getLogger(__name__)


class LLMBlockExtractor:
    """LLMを使用したブロック抽出器"""
    
    def __init__(self,
                 ocr_service: Optional[AzureOCRService] = None,
                 llm_service: Optional[LLMReadingOrderService] = None,
                 image_detector: Optional[ImageBlockDetector] = None):
        """
        Args:
            ocr_service: OCRサービス
            llm_service: LLM読み順序サービス
            image_detector: 画像ブロック検出器
        """
        self.ocr_service = ocr_service or AzureOCRService()
        self.llm_service = llm_service or LLMReadingOrderService()
        self.image_detector = image_detector or ImageBlockDetector()
    
    def extract_blocks_with_llm(self, pdf_path: str) -> DocumentStructure:
        """PDFからLLMを使ってブロックを抽出"""
        logger.info(f"Extracting blocks with LLM from: {pdf_path}")
        
        # 1. Azure OCRでテキストを抽出（テスト用に5ページまでに制限）
        azure_result = self.ocr_service.extract_layout_from_pdf(pdf_path, max_pages=5)
        processed_pages = len(azure_result.pages) if hasattr(azure_result, 'pages') else 0
        logger.info(f"Azure OCR processed {processed_pages} pages (limited to 5 for testing)")
        
        # 2. 画像ベースでブロックを検出（テスト用に5ページまでに制限）
        image_blocks = self.image_detector.detect_blocks_from_pdf(pdf_path, max_pages=5)
        # OCRで処理したページのブロックのみを使用
        image_blocks = [b for b in image_blocks if b['page'] < processed_pages]
        logger.info(f"Using {len(image_blocks)} image blocks from first {processed_pages} pages")
        
        # 3. 各ブロックを処理
        blocks = []
        for img_block in image_blocks:
            block = self._process_image_block(img_block, azure_result)
            if block:
                blocks.append(block)
        
        # 4. ブロック間の読み順序を決定
        self._determine_global_reading_order(blocks)
        
        # 5. 文書構造を作成
        pages = max(b.page for b in blocks) + 1 if blocks else 0
        
        return DocumentStructure(
            blocks=blocks,
            pages=pages,
            metadata={
                'extraction_method': 'llm_based',
                'language': 'ja'  # または検出
            }
        )
    
    def _process_image_block(self, 
                           image_block: Dict[str, Any], 
                           azure_result: Any) -> Optional[Block]:
        """画像ブロックを処理してBlockオブジェクトを作成"""
        page_num = image_block['page']
        bbox = image_block['bbox']  # [x, y, width, height]
        block_image = image_block['image']
        
        # このブロック内のOCR要素を抽出
        ocr_elements = self._extract_ocr_elements_in_block(
            azure_result, page_num, bbox
        )
        
        if not ocr_elements:
            logger.debug(f"No OCR elements found in block at page {page_num}")
            return None
        
        # LLMで読み順序を決定
        ordered_elements = self.llm_service.determine_reading_order(
            block_image, ocr_elements
        )
        
        # ブロック全体のテキストを結合
        block_text = " ".join(elem.text for elem in ordered_elements)
        
        # LLMでブロックタイプを分析
        block_type_str = self.llm_service.analyze_block_type(
            block_image, block_text
        )
        logger.info(f"LLM analyzed block type: '{block_type_str}' for text: {block_text[:50]}...")
        
        # BlockTypeに変換
        block_type = self._str_to_block_type(block_type_str)
        logger.info(f"Converted to BlockType: {block_type}")
        
        # フォールバック: 位置ベースの推定
        if block_type == BlockType.PARAGRAPH:  # デフォルト値の場合
            block_type = self._infer_block_type_by_position(bbox, image_block['image'].shape, page_num, block_text)
        
        # レイアウト役割を推定
        layout_role = self._infer_layout_role(block_type, bbox, image_block['image'].shape)
        
        # DPIを考慮してポイントに変換（150 DPI → 72 ポイント）
        scale = 72.0 / self.image_detector.dpi
        
        # Blockオブジェクトを作成
        block = Block(
            block_id=image_block['block_id'],
            block_type=block_type,
            bbox=BoundingBox(
                x=bbox[0] * scale,
                y=bbox[1] * scale,
                width=bbox[2] * scale,
                height=bbox[3] * scale
            ),
            elements=ordered_elements,
            layout_role=layout_role,
            page=page_num,
            confidence=1.0,
            metadata={
                'extraction_method': 'llm',
                'original_bbox': bbox
            }
        )
        
        return block
    
    def _extract_ocr_elements_in_block(self, 
                                     azure_result: Any,
                                     page_num: int,
                                     block_bbox: List[int]) -> List[Dict[str, Any]]:
        """ブロック内のOCR要素を抽出"""
        elements = []
        
        # ページ数チェック
        if page_num >= len(azure_result.pages):
            logger.warning(f"Page {page_num} not found in Azure OCR result (total pages: {len(azure_result.pages)})")
            return elements
        
        page = azure_result.pages[page_num]
        block_x, block_y, block_w, block_h = block_bbox
        
        # DPIスケールを計算（Azure OCRの座標をピクセルに変換）
        scale = self.image_detector.dpi / 72.0
        
        logger.debug(f"Block bbox (pixels): x={block_x}, y={block_y}, w={block_w}, h={block_h}")
        logger.debug(f"DPI scale: {scale}")
        
        # ページ内の単語を確認
        if hasattr(page, 'words'):
            logger.debug(f"Total words in page {page_num}: {len(page.words)}")
            for word in page.words:
                # 単語の位置を取得
                if hasattr(word, 'polygon') and word.polygon:
                    points = word.polygon
                elif hasattr(word, 'bounding_box') and word.bounding_box:
                    points = word.bounding_box
                else:
                    continue
                
                # バウンディングボックスを計算
                if isinstance(points, list) and len(points) >= 8:
                    x_coords = [points[i] * scale for i in range(0, 8, 2)]
                    y_coords = [points[i] * scale for i in range(1, 8, 2)]
                else:
                    continue
                
                word_x = min(x_coords)
                word_y = min(y_coords)
                word_w = max(x_coords) - word_x
                word_h = max(y_coords) - word_y
                
                # ブロック内に含まれるかチェック
                if (word_x >= block_x and 
                    word_y >= block_y and 
                    word_x + word_w <= block_x + block_w and 
                    word_y + word_h <= block_y + block_h):
                    
                    elements.append({
                        'text': word.content,
                        'bbox': [word_x - block_x, word_y - block_y, word_w, word_h],
                        'confidence': getattr(word, 'confidence', 1.0)
                    })
        
        return elements
    
    def _str_to_block_type(self, type_str: str) -> BlockType:
        """文字列をBlockTypeに変換"""
        mapping = {
            'title': BlockType.TITLE,
            'subtitle': BlockType.SUBTITLE,
            'paragraph': BlockType.PARAGRAPH,
            'table': BlockType.TABLE,
            'figure': BlockType.FIGURE,
            'list': BlockType.LIST,
            'header': BlockType.HEADER,
            'footer': BlockType.FOOTER,
            'sidebar': BlockType.SIDEBAR,
            'caption': BlockType.CAPTION
        }
        
        return mapping.get(type_str, BlockType.PARAGRAPH)
    
    def _infer_layout_role(self, block_type: BlockType, 
                          bbox: List[int], 
                          image_shape: tuple) -> LayoutRole:
        """レイアウト役割を推定"""
        x, y, w, h = bbox
        img_height, img_width = image_shape[:2]
        
        # 相対位置を計算
        relative_y = y / img_height
        relative_x = x / img_width
        
        # ヘッダー・フッターの判定
        if block_type == BlockType.HEADER or relative_y < 0.1:
            return LayoutRole.HEADER_CONTENT
        elif block_type == BlockType.FOOTER or relative_y > 0.9:
            return LayoutRole.FOOTER_CONTENT
        elif block_type == BlockType.SIDEBAR or relative_x > 0.8 or relative_x < 0.2:
            return LayoutRole.SIDE_CONTENT
        else:
            return LayoutRole.MAIN_CONTENT
    
    def _infer_block_type_by_position(self, bbox: List[int], image_shape: tuple, page_num: int, text: str) -> BlockType:
        """位置情報に基づいてブロックタイプを推定"""
        x, y, w, h = bbox
        img_height, img_width = image_shape[:2]
        
        # 相対位置を計算
        relative_y = y / img_height
        relative_x = x / img_width
        relative_height = h / img_height
        relative_width = w / img_width
        
        # ページ上部の大きなテキストはタイトルの可能性
        if page_num == 0 and relative_y < 0.2 and relative_height > 0.05:
            # テキストに基づく追加判定
            if len(text) < 100:  # 短いテキスト
                return BlockType.TITLE
        
        # ヘッダー領域（上部10%）
        if relative_y < 0.1:
            return BlockType.HEADER
        
        # フッター領域（下部10%）
        if relative_y > 0.9:
            return BlockType.FOOTER
        
        # ページ番号の可能性（小さくて下部）
        if relative_y > 0.85 and relative_height < 0.05 and len(text) < 10:
            return BlockType.PAGE_NUMBER
        
        # サイドバー（左右の端）
        if relative_x < 0.15 or relative_x > 0.85:
            return BlockType.SIDEBAR
        
        # テーブルの可能性（幅が広く、高さが中程度）
        if relative_width > 0.6 and 0.1 < relative_height < 0.3:
            # テキストにテーブルらしいパターンがあるか
            if any(pattern in text for pattern in ['|', '\t', '   ']):
                return BlockType.TABLE
        
        # リストの可能性
        if any(text.strip().startswith(p) for p in ['・', '●', '◆', '1.', '2.', '①', '②']):
            return BlockType.LIST
        
        # 図表のキャプション
        if any(keyword in text for keyword in ['図', '表', 'Figure', 'Table']):
            return BlockType.CAPTION
        
        # デフォルトは段落
        return BlockType.PARAGRAPH
    
    def _determine_global_reading_order(self, blocks: List[Block]):
        """ブロック間のグローバルな読み順序を決定"""
        # ページごとにブロックをグループ化
        page_blocks = {}
        for block in blocks:
            if block.page not in page_blocks:
                page_blocks[block.page] = []
            page_blocks[block.page].append(block)
        
        # 各ページでブロックをソート
        reading_order = 0
        for page_num in sorted(page_blocks.keys()):
            # レイアウト役割と位置でソート
            sorted_blocks = sorted(
                page_blocks[page_num],
                key=lambda b: (
                    # ヘッダーを最初に
                    0 if b.layout_role == LayoutRole.HEADER_CONTENT else
                    # メインコンテンツを次に
                    1 if b.layout_role == LayoutRole.MAIN_CONTENT else
                    # サイドコンテンツ
                    2 if b.layout_role == LayoutRole.SIDE_CONTENT else
                    # フッターを最後に
                    3,
                    # Y座標でソート
                    b.bbox.y,
                    # X座標でソート
                    b.bbox.x
                )
            )
            
            # 読み順序を割り当て
            for block in sorted_blocks:
                block.reading_order = reading_order
                reading_order += 1