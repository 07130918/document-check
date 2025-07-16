"""
Data models for document diff system
"""
from .bbox_models import BBoxTextData, DiffResult, ChangeType, Highlight

__all__ = ['BBoxTextData', 'DiffResult', 'ChangeType', 'Highlight']