"""
出力ハンドラー（ベースライン互換）
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..models.bbox_models import ComparisonResult, Highlight, ChangeType
from ..config.settings import settings
from ..utils.pdf_utils import PDFProcessor

logger = logging.getLogger(__name__)


class OutputHandler:
    """ベースライン互換の出力ハンドラー"""
    
    def __init__(self):
        """初期化"""
        self.pdf_processor = PDFProcessor()
        self.output_dir = settings.OUTPUT_DIR
    
    def save_all_outputs(self, comparison_result: ComparisonResult,
                        pdf1_bytes: bytes, pdf2_bytes: bytes,
                        pdf1_path: Path, pdf2_path: Path,
                        output_dir: Path = None):
        """すべての出力を保存（v3 LLM版用）"""
        if output_dir:
            self.output_dir = output_dir
        
        # ファイル名を取得
        pdf1_name = pdf1_path.name
        pdf2_name = pdf2_path.name
        
        # 比較結果を保存
        return self.save_comparison_result(
            result=comparison_result,
            output_name="comparison",
            pdf1_bytes=pdf1_bytes,
            pdf2_bytes=pdf2_bytes,
            pdf1_name=pdf1_name,
            pdf2_name=pdf2_name
        )
    
    def save_comparison_result(self, result: ComparisonResult, 
                             output_name: str = "comparison",
                             pdf1_bytes: bytes = None, pdf2_bytes: bytes = None,
                             pdf1_name: str = None, pdf2_name: str = None) -> Dict[str, str]:
        """比較結果を保存
        
        Args:
            result: 比較結果
            output_name: 出力ファイル名のプレフィックス
            pdf1_bytes: 文書1のPDFバイトデータ（読み順序表示用）
            pdf2_bytes: 文書2のPDFバイトデータ（読み順序表示用）
            pdf1_name: 文書1のファイル名
            pdf2_name: 文書2のファイル名
            
        Returns:
            保存されたファイルパスの辞書
        """
        # ベースラインと同じように、タイムスタンプを使用しない
        base_name = output_name
        
        # ファイル名を取得（metadataから取得、またはパラメータから取得）
        if not pdf1_name:
            pdf1_name = result.metadata.get('doc1_name', '2023.pdf')
        if not pdf2_name:
            pdf2_name = result.metadata.get('doc2_name', '2024.pdf')
        
        # 拡張子を除去
        pdf1_basename = Path(pdf1_name).stem
        pdf2_basename = Path(pdf2_name).stem
        
        saved_files = {}
        
        try:
            # 1. JSONファイルを保存（ベースライン互換形式）
            json_path = self._save_json_result(result, base_name)
            saved_files["json"] = str(json_path)
            
            # 2. 差分CSVを保存
            csv_path = self._save_diff_csv(result, base_name)
            saved_files["diff_csv"] = str(csv_path)
            
            # 3. 読み順序JSONを保存
            order_json_path = self._save_reading_order_csv(result, base_name)
            saved_files["order_json"] = str(order_json_path)
            
            # 4. sentence_info.jsonを保存（ベースライン互換）
            sentence_info_path = self._save_sentence_info(result, base_name)
            saved_files["sentence_info"] = str(sentence_info_path)
            
            # 5. サマリーレポートを保存
            report_path = self._save_summary_report(result, base_name)
            saved_files["report"] = str(report_path)
            
            # 6. デバッグ情報を保存（設定に応じて）
            if settings.DEBUG:
                debug_path = self._save_debug_info(result, base_name)
                saved_files["debug"] = str(debug_path)
            
            # 6.5. Azure抽出データを保存（Azure使用時のみ）
            if result.metadata.get('azure_ocr_used') and settings.DEBUG:
                azure_paths = self._save_azure_extraction_data(result, base_name)
                saved_files.update(azure_paths)
            
            # 7. 読み順序CSVファイルをdebugディレクトリに保存（ベースライン互換）
            debug_csv_paths = self._save_reading_order_debug_csv(result, base_name)
            saved_files.update(debug_csv_paths)
            
            # 8. 読み順序を可視化したPDFを保存（PDFバイトデータが提供された場合）
            if pdf1_bytes or pdf2_bytes:
                reading_order_paths = self._save_reading_order_pdfs(
                    result, base_name, pdf1_bytes, pdf2_bytes, pdf1_basename, pdf2_basename
                )
                saved_files.update(reading_order_paths)
                
                # 9. 元の順序PDFを保存（ベースライン互換）
                original_order_paths = self._save_original_order_pdfs(
                    result, base_name, pdf1_bytes, pdf2_bytes, pdf1_basename, pdf2_basename
                )
                saved_files.update(original_order_paths)
                
                # 10. 比較用ハイライトPDFを保存（ベースライン互換）
                compared_paths = self._save_compared_pdfs(
                    result, base_name, pdf1_bytes, pdf2_bytes, pdf1_basename, pdf2_basename
                )
                saved_files.update(compared_paths)
                
                # 11. 並列比較PDFを保存（2つのPDFを並べて表示）
                side_by_side_path = self._save_side_by_side_pdf(
                    result, base_name, pdf1_bytes, pdf2_bytes, pdf1_basename, pdf2_basename
                )
                if side_by_side_path:
                    saved_files["side_by_side_pdf"] = str(side_by_side_path)
            
            logger.info(f"Saved comparison results to {self.output_dir}")
            return saved_files
            
        except Exception as e:
            logger.error(f"Failed to save comparison results: {e}")
            raise
    
    def _save_json_result(self, result: ComparisonResult, base_name: str) -> Path:
        """JSON形式で結果を保存（ベースライン互換）
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパス
        """
        # ベースライン互換形式に変換
        baseline_format = {
            "execution_time": result.execution_time,
            "metadata": result.metadata,
            "differences": []
        }
        
        # 差分をベースライン形式に変換
        for diff in result.diff_results:
            diff_item = {
                "type": diff.change_type.value,
                "page": diff.page + 1,  # 1-indexed for baseline compatibility
                "confidence": diff.confidence
            }
            
            if diff.original_bbox:
                diff_item["original"] = {
                    "text": diff.original_bbox["text"],
                    "bbox": diff.original_bbox["bbox"]
                }
            
            if diff.modified_bbox:
                diff_item["modified"] = {
                    "text": diff.modified_bbox["text"],
                    "bbox": diff.modified_bbox["bbox"]
                }
            
            # LLM拡張フィールド
            diff_item["llm_extensions"] = {
                "semantic_similarity": diff.semantic_similarity,
                "context": diff.context,
                "explanation": diff.llm_explanation
            }
            
            baseline_format["differences"].append(diff_item)
        
        # 読み順序情報
        baseline_format["reading_order"] = {
            "document1": [{"text": b["text"], "page": b["page"] + 1, "bbox": b["bbox"]} 
                         for b in result.reading_order_doc1],
            "document2": [{"text": b["text"], "page": b["page"] + 1, "bbox": b["bbox"]} 
                         for b in result.reading_order_doc2]
        }
        
        # LLM解析結果
        if result.llm_analysis:
            baseline_format["llm_analysis"] = result.llm_analysis.to_dict()
        
        # 保存（ベースラインと同じくreportsディレクトリに保存）
        reports_dir = self.output_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        json_path = reports_dir / "execution_report.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(baseline_format, f, ensure_ascii=False, indent=2)
        
        return json_path
    
    def _save_diff_csv(self, result: ComparisonResult, base_name: str) -> Path:
        """差分とマッチング結果をCSV形式で保存
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパス
        """
        csv_path = self.output_dir / f"{base_name}_differences.csv"
        
        # CSVヘッダー
        headers = [
            "番号", "変更タイプ", "前年ページ数", "今年ページ数", "元のテキスト", "変更後のテキスト",
            "類似度", "説明"
        ]
        
        rows = []
        row_number = 1
        
        # まず差分を追加
        for diff in result.diff_results:
            original_text = diff.original_bbox["text"] if diff.original_bbox else ""
            modified_text = diff.modified_bbox["text"] if diff.modified_bbox else ""
            
            # ページ番号の設定
            if diff.change_type.value == "deletion":
                # 削除の場合：前年のページのみ
                doc1_page = diff.page + 1
                doc2_page = ""
            elif diff.change_type.value == "addition":
                # 追加の場合：今年のページのみ
                doc1_page = ""
                doc2_page = diff.page + 1
            else:  # modification
                # 変更の場合：両方のページ
                doc1_page = diff.original_bbox["page"] + 1 if diff.original_bbox else diff.page + 1
                doc2_page = diff.modified_bbox["page"] + 1 if diff.modified_bbox else diff.page + 1
            
            row = [
                row_number,
                diff.change_type.value,
                doc1_page,
                doc2_page,
                original_text,
                modified_text,
                f"{diff.semantic_similarity:.2f}",
                diff.llm_explanation or ""
            ]
            rows.append(row)
            row_number += 1
        
        # マッチングした文言を検出して追加
        # metadataからmatched_itemsを取得（存在する場合）
        matched_items = result.metadata.get('matched_items', [])
        
        if matched_items:
            # matched_itemsから直接MATCHEDを追加
            for match in matched_items:
                item1 = match['doc1_item']
                item2 = match['doc2_item']
                text = match['text']
                
                row = [
                    row_number,
                    "MATCHED",  # マッチングした文言
                    item1['page'] + 1,  # 前年ページ数
                    item2['page'] + 1,  # 今年ページ数
                    text,  # 元のテキスト
                    text,  # 変更後のテキスト（同じ）
                    "1.00",  # 完全一致なので類似度1.0
                    "変更なし"  # 説明
                ]
                rows.append(row)
                row_number += 1
        else:
            # 旧方式のフォールバック（matched_itemsがない場合）
            logger.info("matched_items not found in metadata, using fallback method")
        
        # CSVとして保存
        import csv
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        
        logger.info(f"CSV saved with {len(rows)} items (including matched texts)")
        return csv_path
    
    def _save_reading_order_csv(self, result: ComparisonResult, base_name: str) -> Path:
        """読み順序をJSON形式で保存（ベースライン互換）
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパス
        """
        # ベースラインと同じくreportsディレクトリに保存
        reports_dir = self.output_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        json_path = reports_dir / "reading_order.json"
        
        # ベースライン形式のJSON構造を作成
        reading_order_data = {
            "document1": result.reading_order_doc1,
            "document2": result.reading_order_doc2
        }
        
        # JSONとして保存
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(reading_order_data, f, ensure_ascii=False, indent=2)
        
        return json_path
    
    def _save_sentence_info(self, result: ComparisonResult, base_name: str) -> Path:
        """sentence_info.jsonを保存（ベースライン互換）
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパス
        """
        reports_dir = self.output_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        json_path = reports_dir / "sentence_info.json"
        
        # ベースライン形式のsentence_info構造を作成
        sentence_info = {
            "document1_sentences": len(result.reading_order_doc1),
            "document2_sentences": len(result.reading_order_doc2),
            "differences": len(result.diff_results),
            "change_types": {}
        }
        
        # 変更タイプの集計
        for diff in result.diff_results:
            change_type = diff.change_type.value
            sentence_info["change_types"][change_type] = \
                sentence_info["change_types"].get(change_type, 0) + 1
        
        # JSONとして保存
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(sentence_info, f, ensure_ascii=False, indent=2)
        
        return json_path
    
    def _save_summary_report(self, result: ComparisonResult, base_name: str) -> Path:
        """サマリーレポートを保存
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパス
        """
        # ベースラインと同じファイル名形式を使用
        report_path = self.output_dir / "reports" / "execution_report.md"
        report_path.parent.mkdir(exist_ok=True)
        
        # レポート内容を生成
        report_lines = [
            f"# 文書比較レポート",
            f"",
            f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}",
            f"",
            f"## 概要",
            f"- 文書1: {result.metadata.get('file1', 'N/A')}",
            f"- 文書2: {result.metadata.get('file2', 'N/A')}",
            f"- 総ページ数: 文書1={result.metadata.get('doc1_pages', 0)}ページ, "
            f"文書2={result.metadata.get('doc2_pages', 0)}ページ",
            f"- 検出された差分: {len(result.diff_results)}件",
            f"- 処理時間: {result.execution_time:.2f}秒",
            f"",
            f"## 差分の内訳",
            f""
        ]
        
        # 変更タイプ別の集計
        type_counts = {}
        for diff in result.diff_results:
            change_type = diff.change_type.value
            type_counts[change_type] = type_counts.get(change_type, 0) + 1
        
        for change_type, count in type_counts.items():
            report_lines.append(f"- {change_type}: {count}件")
        
        # LLM解析結果
        if result.llm_analysis:
            report_lines.extend([
                f"",
                f"## LLM解析結果",
                f"",
                f"### 文書要約",
                f"{result.llm_analysis.document_summary}",
                f"",
                f"### 主要な変更点"
            ])
            
            for change in result.llm_analysis.key_changes:
                report_lines.append(f"- {change}")
            
            report_lines.extend([
                f"",
                f"### リスク評価"
            ])
            
            for risk_type, score in result.llm_analysis.risk_assessment.items():
                report_lines.append(f"- {risk_type}: {score:.2%}")
        
        # 主要な差分（最初の10件）
        report_lines.extend([
            f"",
            f"## 主要な差分（最初の10件）",
            f""
        ])
        
        for i, diff in enumerate(result.diff_results[:10], 1):
            original = diff.original_bbox["text"] if diff.original_bbox else "（なし）"
            modified = diff.modified_bbox["text"] if diff.modified_bbox else "（なし）"
            
            report_lines.extend([
                f"### {i}. {diff.change_type.value}",
                f"- ページ: {diff.page + 1}",
                f"- 元: {original}",
                f"- 後: {modified}",
                f"- 説明: {diff.llm_explanation or 'なし'}",
                f""
            ])
        
        # ファイルに保存
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        return report_path
    
    def _save_debug_info(self, result: ComparisonResult, base_name: str) -> Path:
        """デバッグ情報を保存
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパス
        """
        debug_dir = self.output_dir / "debug" / base_name
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # 完全な結果をJSON形式で保存
        full_result_path = debug_dir / "full_result.json"
        with open(full_result_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 統計情報を保存
        stats = {
            "total_differences": len(result.diff_results),
            "doc1_word_count": len(result.reading_order_doc1),
            "doc2_word_count": len(result.reading_order_doc2),
            "change_type_distribution": {},
            "pages_with_changes": set()
        }
        
        # 変更タイプの分布を集計
        for diff in result.diff_results:
            change_type = diff.change_type.value
            stats["change_type_distribution"][change_type] = \
                stats["change_type_distribution"].get(change_type, 0) + 1
            stats["pages_with_changes"].add(diff.page + 1)
        
        stats["pages_with_changes"] = sorted(list(stats["pages_with_changes"]))
        
        stats_path = debug_dir / "statistics.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        return debug_dir
    
    def create_highlighted_pdfs(self, pdf1_bytes: bytes, pdf2_bytes: bytes,
                              result: ComparisonResult) -> Dict[str, bytes]:
        """ハイライト付きPDFを作成
        
        Args:
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            result: 比較結果
            
        Returns:
            ハイライト付きPDFのバイトデータ辞書
        """
        # 最大ページ数を取得（TEST_MAX_PAGESが設定されている場合）
        max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
        
        # PDFをページ制限する
        if max_pages:
            logger.info(f"Limiting PDFs to {max_pages} pages for highlighted output")
            pdf1_bytes = self.pdf_processor.limit_pdf_pages(pdf1_bytes, max_pages)
            pdf2_bytes = self.pdf_processor.limit_pdf_pages(pdf2_bytes, max_pages)
        
        highlights1 = []
        highlights2 = []
        
        # 差分をハイライトに変換
        for diff in result.diff_results:
            if diff.change_type == ChangeType.DELETION and diff.original_bbox:
                # 削除: 文書1で赤
                highlights1.append(Highlight(
                    bbox=diff.original_bbox["bbox"],
                    page=diff.original_bbox["page"],
                    color="red"
                ).to_dict())
            
            elif diff.change_type == ChangeType.ADDITION and diff.modified_bbox:
                # 追加: 文書2で緑
                highlights2.append(Highlight(
                    bbox=diff.modified_bbox["bbox"],
                    page=diff.modified_bbox["page"],
                    color="green"
                ).to_dict())
            
            elif diff.change_type == ChangeType.MODIFICATION:
                # 修正: 両方で黄色
                if diff.original_bbox:
                    highlights1.append(Highlight(
                        bbox=diff.original_bbox["bbox"],
                        page=diff.original_bbox["page"],
                        color="yellow"
                    ).to_dict())
                
                if diff.modified_bbox:
                    highlights2.append(Highlight(
                        bbox=diff.modified_bbox["bbox"],
                        page=diff.modified_bbox["page"],
                        color="yellow"
                    ).to_dict())
        
        # PDFを生成
        highlighted_pdfs = {}
        
        logger.info(f"Creating highlighted PDFs: doc1={len(highlights1)} highlights, doc2={len(highlights2)} highlights")
        
        if highlights1:
            highlighted_pdfs["doc1"] = self.pdf_processor.create_highlighted_pdf(
                pdf1_bytes, highlights1
            )
        
        if highlights2:
            highlighted_pdfs["doc2"] = self.pdf_processor.create_highlighted_pdf(
                pdf2_bytes, highlights2
            )
        
        return highlighted_pdfs
    
    def _save_reading_order_pdfs(self, result: ComparisonResult, base_name: str,
                                pdf1_bytes: bytes = None, pdf2_bytes: bytes = None,
                                pdf1_basename: str = "2023", pdf2_basename: str = "2024") -> Dict[str, str]:
        """読み順序を可視化したPDFを保存
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            
        Returns:
            保存されたファイルパスの辞書
        """
        saved_paths = {}
        
        # 文書1の読み順序PDF
        if pdf1_bytes and result.reading_order_doc1:
            highlights = []
            # すべての要素にハイライトと番号を付ける
            for idx, bbox_data in enumerate(result.reading_order_doc1):
                # global_orderが存在する場合はそれを使用、なければidx+1を使用
                order_num = bbox_data.get("global_order", idx + 1)
                highlights.append({
                    "bbox": bbox_data["bbox"],
                    "page": bbox_data["page"],
                    "color": "blue",
                    "label": str(order_num)  # グローバル順序番号を表示
                })
            
            # 最大ページ数を取得（TEST_MAX_PAGESが設定されている場合）
            max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
            if max_pages:
                # 制限されたページ数分のみのPDFを作成
                logger.info(f"Creating reading order PDF with {len(highlights)} highlights for doc1 (limited to {max_pages} pages)")
                # PDFのページ数も制限する
                limited_pdf = self.pdf_processor.limit_pdf_pages(pdf1_bytes, max_pages)
                reading_order_pdf = self.pdf_processor.create_highlighted_pdf(
                    limited_pdf, highlights
                )
            else:
                # 読み順序を可視化したPDFを作成
                logger.info(f"Creating reading order PDF with {len(highlights)} highlights for doc1")
                reading_order_pdf = self.pdf_processor.create_highlighted_pdf(
                    pdf1_bytes, highlights
                )
            
            # 保存（元のファイル名を使用）
            pdfs_dir = self.output_dir / "PDFs"
            pdfs_dir.mkdir(exist_ok=True)
            pdf_path = pdfs_dir / f"{pdf1_basename}_reading_order.pdf"
            with open(pdf_path, 'wb') as f:
                f.write(reading_order_pdf)
            saved_paths["reading_order_pdf1"] = str(pdf_path)
        
        # 文書2の読み順序PDF
        if pdf2_bytes and result.reading_order_doc2:
            highlights = []
            # すべての要素にハイライトと番号を付ける
            for idx, bbox_data in enumerate(result.reading_order_doc2):
                # global_orderが存在する場合はそれを使用、なければidx+1を使用
                order_num = bbox_data.get("global_order", idx + 1)
                highlights.append({
                    "bbox": bbox_data["bbox"],
                    "page": bbox_data["page"],
                    "color": "blue",
                    "label": str(order_num)  # グローバル順序番号を表示
                })
            
            # 最大ページ数を取得（TEST_MAX_PAGESが設定されている場合）
            max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
            if max_pages:
                # 制限されたページ数分のみのPDFを作成
                logger.info(f"Creating reading order PDF with {len(highlights)} highlights for doc2 (limited to {max_pages} pages)")
                # PDFのページ数も制限する
                limited_pdf = self.pdf_processor.limit_pdf_pages(pdf2_bytes, max_pages)
                reading_order_pdf = self.pdf_processor.create_highlighted_pdf(
                    limited_pdf, highlights
                )
            else:
                # 読み順序を可視化したPDFを作成
                logger.info(f"Creating reading order PDF with {len(highlights)} highlights for doc2")
                reading_order_pdf = self.pdf_processor.create_highlighted_pdf(
                    pdf2_bytes, highlights
                )
            
            pdfs_dir = self.output_dir / "PDFs"
            pdfs_dir.mkdir(exist_ok=True)
            pdf_path = pdfs_dir / f"{pdf2_basename}_reading_order.pdf"
            with open(pdf_path, 'wb') as f:
                f.write(reading_order_pdf)
            saved_paths["reading_order_pdf2"] = str(pdf_path)
        
        return saved_paths
    
    def _save_reading_order_debug_csv(self, result: ComparisonResult, base_name: str) -> Dict[str, str]:
        """読み順序CSVをdebugディレクトリに保存（ベースライン互換）
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパスの辞書
        """
        debug_dir = self.output_dir / "debug"
        debug_dir.mkdir(exist_ok=True)
        
        saved_paths = {}
        
        # metadataからファイル名を取得
        pdf1_basename = Path(result.metadata.get('doc1_name', '2023.pdf')).stem
        pdf2_basename = Path(result.metadata.get('doc2_name', '2024.pdf')).stem
        
        # 文書1の元の順序CSV
        if result.metadata.get('doc1_boxes'):
            csv_path = debug_dir / f"{pdf1_basename}_reading_order_original.csv"
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["順序", "テキスト", "ページ"])
                for i, bbox_data in enumerate(result.metadata['doc1_boxes']):
                    writer.writerow([i + 1, bbox_data["text"], bbox_data["page"] + 1])
            saved_paths["debug_csv1_original"] = str(csv_path)
        
        # 文書1の推定順序CSV（グローバル順序を使用）
        if result.reading_order_doc1:
            csv_path = debug_dir / f"{pdf1_basename}_reading_order_estimated.csv"
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["順序", "テキスト", "ページ", "グローバル順序"])
                for i, bbox_data in enumerate(result.reading_order_doc1):
                    global_order = bbox_data.get("global_order", i + 1)
                    writer.writerow([i + 1, bbox_data["text"], bbox_data["page"] + 1, global_order])
            saved_paths["debug_csv1_estimated"] = str(csv_path)
        
        # 文書2の元の順序CSV
        if result.metadata.get('doc2_boxes'):
            csv_path = debug_dir / f"{pdf2_basename}_reading_order_original.csv"
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["順序", "テキスト", "ページ"])
                for i, bbox_data in enumerate(result.metadata['doc2_boxes']):
                    writer.writerow([i + 1, bbox_data["text"], bbox_data["page"] + 1])
            saved_paths["debug_csv2_original"] = str(csv_path)
        
        # 文書2の推定順序CSV（グローバル順序を使用）
        if result.reading_order_doc2:
            csv_path = debug_dir / f"{pdf2_basename}_reading_order_estimated.csv"
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["順序", "テキスト", "ページ", "グローバル順序"])
                for i, bbox_data in enumerate(result.reading_order_doc2):
                    global_order = bbox_data.get("global_order", i + 1)
                    writer.writerow([i + 1, bbox_data["text"], bbox_data["page"] + 1, global_order])
            saved_paths["debug_csv2_estimated"] = str(csv_path)
        
        # 見開き/ページ単位のデバッグ情報を保存
        self._save_spread_debug_info(result, saved_paths)
        
        return saved_paths
    
    def _save_spread_debug_info(self, result: ComparisonResult, saved_paths: Dict[str, str]):
        """見開き/ページ単位のデバッグ情報を保存
        
        Args:
            result: 比較結果
            saved_paths: 保存されたファイルパスの辞書
        """
        debug_dir = self.output_dir / "debug"
        
        # metadataからファイル名を取得
        pdf1_basename = Path(result.metadata.get('doc1_name', '2023.pdf')).stem
        pdf2_basename = Path(result.metadata.get('doc2_name', '2024.pdf')).stem
        
        # 文書1の見開き単位デバッグ情報
        if result.reading_order_doc1:
            spreads_data = self._group_by_spreads(result.reading_order_doc1)
            csv_path = debug_dir / f"{pdf1_basename}_spreads_debug.csv"
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["見開き/ページ", "開始順序", "終了順序", "要素数", "結合テキスト"])
                
                for spread_info in spreads_data:
                    combined_text = " ".join([item["text"] for item in spread_info["items"]])[:200]
                    writer.writerow([
                        spread_info["spread_name"],
                        spread_info["start_order"],
                        spread_info["end_order"],
                        spread_info["item_count"],
                        combined_text + "..." if len(combined_text) >= 200 else combined_text
                    ])
            saved_paths["debug_spreads1"] = str(csv_path)
        
        # 文書2の見開き単位デバッグ情報
        if result.reading_order_doc2:
            spreads_data = self._group_by_spreads(result.reading_order_doc2)
            csv_path = debug_dir / f"{pdf2_basename}_spreads_debug.csv"
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["見開き/ページ", "開始順序", "終了順序", "要素数", "結合テキスト"])
                
                for spread_info in spreads_data:
                    combined_text = " ".join([item["text"] for item in spread_info["items"]])[:200]
                    writer.writerow([
                        spread_info["spread_name"],
                        spread_info["start_order"],
                        spread_info["end_order"],
                        spread_info["item_count"],
                        combined_text + "..." if len(combined_text) >= 200 else combined_text
                    ])
            saved_paths["debug_spreads2"] = str(csv_path)
    
    def _group_by_spreads(self, reading_order_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """読み順序データを見開き/ページ単位でグループ化
        
        Args:
            reading_order_data: 読み順序データ
            
        Returns:
            見開き単位の情報リスト
        """
        from collections import defaultdict
        
        # ページごとにグループ化
        pages = defaultdict(list)
        for item in reading_order_data:
            pages[item["page"]].append(item)
        
        # 見開き単位でまとめる
        spreads_data = []
        processed_pages = set()
        
        for page_num in sorted(pages.keys()):
            if page_num in processed_pages:
                continue
            
            # 単独ページか見開きかを判定
            if page_num == 0:  # 最初のページ（表紙）
                spread_name = "表紙（ページ1）"
                spread_items = pages[page_num]
                processed_pages.add(page_num)
            elif page_num % 2 == 1 and (page_num + 1) in pages:  # 見開きの左ページ
                spread_name = f"見開きページ{page_num + 1}-{page_num + 2}"
                spread_items = pages[page_num] + pages[page_num + 1]
                processed_pages.add(page_num)
                processed_pages.add(page_num + 1)
            else:  # 単独ページ
                spread_name = f"ページ{page_num + 1}"
                spread_items = pages[page_num]
                processed_pages.add(page_num)
            
            # グローバル順序でソート
            spread_items.sort(key=lambda x: x.get("global_order", 0))
            
            if spread_items:
                spreads_data.append({
                    "spread_name": spread_name,
                    "start_order": spread_items[0].get("global_order", 0),
                    "end_order": spread_items[-1].get("global_order", 0),
                    "item_count": len(spread_items),
                    "items": spread_items
                })
        
        return spreads_data
    
    def _save_original_order_pdfs(self, result: ComparisonResult, base_name: str,
                                 pdf1_bytes: bytes = None, pdf2_bytes: bytes = None,
                                 pdf1_basename: str = "2023", pdf2_basename: str = "2024") -> Dict[str, str]:
        """元の順序を可視化したPDFを保存（ベースライン互換）
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            
        Returns:
            保存されたファイルパスの辞書
        """
        saved_paths = {}
        
        # 最大ページ数を取得（TEST_MAX_PAGESが設定されている場合）
        max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
        
        # 文書1の元の順序PDF
        if pdf1_bytes and result.metadata.get('doc1_boxes'):
            # PDFをページ制限する
            if max_pages:
                logger.info(f"Limiting doc1 to {max_pages} pages for original order output")
                pdf1_bytes = self.pdf_processor.limit_pdf_pages(pdf1_bytes, max_pages)
            
            highlights = []
            # すべての要素にハイライトと番号を付ける
            for idx, bbox_data in enumerate(result.metadata['doc1_boxes']):
                # ページ制限内の要素のみを含める
                if not max_pages or bbox_data["page"] < max_pages:
                    highlights.append({
                        "bbox": bbox_data["bbox"],
                        "page": bbox_data["page"],
                        "color": "blue",
                        "label": str(idx + 1)  # すべてに番号を表示
                    })
            
            # 元の順序を可視化したPDFを作成
            logger.info(f"Creating original order PDF with {len(highlights)} highlights for doc1")
            original_order_pdf = self.pdf_processor.create_highlighted_pdf(
                pdf1_bytes, highlights
            )
            
            # 保存
            pdfs_dir = self.output_dir / "PDFs"
            pdfs_dir.mkdir(exist_ok=True)
            pdf_path = pdfs_dir / "2023_original_order.pdf"
            with open(pdf_path, 'wb') as f:
                f.write(original_order_pdf)
            saved_paths["original_order_pdf1"] = str(pdf_path)
        
        # 文書2の元の順序PDF
        if pdf2_bytes and result.metadata.get('doc2_boxes'):
            # PDFをページ制限する
            if max_pages:
                logger.info(f"Limiting doc2 to {max_pages} pages for original order output")
                pdf2_bytes = self.pdf_processor.limit_pdf_pages(pdf2_bytes, max_pages)
            
            highlights = []
            # すべての要素にハイライトと番号を付ける
            for idx, bbox_data in enumerate(result.metadata['doc2_boxes']):
                # ページ制限内の要素のみを含める
                if not max_pages or bbox_data["page"] < max_pages:
                    highlights.append({
                        "bbox": bbox_data["bbox"],
                        "page": bbox_data["page"],
                        "color": "blue",
                        "label": str(idx + 1)  # すべてに番号を表示
                    })
            
            original_order_pdf = self.pdf_processor.create_highlighted_pdf(
                pdf2_bytes, highlights
            )
            
            pdf_path = pdfs_dir / "2024_original_order.pdf"
            with open(pdf_path, 'wb') as f:
                f.write(original_order_pdf)
            saved_paths["original_order_pdf2"] = str(pdf_path)
        
        return saved_paths
    
    def _save_compared_pdfs(self, result: ComparisonResult, base_name: str,
                           pdf1_bytes: bytes = None, pdf2_bytes: bytes = None,
                           pdf1_basename: str = "2023", pdf2_basename: str = "2024") -> Dict[str, str]:
        """比較用ハイライトPDFを保存（ベースライン互換）
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            
        Returns:
            保存されたファイルパスの辞書
        """
        # ハイライト付きPDFを作成
        highlighted_pdfs = self.create_highlighted_pdfs(pdf1_bytes, pdf2_bytes, result)
        
        saved_paths = {}
        pdfs_dir = self.output_dir / "PDFs"
        pdfs_dir.mkdir(exist_ok=True)
        
        # 文書1の比較PDF
        if "doc1" in highlighted_pdfs:
            pdf_path = pdfs_dir / f"{pdf1_basename}_compared.pdf"
            with open(pdf_path, 'wb') as f:
                f.write(highlighted_pdfs["doc1"])
            saved_paths["compared_pdf1"] = str(pdf_path)
        
        # 文書2の比較PDF
        if "doc2" in highlighted_pdfs:
            pdf_path = pdfs_dir / f"{pdf2_basename}_compared.pdf"
            with open(pdf_path, 'wb') as f:
                f.write(highlighted_pdfs["doc2"])
            saved_paths["compared_pdf2"] = str(pdf_path)
        
        return saved_paths
    
    def _save_side_by_side_pdf(self, result: ComparisonResult, base_name: str,
                               pdf1_bytes: bytes = None, pdf2_bytes: bytes = None,
                               pdf1_basename: str = "2023", pdf2_basename: str = "2024") -> Optional[Path]:
        """2つのPDFを並べて表示する比較PDFを作成
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            
        Returns:
            保存されたファイルパス（失敗時はNone）
        """
        if not pdf1_bytes or not pdf2_bytes:
            return None
        
        try:
            import fitz  # PyMuPDF
            
            # 最大ページ数を取得（TEST_MAX_PAGESが設定されている場合）
            max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
            
            # まずハイライト付きPDFを作成（create_highlighted_pdfs内でページ制限される）
            highlighted_pdfs = self.create_highlighted_pdfs(pdf1_bytes, pdf2_bytes, result)
            
            # ハイライト付きPDFを使用（なければ元のPDFを使用）
            if "doc1" in highlighted_pdfs:
                doc1_bytes = highlighted_pdfs["doc1"]
                logger.info("Using highlighted PDF for doc1 in side-by-side")
            else:
                # ハイライトがない場合は元のPDFをページ制限
                if max_pages:
                    doc1_bytes = self.pdf_processor.limit_pdf_pages(pdf1_bytes, max_pages)
                else:
                    doc1_bytes = pdf1_bytes
                logger.info("No highlights for doc1, using original PDF")
                
            if "doc2" in highlighted_pdfs:
                doc2_bytes = highlighted_pdfs["doc2"] 
                logger.info("Using highlighted PDF for doc2 in side-by-side")
            else:
                # ハイライトがない場合は元のPDFをページ制限
                if max_pages:
                    doc2_bytes = self.pdf_processor.limit_pdf_pages(pdf2_bytes, max_pages)
                else:
                    doc2_bytes = pdf2_bytes
                logger.info("No highlights for doc2, using original PDF")
            
            # PDFドキュメントを開く
            doc1 = fitz.open(stream=doc1_bytes, filetype="pdf")
            doc2 = fitz.open(stream=doc2_bytes, filetype="pdf")
            
            # 新しいPDFを作成
            new_doc = fitz.open()
            
            # ページ数を取得（少ない方に合わせる）
            max_page_count = max(len(doc1), len(doc2))
            
            for page_idx in range(max_page_count):
                # 各文書のページを取得（存在しない場合は空白ページ）
                if page_idx < len(doc1):
                    page1 = doc1[page_idx]
                    rect1 = page1.rect
                else:
                    # 空白ページの場合、doc1の最初のページのサイズを使用
                    rect1 = doc1[0].rect if len(doc1) > 0 else fitz.Rect(0, 0, 595, 842)
                    page1 = None
                
                if page_idx < len(doc2):
                    page2 = doc2[page_idx]
                    rect2 = page2.rect
                else:
                    # 空白ページの場合、doc2の最初のページのサイズを使用
                    rect2 = doc2[0].rect if len(doc2) > 0 else fitz.Rect(0, 0, 595, 842)
                    page2 = None
                
                # 新しいページのサイズを計算（横に並べる）
                new_width = rect1.width + rect2.width + 20  # 20ポイントの間隔
                new_height = max(rect1.height, rect2.height)
                
                # 新しいページを作成
                new_page = new_doc.new_page(width=new_width, height=new_height)
                
                # 左側に文書1のページを配置（アノテーション付き）
                if page1:
                    # show_pdf_pageの代わりに、元のページの内容をコピー
                    # これによりアノテーション（ハイライト）も含まれる
                    xref = new_page.show_pdf_page(
                        fitz.Rect(0, 0, rect1.width, rect1.height),
                        doc1,
                        page_idx,
                        keep_proportion=True,
                        overlay=True,
                        oc=0,
                        rotate=0,
                        clip=None
                    )
                    
                    # アノテーションも手動でコピー
                    for annot in page1.annots():
                        # アノテーションの座標を取得
                        annot_rect = annot.rect
                        # 新しいページでの座標に変換（そのまま使用）
                        new_rect = fitz.Rect(annot_rect)
                        
                        # ハイライトアノテーションを新しいページに追加
                        if annot.type[0] == 8:  # ハイライトタイプ
                            new_annot = new_page.add_highlight_annot(new_rect)
                            # 色をコピー
                            new_annot.set_colors(stroke=annot.colors["stroke"])
                            new_annot.set_opacity(annot.opacity)
                            new_annot.update()
                
                # 右側に文書2のページを配置（アノテーション付き）
                if page2:
                    xref = new_page.show_pdf_page(
                        fitz.Rect(rect1.width + 20, 0, rect1.width + 20 + rect2.width, rect2.height),
                        doc2,
                        page_idx,
                        keep_proportion=True,
                        overlay=True,
                        oc=0,
                        rotate=0,
                        clip=None
                    )
                    
                    # アノテーションも手動でコピー
                    for annot in page2.annots():
                        # アノテーションの座標を取得
                        annot_rect = annot.rect
                        # 新しいページでの座標に変換（右側にシフト）
                        new_rect = fitz.Rect(
                            annot_rect.x0 + rect1.width + 20,
                            annot_rect.y0,
                            annot_rect.x1 + rect1.width + 20,
                            annot_rect.y1
                        )
                        
                        # ハイライトアノテーションを新しいページに追加
                        if annot.type[0] == 8:  # ハイライトタイプ
                            new_annot = new_page.add_highlight_annot(new_rect)
                            # 色をコピー
                            new_annot.set_colors(stroke=annot.colors["stroke"])
                            new_annot.set_opacity(annot.opacity)
                            new_annot.update()
                
                # ページ番号とラベルを追加
                # 左側のラベル
                label1_point = fitz.Point(rect1.width / 2, 20)
                new_page.insert_text(
                    label1_point,
                    f"2023年版 - ページ {page_idx + 1}",
                    fontsize=12,
                    color=(0, 0, 0),
                    fontname="helv"
                )
                
                # 右側のラベル
                label2_point = fitz.Point(rect1.width + 20 + rect2.width / 2, 20)
                new_page.insert_text(
                    label2_point,
                    f"2024年版 - ページ {page_idx + 1}",
                    fontsize=12,
                    color=(0, 0, 0),
                    fontname="helv"
                )
            
            # PDFをバイトデータに変換
            import io
            output_buffer = io.BytesIO()
            new_doc.save(output_buffer)
            
            # クリーンアップ
            doc1.close()
            doc2.close()
            new_doc.close()
            
            # ファイルとして保存
            pdfs_dir = self.output_dir / "PDFs"
            pdfs_dir.mkdir(exist_ok=True)
            pdf_path = pdfs_dir / "side_by_side_comparison.pdf"
            
            with open(pdf_path, 'wb') as f:
                f.write(output_buffer.getvalue())
            
            logger.info(f"Created side-by-side comparison PDF: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to create side-by-side PDF: {e}")
            return None
    
    def _save_azure_extraction_data(self, result: ComparisonResult, base_name: str) -> Dict[str, str]:
        """Azure Document Intelligenceの抽出データを保存
        
        Args:
            result: 比較結果
            base_name: ベースファイル名
            
        Returns:
            保存されたファイルパスの辞書
        """
        azure_dir = self.output_dir / "azure_extraction"
        azure_dir.mkdir(exist_ok=True)
        
        saved_paths = {}
        
        # Azure抽出データがメタデータに含まれている場合
        if result.metadata.get('azure_doc1_boxes'):
            # 文書1のAzure抽出データ
            azure_data1 = {
                "source": "Azure Document Intelligence",
                "extraction_method": "prebuilt-layout",
                "word_count": len(result.metadata['azure_doc1_boxes']),
                "pages": max(b["page"] for b in result.metadata['azure_doc1_boxes']) + 1 if result.metadata['azure_doc1_boxes'] else 0,
                "words": result.metadata['azure_doc1_boxes']
            }
            
            azure1_path = azure_dir / "2023_azure_extraction.json"
            with open(azure1_path, 'w', encoding='utf-8') as f:
                json.dump(azure_data1, f, ensure_ascii=False, indent=2)
            saved_paths["azure_doc1"] = str(azure1_path)
            
            # Azure抽出データのCSV
            csv1_path = azure_dir / "2023_azure_words.csv"
            with open(csv1_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["番号", "テキスト", "ページ", "X座標", "Y座標", "幅", "高さ"])
                for i, bbox_data in enumerate(result.metadata['azure_doc1_boxes'], 1):
                    bbox = bbox_data["bbox"]
                    writer.writerow([
                        i, 
                        bbox_data["text"], 
                        bbox_data["page"] + 1,
                        f"{bbox[0]:.2f}",
                        f"{bbox[1]:.2f}",
                        f"{bbox[2]:.2f}",
                        f"{bbox[3]:.2f}"
                    ])
            saved_paths["azure_csv1"] = str(csv1_path)
        
        if result.metadata.get('azure_doc2_boxes'):
            # 文書2のAzure抽出データ
            azure_data2 = {
                "source": "Azure Document Intelligence",
                "extraction_method": "prebuilt-layout",
                "word_count": len(result.metadata['azure_doc2_boxes']),
                "pages": max(b["page"] for b in result.metadata['azure_doc2_boxes']) + 1 if result.metadata['azure_doc2_boxes'] else 0,
                "words": result.metadata['azure_doc2_boxes']
            }
            
            azure2_path = azure_dir / "2024_azure_extraction.json"
            with open(azure2_path, 'w', encoding='utf-8') as f:
                json.dump(azure_data2, f, ensure_ascii=False, indent=2)
            saved_paths["azure_doc2"] = str(azure2_path)
            
            # Azure抽出データのCSV
            csv2_path = azure_dir / "2024_azure_words.csv"
            with open(csv2_path, 'w', encoding='utf-8-sig', newline='') as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["番号", "テキスト", "ページ", "X座標", "Y座標", "幅", "高さ"])
                for i, bbox_data in enumerate(result.metadata['azure_doc2_boxes'], 1):
                    bbox = bbox_data["bbox"]
                    writer.writerow([
                        i, 
                        bbox_data["text"], 
                        bbox_data["page"] + 1,
                        f"{bbox[0]:.2f}",
                        f"{bbox[1]:.2f}",
                        f"{bbox[2]:.2f}",
                        f"{bbox[3]:.2f}"
                    ])
            saved_paths["azure_csv2"] = str(csv2_path)
        
        # 通常抽出との比較統計
        if result.metadata.get('doc1_boxes') and result.metadata.get('azure_doc1_boxes'):
            comparison_stats = {
                "document1": {
                    "standard_extraction": len(result.metadata['doc1_boxes']),
                    "azure_extraction": len(result.metadata['azure_doc1_boxes']),
                    "difference": len(result.metadata['azure_doc1_boxes']) - len(result.metadata['doc1_boxes'])
                }
            }
            
            if result.metadata.get('doc2_boxes') and result.metadata.get('azure_doc2_boxes'):
                comparison_stats["document2"] = {
                    "standard_extraction": len(result.metadata['doc2_boxes']),
                    "azure_extraction": len(result.metadata['azure_doc2_boxes']),
                    "difference": len(result.metadata['azure_doc2_boxes']) - len(result.metadata['doc2_boxes'])
                }
            
            stats_path = azure_dir / "extraction_comparison.json"
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(comparison_stats, f, ensure_ascii=False, indent=2)
            saved_paths["azure_comparison"] = str(stats_path)
        
        return saved_paths