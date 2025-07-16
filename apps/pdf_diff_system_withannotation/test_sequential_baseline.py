#!/usr/bin/env python3
"""
実際のアノテーションデータを使用したベースライン評価のテスト
"""
import sys
from pathlib import Path
import os
import csv

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ['MECABRC'] = '/etc/mecabrc'

from apps.pdf_diff_system_withannotation.baseline_evaluation import BaselineEvaluator
from apps.pdf_diff_system_withannotation.app.infrastructure.evaluation.annotation_loader import AnnotationDataLoader


def load_real_test_cases():
    """実際のアノテーションデータからテストケースを読み込み（5ページ目まで）"""
    # 新しいファイルパスに対応
    data_dir = Path(__file__).parent / "data"
    diff_dir = data_dir / "diff"

    # デバッグ情報
    print(f"data_dir: {data_dir}")
    print(f"data_dir exists: {data_dir.exists()}")
    print(f"diff_dir: {diff_dir}")
    print(f"diff_dir exists: {diff_dir.exists()}")

    annotation_csv = None
    if diff_dir.exists():
        print("Files in diff dir:")
        for f in diff_dir.iterdir():
            print(f"  - {f.name}")
            if 'annotation_MSAD' in f.name and '2023and2024' in f.name:
                annotation_csv = f
                print(f"Found annotation file: {f}")
                break

    if not annotation_csv or not annotation_csv.exists():
        print(f"アノテーションファイルが見つかりません")
        return []

    print(f"アノテーションファイルを読み込み: {annotation_csv.name}")

    test_cases = []
    total_rows = 0
    page5_rows = 0

    try:
        with open(annotation_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                total_rows += 1
                # 5ページ目までのデータのみを使用
                try:
                    page_num = int(row.get('前年ページ数', '0'))
                    if page_num > 5:
                        continue
                    page5_rows += 1
                except ValueError:
                    continue

                if row.get('前年テキスト') and row.get('後年テキスト') and row.get('ラベル(変更あり：1)') == '1':
                    test_case = {
                        'case_id': row['要素ID'],
                        'name': row.get('変更詳細', row.get('変更タイプ', '不明')),
                        'doc1_text': row['前年テキスト'],
                        'doc2_text': row['後年テキスト'],
                        'ground_truth': [{
                            'original_text': row['前年テキスト'],
                            'modified_text': row['後年テキスト']
                        }],
                        'change_type': row.get('変更タイプ', ''),
                        'note': row.get('備考', '')
                    }
                    test_cases.append(test_case)
    except Exception as e:
        print(f"アノテーションデータの読み込みエラー: {e}")
        return []

    print(f"\n統計情報:")
    print(f"  全行数: {total_rows}")
    print(f"  5ページ目までの行数: {page5_rows}")
    print(f"  読み込まれた変更ありデータ: {len(test_cases)}")

    return test_cases


def test_with_real_data():
    """実際のアノテーションデータでのベースライン評価"""
    print("=== 実際のアノテーションデータでのベースライン評価 ===\n")

    # 評価器の初期化
    evaluator = BaselineEvaluator()

    # 実際のアノテーションデータを読み込み
    test_cases = load_real_test_cases()

    if not test_cases:
        print("テストケースが読み込めませんでした")
        return

    print(f"読み込まれたテストケース数: {len(test_cases)}")

    # 変更タイプ別の統計
    change_types = {}
    for tc in test_cases:
        ct = tc['change_type']
        change_types[ct] = change_types.get(ct, 0) + 1

    print("\n変更タイプ別の分布:")
    for ct, count in sorted(change_types.items()):
        print(f"  {ct}: {count}件")

    # 最初の10件を詳細評価
    print("\n\n=== 詳細評価（最初の10件） ===")

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for i, test_case in enumerate(test_cases[:10]):
        print(f"\n--- ケース {test_case['case_id']}: {test_case['name']} ---")
        print(f"文書1: {test_case['doc1_text']}")
        print(f"文書2: {test_case['doc2_text']}")
        if test_case['note']:
            print(f"備考: {test_case['note']}")

        # 差分検出
        detected_diffs = evaluator.diff_detector.detect_differences(
            test_case['doc1_text'],
            test_case['doc2_text']
        )

        print(f"検出された差分: {len(detected_diffs)}件")
        for diff in detected_diffs[:3]:  # 最初の3件のみ表示
            print(f"  - {diff.change_type.value}: '{diff.original_text}' → '{diff.modified_text}'")
            if hasattr(diff, 'similarity_score'):
                print(f"    類似度: {diff.similarity_score:.2f}, 信頼度: {diff.confidence_score:.2f}")

        # 評価
        tp, fp, fn, tn = evaluator._evaluate_detections(detected_diffs, test_case['ground_truth'])
        total_tp += tp
        total_fp += fp
        total_fn += fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        print(f"評価結果: TP={tp}, FP={fp}, FN={fn}")
        print(f"適合率: {precision:.2f}, 再現率: {recall:.2f}, F1: {f1:.2f}")

    # 全体の評価結果
    print("\n\n=== 全体評価結果（最初の10件） ===")
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0

    print(f"総TP: {total_tp}, 総FP: {total_fp}, 総FN: {total_fn}")
    print(f"全体適合率: {overall_precision:.3f}")
    print(f"全体再現率: {overall_recall:.3f}")
    print(f"全体F1スコア: {overall_f1:.3f}")


if __name__ == "__main__":
    test_with_real_data()
