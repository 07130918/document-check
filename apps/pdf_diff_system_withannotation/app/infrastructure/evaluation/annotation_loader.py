"""
Annotation CSV Data Loader
Real PDF difference annotation data loader for evaluation
"""
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AnnotationDiff:
    """Real annotation difference data"""
    element_id: str
    previous_page: Optional[int]
    previous_text: Optional[str]
    current_page: Optional[int]
    current_text: Optional[str]
    has_change: bool  # ラベル(変更あり：1)
    change_type: str  # 変更タイプ
    change_detail: str  # 変更詳細
    remarks: Optional[str]

    # 意味的分割結果
    segmented_previous_text: Optional[List[str]] = None
    segmented_current_text: Optional[List[str]] = None


class AnnotationDataLoader:
    """Load and process annotation CSV data"""

    def __init__(self):
        self.phrase_segmenter = None

    def load_annotation_csv(self, csv_path: Path) -> List[AnnotationDiff]:
        """Load annotation data from CSV file"""
        logger.info(f"Loading annotation data from: {csv_path}")

        annotations = []

        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)

                for row_num, row in enumerate(reader, start=2):  # start=2 because header is row 1
                    try:
                        annotation = self._parse_annotation_row(row, row_num)
                        if annotation:
                            annotations.append(annotation)
                    except Exception as e:
                        logger.warning(f"Error parsing row {row_num}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            raise

        logger.info(f"Loaded {len(annotations)} annotation entries")
        return annotations

    def _parse_annotation_row(self, row: Dict[str, str], row_num: int) -> Optional[AnnotationDiff]:
        """Parse a single annotation row"""
        try:
            # Extract and clean data
            element_id = row.get('要素ID', '').strip()
            if not element_id:
                return None

            # Parse page numbers (can be empty)
            prev_page_str = row.get('前年ページ数', '').strip()
            curr_page_str = row.get('後年ページ数', '').strip()

            prev_page = int(prev_page_str) if prev_page_str else None
            curr_page = int(curr_page_str) if curr_page_str else None

            # Extract text content (can be empty)
            # 改行を除去してテキストを正規化
            prev_text_raw = row.get('前年テキスト', '').strip()
            curr_text_raw = row.get('後年テキスト', '').strip()

            # 改行を除去（複数の改行も1つのスペースに置換）
            prev_text = prev_text_raw.replace('\n', ' ').replace('\r', ' ') if prev_text_raw else None
            curr_text = curr_text_raw.replace('\n', ' ').replace('\r', ' ') if curr_text_raw else None

            # 連続するスペースを1つに正規化
            if prev_text:
                prev_text = ' '.join(prev_text.split()) or None
            if curr_text:
                curr_text = ' '.join(curr_text.split()) or None

            # Parse change information
            has_change = row.get('ラベル(変更あり：1)', '').strip() == '1'
            change_type = row.get('変更タイプ', '').strip()
            change_detail = row.get('変更詳細', '').strip()
            remarks = row.get('備考', '').strip() or None

            return AnnotationDiff(
                element_id=element_id,
                previous_page=prev_page,
                previous_text=prev_text,
                current_page=curr_page,
                current_text=curr_text,
                has_change=has_change,
                change_type=change_type,
                change_detail=change_detail,
                remarks=remarks
            )

        except ValueError as e:
            logger.warning(f"Value error in row {row_num}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing row {row_num}: {e}")
            return None

    def convert_to_test_cases(self, annotations: List[AnnotationDiff],
                            pages_2023: Dict[int, str],
                            pages_2024: Dict[int, str]) -> List[Dict]:
        """Convert annotations to test cases for evaluation"""
        logger.info("Converting annotations to test cases")

        test_cases = []

        # Group annotations by page for efficient processing
        page_groups = self._group_by_page(annotations)

        for page_num in sorted(page_groups.keys()):
            if page_num <= 9:  # Only process up to page 9 as specified
                page_annotations = page_groups[page_num]

                # Get page texts
                doc1_text = pages_2023.get(page_num, "")
                doc2_text = pages_2024.get(page_num, "")

                if doc1_text and doc2_text:
                    # Create ground truth from annotations
                    ground_truth = self._create_ground_truth(page_annotations)

                    test_case = {
                        "case_id": f"page_{page_num:02d}",
                        "name": f"Page {page_num} Differences",
                        "doc1_text": doc1_text,
                        "doc2_text": doc2_text,
                        "ground_truth": ground_truth,
                        "description": f"Real annotation data for page {page_num}",
                        "page_number": page_num,
                        "annotation_count": len(ground_truth)
                    }

                    test_cases.append(test_case)
                    logger.debug(f"Created test case for page {page_num} with {len(ground_truth)} differences")

        logger.info(f"Created {len(test_cases)} test cases from annotations")
        return test_cases

    def _group_by_page(self, annotations: List[AnnotationDiff]) -> Dict[int, List[AnnotationDiff]]:
        """Group annotations by page number"""
        page_groups = {}

        for annotation in annotations:
            # Use current page as primary, fallback to previous page
            page_num = annotation.current_page or annotation.previous_page

            if page_num:
                if page_num not in page_groups:
                    page_groups[page_num] = []
                page_groups[page_num].append(annotation)

        return page_groups

    def _create_ground_truth(self, page_annotations: List[AnnotationDiff]) -> List[Dict]:
        """Create ground truth differences from page annotations"""
        ground_truth = []

        for annotation in page_annotations:
            if annotation.has_change:
                # Map annotation change types to our change types
                change_type = self._map_change_type(annotation.change_type)

                gt_diff = {
                    "change_type": change_type,
                    "original_text": annotation.previous_text,
                    "modified_text": annotation.current_text,
                    "element_id": annotation.element_id,
                    "change_detail": annotation.change_detail,
                    "annotation_type": annotation.change_type
                }

                ground_truth.append(gt_diff)

        return ground_truth

    def _map_change_type(self, annotation_type: str) -> str:
        """Map annotation change types to standard change types"""
        type_mapping = {
            "変更": "modification",
            "追加": "addition",
            "削除": "deletion",
            "文言変更": "modification",
            "文言追加": "addition",
            "文言削除": "deletion",
            "日付変更": "modification",
            "金額変更": "modification"
        }

        return type_mapping.get(annotation_type, "modification")

    def segment_annotation_data(self, annotations: List[AnnotationDiff]) -> List[AnnotationDiff]:
        """アノテーションデータを意味的に分割"""
        if not self.phrase_segmenter:
            # PhraseBasedDiffDetectorをインポートして使用
            try:
                from apps.pdf_diff_system_withannotation.app.modules.diff_detection.phrase_based_diff_detector import PhraseBasedDiffDetector
                self.phrase_segmenter = PhraseBasedDiffDetector()
            except ImportError:
                logger.warning("PhraseBasedDiffDetector not available for segmentation")
                return annotations

        segmented_annotations = []

        print("\n=== アノテーションデータの意味的分割開始 ===")

        for i, annotation in enumerate(annotations):
            segmented_annotation = self._segment_single_annotation(annotation, i + 1)
            segmented_annotations.append(segmented_annotation)

        # print(f"✓ {len(segmented_annotations)}件のアノテーションを意味的分割しました")
        return segmented_annotations

    def _segment_single_annotation(self, annotation: AnnotationDiff, index: int) -> AnnotationDiff:
        """単一のアノテーションを意味的に分割"""
        # print(f"\n--- アノテーション {index}: {annotation.element_id} ---")

        # 前テキストの分割
        if annotation.previous_text:
            segmented_previous = self.phrase_segmenter._segment_into_phrases(annotation.previous_text)
            annotation.segmented_previous_text = segmented_previous
            # print(f"前テキスト: '{annotation.previous_text}'")
            # print(f"  → 分割結果 ({len(segmented_previous)}個): {segmented_previous}")

        # 後テキストの分割
        if annotation.current_text:
            segmented_current = self.phrase_segmenter._segment_into_phrases(annotation.current_text)
            annotation.segmented_current_text = segmented_current
            # print(f"後テキスト: '{annotation.current_text}'")
            # print(f"  → 分割結果 ({len(segmented_current)}個): {segmented_current}")

        # 分割の必要性を分析
        self._analyze_segmentation_need(annotation)

        return annotation

    def _analyze_segmentation_need(self, annotation: AnnotationDiff):
        """分割の必要性を分析"""
        prev_segments = len(annotation.segmented_previous_text) if annotation.segmented_previous_text else 0
        curr_segments = len(annotation.segmented_current_text) if annotation.segmented_current_text else 0

        if prev_segments > 1 or curr_segments > 1:
            # print(f"  ⚠️  複数セグメントに分割されました（前:{prev_segments}個, 後:{curr_segments}個）")
            # print(f"  → アノテーション粒度の調整が必要な可能性があります")
            pass
        else:
            # print(f"  ✓  適切な粒度です")
            pass

    def print_annotation_segmentation_summary(self, annotations: List[AnnotationDiff]):
        """アノテーション分割結果のサマリーを出力"""
        print(f"\n=== アノテーション分割結果サマリー ===")

        total_annotations = len(annotations)
        multi_segment_annotations = 0
        total_previous_segments = 0
        total_current_segments = 0

        for annotation in annotations:
            prev_count = len(annotation.segmented_previous_text) if annotation.segmented_previous_text else 0
            curr_count = len(annotation.segmented_current_text) if annotation.segmented_current_text else 0

            total_previous_segments += prev_count
            total_current_segments += curr_count

            if prev_count > 1 or curr_count > 1:
                multi_segment_annotations += 1

        print(f"総アノテーション数: {total_annotations}")
        print(f"複数セグメント分割: {multi_segment_annotations}件 ({multi_segment_annotations/total_annotations*100:.1f}%)")
        print(f"平均前テキストセグメント数: {total_previous_segments/total_annotations:.1f}")
        print(f"平均後テキストセグメント数: {total_current_segments/total_annotations:.1f}")

        # 分割が必要なアノテーションの詳細
        if multi_segment_annotations > 0:
            print(f"\n複数セグメント分割されたアノテーション:")
            for annotation in annotations:
                prev_count = len(annotation.segmented_previous_text) if annotation.segmented_previous_text else 0
                curr_count = len(annotation.segmented_current_text) if annotation.segmented_current_text else 0

                if prev_count > 1 or curr_count > 1:
                    print(f"  {annotation.element_id}: 前{prev_count}個, 後{curr_count}個")
                    print(f"    前: {annotation.previous_text}")
                    print(f"    後: {annotation.current_text}")

        print("-" * 50)

    def save_annotation_segmentation_report(self, annotations: List[AnnotationDiff], output_path: str = None):
        """アノテーション分割分析レポートをファイルに保存"""
        from pathlib import Path
        import json
        from datetime import datetime

        if output_path is None:
            output_path = "/root/AICE/prj-ms-document-check/apps/pdf_diff_system/results/annotation_segmentation_report.md"

        output_file = Path(output_path)
        output_file.parent.mkdir(exist_ok=True)

        # マークダウンレポート生成
        report_content = self._generate_annotation_segmentation_report(annotations)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        # JSON形式でも詳細データを保存
        json_path = output_file.with_suffix('.json')
        segmentation_data = []

        for annotation in annotations:
            data = {
                'element_id': annotation.element_id,
                'has_change': annotation.has_change,
                'change_type': annotation.change_type,
                'previous_text': annotation.previous_text,
                'current_text': annotation.current_text,
                'segmented_previous_text': annotation.segmented_previous_text,
                'segmented_current_text': annotation.segmented_current_text,
                'previous_segments_count': len(annotation.segmented_previous_text) if annotation.segmented_previous_text else 0,
                'current_segments_count': len(annotation.segmented_current_text) if annotation.segmented_current_text else 0
            }
            segmentation_data.append(data)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_annotations': len(annotations),
                'segmentation_data': segmentation_data
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"アノテーション分割分析レポート保存: {output_file}")
        logger.info(f"アノテーション分割データ保存: {json_path}")

        return output_file

    def _generate_annotation_segmentation_report(self, annotations: List[AnnotationDiff]):
        """マークダウン形式のアノテーション分割レポート生成"""
        from datetime import datetime

        total_annotations = len(annotations)
        multi_segment_annotations = 0
        total_previous_segments = 0
        total_current_segments = 0

        # 統計計算
        for annotation in annotations:
            prev_count = len(annotation.segmented_previous_text) if annotation.segmented_previous_text else 0
            curr_count = len(annotation.segmented_current_text) if annotation.segmented_current_text else 0

            total_previous_segments += prev_count
            total_current_segments += curr_count

            if prev_count > 1 or curr_count > 1:
                multi_segment_annotations += 1

        avg_prev_segments = total_previous_segments / total_annotations if total_annotations > 0 else 0
        avg_curr_segments = total_current_segments / total_annotations if total_annotations > 0 else 0
        multi_segment_percentage = (multi_segment_annotations / total_annotations * 100) if total_annotations > 0 else 0

        report = f"""# アノテーションデータ分割分析レポート

生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
分析対象: {total_annotations}件のアノテーション

## 概要

このレポートは、アノテーションデータの意味的分割結果を詳細に分析したものです。
各アノテーションがどのように分割され、どの程度の粒度調整が必要かを評価します。

## 全体統計

### 基本統計
- **総アノテーション数**: {total_annotations}件
- **複数セグメント分割**: {multi_segment_annotations}件 ({multi_segment_percentage:.1f}%)
- **平均前テキストセグメント数**: {avg_prev_segments:.1f}個
- **平均後テキストセグメント数**: {avg_curr_segments:.1f}個

### 分割の必要性
- **適切な粒度**: {total_annotations - multi_segment_annotations}件 ({100 - multi_segment_percentage:.1f}%)
- **粒度調整が必要**: {multi_segment_annotations}件 ({multi_segment_percentage:.1f}%)

## 詳細分析結果

"""

        # 各アノテーションの詳細
        for i, annotation in enumerate(annotations, 1):
            prev_count = len(annotation.segmented_previous_text) if annotation.segmented_previous_text else 0
            curr_count = len(annotation.segmented_current_text) if annotation.segmented_current_text else 0

            is_multi_segment = prev_count > 1 or curr_count > 1
            status = "⚠️ 複数セグメント分割" if is_multi_segment else "✓ 適切な粒度"

            report += f"""
### {i}. アノテーション {annotation.element_id} {status}

- **変更タイプ**: {annotation.change_type}
- **前セグメント数**: {prev_count}個
- **後セグメント数**: {curr_count}個

"""

            if annotation.previous_text:
                report += f"**前テキスト**: {annotation.previous_text}\n"
                if annotation.segmented_previous_text:
                    report += f"**前分割結果**: {annotation.segmented_previous_text}\n"

            if annotation.current_text:
                report += f"**後テキスト**: {annotation.current_text}\n"
                if annotation.segmented_current_text:
                    report += f"**後分割結果**: {annotation.segmented_current_text}\n"

            if is_multi_segment:
                report += f"**推奨**: この差分は複数の意味単位に分かれているため、より小さな粒度でのアノテーションを検討してください。\n"

            report += "\n---\n"

        # 複数セグメント分割のサマリー
        if multi_segment_annotations > 0:
            report += f"""
## 複数セグメント分割の詳細サマリー

以下の{multi_segment_annotations}件のアノテーションで複数セグメント分割が検出されました：

"""
            for annotation in annotations:
                prev_count = len(annotation.segmented_previous_text) if annotation.segmented_previous_text else 0
                curr_count = len(annotation.segmented_current_text) if annotation.segmented_current_text else 0

                if prev_count > 1 or curr_count > 1:
                    report += f"- **{annotation.element_id}**: 前{prev_count}個, 後{curr_count}個\n"
                    report += f"  - 前: {annotation.previous_text}\n"
                    report += f"  - 後: {annotation.current_text}\n\n"

        report += f"""
## 改善提案

### 分割精度向上のために
1. **長い文章の分割**: 複数セグメントに分かれた長文アノテーションは、より小さな意味単位での再アノテーションを検討
2. **バージョン情報の統一**: iOS/Androidバージョン情報は統一的な粒度でのアノテーションが推奨
3. **日付情報の一貫性**: 日付表記の分割パターンを統一

### 検出精度への影響
- 現在の複数セグメント分割率({multi_segment_percentage:.1f}%)は、差分検出の精度に影響する可能性があります
- より一貫した粒度でのアノテーションにより、検出性能の向上が期待できます

🤖 Generated with Claude Code
"""

        return report


    def get_statistics(self, annotations: List[AnnotationDiff]) -> Dict:
        """Get statistics about the annotation data"""
        total_count = len(annotations)
        change_count = len([a for a in annotations if a.has_change])

        change_types = {}
        for annotation in annotations:
            if annotation.has_change:
                change_type = annotation.change_type
                change_types[change_type] = change_types.get(change_type, 0) + 1

        page_distribution = {}
        for annotation in annotations:
            page = annotation.current_page or annotation.previous_page
            if page:
                page_distribution[page] = page_distribution.get(page, 0) + 1

        return {
            "total_annotations": total_count,
            "changes": change_count,
            "no_changes": total_count - change_count,
            "change_types": change_types,
            "page_distribution": page_distribution
        }
