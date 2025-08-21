"""
シンプルなLLMベースのブロック抽出サービス
Azure OCRの結果を直接使用してブロックを作成
"""
import logging
from typing import List, Dict, Any, Optional
import uuid

from .ocr_service import AzureOCRService
from ..models.block_models import (
    Block, BlockType, LayoutRole, BoundingBox, 
    TextElement, DocumentStructure
)

logger = logging.getLogger(__name__)


class SimpleLLMBlockExtractor:
    """シンプルなLLMベースのブロック抽出器"""
    
    def __init__(self, ocr_service: Optional[AzureOCRService] = None):
        """
        Args:
            ocr_service: OCRサービス
        """
        self.ocr_service = ocr_service or AzureOCRService()
    
    def extract_blocks_with_llm(self, pdf_path: str) -> DocumentStructure:
        """PDFからLLMを使ってブロックを抽出（シンプル版）"""
        logger.info(f"Extracting blocks with simple LLM approach from: {pdf_path}")
        
        # 1. Azure OCRでレイアウトを抽出（有料版では制限なし）
        azure_result = self.ocr_service.extract_layout_from_pdf(pdf_path)
        processed_pages = len(azure_result.pages) if hasattr(azure_result, 'pages') else 0
        logger.info(f"Azure OCR processed {processed_pages} pages")
        
        # Azure OCRの結果を保存（単語情報の抽出用）
        self.azure_result = azure_result
        
        # 2. Azure OCRの段落をブロックとして使用
        blocks = []
        
        # 段落ベースでブロックを作成
        if hasattr(azure_result, 'paragraphs'):
            for para_idx, paragraph in enumerate(azure_result.paragraphs):
                block = self._create_block_from_paragraph(paragraph, para_idx)
                if block:
                    blocks.append(block)
        
        logger.info(f"Created {len(blocks)} blocks from paragraphs")
        
        # 3. 近接するブロックをマージ（無効化して精度向上）
        # blocks = self._merge_nearby_blocks(blocks)
        
        # 4. ブロックのソートと読み順序の決定
        blocks.sort(key=lambda b: (b.page, b.bbox.y, b.bbox.x))
        for idx, block in enumerate(blocks):
            block.reading_order = idx
        
        # 4. 文書構造を作成
        pages = max(b.page for b in blocks) + 1 if blocks else 0
        
        return DocumentStructure(
            blocks=blocks,
            pages=pages,
            metadata={
                'extraction_method': 'llm_based_simple',
                'language': 'ja'
                # Azure OCR結果は別途保存するため、ここには含めない
            }
        )
    
    def _create_block_from_paragraph(self, paragraph: Any, idx: int) -> Optional[Block]:
        """Azure OCRの段落からブロックを作成"""
        try:
            # バウンディングボックスを取得
            if hasattr(paragraph, 'bounding_regions') and paragraph.bounding_regions:
                region = paragraph.bounding_regions[0]
                page_num = region.page_number - 1  # 0-indexed
                
                # ポリゴンまたはバウンディングボックスから座標を取得
                if hasattr(region, 'polygon') and region.polygon:
                    points = region.polygon
                    x_coords = [points[i] for i in range(0, len(points), 2)]
                    y_coords = [points[i] for i in range(1, len(points), 2)]
                    
                    # ページサイズを取得（デフォルトはA4サイズのインチ単位）
                    page_width = 8.27  # A4 width in inches
                    page_height = 11.69  # A4 height in inches
                    if hasattr(self, 'azure_result') and hasattr(self.azure_result, 'pages'):
                        if len(self.azure_result.pages) > page_num:
                            page = self.azure_result.pages[page_num]
                            if hasattr(page, 'width') and hasattr(page, 'height'):
                                # Azure OCRではインチ単位で返される
                                page_width = page.width
                                page_height = page.height
                    
                    # デバッグ: 座標値を確認
                    logger.debug(f"Page size: width={page_width}, height={page_height}")
                    logger.debug(f"Raw x_coords: {x_coords}")
                    logger.debug(f"Raw y_coords: {y_coords}")
                    
                    # Azure OCRの座標はインチ単位のようなので、ポイントに変換
                    x = min(x_coords) * 72
                    y = min(y_coords) * 72
                    width = (max(x_coords) - min(x_coords)) * 72
                    height = (max(y_coords) - min(y_coords)) * 72
                    
                    logger.debug(f"Calculated bbox: x={x}, y={y}, width={width}, height={height}")
                else:
                    return None
            else:
                return None
            
            # テキスト要素を作成
            elements = []
            text = paragraph.content if hasattr(paragraph, 'content') else ''
            
            if text:
                elements.append(TextElement(
                    text=text,
                    bbox=BoundingBox(x=0, y=0, width=width, height=height),
                    confidence=1.0
                ))
            
            # ブロックタイプを推定（シンプルなルールベース）
            block_type = self._infer_block_type(text, y, height, page_num)
            
            # レイアウトロールを推定
            layout_role = self._infer_layout_role(x, width, page_num)
            
            # ブロックを作成
            block = Block(
                block_id=str(uuid.uuid4()),
                block_type=block_type,
                bbox=BoundingBox(x=x, y=y, width=width, height=height),
                elements=elements,
                page=page_num,
                layout_role=layout_role,
                confidence=1.0,
                metadata={
                    'paragraph_spans': self._extract_paragraph_spans(paragraph, page_num)
                }
            )
            
            return block
            
        except Exception as e:
            logger.error(f"Error creating block from paragraph: {e}")
            return None
    
    def _infer_block_type(self, text: str, y: float, height: float, page_num: int) -> BlockType:
        """テキストと位置からブロックタイプを推定"""
        # ヘッダー/フッターの判定（ポイント単位）
        if y < 100:  # ページ上部（約1.4インチ）
            return BlockType.HEADER
        elif y > 700:  # ページ下部（約9.7インチ）
            return BlockType.FOOTER
        
        # タイトルの判定（最初のページの上部にある大きなテキスト）
        if page_num == 0 and y < 300 and height > 50:
            return BlockType.TITLE
        
        # デフォルトは段落
        return BlockType.PARAGRAPH
    
    def _infer_layout_role(self, x: float, width: float, page_num: int) -> LayoutRole:
        """位置からレイアウトロールを推定"""
        # サイドバーの判定（左右の端、ポイント単位）
        if x < 100 or x > 400:  # 約1.4インチ未満、または約5.6インチ以上
            return LayoutRole.SIDE_CONTENT
        
        # メインコンテンツ
        return LayoutRole.MAIN_CONTENT
    
    def _merge_nearby_blocks(self, blocks: List[Block]) -> List[Block]:
        """近接するブロックをマージして大きなセマンティックユニットを作成"""
        if not blocks:
            return blocks
        
        # ページごとにグループ化
        page_blocks = {}
        for block in blocks:
            if block.page not in page_blocks:
                page_blocks[block.page] = []
            page_blocks[block.page].append(block)
        
        merged_blocks = []
        
        for page_num in sorted(page_blocks.keys()):
            page_blocks_list = page_blocks[page_num]
            # Y座標でソート
            page_blocks_list.sort(key=lambda b: (b.bbox.y, b.bbox.x))
            
            # マージ処理
            current_group = [page_blocks_list[0]]
            
            for i in range(1, len(page_blocks_list)):
                block = page_blocks_list[i]
                last_block = current_group[-1]
                
                # マージ条件：
                # 1. 垂直方向の距離
                # 2. 水平方向に大きく重なっているか、近い
                # 3. 同じレイアウトロール（ヘッダー同士など）
                vertical_distance = block.bbox.y - (last_block.bbox.y + last_block.bbox.height)
                horizontal_overlap = self._calculate_horizontal_overlap(last_block.bbox, block.bbox)
                
                # より積極的なマージ条件
                should_merge = False
                
                # ヘッダー要素は積極的にマージ（150ポイント以内）
                if (block.block_type == BlockType.HEADER and last_block.block_type == BlockType.HEADER and
                    vertical_distance < 150):
                    should_merge = True
                
                # フッター要素も積極的にマージ（100ポイント以内）
                elif (block.block_type == BlockType.FOOTER and last_block.block_type == BlockType.FOOTER and
                    vertical_distance < 100):
                    should_merge = True
                
                # 通常の段落は80ポイント以内でマージ
                elif (block.block_type == BlockType.PARAGRAPH and last_block.block_type == BlockType.PARAGRAPH and
                    vertical_distance < 80 and
                    (horizontal_overlap > 0.2 or abs(block.bbox.x - last_block.bbox.x) < 150) and
                    block.layout_role == last_block.layout_role):
                    should_merge = True
                
                # セマンティックグループ判定：同じ論理的ブロックの可能性が高い場合
                # 例：箇条書き、連続する小さなテキストブロック等
                elif (vertical_distance < 60 and
                      block.layout_role == last_block.layout_role and
                      abs(block.bbox.x - last_block.bbox.x) < 50):  # インデントが近い
                    should_merge = True
                
                if should_merge:
                    current_group.append(block)
                else:
                    # 現在のグループをマージして追加
                    merged_block = self._merge_block_group(current_group)
                    merged_blocks.append(merged_block)
                    current_group = [block]
            
            # 最後のグループを追加
            if current_group:
                merged_block = self._merge_block_group(current_group)
                merged_blocks.append(merged_block)
        
        logger.info(f"Merged {len(blocks)} blocks into {len(merged_blocks)} blocks")
        return merged_blocks
    
    def _calculate_horizontal_overlap(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
        """2つのバウンディングボックスの水平方向の重なり率を計算"""
        x1_start = bbox1.x
        x1_end = bbox1.x + bbox1.width
        x2_start = bbox2.x
        x2_end = bbox2.x + bbox2.width
        
        overlap_start = max(x1_start, x2_start)
        overlap_end = min(x1_end, x2_end)
        
        if overlap_start < overlap_end:
            overlap_width = overlap_end - overlap_start
            min_width = min(bbox1.width, bbox2.width)
            return overlap_width / min_width if min_width > 0 else 0
        return 0
    
    def _merge_block_group(self, blocks: List[Block]) -> Block:
        """ブロックのグループを1つのブロックにマージ"""
        if len(blocks) == 1:
            return blocks[0]
        
        # バウンディングボックスを計算
        min_x = min(b.bbox.x for b in blocks)
        min_y = min(b.bbox.y for b in blocks)
        max_x = max(b.bbox.x + b.bbox.width for b in blocks)
        max_y = max(b.bbox.y + b.bbox.height for b in blocks)
        
        # テキスト要素を結合
        all_elements = []
        all_text = []
        for block in blocks:
            all_elements.extend(block.elements)
            if block.text:
                all_text.append(block.text)
        
        # 最も一般的なブロックタイプを使用
        block_types = [b.block_type for b in blocks]
        most_common_type = max(set(block_types), key=block_types.count)
        
        # マージされたブロックを作成
        merged_block = Block(
            block_id=str(uuid.uuid4()),
            block_type=most_common_type,
            bbox=BoundingBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y),
            elements=all_elements,
            page=blocks[0].page,
            layout_role=blocks[0].layout_role,
            confidence=min(b.confidence for b in blocks),
            metadata={'merged_from': len(blocks)}
        )
        
        return merged_block
    
    def _extract_paragraph_spans(self, paragraph: Any, page_num: int) -> List[Dict[str, Any]]:
        """段落から単語レベルのスパン情報を抽出"""
        spans = []
        
        # 段落のスパン情報を取得
        if hasattr(paragraph, 'spans') and paragraph.spans:
            for span in paragraph.spans:
                # 各スパンの位置情報を取得
                if hasattr(span, 'offset') and hasattr(span, 'length'):
                    # ページサイズを取得
                    page_width = 595  # A4 width in points
                    page_height = 842  # A4 height in points
                    if hasattr(self, 'azure_result') and hasattr(self.azure_result, 'pages'):
                        if len(self.azure_result.pages) > page_num:
                            page = self.azure_result.pages[page_num]
                            if hasattr(page, 'width') and hasattr(page, 'height'):
                                page_width = page.width * 72
                                page_height = page.height * 72
                    
                    # スパンのバウンディングボックスを取得（もしあれば）
                    span_bbox = None
                    if hasattr(span, 'bounding_box') and span.bounding_box:
                        bbox = span.bounding_box
                        if hasattr(bbox, 'x') and hasattr(bbox, 'y'):
                            span_bbox = {
                                'x': bbox.x * page_width,
                                'y': bbox.y * page_height,
                                'width': bbox.width * page_width if hasattr(bbox, 'width') else 0,
                                'height': bbox.height * page_height if hasattr(bbox, 'height') else 0
                            }
                    
                    spans.append({
                        'offset': span.offset,
                        'length': span.length,
                        'bbox': span_bbox
                    })
        
        return spans