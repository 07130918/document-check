"""
LLM enhanced BBox based data models
"""
from typing import TypedDict, List, Optional, Literal, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class BBoxTextData(TypedDict):
    """単語単位のbounding boxとテキストデータ"""
    bbox: List[float]  # [x, y, width, height]
    text: str          # 単語単位のテキスト
    page: int          # ページ番号


class ChangeType(Enum):
    """変更タイプの列挙型"""
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"


@dataclass
class DiffResult:
    """差分検出結果（LLM拡張版）"""
    change_type: ChangeType
    original_bbox: Optional[BBoxTextData]
    modified_bbox: Optional[BBoxTextData]
    page: int
    confidence: float = 1.0
    # LLM拡張フィールド
    semantic_similarity: float = 0.0  # 意味的類似度
    context: Optional[str] = None  # 文脈情報
    llm_explanation: Optional[str] = None  # LLMによる説明
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'change_type': self.change_type.value,
            'original_bbox': self.original_bbox,
            'modified_bbox': self.modified_bbox,
            'page': self.page,
            'confidence': self.confidence,
            'semantic_similarity': self.semantic_similarity,
            'context': self.context,
            'llm_explanation': self.llm_explanation
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


@dataclass
class LLMAnalysisResult:
    """LLMによる文書解析結果"""
    document_summary: str  # 文書要約
    structure_analysis: Dict[str, Any]  # 文書構造解析
    key_changes: List[str]  # 主要な変更点
    risk_assessment: Dict[str, float]  # リスク評価
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'document_summary': self.document_summary,
            'structure_analysis': self.structure_analysis,
            'key_changes': self.key_changes,
            'risk_assessment': self.risk_assessment,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ComparisonResult:
    """文書比較結果（統合版）"""
    diff_results: List[DiffResult]
    reading_order_doc1: List[BBoxTextData]
    reading_order_doc2: List[BBoxTextData]
    llm_analysis: Optional[LLMAnalysisResult] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'diff_results': [d.to_dict() for d in self.diff_results],
            'reading_order_doc1': self.reading_order_doc1,
            'reading_order_doc2': self.reading_order_doc2,
            'llm_analysis': self.llm_analysis.to_dict() if self.llm_analysis else None,
            'execution_time': self.execution_time,
            'metadata': self.metadata
        }