"""
BBox based data models
"""
from typing import TypedDict, List, Optional, Literal
from enum import Enum
from dataclasses import dataclass


class BBoxTextData(TypedDict):
    """単語単位のbounding boxとテキストデータ"""
    bbox: List[float]  # [x, y, width, height]
    text: str          # 単語単位のテキスト
    page: int          # ページ番号


class ChangeType(Enum):
    """変更タイプの列挙型"""
    DIFFERENCE = "difference"  # 統一された差分タイプ
    # 互換性のため旧タイプも保持
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"


@dataclass
class DiffResult:
    """差分検出結果"""
    change_type: ChangeType
    original_bbox: Optional[BBoxTextData]
    modified_bbox: Optional[BBoxTextData]
    page: int
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'change_type': self.change_type.value,
            'original_bbox': self.original_bbox,
            'modified_bbox': self.modified_bbox,
            'page': self.page,
            'confidence': self.confidence
        }


@dataclass
class Highlight:
    """ハイライト情報"""
    bbox: List[float]  # [x, y, width, height]
    page: int
    color: str  # "red", "green", "yellow", "blue"
    label: Optional[str] = None  # 読み順序の番号など
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'bbox': self.bbox,
            'page': self.page,
            'color': self.color,
            'label': self.label
        }