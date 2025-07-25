"""
ブロックベースのモデル定義
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class BlockType(Enum):
    """ブロックタイプ"""
    HEADER = "header"
    FOOTER = "footer"
    TITLE = "title"
    SUBTITLE = "subtitle"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    LIST = "list"
    SIDEBAR = "sidebar"
    FOOTNOTE = "footnote"
    PAGE_NUMBER = "page_number"
    UNKNOWN = "unknown"


class LayoutRole(Enum):
    """レイアウト上の役割"""
    MAIN_CONTENT = "main_content"
    SIDE_CONTENT = "side_content"
    HEADER_CONTENT = "header_content"
    FOOTER_CONTENT = "footer_content"
    FLOATING_CONTENT = "floating_content"


@dataclass
class BoundingBox:
    """バウンディングボックス"""
    x: float
    y: float
    width: float
    height: float
    
    @property
    def x2(self) -> float:
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        return self.y + self.height
    
    @property
    def center_x(self) -> float:
        return self.x + self.width / 2
    
    @property
    def center_y(self) -> float:
        return self.y + self.height / 2
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    def contains(self, other: 'BoundingBox') -> bool:
        """他のBBoxがこのBBox内に含まれるかチェック"""
        return (self.x <= other.x and 
                self.y <= other.y and 
                self.x2 >= other.x2 and 
                self.y2 >= other.y2)
    
    def intersects(self, other: 'BoundingBox') -> bool:
        """他のBBoxと交差するかチェック"""
        return not (self.x2 < other.x or 
                    self.x > other.x2 or 
                    self.y2 < other.y or 
                    self.y > other.y2)
    
    def intersection_area(self, other: 'BoundingBox') -> float:
        """交差面積を計算"""
        if not self.intersects(other):
            return 0.0
        
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x2, other.x2)
        y2 = min(self.y2, other.y2)
        
        return (x2 - x1) * (y2 - y1)
    
    def iou(self, other: 'BoundingBox') -> float:
        """IoU (Intersection over Union) を計算"""
        intersection = self.intersection_area(other)
        union = self.area + other.area - intersection
        return intersection / union if union > 0 else 0.0


@dataclass
class TextElement:
    """テキスト要素"""
    text: str
    bbox: BoundingBox
    confidence: float = 1.0
    font_size: Optional[float] = None
    font_family: Optional[str] = None
    is_bold: bool = False
    is_italic: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'bbox': [self.bbox.x, self.bbox.y, self.bbox.width, self.bbox.height],
            'confidence': self.confidence,
            'font_size': self.font_size,
            'font_family': self.font_family,
            'is_bold': self.is_bold,
            'is_italic': self.is_italic
        }


@dataclass
class Block:
    """ドキュメントブロック"""
    block_id: str
    block_type: BlockType
    bbox: BoundingBox
    elements: List[TextElement] = field(default_factory=list)
    layout_role: LayoutRole = LayoutRole.MAIN_CONTENT
    page: int = 0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 階層構造
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    
    # 読み順序
    reading_order: Optional[int] = None
    
    @property
    def text(self) -> str:
        """ブロック内のテキストを結合"""
        if not self.elements:
            return ""
        
        # 要素を読み順序でソート（まずY座標、次にX座標）
        sorted_elements = sorted(
            self.elements,
            key=lambda e: (e.bbox.y, e.bbox.x)
        )
        
        # テキストを結合
        texts = []
        prev_y = None
        current_line = []
        
        for elem in sorted_elements:
            # 新しい行かチェック
            if prev_y is not None and abs(elem.bbox.y - prev_y) > elem.bbox.height * 0.5:
                # 前の行を結合
                if current_line:
                    texts.append(" ".join(current_line))
                current_line = [elem.text]
            else:
                current_line.append(elem.text)
            prev_y = elem.bbox.y
        
        # 最後の行を追加
        if current_line:
            texts.append(" ".join(current_line))
        
        return "\n".join(texts)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'block_id': self.block_id,
            'block_type': self.block_type.value,
            'bbox': [self.bbox.x, self.bbox.y, self.bbox.width, self.bbox.height],
            'text': self.text,
            'elements': [elem.to_dict() for elem in self.elements],
            'layout_role': self.layout_role.value,
            'page': self.page,
            'confidence': self.confidence,
            'metadata': self.metadata,
            'parent_id': self.parent_id,
            'children_ids': self.children_ids,
            'reading_order': self.reading_order
        }


@dataclass
class DocumentStructure:
    """文書構造"""
    blocks: List[Block]
    pages: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_blocks_by_page(self, page: int) -> List[Block]:
        """指定ページのブロックを取得"""
        return [b for b in self.blocks if b.page == page]
    
    def get_blocks_by_type(self, block_type: BlockType) -> List[Block]:
        """指定タイプのブロックを取得"""
        return [b for b in self.blocks if b.block_type == block_type]
    
    def get_ordered_blocks(self) -> List[Block]:
        """読み順序でソートされたブロックを取得"""
        return sorted(
            self.blocks,
            key=lambda b: (b.page, b.reading_order or float('inf'))
        )


@dataclass
class BlockDifference:
    """ブロック単位の差分"""
    change_type: str  # "added", "deleted", "modified", "moved"
    block1: Optional[Block] = None
    block2: Optional[Block] = None
    similarity: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'change_type': self.change_type,
            'block1': self.block1.to_dict() if self.block1 else None,
            'block2': self.block2.to_dict() if self.block2 else None,
            'similarity': self.similarity,
            'details': self.details
        }