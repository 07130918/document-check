"""
ブロック抽出サービス
Azure Document Intelligenceの結果からブロック構造を抽出
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import uuid
from collections import defaultdict

from ..models.block_models import (
    Block, BlockType, LayoutRole, BoundingBox, 
    TextElement, DocumentStructure
)

logger = logging.getLogger(__name__)


class BlockExtractor:
    """ブロック抽出器"""
    
    def __init__(self, 
                 merge_threshold: float = 10.0,
                 min_block_area: float = 100.0):
        """
        Args:
            merge_threshold: ブロックをマージする距離の閾値
            min_block_area: 最小ブロック面積
        """
        self.merge_threshold = merge_threshold
        self.min_block_area = min_block_area
    
    def extract_blocks_from_azure(self, azure_result: Any) -> DocumentStructure:
        """Azure Document Intelligenceの結果からブロックを抽出"""
        blocks = []
        
        # ページごとに処理
        for page_idx, page in enumerate(azure_result.pages):
            page_blocks = []
            
            # 1. 段落からブロックを作成
            if hasattr(azure_result, 'paragraphs'):
                for para in azure_result.paragraphs:
                    if self._get_page_number(para) == page_idx:
                        block = self._create_block_from_paragraph(para, page_idx)
                        if block:
                            page_blocks.append(block)
            
            # 2. テーブルからブロックを作成
            if hasattr(azure_result, 'tables'):
                for table in azure_result.tables:
                    if self._get_page_number(table) == page_idx:
                        block = self._create_block_from_table(table, page_idx)
                        if block:
                            page_blocks.append(block)
            
            # 3. 図表（figures）からブロックを作成
            if hasattr(azure_result, 'figures'):
                for figure in azure_result.figures:
                    if self._get_page_number(figure) == page_idx:
                        block = self._create_block_from_figure(figure, page_idx)
                        if block:
                            page_blocks.append(block)
            
            # 4. 孤立した行やワードをブロックとして扱う
            orphan_blocks = self._create_blocks_from_orphans(
                page, page_idx, page_blocks, azure_result
            )
            page_blocks.extend(orphan_blocks)
            
            # 5. 近接するブロックをマージ
            merged_blocks = self._merge_nearby_blocks(page_blocks)
            
            # 6. ブロックタイプを推定
            # （既にブロック作成時に推定済みのためスキップ）
            
            # 7. レイアウト役割を推定
            self._infer_layout_roles(merged_blocks, page)
            
            blocks.extend(merged_blocks)
        
        # 階層構造を構築
        self._build_hierarchy(blocks)
        
        # 文書構造を返す
        languages = getattr(azure_result, 'languages', None)
        language = languages[0] if languages else 'unknown'
        
        return DocumentStructure(
            blocks=blocks,
            pages=len(azure_result.pages),
            metadata={
                'language': language,
                'content_format': getattr(azure_result, 'content_format', 'unknown')
            }
        )
    
    def _create_block_from_paragraph(self, para: Any, page_idx: int) -> Optional[Block]:
        """段落からブロックを作成"""
        if not hasattr(para, 'bounding_regions') or not para.bounding_regions:
            return None
        
        # バウンディングボックスを取得
        bbox_data = para.bounding_regions[0].polygon
        bbox = self._polygon_to_bbox(bbox_data)
        
        if bbox.area < self.min_block_area:
            return None
        
        # テキスト要素を抽出
        elements = []
        if hasattr(para, 'spans'):
            for span in para.spans:
                # スパンからテキストと位置を取得（実装は簡略化）
                text = self._get_span_text(span, para)
                if text:
                    elements.append(TextElement(
                        text=text,
                        bbox=bbox,  # 簡略化：段落全体のBBoxを使用
                        confidence=1.0
                    ))
        
        return Block(
            block_id=str(uuid.uuid4()),
            block_type=BlockType.PARAGRAPH,
            bbox=bbox,
            elements=elements,
            page=page_idx,
            metadata={'role': getattr(para, 'role', 'paragraph')}
        )
    
    def _create_block_from_table(self, table: Any, page_idx: int) -> Optional[Block]:
        """テーブルからブロックを作成"""
        if not hasattr(table, 'bounding_regions') or not table.bounding_regions:
            return None
        
        bbox_data = table.bounding_regions[0].polygon
        bbox = self._polygon_to_bbox(bbox_data)
        
        # テーブルのセルからテキスト要素を作成
        elements = []
        if hasattr(table, 'cells'):
            for cell in table.cells:
                if hasattr(cell, 'content') and cell.content:
                    # セルの位置を計算（簡略化）
                    cell_bbox = bbox  # 実際にはセルごとの位置が必要
                    elements.append(TextElement(
                        text=cell.content,
                        bbox=cell_bbox,
                        confidence=1.0
                    ))
        
        return Block(
            block_id=str(uuid.uuid4()),
            block_type=BlockType.TABLE,
            bbox=bbox,
            elements=elements,
            page=page_idx,
            metadata={
                'rows': table.row_count if hasattr(table, 'row_count') else 0,
                'columns': table.column_count if hasattr(table, 'column_count') else 0
            }
        )
    
    def _create_block_from_figure(self, figure: Any, page_idx: int) -> Optional[Block]:
        """図表からブロックを作成"""
        if not hasattr(figure, 'bounding_regions') or not figure.bounding_regions:
            return None
        
        bbox_data = figure.bounding_regions[0].polygon
        bbox = self._polygon_to_bbox(bbox_data)
        
        # キャプションを要素として追加
        elements = []
        if hasattr(figure, 'caption') and figure.caption:
            elements.append(TextElement(
                text=figure.caption.content,
                bbox=bbox,
                confidence=1.0
            ))
        
        return Block(
            block_id=str(uuid.uuid4()),
            block_type=BlockType.FIGURE,
            bbox=bbox,
            elements=elements,
            page=page_idx,
            metadata={'has_caption': bool(elements)}
        )
    
    def _create_blocks_from_orphans(self, page: Any, page_idx: int, 
                                   existing_blocks: List[Block], 
                                   azure_result: Any) -> List[Block]:
        """既存ブロックに含まれない要素からブロックを作成"""
        orphan_blocks = []
        
        # ページ内のすべての行を確認
        if hasattr(azure_result, 'pages') and page_idx < len(azure_result.pages):
            page_data = azure_result.pages[page_idx]
            
            if hasattr(page_data, 'lines'):
                for line in page_data.lines:
                    # この行が既存のブロックに含まれているかチェック
                    line_bbox = self._polygon_to_bbox(line.polygon)
                    
                    is_contained = False
                    for block in existing_blocks:
                        if block.bbox.contains(line_bbox):
                            is_contained = True
                            break
                    
                    if not is_contained:
                        # 新しいブロックとして作成
                        elements = [TextElement(
                            text=line.content,
                            bbox=line_bbox,
                            confidence=1.0
                        )]
                        
                        # ブロックタイプを推定
                        block_type = self._infer_block_type(line.content, line_bbox, page_data)
                        
                        orphan_blocks.append(Block(
                            block_id=str(uuid.uuid4()),
                            block_type=block_type,
                            bbox=line_bbox,
                            elements=elements,
                            page=page_idx
                        ))
        
        return orphan_blocks
    
    def _merge_nearby_blocks(self, blocks: List[Block]) -> List[Block]:
        """近接するブロックをマージ"""
        if not blocks:
            return blocks
        
        merged = []
        used = set()
        
        for i, block1 in enumerate(blocks):
            if i in used:
                continue
            
            # マージ候補を探す
            merge_candidates = [block1]
            
            for j, block2 in enumerate(blocks[i+1:], i+1):
                if j in used:
                    continue
                
                # 同じタイプで近接しているかチェック
                if (block1.block_type == block2.block_type and
                    self._are_blocks_nearby(block1, block2)):
                    merge_candidates.append(block2)
                    used.add(j)
            
            # マージ実行
            if len(merge_candidates) > 1:
                merged_block = self._merge_blocks(merge_candidates)
                merged.append(merged_block)
            else:
                merged.append(block1)
        
        return merged
    
    def _are_blocks_nearby(self, block1: Block, block2: Block) -> bool:
        """2つのブロックが近接しているかチェック"""
        # 水平方向の距離
        h_distance = min(
            abs(block1.bbox.x - block2.bbox.x2),
            abs(block1.bbox.x2 - block2.bbox.x)
        )
        
        # 垂直方向の距離
        v_distance = min(
            abs(block1.bbox.y - block2.bbox.y2),
            abs(block1.bbox.y2 - block2.bbox.y)
        )
        
        # どちらかが閾値以下なら近接と判定
        return min(h_distance, v_distance) <= self.merge_threshold
    
    def _merge_blocks(self, blocks: List[Block]) -> Block:
        """複数のブロックをマージ"""
        # バウンディングボックスを計算
        min_x = min(b.bbox.x for b in blocks)
        min_y = min(b.bbox.y for b in blocks)
        max_x = max(b.bbox.x2 for b in blocks)
        max_y = max(b.bbox.y2 for b in blocks)
        
        merged_bbox = BoundingBox(
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y
        )
        
        # 要素を結合
        merged_elements = []
        for block in blocks:
            merged_elements.extend(block.elements)
        
        # 新しいブロックを作成
        return Block(
            block_id=str(uuid.uuid4()),
            block_type=blocks[0].block_type,
            bbox=merged_bbox,
            elements=merged_elements,
            page=blocks[0].page,
            layout_role=blocks[0].layout_role,
            confidence=min(b.confidence for b in blocks)
        )
    
    
    def _infer_layout_roles(self, blocks: List[Block], page: Any):
        """レイアウト役割を推定"""
        if not blocks:
            return
        
        # ページを垂直方向に分割してカラムを検出
        page_width = getattr(page, 'width', 800)
        
        # X座標でグループ化
        x_groups = defaultdict(list)
        for block in blocks:
            # 左端のX座標で大まかにグループ化
            group_x = int(block.bbox.x / 50) * 50  # 50ポイント単位
            x_groups[group_x].append(block)
        
        # メインコンテンツエリアを特定（最も多くのブロックがあるグループ）
        if x_groups:
            main_group = max(x_groups.values(), key=len)
            
            for block in blocks:
                if block in main_group:
                    block.layout_role = LayoutRole.MAIN_CONTENT
                elif block.bbox.x < page_width * 0.2:
                    # 左側20%はサイドコンテンツ
                    block.layout_role = LayoutRole.SIDE_CONTENT
                elif block.bbox.x > page_width * 0.8:
                    # 右側20%もサイドコンテンツ
                    block.layout_role = LayoutRole.SIDE_CONTENT
                elif block.block_type in [BlockType.HEADER, BlockType.TITLE]:
                    block.layout_role = LayoutRole.HEADER_CONTENT
                elif block.block_type in [BlockType.FOOTER, BlockType.PAGE_NUMBER]:
                    block.layout_role = LayoutRole.FOOTER_CONTENT
                else:
                    block.layout_role = LayoutRole.FLOATING_CONTENT
    
    def _build_hierarchy(self, blocks: List[Block]):
        """ブロック間の階層構造を構築"""
        # 包含関係に基づいて親子関係を設定
        for i, parent in enumerate(blocks):
            for j, child in enumerate(blocks):
                if i != j and parent.bbox.contains(child.bbox):
                    # 既に他の親がいる場合はスキップ
                    if child.parent_id is None:
                        child.parent_id = parent.block_id
                        parent.children_ids.append(child.block_id)
    
    def _polygon_to_bbox(self, polygon: List[float]) -> BoundingBox:
        """ポリゴンデータからBoundingBoxを作成"""
        if len(polygon) < 8:
            return BoundingBox(0, 0, 0, 0)
        
        # [x1,y1,x2,y2,x3,y3,x4,y4] 形式を想定
        x_coords = [polygon[i] for i in range(0, 8, 2)]
        y_coords = [polygon[i] for i in range(1, 8, 2)]
        
        min_x = min(x_coords)
        min_y = min(y_coords)
        max_x = max(x_coords)
        max_y = max(y_coords)
        
        # インチからポイントに変換（1インチ = 72ポイント）
        return BoundingBox(
            x=min_x * 72,
            y=min_y * 72,
            width=(max_x - min_x) * 72,
            height=(max_y - min_y) * 72
        )
    
    def _get_page_number(self, element: Any) -> int:
        """要素のページ番号を取得"""
        if hasattr(element, 'bounding_regions') and element.bounding_regions:
            return element.bounding_regions[0].page_number - 1  # 0-indexed
        return 0
    
    def _get_span_text(self, span: Any, parent: Any) -> str:
        """スパンからテキストを取得"""
        if hasattr(parent, 'content') and hasattr(span, 'offset') and hasattr(span, 'length'):
            return parent.content[span.offset:span.offset + span.length]
        return ""
    
    def _is_page_number(self, text: str) -> bool:
        """ページ番号かどうか判定"""
        text = text.strip()
        # 数字のみ、またはページ番号パターン
        return (text.isdigit() or 
                any(pattern in text.lower() for pattern in ['page', 'ページ', 'p.', '-']))
    
    def _infer_block_type(self, content: str, bbox: BoundingBox, page_data: Any) -> BlockType:
        """コンテンツと位置からブロックタイプを推定"""
        # テキストがない場合
        if not content or not content.strip():
            return BlockType.UNKNOWN
        
        # ページ番号の可能性をチェック
        if self._is_page_number(content):
            # ページ下部にある小さな数字はページ番号の可能性が高い
            if bbox.y > 700 and bbox.area < 1000:
                return BlockType.PAGE_NUMBER
        
        # タイトルの可能性をチェック（大きなフォントサイズ、上部配置）
        if bbox.y < 200 and bbox.height > 20:
            # 最初のページの上部にある大きなテキストはタイトルの可能性
            return BlockType.TITLE
        
        # ヘッダー・フッターのチェック
        if bbox.y < 100:
            return BlockType.HEADER
        elif bbox.y > 700:
            return BlockType.FOOTER
        
        # テーブルのセルの可能性（小さくて整列している）
        if bbox.area < 500 and bbox.width < 100:
            return BlockType.UNKNOWN  # テーブルセルは親テーブルで処理されるべき
        
        # デフォルトは段落
        return BlockType.PARAGRAPH