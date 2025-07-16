"""
Sequential Difference Detector with Order Tolerance
順序を考慮した差分検出器（順序のズレ許容機能付き）
"""
import logging
from typing import List, Tuple, Optional, Dict
import time
from difflib import SequenceMatcher
from dataclasses import dataclass

from apps.pdf_diff_system_withannotation.app.domain.interfaces.diff_detector_interface import DiffDetectorInterface
from apps.pdf_diff_system_withannotation.app.domain.models.diff_result import DiffResult, ChangeType
from .text_normalizer import TextNormalizer
from .mecab_tokenizer import MeCabTokenizer

logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """アラインメント結果"""
    action: str  # 'match', 'substitute', 'delete', 'insert'
    phrase1_idx: Optional[int]
    phrase2_idx: Optional[int]
    phrase1: Optional[str]
    phrase2: Optional[str]
    similarity_score: float = 0.0


class SequentialDiffDetector(DiffDetectorInterface):
    """順序を考慮した差分検出器"""

    def __init__(self, window_size: int = 3, similarity_threshold: float = 0.85):
        """
        Args:
            window_size: 順序のズレを許容する範囲（前後のフレーズ数）
            similarity_threshold: 類似と判定する閾値
        """
        self.tokenizer = MeCabTokenizer()
        self.normalizer = TextNormalizer()
        self.window_size = window_size
        self.similarity_threshold = similarity_threshold
        logger.info(f"SequentialDiffDetector initialized (window={window_size}, threshold={similarity_threshold})")

    def detect_differences(self, doc1_text: str, doc2_text: str) -> List[DiffResult]:
        """
        順序を考慮した差分検出

        Args:
            doc1_text: 元文書テキスト
            doc2_text: 比較文書テキスト

        Returns:
            検出された差分のリスト
        """
        logger.debug("=== 順序考慮型差分検出開始 ===")

        # テキストの正規化
        doc1_normalized = self.normalizer.normalize(doc1_text)
        doc2_normalized = self.normalizer.normalize(doc2_text)

        # フレーズに分割
        phrases1 = self._segment_into_phrases(doc1_normalized)
        phrases2 = self._segment_into_phrases(doc2_normalized)

        logger.debug(f"Doc1: {len(phrases1)} phrases, Doc2: {len(phrases2)} phrases")

        # 順序を考慮したアラインメント
        alignments = self._align_sequences_with_tolerance(phrases1, phrases2)

        # アラインメント結果から差分を生成
        differences = self._generate_differences_from_alignments(alignments)

        logger.debug(f"検出された差分数: {len(differences)}")
        return differences

    def _segment_into_phrases(self, text: str) -> List[str]:
        """テキストをフレーズに分割（既存の実装を簡略化）"""
        import re

        if not text.strip():
            return []

        # 基本的な区切り文字での分割
        # スペース、句読点、改行で分割
        phrases = re.split(r'[\s　。、！？\n]+', text.strip())

        # 空のフレーズを除去
        phrases = [p.strip() for p in phrases if p.strip()]

        return phrases

    def _align_sequences_with_tolerance(self, phrases1: List[str], phrases2: List[str]) -> List[AlignmentResult]:
        """
        順序のズレを許容するシーケンスアラインメント

        動的計画法ベースで、window_size内での最適マッチングを探す
        """
        n, m = len(phrases1), len(phrases2)

        # DP table: dp[i][j] = (score, action, prev_i, prev_j)
        dp = [[(-float('inf'), '', -1, -1) for _ in range(m + 1)] for _ in range(n + 1)]
        dp[0][0] = (0.0, 'start', -1, -1)

        # 初期化：最初の行と列
        for i in range(1, n + 1):
            dp[i][0] = (dp[i-1][0][0] - 1.0, 'delete', i-1, 0)
        for j in range(1, m + 1):
            dp[0][j] = (dp[0][j-1][0] - 1.0, 'insert', 0, j-1)

        # DP計算
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                # window内の範囲を計算
                window_start = max(1, j - self.window_size)
                window_end = min(m + 1, j + self.window_size + 1)

                best_score = -float('inf')
                best_action = ''
                best_prev_i = -1
                best_prev_j = -1

                # 削除（i-1からiへ、jは変わらない）
                if dp[i-1][j][0] > -float('inf'):
                    score = dp[i-1][j][0] - 1.0
                    if score > best_score:
                        best_score = score
                        best_action = 'delete'
                        best_prev_i = i - 1
                        best_prev_j = j

                # 挿入（iは変わらない、j-1からjへ）
                if dp[i][j-1][0] > -float('inf'):
                    score = dp[i][j-1][0] - 1.0
                    if score > best_score:
                        best_score = score
                        best_action = 'insert'
                        best_prev_i = i
                        best_prev_j = j - 1

                # マッチ/置換（window内の範囲で探す）
                for k in range(max(0, j - self.window_size), j):
                    if dp[i-1][k][0] > -float('inf'):
                        # jとkの距離によるペナルティ
                        distance_penalty = abs(j - k - 1) * 0.1

                        similarity = self._calculate_similarity(phrases1[i-1], phrases2[j-1])

                        if similarity >= self.similarity_threshold:
                            # マッチ（高い類似度）
                            score = dp[i-1][k][0] + 2.0 - distance_penalty
                            if score > best_score:
                                best_score = score
                                best_action = 'match'
                                best_prev_i = i - 1
                                best_prev_j = k
                        elif similarity > 0.3:  # ある程度似ている場合は置換
                            # 置換
                            score = dp[i-1][k][0] + similarity - 1.0 - distance_penalty
                            if score > best_score:
                                best_score = score
                                best_action = 'substitute'
                                best_prev_i = i - 1
                                best_prev_j = k

                dp[i][j] = (best_score, best_action, best_prev_i, best_prev_j)

        # バックトラッキングで最適パスを復元
        alignments = self._backtrack_alignment(dp, phrases1, phrases2, n, m)

        return alignments

    def _backtrack_alignment(self, dp: List[List[Tuple]], phrases1: List[str], phrases2: List[str],
                            n: int, m: int) -> List[AlignmentResult]:
        """DPテーブルから最適なアラインメントを復元"""
        alignments = []
        i, j = n, m

        while i > 0 or j > 0:
            if i == 0:
                # 残りはすべて挿入
                alignments.append(AlignmentResult(
                    action='insert',
                    phrase1_idx=None,
                    phrase2_idx=j-1,
                    phrase1=None,
                    phrase2=phrases2[j-1],
                    similarity_score=0.0
                ))
                j -= 1
                continue

            if j == 0:
                # 残りはすべて削除
                alignments.append(AlignmentResult(
                    action='delete',
                    phrase1_idx=i-1,
                    phrase2_idx=None,
                    phrase1=phrases1[i-1],
                    phrase2=None,
                    similarity_score=0.0
                ))
                i -= 1
                continue

            score, action, prev_i, prev_j = dp[i][j]

            if action == 'match' or action == 'substitute':
                # prev_jからjまでのギャップに挿入を追加
                for k in range(prev_j + 1, j):
                    alignments.append(AlignmentResult(
                        action='insert',
                        phrase1_idx=None,
                        phrase2_idx=k,
                        phrase1=None,
                        phrase2=phrases2[k],
                        similarity_score=0.0
                    ))

                # マッチまたは置換
                alignments.append(AlignmentResult(
                    action=action,
                    phrase1_idx=i-1,
                    phrase2_idx=j-1,
                    phrase1=phrases1[i-1],
                    phrase2=phrases2[j-1],
                    similarity_score=self._calculate_similarity(phrases1[i-1], phrases2[j-1])
                ))

            elif action == 'delete':
                alignments.append(AlignmentResult(
                    action='delete',
                    phrase1_idx=i-1,
                    phrase2_idx=None,
                    phrase1=phrases1[i-1],
                    phrase2=None,
                    similarity_score=0.0
                ))
            elif action == 'insert':
                alignments.append(AlignmentResult(
                    action='insert',
                    phrase1_idx=None,
                    phrase2_idx=j-1,
                    phrase1=None,
                    phrase2=phrases2[j-1],
                    similarity_score=0.0
                ))

            i, j = prev_i, prev_j

        # 逆順になっているので反転
        alignments.reverse()

        return alignments

    def _calculate_similarity(self, phrase1: str, phrase2: str) -> float:
        """フレーズ間の類似度を計算"""
        if not phrase1 or not phrase2:
            return 0.0

        # 正規化
        norm1 = self.normalizer.normalize(phrase1)
        norm2 = self.normalizer.normalize(phrase2)

        # SequenceMatcherで類似度計算
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()

    def _generate_differences_from_alignments(self, alignments: List[AlignmentResult]) -> List[DiffResult]:
        """アラインメント結果から差分リストを生成"""
        differences = []

        for alignment in alignments:
            if alignment.action == 'match':
                # 一致は差分として記録しない
                continue

            elif alignment.action == 'substitute':
                differences.append(DiffResult(
                    change_type=ChangeType.MODIFICATION,
                    confidence_score=0.9,
                    original_text=alignment.phrase1,
                    modified_text=alignment.phrase2,
                    similarity_score=alignment.similarity_score,
                    detection_method="sequential_alignment"
                ))

            elif alignment.action == 'delete':
                differences.append(DiffResult(
                    change_type=ChangeType.DELETION,
                    confidence_score=0.95,
                    original_text=alignment.phrase1,
                    modified_text=None,
                    similarity_score=0.0,
                    detection_method="sequential_alignment"
                ))

            elif alignment.action == 'insert':
                differences.append(DiffResult(
                    change_type=ChangeType.ADDITION,
                    confidence_score=0.95,
                    original_text=None,
                    modified_text=alignment.phrase2,
                    similarity_score=0.0,
                    detection_method="sequential_alignment"
                ))

        return differences

    def visualize_alignment(self, doc1_text: str, doc2_text: str) -> str:
        """アラインメント結果を視覚化（デバッグ用）"""
        phrases1 = self._segment_into_phrases(self.normalizer.normalize(doc1_text))
        phrases2 = self._segment_into_phrases(self.normalizer.normalize(doc2_text))
        alignments = self._align_sequences_with_tolerance(phrases1, phrases2)

        output = []
        output.append("=== アラインメント結果 ===\n")
        output.append(f"Window size: {self.window_size}, Similarity threshold: {self.similarity_threshold}\n")
        output.append("-" * 80 + "\n")

        for align in alignments:
            if align.action == 'match':
                output.append(f"[MATCH] '{align.phrase1}' = '{align.phrase2}' (sim: {align.similarity_score:.2f})\n")
            elif align.action == 'substitute':
                output.append(f"[MODIFY] '{align.phrase1}' → '{align.phrase2}' (sim: {align.similarity_score:.2f})\n")
            elif align.action == 'delete':
                output.append(f"[DELETE] '{align.phrase1}' ✗\n")
            elif align.action == 'insert':
                output.append(f"[INSERT] ✓ '{align.phrase2}'\n")

        return "".join(output)

    def measure_performance(self, doc1_text: str, doc2_text: str) -> dict:
        """
        性能測定を実行

        Args:
            doc1_text: 元文書テキスト
            doc2_text: 比較文書テキスト

        Returns:
            性能メトリクス
        """
        start_time = time.time()

        # 差分検出実行
        differences = self.detect_differences(doc1_text, doc2_text)

        end_time = time.time()
        processing_time = end_time - start_time

        # フレーズ統計
        phrases1 = self._segment_into_phrases(self.normalizer.normalize(doc1_text))
        phrases2 = self._segment_into_phrases(self.normalizer.normalize(doc2_text))

        performance_metrics = {
            "processing_time": processing_time,
            "differences_count": len(differences),
            "doc1_phrases": len(phrases1),
            "doc2_phrases": len(phrases2),
            "detection_method": "sequential_alignment",
            "window_size": self.window_size,
            "similarity_threshold": self.similarity_threshold,
            "additions": len([d for d in differences if d.change_type == ChangeType.ADDITION]),
            "deletions": len([d for d in differences if d.change_type == ChangeType.DELETION]),
            "modifications": len([d for d in differences if d.change_type == ChangeType.MODIFICATION])
        }

        logger.info(f"順序考慮型差分検出完了: {processing_time:.2f}秒, {len(differences)}件の差分")
        return performance_metrics
