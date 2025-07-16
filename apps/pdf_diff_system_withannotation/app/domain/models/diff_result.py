"""
Domain Models - 差分検出結果関連
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ChangeType(Enum):
    """変更タイプ列挙型"""
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"


class DifficultyLevel(Enum):
    """テストケース難易度"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class DiffResult:
    """差分検出結果ドメインモデル"""
    change_type: ChangeType
    confidence_score: float
    original_text: Optional[str]
    modified_text: Optional[str]
    similarity_score: float
    detection_method: str = "unknown"
    
    def __post_init__(self):
        """ドメインルール検証"""
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError("similarity_score must be between 0.0 and 1.0")


@dataclass
class TestCase:
    """テストケースドメインモデル"""
    case_id: str
    name: str
    difficulty: DifficultyLevel
    doc1_text: str
    doc2_text: str
    description: str = ""
    
    def __post_init__(self):
        """ドメインルール検証"""
        if not self.case_id:
            raise ValueError("case_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")