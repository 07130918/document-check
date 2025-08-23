"""
拡張差分検出器
"""
from typing import List, Dict, Any, Optional, Tuple
import difflib
import logging
from dataclasses import dataclass

from ..models.bbox_models import BBoxTextData, DiffResult, ChangeType

logger = logging.getLogger(__name__)


class EnhancedDiffDetector:
    """LLM拡張差分検出器"""
    
    def __init__(self, similarity_threshold: float = 0.8):
        """初期化
        
        Args:
            similarity_threshold: 類似度の閾値
        """
        self.similarity_threshold = similarity_threshold
    
    def detect_differences(self, bbox_list1: List[BBoxTextData], 
                         bbox_list2: List[BBoxTextData]) -> List[DiffResult]:
        """2つの文書間の差分を検出
        
        Args:
            bbox_list1: 文書1のBBoxデータリスト
            bbox_list2: 文書2のBBoxデータリスト
            
        Returns:
            差分結果のリスト
        """
        diff_results = []
        
        # テキストの配列を作成
        texts1 = [bbox["text"] for bbox in bbox_list1]
        texts2 = [bbox["text"] for bbox in bbox_list2]
        
        # difflibで差分を検出
        matcher = difflib.SequenceMatcher(None, texts1, texts2)
        
        # 各操作を処理
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            
            elif tag == 'delete':
                # 削除された要素
                for i in range(i1, i2):
                    diff_results.append(DiffResult(
                        change_type=ChangeType.DELETION,
                        original_bbox=bbox_list1[i],
                        modified_bbox=None,
                        page=bbox_list1[i]["page"]
                    ))
            
            elif tag == 'insert':
                # 追加された要素
                for j in range(j1, j2):
                    diff_results.append(DiffResult(
                        change_type=ChangeType.ADDITION,
                        original_bbox=None,
                        modified_bbox=bbox_list2[j],
                        page=bbox_list2[j]["page"]
                    ))
            
            elif tag == 'replace':
                # 置換された要素
                # より詳細な分析を行う
                self._analyze_replacement(
                    bbox_list1[i1:i2],
                    bbox_list2[j1:j2],
                    diff_results
                )
        
        # 文脈情報を追加
        self._add_context_information(diff_results, bbox_list1, bbox_list2)
        
        logger.info(f"Detected {len(diff_results)} differences")
        return diff_results
    
    def _analyze_replacement(self, old_bboxes: List[BBoxTextData],
                           new_bboxes: List[BBoxTextData],
                           diff_results: List[DiffResult]):
        """置換操作をより詳細に分析
        
        Args:
            old_bboxes: 元のBBoxリスト
            new_bboxes: 新しいBBoxリスト
            diff_results: 差分結果を追加するリスト
        """
        # 簡単なケース: 1対1の置換
        if len(old_bboxes) == 1 and len(new_bboxes) == 1:
            old_text = old_bboxes[0]["text"]
            new_text = new_bboxes[0]["text"]
            
            # 類似度を計算
            similarity = difflib.SequenceMatcher(None, old_text, new_text).ratio()
            
            diff_results.append(DiffResult(
                change_type=ChangeType.MODIFICATION,
                original_bbox=old_bboxes[0],
                modified_bbox=new_bboxes[0],
                page=old_bboxes[0]["page"],
                confidence=1.0,
                semantic_similarity=similarity
            ))
            return
        
        # 複雑なケース: 複数要素の置換
        # まず全体を結合してみる
        old_text = " ".join(bbox["text"] for bbox in old_bboxes)
        new_text = " ".join(bbox["text"] for bbox in new_bboxes)
        
        similarity = difflib.SequenceMatcher(None, old_text, new_text).ratio()
        
        if similarity > self.similarity_threshold:
            # 高い類似度: 修正として扱う
            for old_bbox in old_bboxes:
                diff_results.append(DiffResult(
                    change_type=ChangeType.DELETION,
                    original_bbox=old_bbox,
                    modified_bbox=None,
                    page=old_bbox["page"]
                ))
            
            for new_bbox in new_bboxes:
                diff_results.append(DiffResult(
                    change_type=ChangeType.ADDITION,
                    original_bbox=None,
                    modified_bbox=new_bbox,
                    page=new_bbox["page"]
                ))
        else:
            # 低い類似度: 削除と追加として扱う
            for old_bbox in old_bboxes:
                diff_results.append(DiffResult(
                    change_type=ChangeType.DELETION,
                    original_bbox=old_bbox,
                    modified_bbox=None,
                    page=old_bbox["page"]
                ))
            
            for new_bbox in new_bboxes:
                diff_results.append(DiffResult(
                    change_type=ChangeType.ADDITION,
                    original_bbox=None,
                    modified_bbox=new_bbox,
                    page=new_bbox["page"]
                ))
    
    def _add_context_information(self, diff_results: List[DiffResult],
                                bbox_list1: List[BBoxTextData],
                                bbox_list2: List[BBoxTextData]):
        """差分に文脈情報を追加
        
        Args:
            diff_results: 差分結果のリスト
            bbox_list1: 文書1のBBoxデータ
            bbox_list2: 文書2のBBoxデータ
        """
        # 各BBoxのインデックスマップを作成
        bbox1_map = {id(bbox): i for i, bbox in enumerate(bbox_list1)}
        bbox2_map = {id(bbox): i for i, bbox in enumerate(bbox_list2)}
        
        for diff in diff_results:
            context_words = []
            
            # 元の文書での前後の文脈を取得
            if diff.original_bbox:
                idx = bbox1_map.get(id(diff.original_bbox))
                if idx is not None:
                    # 前後3単語を文脈として取得
                    start_idx = max(0, idx - 3)
                    end_idx = min(len(bbox_list1), idx + 4)
                    
                    for i in range(start_idx, end_idx):
                        if i != idx:
                            context_words.append(bbox_list1[i]["text"])
            
            # 変更後の文書での前後の文脈を取得
            if diff.modified_bbox:
                idx = bbox2_map.get(id(diff.modified_bbox))
                if idx is not None:
                    start_idx = max(0, idx - 3)
                    end_idx = min(len(bbox_list2), idx + 4)
                    
                    for i in range(start_idx, end_idx):
                        if i != idx:
                            context_words.append(bbox_list2[i]["text"])
            
            # 文脈を設定
            if context_words:
                diff.context = " ".join(context_words[:6])  # 最大6単語