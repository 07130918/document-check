"""
表関連のモデル定義
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .bbox_models import ChangeType


@dataclass
class TableDiffResult:
    """表の差分結果"""
    table_index1: int
    table_index2: Optional[int]
    change_type: ChangeType
    structure_changes: List[str]  # 構造変更（行・列の追加削除）
    cell_changes: List[Dict[str, Any]]  # セル内容の変更
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（JSON化可能）"""
        return {
            "table_index1": self.table_index1,
            "table_index2": self.table_index2,
            "change_type": self.change_type.value,
            "structure_changes": self.structure_changes,
            "cell_changes": self.cell_changes,
            "summary": self.summary
        }