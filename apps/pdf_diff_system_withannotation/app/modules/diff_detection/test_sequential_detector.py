#!/usr/bin/env python3
"""
Sequential Diff Detector のテストスクリプト
順序を考慮した差分検出の動作確認
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.pdf_diff_system_withannotation.app.modules.diff_detection.sequential_diff_detector import SequentialDiffDetector
from apps.pdf_diff_system_withannotation.app.modules.diff_detection.phrase_based_diff_detector import PhraseBasedDiffDetector


def test_basic_sequential_detection():
    """基本的な順序考慮型差分検出のテスト"""
    print("=== 基本的な順序考慮型差分検出テスト ===\n")

    # テストケース1: 順序が保たれている場合
    doc1 = "令和5年度 保存版 MS&ADインシュアランスグループ 団体保険制度"
    doc2 = "令和6年度 保存版 MS&ADインシュアランスグループ 団体保険制度"

    detector = SequentialDiffDetector(window_size=3, similarity_threshold=0.7)
    differences = detector.detect_differences(doc1, doc2)

    print(f"文書1: {doc1}")
    print(f"文書2: {doc2}")
    print(f"\n検出された差分: {len(differences)}件")
    for diff in differences:
        print(f"  - {diff.change_type.value}: '{diff.original_text}' → '{diff.modified_text}'")

    # アラインメントの可視化
    print("\n" + detector.visualize_alignment(doc1, doc2))


def test_order_tolerance():
    """順序のズレ許容テスト"""
    print("\n=== 順序のズレ許容テスト ===\n")

    # テストケース2: 順序が入れ替わっている場合
    doc1 = "住宅 購入 子供 独立 退職"
    doc2 = "住宅 子供 購入 独立 退職"  # "購入"と"子供"が入れ替わっている

    # window_size=1（厳密）
    detector_strict = SequentialDiffDetector(window_size=1, similarity_threshold=0.8)
    differences_strict = detector_strict.detect_differences(doc1, doc2)

    print("Window size = 1 (厳密):")
    print(f"  差分数: {len(differences_strict)}")

    # window_size=3（寛容）
    detector_tolerant = SequentialDiffDetector(window_size=3, similarity_threshold=0.8)
    differences_tolerant = detector_tolerant.detect_differences(doc1, doc2)

    print("\nWindow size = 3 (寛容):")
    print(f"  差分数: {len(differences_tolerant)}")
    print("\n" + detector_tolerant.visualize_alignment(doc1, doc2))


def test_complex_case():
    """複雑なケースのテスト"""
    print("\n=== 複雑なケースのテスト ===\n")

    doc1 = """令和5年10月25日 午後4時
iOS 11/12/13/14/15/16
約1.8万人"""

    doc2 = """令和6年10月23日 午後4時
iOS 11/12/13/14/15/16/17
約1.6万人"""

    detector = SequentialDiffDetector(window_size=2, similarity_threshold=0.7)
    differences = detector.detect_differences(doc1, doc2)

    print(f"検出された差分: {len(differences)}件")
    for diff in differences:
        print(f"  - {diff.change_type.value}: '{diff.original_text}' → '{diff.modified_text}'")
        print(f"    信頼度: {diff.confidence_score:.2f}, 類似度: {diff.similarity_score:.2f}")


def compare_with_baseline():
    """既存のフレーズベース検出器との比較"""
    print("\n=== 既存手法との比較 ===\n")

    doc1 = "詳細は P4 を ご覧ください。 令和5年度 版"
    doc2 = "令和6年度 版 詳細は P5 を ご覧ください。"  # 順序が大きく変更

    # 既存のフレーズベース（順序無視）
    baseline = PhraseBasedDiffDetector()
    baseline_diffs = baseline.detect_differences(doc1, doc2)

    print("既存手法（順序無視）:")
    print(f"  差分数: {len(baseline_diffs)}")
    for diff in baseline_diffs[:3]:  # 最初の3件のみ
        print(f"  - {diff.change_type.value}: '{diff.original_text}' → '{diff.modified_text}'")

    # 新手法（順序考慮）
    sequential = SequentialDiffDetector(window_size=3, similarity_threshold=0.8)
    sequential_diffs = sequential.detect_differences(doc1, doc2)

    print("\n新手法（順序考慮）:")
    print(f"  差分数: {len(sequential_diffs)}")
    for diff in sequential_diffs:
        print(f"  - {diff.change_type.value}: '{diff.original_text}' → '{diff.modified_text}'")

    print("\n" + sequential.visualize_alignment(doc1, doc2))


def test_performance():
    """パフォーマンステスト"""
    print("\n=== パフォーマンステスト ===\n")

    import time

    # 長い文書のシミュレーション
    doc1 = " ".join([f"フレーズ{i}" for i in range(100)])
    doc2 = " ".join([f"フレーズ{i}" if i % 10 != 0 else f"変更{i}" for i in range(100)])

    # window_sizeによる性能差
    for window_size in [1, 3, 5, 10]:
        detector = SequentialDiffDetector(window_size=window_size)

        start_time = time.time()
        differences = detector.detect_differences(doc1, doc2)
        elapsed_time = time.time() - start_time

        print(f"Window size={window_size}: {elapsed_time:.3f}秒, {len(differences)}件の差分")


if __name__ == "__main__":
    import os
    os.environ['MECABRC'] = '/etc/mecabrc'  # MeCab設定

    test_basic_sequential_detection()
    test_order_tolerance()
    test_complex_case()
    compare_with_baseline()
    test_performance()
