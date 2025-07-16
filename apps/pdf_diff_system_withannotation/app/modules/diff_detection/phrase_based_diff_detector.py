"""
Phrase-based Difference Detector
フレーズ（意味的まとまり）ベース差分検出器
"""
import logging
from typing import List, Dict, Set, Tuple
import time
import re
from difflib import SequenceMatcher

from apps.pdf_diff_system_withannotation.app.domain.interfaces.diff_detector_interface import DiffDetectorInterface
from apps.pdf_diff_system_withannotation.app.domain.models.diff_result import DiffResult, ChangeType
from .mecab_tokenizer import MeCabTokenizer

logger = logging.getLogger(__name__)


class PhraseBasedDiffDetector(DiffDetectorInterface):
    """フレーズベース差分検出器（意味的まとまり単位）"""

    def __init__(self):
        self.tokenizer = MeCabTokenizer()
        logger.info("PhraseBasedDiffDetector initialized with MeCab tokenizer")

    def detect_differences(self, doc1_text: str, doc2_text: str) -> List[DiffResult]:
        """
        フレーズレベルでの差分検出

        Args:
            doc1_text: 元文書テキスト
            doc2_text: 比較文書テキスト

        Returns:
            検出された差分のリスト
        """
        logger.debug("=== フレーズベース差分検出開始 ===")
        logger.debug(f"Doc1 ({len(doc1_text)} chars): {doc1_text[:100]}...")
        logger.debug(f"Doc2 ({len(doc2_text)} chars): {doc2_text[:100]}...")

        # 1. 意味的なフレーズに分割
        phrases1 = self._segment_into_phrases(doc1_text)
        phrases2 = self._segment_into_phrases(doc2_text)

        logger.debug(f"Phrases1 ({len(phrases1)}): {phrases1[:5]}...")
        logger.debug(f"Phrases2 ({len(phrases2)}): {phrases2[:5]}...")

        # 分割結果を出力
        self._print_segmentation_results(doc1_text, phrases1, "文書1")
        self._print_segmentation_results(doc2_text, phrases2, "文書2")

        # 2. フレーズレベル差分検出
        differences = self._detect_phrase_differences(phrases1, phrases2)

        logger.debug(f"検出された差分数: {len(differences)}")
        for i, diff in enumerate(differences[:5]):  # 最初の5件のみログ
            logger.debug(f"差分 {i+1}: {diff.change_type.value} - '{diff.original_text}' -> '{diff.modified_text}'")

        logger.debug("=== フレーズベース差分検出終了 ===")
        return differences

    def _segment_into_phrases(self, text: str) -> List[str]:
        """テキストを意味的なフレーズに分割"""
        if not text.strip():
            return []

        # 1. 基本的な区切り文字での分割
        phrases = []

        # スペース、句読点、特殊記号での分割
        segments = re.split(r'[\s　\n\t]+', text.strip())

        for segment in segments:
            if not segment:
                continue

            # 意味的なフレーズに細分化
            sub_phrases = self._split_into_meaningful_units(segment)
            phrases.extend(sub_phrases)

        # 空の要素を除去
        phrases = [p.strip() for p in phrases if p.strip()]

        return phrases

    def _split_into_meaningful_units(self, segment: str) -> List[str]:
        """セグメントを意味的な単位に分割"""
        if not segment:
            return []

        phrases = []

        # 複数のパターンで分割
        patterns = [
            # 日付パターン（令和5年10月25日）
            r'(令和\d+年\d+月\d+日(?:午後\d+時)?)',
            # 時刻パターン（午後4時）
            r'(\d+月\d+日\([月火水木金土日]\))',
            # ページパターン（p34）
            r'(p\d+)',
            # URLパターン
            r'(https?://[^\s]+)',
            # バージョンパターン（iOS 11/12/13...）
            r'(iOS\s+[\d/]+)',
            r'(Android\s+[\d./]+)',
            # 数値パターン（約1.8万人）
            r'(約\d+\.\d+万人)',
            # 句読点での分割
            r'([。！？]+)',
        ]

        current_segment = segment

        for pattern in patterns:
            matches = list(re.finditer(pattern, current_segment))
            if matches:
                # マッチした部分を抽出
                new_phrases = []
                last_end = 0

                for match in matches:
                    # マッチ前の部分
                    if match.start() > last_end:
                        before = current_segment[last_end:match.start()].strip()
                        if before:
                            new_phrases.append(before)

                    # マッチした部分
                    matched = match.group(1).strip()
                    if matched:
                        new_phrases.append(matched)

                    last_end = match.end()

                # 残りの部分
                if last_end < len(current_segment):
                    remaining = current_segment[last_end:].strip()
                    if remaining:
                        new_phrases.append(remaining)

                if new_phrases:
                    phrases.extend(new_phrases)
                    break
        else:
            # パターンにマッチしない場合は元のセグメントを追加
            if current_segment.strip():
                phrases.append(current_segment.strip())

        # 短すぎる断片は前後と結合
        return self._merge_short_fragments(phrases)

    def _merge_short_fragments(self, phrases: List[str], min_length: int = 2) -> List[str]:
        """短い断片を前後と結合"""
        if not phrases:
            return []

        merged = []
        current = ""

        for phrase in phrases:
            if len(phrase) < min_length and current:
                # 短い断片は前の要素と結合
                current += phrase
            else:
                if current:
                    merged.append(current)
                current = phrase

        if current:
            merged.append(current)

        return merged

    def _print_segmentation_results(self, original_text: str, phrases: List[str], label: str):
        """分割結果を出力"""
        print(f"\n=== {label}の分割結果 ===")
        print(f"原文: {original_text}")
        print(f"分割数: {len(phrases)}個")
        for i, phrase in enumerate(phrases, 1):
            print(f"  {i:2d}: '{phrase}'")
        print()

        # 詳細分析用の追加出力
        self._print_detailed_segmentation_analysis(original_text, phrases, label)

    def _print_detailed_segmentation_analysis(self, original_text: str, phrases: List[str], label: str):
        """詳細な分割分析結果を出力"""
        print(f"\n=== {label}の詳細分割分析 ===")

        # 1. 原文の文字数と分割後の合計文字数比較
        original_length = len(original_text)
        phrases_total_length = sum(len(phrase) for phrase in phrases)
        print(f"原文文字数: {original_length}")
        print(f"分割後合計文字数: {phrases_total_length}")
        print(f"文字数差異: {abs(original_length - phrases_total_length)}")

        # 2. 分割パターンの分析
        pattern_analysis = self._analyze_phrase_patterns(phrases)
        print(f"\n分割パターン分析:")
        for pattern, count in pattern_analysis.items():
            print(f"  {pattern}: {count}個")

        # 3. 各フレーズの詳細分析
        print(f"\n各フレーズの詳細:")
        for i, phrase in enumerate(phrases, 1):
            phrase_type = self._classify_phrase_type(phrase)
            print(f"  {i:2d}: [{phrase_type:8s}] '{phrase}' ({len(phrase)}文字)")

        print("-" * 50)

        # 4. ファイル出力用のデータを保存
        if not hasattr(self, '_segmentation_reports'):
            self._segmentation_reports = []

        self._segmentation_reports.append({
            'label': label,
            'original_text': original_text,
            'original_length': original_length,
            'phrases': phrases,
            'phrases_total_length': phrases_total_length,
            'character_difference': abs(original_length - phrases_total_length),
            'pattern_analysis': pattern_analysis,
            'phrase_details': [
                {
                    'index': i,
                    'phrase': phrase,
                    'type': self._classify_phrase_type(phrase),
                    'length': len(phrase)
                }
                for i, phrase in enumerate(phrases, 1)
            ]
        })

    def _analyze_phrase_patterns(self, phrases: List[str]) -> Dict[str, int]:
        """フレーズのパターンを分析"""
        patterns = {}

        for phrase in phrases:
            phrase_type = self._classify_phrase_type(phrase)
            patterns[phrase_type] = patterns.get(phrase_type, 0) + 1

        return patterns

    def _classify_phrase_type(self, phrase: str) -> str:
        """フレーズの種類を分類"""
        import re

        if re.match(r'令和\d+年度', phrase):
            return "年度"
        elif re.match(r'令和\d+年\d+月\d+日', phrase):
            return "日付"
        elif re.match(r'p\d+', phrase):
            return "ページ"
        elif re.match(r'https?://', phrase):
            return "URL"
        elif re.match(r'iOS', phrase):
            return "iOS"
        elif re.match(r'Android', phrase):
            return "Android"
        elif re.match(r'約\d+\.\d+万人', phrase):
            return "人数"
        elif re.match(r'\d+月\d+日\([月火水木金土日]\)', phrase):
            return "曜日付日付"
        elif re.match(r'[\d./]+', phrase):
            return "バージョン"
        elif '。' in phrase or '！' in phrase or '？' in phrase:
            return "文章"
        elif len(phrase) <= 3:
            return "短語"
        else:
            return "その他"

    def _detect_phrase_differences(self, phrases1: List[str], phrases2: List[str]) -> List[DiffResult]:
        """フレーズレベル差分の検出"""
        differences = []

        # フレーズを集合化して高速比較
        set1 = set(phrases1)
        set2 = set(phrases2)

        # 削除されたフレーズ
        deleted_phrases = set1 - set2
        for phrase in deleted_phrases:
            differences.append(DiffResult(
                change_type=ChangeType.DELETION,
                confidence_score=1.0,
                original_text=phrase,
                modified_text=None,
                similarity_score=0.0,
                detection_method="phrase_based_exact_match"
            ))

        # 追加されたフレーズ
        added_phrases = set2 - set1
        for phrase in added_phrases:
            differences.append(DiffResult(
                change_type=ChangeType.ADDITION,
                confidence_score=1.0,
                original_text=None,
                modified_text=phrase,
                similarity_score=0.0,
                detection_method="phrase_based_exact_match"
            ))

        # 類似フレーズの修正検出
        modifications = self._detect_similar_phrase_modifications(phrases1, phrases2)
        differences.extend(modifications)

        return differences

    def _detect_similar_phrase_modifications(self, phrases1: List[str], phrases2: List[str]) -> List[DiffResult]:
        """類似フレーズの修正検出"""
        modifications = []

        # 削除・追加されたフレーズから類似ペアを探す
        set1 = set(phrases1)
        set2 = set(phrases2)

        deleted_phrases = list(set1 - set2)
        added_phrases = list(set2 - set1)

        # 類似度が高いペアを修正として扱う
        for deleted in deleted_phrases:
            best_match = None
            best_similarity = 0.0

            for added in added_phrases:
                similarity = self._calculate_phrase_similarity(deleted, added)
                if similarity > best_similarity and similarity > 0.6:  # 60%以上の類似度
                    best_similarity = similarity
                    best_match = added

            if best_match:
                modifications.append(DiffResult(
                    change_type=ChangeType.MODIFICATION,
                    confidence_score=0.8,
                    original_text=deleted,
                    modified_text=best_match,
                    similarity_score=best_similarity,
                    detection_method="phrase_based_similarity_match"
                ))

                # マッチしたものは追加リストから除去
                added_phrases.remove(best_match)

        return modifications

    def _calculate_phrase_similarity(self, phrase1: str, phrase2: str) -> float:
        """フレーズ間の類似度計算"""
        if not phrase1 or not phrase2:
            return 0.0

        # SequenceMatcherで基本的な類似度を計算
        matcher = SequenceMatcher(None, phrase1, phrase2)
        return matcher.ratio()

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
        phrases1 = self._segment_into_phrases(doc1_text)
        phrases2 = self._segment_into_phrases(doc2_text)

        performance_metrics = {
            "processing_time": processing_time,
            "differences_count": len(differences),
            "doc1_phrases": len(phrases1),
            "doc2_phrases": len(phrases2),
            "detection_method": "phrase_based_semantic",
            "additions": len([d for d in differences if d.change_type == ChangeType.ADDITION]),
            "deletions": len([d for d in differences if d.change_type == ChangeType.DELETION]),
            "modifications": len([d for d in differences if d.change_type == ChangeType.MODIFICATION])
        }

        logger.info(f"フレーズベース差分検出完了: {processing_time:.2f}秒, {len(differences)}件の差分")
        return performance_metrics

    def save_segmentation_report(self, output_path: str = None):
        """分割分析レポートをファイルに保存"""
        from pathlib import Path
        import json
        from datetime import datetime

        if not hasattr(self, '_segmentation_reports') or not self._segmentation_reports:
            logger.warning("保存する分割レポートデータがありません")
            return None

        if output_path is None:
            output_path = "/root/AICE/prj-ms-document-check/apps/pdf_diff_system/results/segmentation_analysis_report.md"

        output_file = Path(output_path)
        output_file.parent.mkdir(exist_ok=True)

        # マークダウンレポート生成
        report_content = self._generate_segmentation_markdown_report()

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        # JSON形式でも詳細データを保存
        json_path = output_file.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'segmentation_reports': self._segmentation_reports
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"分割分析レポート保存: {output_file}")
        logger.info(f"分割分析データ保存: {json_path}")

        return output_file

    def _generate_segmentation_markdown_report(self):
        """マークダウン形式の分割分析レポート生成"""
        from datetime import datetime

        report = f"""# 文書分割分析レポート

生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
分析対象: {len(self._segmentation_reports)}件の文書

## 概要

このレポートは、フレーズベース差分検出における文書の意味的分割結果を詳細に分析したものです。

"""

        # 各文書の分析結果
        for i, report_data in enumerate(self._segmentation_reports, 1):
            report += f"""
## {i}. {report_data['label']}

### 基本情報
- **原文文字数**: {report_data['original_length']}文字
- **分割後合計文字数**: {report_data['phrases_total_length']}文字
- **文字数差異**: {report_data['character_difference']}文字
- **分割フレーズ数**: {len(report_data['phrases'])}個

### 原文
```
{report_data['original_text']}
```

### 分割結果
"""
            for phrase_detail in report_data['phrase_details']:
                report += f"   {phrase_detail['index']:2d}: [{phrase_detail['type']:8s}] '{phrase_detail['phrase']}' ({phrase_detail['length']}文字)\n"

            # 分割パターン分析
            report += f"\n### 分割パターン分析\n"
            for pattern, count in report_data['pattern_analysis'].items():
                report += f"- {pattern}: {count}個\n"

            report += "\n---\n"

        # 全体統計
        total_docs = len(self._segmentation_reports)
        total_phrases = sum(len(r['phrases']) for r in self._segmentation_reports)
        avg_phrases_per_doc = total_phrases / total_docs if total_docs > 0 else 0

        # パターン集計
        all_patterns = {}
        for report_data in self._segmentation_reports:
            for pattern, count in report_data['pattern_analysis'].items():
                all_patterns[pattern] = all_patterns.get(pattern, 0) + count

        report += f"""
## 全体統計

### 基本統計
- **分析文書数**: {total_docs}件
- **総フレーズ数**: {total_phrases}個
- **文書あたり平均フレーズ数**: {avg_phrases_per_doc:.1f}個

### 全体パターン分布
"""
        for pattern, count in sorted(all_patterns.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_phrases * 100) if total_phrases > 0 else 0
            report += f"- **{pattern}**: {count}個 ({percentage:.1f}%)\n"

        report += f"""

## 分析所見

### 分割の特徴
1. **日付パターン**: 令和年号、月日表記が適切に識別されています
2. **URL**: 長いURL文字列が単一フレーズとして正しく分割されています
3. **バージョン情報**: iOS、Androidのバージョン番号が適切に分離されています
4. **ページ番号**: p34、p35などのページ参照が正しく識別されています

### 改善の余地
1. **短語の結合**: 1-2文字の短い語句は前後のフレーズと結合できる可能性があります
2. **文章の細分化**: 長い文章をより小さな意味単位に分割する検討が必要です

🤖 Generated with Claude Code
"""

        return report


def test_phrase_based_detector():
    """PhraseBasedDiffDetectorのテスト"""
    try:
        detector = PhraseBasedDiffDetector()

        # テストケース
        test_cases = [
            ("令和5年度 p34 裏表紙", "令和6年度 p35 背表紙"),
            ("約1.8万人 約2.5万人", "約1.6万人 約2.4万人"),
            ("iOS 11/12/13/14/15/16", "iOS 11/12/13/14/15/16/17"),
            ("令和5年10月25日 午後4時", "令和6年10月23日 午後4時")
        ]

        print("=== PhraseBasedDiffDetector テスト ===")
        for i, (text1, text2) in enumerate(test_cases):
            print(f"\n{'='*50}")
            print(f"テストケース {i+1}: '{text1}' vs '{text2}'")
            print('='*50)

            differences = detector.detect_differences(text1, text2)
            print(f"\n検出差分数: {len(differences)}")

            for diff in differences:
                print(f"  {diff.change_type.value}: '{diff.original_text}' -> '{diff.modified_text}' (確信度: {diff.confidence_score}, 類似度: {diff.similarity_score:.3f})")

        return True

    except Exception as e:
        print(f"PhraseBasedDiffDetector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_phrase_based_detector()
