#!/usr/bin/env python3
"""
並び替え前後の順序評価比較プログラム
PDFテキスト抽出の並び替えアルゴリズムの効果を定量的に評価
"""
import sys
from pathlib import Path
import json
import csv
import numpy as np
from scipy.stats import spearmanr
from typing import List, Dict, Tuple
import logging
from datetime import datetime
import re

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import fitz  # PyMuPDF
from apps.pdf_diff_system_withannotation.evaluate_reading_order_with_annotation import (
    ReadingOrderEvaluatorWithAnnotation, ReadingOrderAnnotation
)

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OrderingComparisonEvaluator:
    """並び替え前後の順序評価を比較するクラス"""

    def __init__(self):
        self.evaluator = ReadingOrderEvaluatorWithAnnotation()

    def extract_text_blocks_without_sorting(self, pdf_path: Path, page_num: int) -> List[Dict]:
        """並び替えなしでテキストブロックを抽出（出現順）"""
        try:
            doc = fitz.open(str(pdf_path))

            if page_num < 1 or page_num > len(doc):
                return []

            page = doc[page_num - 1]
            blocks = page.get_text("dict")["blocks"]

            text_blocks = []
            block_id = 0

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            line_text += span["text"]

                        if line_text.strip():
                            text_blocks.append({
                                'id': block_id,
                                'text': line_text.strip(),
                                'bbox': line["bbox"],
                                'x0': line["bbox"][0],
                                'y0': line["bbox"][1],
                                'order': 'original'  # 元の順序
                            })
                            block_id += 1

            doc.close()
            return text_blocks

        except Exception as e:
            logger.error(f"Error extracting text blocks: {e}")
            return []

    def extract_text_blocks_with_sorting(self, pdf_path: Path, page_num: int) -> List[Dict]:
        """並び替えありでテキストブロックを抽出（Y→X座標でソート）"""
        # まず並び替えなしで取得
        text_blocks = self.extract_text_blocks_without_sorting(pdf_path, page_num)

        # Y座標→X座標でソート
        sorted_blocks = sorted(text_blocks,
                             key=lambda b: (round(b['y0'] / 10) * 10, b['x0']))

        # 新しいIDを割り当て
        for i, block in enumerate(sorted_blocks):
            block['sorted_id'] = i
            block['order'] = 'sorted'

        return sorted_blocks

    def compare_orderings(self, pdf_path: Path, page_num: int,
                         annotations: List[ReadingOrderAnnotation]) -> Dict:
        """並び替え前後の順序を比較評価"""

        # 並び替えなしのブロック
        original_blocks = self.extract_text_blocks_without_sorting(pdf_path, page_num)

        # 並び替えありのブロック
        sorted_blocks = self.extract_text_blocks_with_sorting(pdf_path, page_num)

        # それぞれでアノテーションとマッチング
        original_matches = self._match_annotations_to_blocks(annotations, original_blocks)
        sorted_matches = self._match_annotations_to_blocks(annotations, sorted_blocks)

        # それぞれの評価指標を計算
        original_metrics = self._calculate_metrics(annotations, original_blocks, original_matches)
        sorted_metrics = self._calculate_metrics(annotations, sorted_blocks, sorted_matches)

        # 詳細な比較結果
        comparison = {
            'page': page_num,
            'annotation_count': len(annotations),
            'original_order': {
                'block_count': len(original_blocks),
                'matched_count': len(original_matches),
                'metrics': original_metrics,
                'sample_text': self._get_sample_text(original_blocks, 10)
            },
            'sorted_order': {
                'block_count': len(sorted_blocks),
                'matched_count': len(sorted_matches),
                'metrics': sorted_metrics,
                'sample_text': self._get_sample_text(sorted_blocks, 10)
            },
            'improvement': {
                'spearman_diff': sorted_metrics['spearman_correlation'] - original_metrics['spearman_correlation'],
                'match_rate_diff': sorted_metrics['match_rate'] - original_metrics['match_rate'],
                'order_preservation_diff': sorted_metrics['order_preservation_rate'] - original_metrics['order_preservation_rate']
            }
        }

        return comparison

    def _match_annotations_to_blocks(self, annotations: List[ReadingOrderAnnotation],
                                   text_blocks: List[Dict]) -> List[Tuple[int, int]]:
        """アノテーションとブロックをマッチング"""
        matched_indices = []

        for ann_idx, annotation in enumerate(annotations):
            block_idx = self._find_matching_block(annotation, text_blocks)
            if block_idx is not None:
                matched_indices.append((ann_idx, block_idx))

        return matched_indices

    def _find_matching_block(self, annotation: ReadingOrderAnnotation,
                           text_blocks: List[Dict]) -> int:
        """アノテーションに対応するブロックを検索"""
        ann_text = self.evaluator.normalize_fullwidth_chars(annotation.text).lower().strip()

        # 完全一致
        for i, block in enumerate(text_blocks):
            block_text = self.evaluator.normalize_fullwidth_chars(block['text']).lower().strip()
            if ann_text == block_text:
                return i

        # 部分一致
        for i, block in enumerate(text_blocks):
            block_text = self.evaluator.normalize_fullwidth_chars(block['text']).lower().strip()
            if ann_text in block_text or (block_text in ann_text and len(block_text) > 3):
                return i

        return None

    def _calculate_metrics(self, annotations: List[ReadingOrderAnnotation],
                          text_blocks: List[Dict],
                          matched_indices: List[Tuple[int, int]]) -> Dict:
        """評価指標を計算"""
        if len(matched_indices) < 2:
            return {
                'spearman_correlation': 0.0,
                'order_preservation_rate': 0.0,
                'local_order_consistency': 0.0,
                'match_rate': len(matched_indices) / len(annotations) if annotations else 0.0
            }

        # マッチした順序の配列
        annotation_order = [ann_idx for ann_idx, _ in matched_indices]
        block_order = [block_idx for _, block_idx in matched_indices]

        # スピアマン相関
        spearman_corr, _ = spearmanr(annotation_order, block_order)

        # 順序保持率
        preserved_pairs = 0
        total_pairs = 0

        for i in range(len(matched_indices)):
            for j in range(i + 1, len(matched_indices)):
                ann_i, block_i = matched_indices[i]
                ann_j, block_j = matched_indices[j]

                total_pairs += 1
                if (ann_i < ann_j and block_i < block_j) or \
                   (ann_i > ann_j and block_i > block_j):
                    preserved_pairs += 1

        order_preservation_rate = preserved_pairs / total_pairs if total_pairs > 0 else 0.0

        # 局所順序一致率
        correct_adjacent = 0
        total_adjacent = len(matched_indices) - 1

        for i in range(total_adjacent):
            ann_i, block_i = matched_indices[i]
            ann_j, block_j = matched_indices[i + 1]

            if abs(block_j - block_i) <= 2:
                correct_adjacent += 1

        local_order_consistency = correct_adjacent / total_adjacent if total_adjacent > 0 else 0.0

        return {
            'spearman_correlation': float(spearman_corr) if not np.isnan(spearman_corr) else 0.0,
            'order_preservation_rate': order_preservation_rate,
            'local_order_consistency': local_order_consistency,
            'match_rate': len(matched_indices) / len(annotations)
        }

    def _get_sample_text(self, blocks: List[Dict], n: int = 10) -> List[str]:
        """最初のn個のブロックテキストを取得"""
        return [block['text'][:50] + "..." if len(block['text']) > 50 else block['text']
                for block in blocks[:n]]

    def generate_comparison_report(self, results: Dict) -> str:
        """比較結果のレポートを生成"""
        report = []
        report.append("# 並び替え前後の順序評価比較レポート\n")
        report.append(f"評価日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        for page_result in results['page_results']:
            page_num = page_result['page']
            report.append(f"\n## ページ {page_num} の評価結果\n")

            # 元の順序
            report.append("### 並び替え前（出現順）")
            orig = page_result['original_order']
            report.append(f"- ブロック数: {orig['block_count']}")
            report.append(f"- マッチ数: {orig['matched_count']}")
            report.append(f"- **スピアマン相関**: {orig['metrics']['spearman_correlation']:.3f}")
            report.append(f"- **順序保持率**: {orig['metrics']['order_preservation_rate']:.3f}")
            report.append(f"- **マッチ率**: {orig['metrics']['match_rate']:.3f}")

            # ソート後の順序
            report.append("\n### 並び替え後（Y→X座標順）")
            sorted_order = page_result['sorted_order']
            report.append(f"- ブロック数: {sorted_order['block_count']}")
            report.append(f"- マッチ数: {sorted_order['matched_count']}")
            report.append(f"- **スピアマン相関**: {sorted_order['metrics']['spearman_correlation']:.3f}")
            report.append(f"- **順序保持率**: {sorted_order['metrics']['order_preservation_rate']:.3f}")
            report.append(f"- **マッチ率**: {sorted_order['metrics']['match_rate']:.3f}")

            # 改善度
            report.append("\n### 改善度")
            imp = page_result['improvement']
            report.append(f"- スピアマン相関の変化: {imp['spearman_diff']:+.3f}")
            report.append(f"- 順序保持率の変化: {imp['order_preservation_diff']:+.3f}")
            report.append(f"- マッチ率の変化: {imp['match_rate_diff']:+.3f}")

            # サンプルテキスト
            report.append("\n### テキストサンプル（最初の5個）")
            report.append("**並び替え前:**")
            for i, text in enumerate(orig['sample_text'][:5]):
                report.append(f"{i+1}. {text}")

            report.append("\n**並び替え後:**")
            for i, text in enumerate(sorted_order['sample_text'][:5]):
                report.append(f"{i+1}. {text}")

        # 全体サマリー
        report.append("\n## 全体サマリー")
        if results['summary']['improvement']['avg_spearman_diff'] > 0:
            report.append("✅ **並び替えにより順序評価が改善されました**")
        else:
            report.append("❌ **並び替えにより順序評価が悪化しました**")

        report.append(f"\n- 平均スピアマン相関の改善: {results['summary']['improvement']['avg_spearman_diff']:+.3f}")
        report.append(f"- 平均順序保持率の改善: {results['summary']['improvement']['avg_order_preservation_diff']:+.3f}")

        return '\n'.join(report)


def main():
    """メイン実行関数"""
    logger.info("並び替え前後の順序評価比較を開始...")

    # ファイルパス
    pdf_path = Path("/root/AICE/prj-ms-document-check/docs/img/2023.pdf")
    annotation_path = Path("/root/AICE/prj-ms-document-check/apps/pdf_diff_system/data/reading_order_{㈪2023_MSADグループ_パンフレット} - annotation_template.csv")

    # 評価器初期化
    evaluator = OrderingComparisonEvaluator()
    base_evaluator = ReadingOrderEvaluatorWithAnnotation()

    # アノテーション読み込み
    annotations = base_evaluator.load_reading_order_annotations(annotation_path)

    # ページごとにグループ化
    page_annotations = {}
    for ann in annotations:
        if ann.page not in page_annotations:
            page_annotations[ann.page] = []
        page_annotations[ann.page].append(ann)

    # 結果を格納
    results = {
        'evaluation_date': datetime.now().isoformat(),
        'pdf_path': str(pdf_path),
        'annotation_file': str(annotation_path),
        'page_results': [],
        'summary': {
            'total_pages': len(page_annotations),
            'improvement': {
                'avg_spearman_diff': 0.0,
                'avg_order_preservation_diff': 0.0,
                'avg_match_rate_diff': 0.0
            }
        }
    }

    # 各ページを評価（最初の3ページのみ）
    spearman_diffs = []
    order_preservation_diffs = []

    for page_num in sorted(page_annotations.keys())[:3]:
        logger.info(f"ページ {page_num} を評価中...")
        page_anns = sorted(page_annotations[page_num], key=lambda a: a.order_number)

        comparison = evaluator.compare_orderings(pdf_path, page_num, page_anns)
        results['page_results'].append(comparison)

        # 改善度を記録
        spearman_diffs.append(comparison['improvement']['spearman_diff'])
        order_preservation_diffs.append(comparison['improvement']['order_preservation_diff'])

    # 平均改善度を計算
    if spearman_diffs:
        results['summary']['improvement']['avg_spearman_diff'] = np.mean(spearman_diffs)
        results['summary']['improvement']['avg_order_preservation_diff'] = np.mean(order_preservation_diffs)

    # レポート生成
    report = evaluator.generate_comparison_report(results)

    # 結果保存
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    # JSON保存
    json_output = output_dir / "ordering_comparison_results.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # レポート保存
    report_output = output_dir / "ordering_comparison_report.md"
    with open(report_output, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"評価完了。結果を保存しました:")
    logger.info(f"- JSON: {json_output}")
    logger.info(f"- レポート: {report_output}")

    # コンソールに要約表示
    print("\n" + "="*50)
    print(report)


if __name__ == "__main__":
    main()
