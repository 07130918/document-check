# coding: utf-8
"""
Enhanced Output Handler for LLM Document Diff v3.4
v3互換の詳細出力を生成する拡張出力ハンドラ
"""

import os
import sys
import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import fitz  # PyMuPDF

# プロジェクトルートをPATHに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.settings import Settings

logger = logging.getLogger(__name__)


class EnhancedOutputHandlerV34:
    """v3.4用拡張出力ハンドラ - v3互換の詳細出力を生成"""
    
    def __init__(self):
        """初期化"""
        self.settings = Settings()
        logger.info("拡張出力ハンドラv3.4を初期化しました")
    
    def generate_enhanced_output(self, 
                               analysis_result: Dict[str, Any], 
                               output_tag: str,
                               doc1_path: Optional[str] = None,
                               doc2_path: Optional[str] = None) -> Dict[str, str]:
        """拡張された出力を生成
        
        Args:
            analysis_result: v3.4の分析結果
            output_tag: 出力タグ
            doc1_path: 文書1のパス（PDF生成用）
            doc2_path: 文書2のパス（PDF生成用）
            
        Returns:
            生成されたファイルのパス辞書
        """
        try:
            logger.info("拡張出力生成を開始します")
            
            # タイムスタンプ付きの出力ディレクトリを作成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self.settings.OUTPUT_DIR / f"llm_diff_test_v3_4_{timestamp}" / output_tag
            
            # フォルダ構造を作成
            self._create_folder_structure(output_dir)
            
            saved_files = {}
            
            # 1. 基本出力（JSON/CSV）
            basic_files = self._generate_basic_output(analysis_result, output_dir, output_tag, timestamp)
            saved_files.update(basic_files)
            
            # 2. デバッグ情報出力
            debug_files = self._generate_debug_output(analysis_result, output_dir, timestamp)
            saved_files.update(debug_files)
            
            # 3. レポート出力
            report_files = self._generate_reports(analysis_result, output_dir)
            saved_files.update(report_files)
            
            # 4. PDF出力（パスが提供された場合）
            if doc1_path and doc2_path:
                pdf_files = self._generate_pdf_output(analysis_result, output_dir, doc1_path, doc2_path)
                saved_files.update(pdf_files)
            else:
                logger.warning("PDFパスが提供されていないため、PDF生成をスキップします")
            
            # 5. 詳細分析レポート
            analysis_report_path = self._generate_analysis_report(analysis_result, output_dir)
            if analysis_report_path:
                saved_files["analysis_report"] = str(analysis_report_path)
            
            logger.info(f"拡張出力生成完了: {len(saved_files)}個のファイルを生成")
            return saved_files
            
        except Exception as e:
            logger.error(f"拡張出力生成中にエラーが発生しました: {e}")
            raise
    
    def _create_folder_structure(self, base_dir: Path):
        """v3互換のフォルダ構造を作成"""
        folders = [
            base_dir / "debug" / "llm_diff_test_v3_4",
            base_dir / "PDFs",
            base_dir / "reports"
        ]
        
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
            logger.debug(f"フォルダを作成しました: {folder}")
    
    def _generate_basic_output(self, 
                             analysis_result: Dict[str, Any], 
                             output_dir: Path,
                             output_tag: str, 
                             timestamp: str) -> Dict[str, str]:
        """基本出力（JSON/CSV）を生成"""
        saved_files = {}
        
        try:
            # JSON出力
            json_filename = f"llm_diff_v3_4_{output_tag}_{timestamp}_differences.json"
            json_path = output_dir / json_filename
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            saved_files["main_json"] = str(json_path)
            
            # CSV出力
            csv_filename = f"llm_diff_v3_4_{output_tag}_{timestamp}_differences.csv"
            csv_path = output_dir / csv_filename
            
            self._generate_differences_csv(analysis_result, csv_path)
            saved_files["main_csv"] = str(csv_path)
            
            logger.info(f"基本出力を生成: JSON={json_filename}, CSV={csv_filename}")
            
        except Exception as e:
            logger.error(f"基本出力生成エラー: {e}")
            raise
        
        return saved_files
    
    def _generate_debug_output(self, 
                             analysis_result: Dict[str, Any], 
                             output_dir: Path,
                             timestamp: str) -> Dict[str, str]:
        """デバッグ情報を生成"""
        debug_dir = output_dir / "debug" / "llm_diff_test_v3_4"
        saved_files = {}
        
        try:
            # full_result.json
            full_result_path = debug_dir / "full_result.json"
            with open(full_result_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            saved_files["full_result"] = str(full_result_path)
            
            # statistics.json
            statistics = self._calculate_statistics(analysis_result)
            statistics_path = debug_dir / "statistics.json"
            with open(statistics_path, 'w', encoding='utf-8') as f:
                json.dump(statistics, f, ensure_ascii=False, indent=2)
            saved_files["statistics"] = str(statistics_path)
            
            # processing_log.txt
            log_path = debug_dir / "processing_log.txt"
            self._generate_processing_log(analysis_result, log_path)
            saved_files["processing_log"] = str(log_path)
            
            logger.info("デバッグ情報を生成しました")
            
        except Exception as e:
            logger.error(f"デバッグ情報生成エラー: {e}")
            raise
        
        return saved_files
    
    def _generate_reports(self, 
                        analysis_result: Dict[str, Any], 
                        output_dir: Path) -> Dict[str, str]:
        """レポートファイルを生成"""
        reports_dir = output_dir / "reports"
        saved_files = {}
        
        try:
            # execution_report.json
            execution_report = self._create_execution_report(analysis_result)
            json_report_path = reports_dir / "execution_report.json"
            with open(json_report_path, 'w', encoding='utf-8') as f:
                json.dump(execution_report, f, ensure_ascii=False, indent=2)
            saved_files["execution_report_json"] = str(json_report_path)
            
            # execution_report.md
            md_report_path = reports_dir / "execution_report.md"
            self._generate_markdown_report(execution_report, md_report_path)
            saved_files["execution_report_md"] = str(md_report_path)
            
            # reading_order.json
            reading_order_path = reports_dir / "reading_order.json"
            self._generate_reading_order_json(analysis_result, reading_order_path)
            saved_files["reading_order"] = str(reading_order_path)
            
            # sentence_info.json
            sentence_info_path = reports_dir / "sentence_info.json"
            self._generate_sentence_info_json(analysis_result, sentence_info_path)
            saved_files["sentence_info"] = str(sentence_info_path)
            
            logger.info("レポートファイルを生成しました")
            
        except Exception as e:
            logger.error(f"レポート生成エラー: {e}")
            raise
        
        return saved_files
    
    def _generate_pdf_output(self,
                           analysis_result: Dict[str, Any],
                           output_dir: Path,
                           doc1_path: str,
                           doc2_path: str) -> Dict[str, str]:
        """PDF出力を生成"""
        pdfs_dir = output_dir / "PDFs"
        saved_files = {}
        
        try:
            logger.info("PDF生成を開始します")
            
            # PDFファイルを読み込み
            with open(doc1_path, 'rb') as f:
                doc1_bytes = f.read()
            with open(doc2_path, 'rb') as f:
                doc2_bytes = f.read()
            
            # 並列比較PDF
            side_by_side_path = self._create_side_by_side_pdf(
                analysis_result, pdfs_dir, doc1_bytes, doc2_bytes
            )
            if side_by_side_path:
                saved_files["side_by_side_pdf"] = str(side_by_side_path)
                logger.info(f"並列比較PDF出力完了: {side_by_side_path}")
            
            # 注釈付きPDF
            annotated_files = self._create_annotated_pdfs(
                analysis_result, pdfs_dir, doc1_bytes, doc2_bytes
            )
            saved_files.update(annotated_files)
            
            # 注釈付きPDFのパスも個別に表示
            if "document1_annotated" in annotated_files:
                logger.info(f"文書1注釈付きPDF出力完了: {annotated_files['document1_annotated']}")
            if "document2_annotated" in annotated_files:
                logger.info(f"文書2注釈付きPDF出力完了: {annotated_files['document2_annotated']}")
            
            logger.info("PDF生成完了")
            logger.info(f"生成されたPDFファイル数: {len(saved_files)}")
            
        except Exception as e:
            logger.error(f"PDF生成エラー: {e}")
            # PDF生成失敗は致命的でないため、例外を再発生させない
        
        return saved_files
    
    def _generate_differences_csv(self, analysis_result: Dict[str, Any], csv_path: Path):
        """差分CSVを生成"""
        fieldnames = [
            'change_type', 'page', 'semantic_similarity',
            'original_text', 'modified_text',
            'original_x', 'original_y', 'modified_x', 'modified_y',
            'section_title', 'paragraph_role', 'explanation'
        ]
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for diff in analysis_result.get('differences', []):
                writer.writerow({
                    'change_type': diff.get('change_type', ''),
                    'page': diff.get('page', ''),
                    'semantic_similarity': diff.get('semantic_similarity', ''),
                    'original_text': self._truncate_text(diff.get('original_text', ''), 100),
                    'modified_text': self._truncate_text(diff.get('modified_text', ''), 100),
                    'original_x': self._get_coordinate_value(diff.get('original_coordinates'), 'left'),
                    'original_y': self._get_coordinate_value(diff.get('original_coordinates'), 'top'),
                    'modified_x': self._get_coordinate_value(diff.get('modified_coordinates'), 'left'),
                    'modified_y': self._get_coordinate_value(diff.get('modified_coordinates'), 'top'),
                    'section_title': diff.get('structural_info', {}).get('section_title', ''),
                    'paragraph_role': diff.get('structural_info', {}).get('paragraph_role', ''),
                    'explanation': self._truncate_text(diff.get('explanation', ''), 200)
                })
    
    def _calculate_statistics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """統計情報を計算"""
        differences = analysis_result.get('differences', [])
        
        # 変更タイプ別の集計
        change_types = {}
        for diff in differences:
            change_type = diff.get('change_type', 'unknown')
            change_types[change_type] = change_types.get(change_type, 0) + 1
        
        # ページ別の集計
        pages_with_changes = set()
        for diff in differences:
            page = diff.get('page')
            if page is not None:
                pages_with_changes.add(page)
        
        # 類似度の統計
        similarities = [diff.get('semantic_similarity', 0) for diff in differences if diff.get('semantic_similarity') is not None]
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0
        
        return {
            "generation_timestamp": datetime.now().isoformat(),
            "total_differences": len(differences),
            "change_type_distribution": change_types,
            "pages_with_changes": sorted(list(pages_with_changes)),
            "pages_with_changes_count": len(pages_with_changes),
            "average_semantic_similarity": round(avg_similarity, 3),
            "preprocessing_results": analysis_result.get('preprocessing_results', {}),
            "execution_info": {
                "version": analysis_result.get('version', 'v3.4'),
                "analysis_type": analysis_result.get('analysis_type', 'structured_document_intelligence'),
                "timestamp": analysis_result.get('timestamp')
            }
        }
    
    def _generate_processing_log(self, analysis_result: Dict[str, Any], log_path: Path):
        """処理ログを生成"""
        log_lines = [
            "=== LLM Document Diff v3.4 Processing Log ===",
            f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "=== 分析概要 ===",
            f"バージョン: {analysis_result.get('version', 'v3.4')}",
            f"分析タイプ: {analysis_result.get('analysis_type', 'structured_document_intelligence')}",
            f"分析日時: {analysis_result.get('timestamp', 'N/A')}",
            "",
            "=== 入力ファイル ===",
        ]
        
        input_files = analysis_result.get('input_files', {})
        for key, value in input_files.items():
            log_lines.append(f"{key}: {value}")
        
        log_lines.extend([
            "",
            "=== 前処理結果 ===",
        ])
        
        preprocessing = analysis_result.get('preprocessing_results', {})
        for key, value in preprocessing.items():
            log_lines.append(f"{key}: {value}")
        
        log_lines.extend([
            "",
            "=== 差分検出結果 ===",
            f"総差分数: {len(analysis_result.get('differences', []))}",
        ])
        
        summary = analysis_result.get('summary', {})
        for key, value in summary.items():
            log_lines.append(f"{key}: {value}")
        
        log_lines.extend([
            "",
            "=== 差分詳細（上位10件）===",
        ])
        
        for i, diff in enumerate(analysis_result.get('differences', [])[:10], 1):
            log_lines.extend([
                f"{i}. {diff.get('change_type', 'unknown')} (類似度: {diff.get('semantic_similarity', 'N/A')})",
                f"   元: {self._truncate_text(diff.get('original_text', ''), 100)}",
                f"   新: {self._truncate_text(diff.get('modified_text', ''), 100)}",
                ""
            ])
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
    
    def _create_execution_report(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """実行レポートを作成"""
        return {
            "version": analysis_result.get('version', 'v3.4'),
            "execution_time": 0.0,  # v3.4では未実装
            "timestamp": analysis_result.get('timestamp'),
            "input_files": analysis_result.get('input_files', {}),
            "summary": {
                "total_differences": len(analysis_result.get('differences', [])),
                "change_types": analysis_result.get('summary', {}),
                "preprocessing_results": analysis_result.get('preprocessing_results', {})
            },
            "differences": analysis_result.get('differences', [])[:50],  # 上位50件
            "document_analysis": {
                "document1_sections": len(analysis_result.get('document_analysis', {}).get('document1', {}).get('sections', [])),
                "document2_sections": len(analysis_result.get('document_analysis', {}).get('document2', {}).get('sections', []))
            }
        }
    
    def _generate_markdown_report(self, execution_report: Dict[str, Any], md_path: Path):
        """Markdownレポートを生成"""
        lines = [
            "# LLM Document Diff v3.4 実行レポート",
            "",
            f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}",
            "",
            "## 概要",
            f"- バージョン: {execution_report.get('version', 'v3.4')}",
            f"- 分析日時: {execution_report.get('timestamp', 'N/A')}",
            f"- 検出された差分: {execution_report.get('summary', {}).get('total_differences', 0)}件",
            "",
            "## 入力ファイル",
        ]
        
        for key, value in execution_report.get('input_files', {}).items():
            lines.append(f"- {key}: {value}")
        
        lines.extend([
            "",
            "## 差分の内訳",
        ])
        
        change_types = execution_report.get('summary', {}).get('change_types', {})
        for change_type, count in change_types.items():
            lines.append(f"- {change_type}: {count}件")
        
        lines.extend([
            "",
            "## 文書分析結果",
            f"- 文書1のセクション数: {execution_report.get('document_analysis', {}).get('document1_sections', 0)}",
            f"- 文書2のセクション数: {execution_report.get('document_analysis', {}).get('document2_sections', 0)}",
            "",
            "## 主要な差分（上位10件）",
        ])
        
        for i, diff in enumerate(execution_report.get('differences', [])[:10], 1):
            lines.extend([
                f"### {i}. {diff.get('change_type', 'unknown')}",
                f"- ページ: {diff.get('page', 'N/A')}",
                f"- 類似度: {diff.get('semantic_similarity', 'N/A')}",
                f"- 元テキスト: {self._truncate_text(diff.get('original_text', ''), 100)}",
                f"- 新テキスト: {self._truncate_text(diff.get('modified_text', ''), 100)}",
                ""
            ])
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
    def _generate_reading_order_json(self, analysis_result: Dict[str, Any], json_path: Path):
        """reading_order.jsonを生成（v3互換形式）"""
        reading_order = {
            "document1": [],
            "document2": []
        }
        
        # document_analysisから読み順序情報を抽出（簡易実装）
        doc1_analysis = analysis_result.get('document_analysis', {}).get('document1', {})
        doc2_analysis = analysis_result.get('document_analysis', {}).get('document2', {})
        
        # セクションからパラグラフを抽出
        for section in doc1_analysis.get('sections', []):
            for para in section.get('paragraphs', []):
                reading_order["document1"].append({
                    "text": para.get('content', ''),
                    "page": para.get('page', 1),
                    "bbox": para.get('coordinates', [0, 0, 0, 0])
                })
        
        for section in doc2_analysis.get('sections', []):
            for para in section.get('paragraphs', []):
                reading_order["document2"].append({
                    "text": para.get('content', ''),
                    "page": para.get('page', 1),
                    "bbox": para.get('coordinates', [0, 0, 0, 0])
                })
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(reading_order, f, ensure_ascii=False, indent=2)
    
    def _generate_sentence_info_json(self, analysis_result: Dict[str, Any], json_path: Path):
        """sentence_info.jsonを生成"""
        sentence_info = {
            "generation_timestamp": datetime.now().isoformat(),
            "version": "v3.4",
            "document1_sentences": 0,
            "document2_sentences": 0,
            "differences": len(analysis_result.get('differences', [])),
            "change_types": {}
        }
        
        # 差分のchange_typeを集計
        for diff in analysis_result.get('differences', []):
            change_type = diff.get('change_type', 'unknown')
            sentence_info["change_types"][change_type] = sentence_info["change_types"].get(change_type, 0) + 1
        
        # セクション数から文数を推定（簡易実装）
        doc1_analysis = analysis_result.get('document_analysis', {}).get('document1', {})
        doc2_analysis = analysis_result.get('document_analysis', {}).get('document2', {})
        
        sentence_info["document1_sentences"] = doc1_analysis.get('summary', {}).get('total_paragraphs', 0)
        sentence_info["document2_sentences"] = doc2_analysis.get('summary', {}).get('total_paragraphs', 0)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(sentence_info, f, ensure_ascii=False, indent=2)
    
    def _create_side_by_side_pdf(self,
                                analysis_result: Dict[str, Any],
                                pdfs_dir: Path,
                                doc1_bytes: bytes,
                                doc2_bytes: bytes) -> Optional[Path]:
        """並列比較PDFを作成"""
        try:
            pdf_path = pdfs_dir / "side_by_side_comparison.pdf"
            
            # 基本的な並列PDF作成（詳細実装は後で）
            doc1 = fitz.open(stream=doc1_bytes, filetype="pdf")
            doc2 = fitz.open(stream=doc2_bytes, filetype="pdf")
            
            new_doc = fitz.open()
            
            # 最初のページのみ処理（デモ用）
            if len(doc1) > 0 and len(doc2) > 0:
                page1 = doc1[0]
                page2 = doc2[0]
                
                # 新しいページを作成（横に並べる）
                new_width = page1.rect.width + page2.rect.width + 20
                new_height = max(page1.rect.height, page2.rect.height)
                new_page = new_doc.new_page(width=new_width, height=new_height)
                
                # 左側に文書1
                new_page.show_pdf_page(fitz.Rect(0, 0, page1.rect.width, page1.rect.height), doc1, 0)
                
                # 右側に文書2
                new_page.show_pdf_page(
                    fitz.Rect(page1.rect.width + 20, 0, page1.rect.width + 20 + page2.rect.width, page2.rect.height),
                    doc2, 0
                )
                
                # ラベル追加
                new_page.insert_text(fitz.Point(page1.rect.width / 2, 20), "文書1", fontsize=14)
                new_page.insert_text(fitz.Point(page1.rect.width + 20 + page2.rect.width / 2, 20), "文書2", fontsize=14)
            
            new_doc.save(pdf_path)
            new_doc.close()
            doc1.close()
            doc2.close()
            
            logger.info(f"並列比較PDFを作成: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"並列比較PDF作成エラー: {e}")
            return None
    
    def _create_annotated_pdfs(self,
                              analysis_result: Dict[str, Any],
                              pdfs_dir: Path,
                              doc1_bytes: bytes,
                              doc2_bytes: bytes) -> Dict[str, str]:
        """注釈付きPDFを作成"""
        saved_files = {}
        
        try:
            # 文書1の注釈付きPDF
            doc1_path = pdfs_dir / "document1_annotated.pdf"
            self._create_single_annotated_pdf(doc1_bytes, analysis_result, doc1_path, is_doc1=True)
            saved_files["document1_annotated"] = str(doc1_path)
            
            # 文書2の注釈付きPDF
            doc2_path = pdfs_dir / "document2_annotated.pdf"
            self._create_single_annotated_pdf(doc2_bytes, analysis_result, doc2_path, is_doc1=False)
            saved_files["document2_annotated"] = str(doc2_path)
            
            logger.info("注釈付きPDFを作成しました")
            
        except Exception as e:
            logger.error(f"注釈付きPDF作成エラー: {e}")
        
        return saved_files
    
    def _create_single_annotated_pdf(self,
                                   pdf_bytes: bytes,
                                   analysis_result: Dict[str, Any],
                                   output_path: Path,
                                   is_doc1: bool):
        """単一文書の注釈付きPDFを作成（改良版）"""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # 差分に基づいてハイライトを追加
            differences = analysis_result.get('differences', [])
            annotations_added = 0
            annotations_skipped = 0
            
            logger.info(f"{'文書1' if is_doc1 else '文書2'}の注釈付きPDF作成開始: {len(differences)}件の差分を処理")
            
            for i, diff in enumerate(differences):
                try:
                    change_type = diff.get('change_type', '')
                    coordinates = diff.get('original_coordinates' if is_doc1 else 'modified_coordinates')
                    
                    # 座標の事前検証
                    if not coordinates or not self._validate_coordinates(coordinates):
                        logger.debug(f"差分{i+1}: 座標が無効 - スキップ")
                        annotations_skipped += 1
                        continue
                    
                    # ページ番号の検証
                    page_num = diff.get('page', 1) - 1  # 0-indexed
                    if not (0 <= page_num < len(doc)):
                        logger.debug(f"差分{i+1}: 無効なページ番号 {page_num+1} - スキップ")
                        annotations_skipped += 1
                        continue
                    
                    page = doc[page_num]
                    
                    # 注釈色を決定
                    color = self._determine_annotation_color(change_type, is_doc1)
                    if not color:
                        logger.debug(f"差分{i+1}: 注釈対象外の変更タイプ {change_type} - スキップ")
                        annotations_skipped += 1
                        continue
                    
                    # 有効な矩形を作成
                    rect = self._create_valid_rect(coordinates, page)
                    if not rect:
                        logger.debug(f"差分{i+1}: 矩形作成失敗 - スキップ")
                        annotations_skipped += 1
                        continue
                    
                    # 安全な注釈追加
                    success = self._add_safe_annotation(page, rect, color, change_type, i+1)
                    if success:
                        annotations_added += 1
                    else:
                        annotations_skipped += 1
                        
                except Exception as diff_error:
                    logger.debug(f"差分{i+1}処理エラー: {diff_error}")
                    annotations_skipped += 1
                    continue
            
            logger.info(f"注釈処理完了: 追加={annotations_added}件, スキップ={annotations_skipped}件")
            
            # PDFを保存
            doc.save(output_path)
            doc.close()
            
            if annotations_added == 0:
                logger.warning("注釈が1件も追加されませんでした")
            
        except Exception as e:
            logger.error(f"単一注釈付きPDF作成エラー: {e}")
            raise
    
    def _generate_analysis_report(self, analysis_result: Dict[str, Any], output_dir: Path) -> Optional[Path]:
        """詳細分析レポートを生成"""
        try:
            report_path = output_dir / "analysis_report.md"
            
            lines = [
                "# LLM Document Diff v3.4 詳細分析レポート",
                "",
                f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}",
                f"バージョン: {analysis_result.get('version', 'v3.4')}",
                f"分析タイプ: {analysis_result.get('analysis_type', 'structured_document_intelligence')}",
                "",
                "## エグゼクティブサマリー",
                "",
                f"本分析では、2つの文書間で{len(analysis_result.get('differences', []))}件の差分を検出しました。",
                "主な変更内容は以下の通りです：",
                ""
            ]
            
            # サマリー情報
            summary = analysis_result.get('summary', {})
            for change_type, count in summary.items():
                if count > 0:
                    lines.append(f"- {change_type}: {count}件")
            
            lines.extend([
                "",
                "## 文書構造分析",
                "",
                "### 文書1の構造",
            ])
            
            doc1_analysis = analysis_result.get('document_analysis', {}).get('document1', {})
            doc1_summary = doc1_analysis.get('summary', {})
            lines.extend([
                f"- 総セクション数: {doc1_summary.get('total_sections', 0)}",
                f"- 総パラグラフ数: {doc1_summary.get('total_paragraphs', 0)}",
                f"- コンテンツ長: {doc1_summary.get('content_length', 0)}文字",
                "",
                "### 文書2の構造",
            ])
            
            doc2_analysis = analysis_result.get('document_analysis', {}).get('document2', {})
            doc2_summary = doc2_analysis.get('summary', {})
            lines.extend([
                f"- 総セクション数: {doc2_summary.get('total_sections', 0)}",
                f"- 総パラグラフ数: {doc2_summary.get('total_paragraphs', 0)}",
                f"- コンテンツ長: {doc2_summary.get('content_length', 0)}文字",
                "",
                "## 差分詳細分析",
                "",
                "### 主要な変更点",
            ])
            
            # 上位10件の差分詳細
            for i, diff in enumerate(analysis_result.get('differences', [])[:10], 1):
                lines.extend([
                    f"#### {i}. {diff.get('change_type', 'unknown')}",
                    f"**ページ**: {diff.get('page', 'N/A')}  ",
                    f"**類似度**: {diff.get('semantic_similarity', 'N/A')}  ",
                    "",
                    f"**元テキスト**: {diff.get('original_text', 'N/A')}  ",
                    f"**新テキスト**: {diff.get('modified_text', 'N/A')}  ",
                    "",
                ])
            
            lines.extend([
                "## 推奨事項",
                "",
                "1. **高優先度の変更**: 類似度の低い変更（0.5未満）については重点的に確認することを推奨します。",
                "2. **構造的変更**: セクション構造に変更がある場合は、文書全体の整合性を確認してください。",
                "3. **継続監視**: 定期的な差分チェックを実施し、変更の累積を追跡することを推奨します。",
                "",
                "---",
                "",
                "このレポートは LLM Document Diff v3.4 によって自動生成されました。"
            ])
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            logger.info(f"詳細分析レポートを生成: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"分析レポート生成エラー: {e}")
            return None
    
    def _normalize_coordinates(self, coordinates: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """座標データを正規化してleft, top, right, bottomを返す
        
        Args:
            coordinates: 座標データ（新旧両方の形式に対応）
            
        Returns:
            正規化された座標辞書 または None
        """
        if not coordinates:
            return None
        
        coord_type = coordinates.get('type', 'legacy')
        
        # 新しいポリゴン形式の場合
        if coord_type in ['polygon', 'morpheme_polygon', 'combined_polygon']:
            # boundsが存在する場合（優先）
            if 'bounds' in coordinates:
                bounds = coordinates['bounds']
                try:
                    return {
                        'left': float(bounds.get('left', 0)),
                        'top': float(bounds.get('top', 0)),
                        'right': float(bounds.get('right', 0)),
                        'bottom': float(bounds.get('bottom', 0))
                    }
                except (ValueError, TypeError):
                    logger.debug("bounds座標の数値変換に失敗")
            
            # raw_coordinatesからboundsを計算
            elif 'raw_coordinates' in coordinates:
                raw_coords = coordinates['raw_coordinates']
                if len(raw_coords) >= 4:
                    try:
                        # ポリゴンの境界ボックスを計算
                        x_coords = [raw_coords[i] for i in range(0, len(raw_coords), 2)]
                        y_coords = [raw_coords[i] for i in range(1, len(raw_coords), 2)]
                        
                        return {
                            'left': min(x_coords),
                            'top': min(y_coords),
                            'right': max(x_coords),
                            'bottom': max(y_coords)
                        }
                    except (ValueError, TypeError, IndexError):
                        logger.debug("raw_coordinates座標の計算に失敗")
        
        # 古い形式の場合（後方互換性）
        try:
            left = float(coordinates.get('left', 0))
            top = float(coordinates.get('top', 0))
            right = coordinates.get('right')
            bottom = coordinates.get('bottom')
            
            # right, bottomがない場合はwidth, heightから計算
            if right is None and 'width' in coordinates and coordinates['width'] is not None:
                right = left + float(coordinates['width'])
            if bottom is None and 'height' in coordinates and coordinates['height'] is not None:
                bottom = top + float(coordinates['height'])
                
            if right is not None and bottom is not None:
                return {
                    'left': left,
                    'top': top,
                    'right': float(right),
                    'bottom': float(bottom)
                }
        except (ValueError, TypeError):
            logger.debug("古い形式座標の処理に失敗")
        
        logger.debug(f"座標正規化失敗: type={coord_type}, keys={coordinates.keys()}")
        return None
    
    def _get_coordinate_value(self, coordinates: Dict[str, Any], coord_key: str) -> str:
        """座標辞書から指定の座標値を安全に取得
        
        Args:
            coordinates: 座標データ
            coord_key: 取得したい座標キー（'left', 'top', 'right', 'bottom'）
            
        Returns:
            座標値の文字列、取得できない場合は空文字
        """
        if not coordinates:
            return ''
        
        normalized = self._normalize_coordinates(coordinates)
        if not normalized:
            return ''
        
        return str(normalized.get(coord_key, ''))
    
    def _validate_coordinates(self, coordinates: Dict[str, Any]) -> bool:
        """座標情報の有効性をチェック（新形式対応版）"""
        if not coordinates:
            logger.debug("座標が空です")
            return False
        
        # 座標を正規化
        normalized = self._normalize_coordinates(coordinates)
        if not normalized:
            logger.debug("座標の正規化に失敗しました")
            return False
        
        try:
            left = normalized['left']
            top = normalized['top']
            right = normalized['right']
            bottom = normalized['bottom']
            
            # 基本的な座標チェック
            if left < 0 or top < 0:
                logger.debug(f"負の座標値: left={left}, top={top}")
                return False
                
            if right <= left or bottom <= top:
                logger.debug(f"無効な座標関係: left={left}, top={top}, right={right}, bottom={bottom}")
                return False
            
            # Document Intelligence座標の妥当性チェック（インチ単位）
            max_width_inches = 20.0
            max_height_inches = 30.0
            
            if right > max_width_inches or bottom > max_height_inches:
                logger.debug(f"座標が想定範囲を超えています: right={right}, bottom={bottom}")
                return False
                
            logger.debug(f"座標検証成功: left={left}, top={top}, right={right}, bottom={bottom}")
            return True
            
        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"座標値の処理エラー: {e}")
            return False
    
    def _create_valid_rect(self, coordinates: Dict[str, Any], page) -> Optional[fitz.Rect]:
        """有効なfitz.Rectを作成（新形式対応版）"""
        try:
            # 座標を正規化
            normalized = self._normalize_coordinates(coordinates)
            if not normalized:
                logger.debug("座標の正規化に失敗しました")
                return None
            
            left = normalized['left']
            top = normalized['top']
            right = normalized['right']
            bottom = normalized['bottom']
            
            # PDFページサイズを取得
            page_width = page.rect.width  # ポイント単位
            page_height = page.rect.height  # ポイント単位
            
            # Document Intelligence座標（インチ）をPDF座標（ポイント）に変換
            # 1インチ = 72ポイント
            DPI_SCALE = 72.0
            
            pdf_left = left * DPI_SCALE
            pdf_top = top * DPI_SCALE
            pdf_right = right * DPI_SCALE
            pdf_bottom = bottom * DPI_SCALE
            
            # 座標をページサイズ内に制限
            pdf_left = max(0, min(pdf_left, page_width))
            pdf_top = max(0, min(pdf_top, page_height))
            pdf_right = max(pdf_left + 1, min(pdf_right, page_width))  # 最小1ポイント幅を保証
            pdf_bottom = max(pdf_top + 1, min(pdf_bottom, page_height))  # 最小1ポイント高を保証
            
            # デバッグログ出力
            logger.debug(f"座標変換: 元座標=({left:.3f}, {top:.3f}, {right:.3f}, {bottom:.3f}) → "
                        f"PDF座標=({pdf_left:.1f}, {pdf_top:.1f}, {pdf_right:.1f}, {pdf_bottom:.1f}) "
                        f"ページサイズ=({page_width:.1f}, {page_height:.1f})")
            
            # PyMuPDF Rectを作成
            rect = fitz.Rect(pdf_left, pdf_top, pdf_right, pdf_bottom)
            
            # 有効性チェック
            if not rect.is_valid:
                logger.warning(f"無効なRect: {rect}")
                return None
                
            # サイズチェック（極小サイズを避ける）
            if rect.width < 1 or rect.height < 1:
                logger.debug(f"極小Rect: width={rect.width}, height={rect.height}")
                return None
                
            return rect
            
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"座標変換エラー: {e}, 座標: {coordinates}")
            return None

    
    def _determine_annotation_color(self, change_type: str, is_doc1: bool) -> Optional[tuple]:
        """変更タイプに基づいて注釈色を決定"""
        change_type_upper = change_type.upper()
        
        # 削除（文書1のみ）
        if 'DELETION' in change_type_upper and is_doc1:
            return (1, 0, 0)  # 赤
        
        # 追加（文書2のみ）
        if 'ADDITION' in change_type_upper and not is_doc1:
            return (0, 1, 0)  # 緑
        
        # 変更（両方の文書）
        if 'MODIFICATION' in change_type_upper or 'CHANGE' in change_type_upper:
            return (1, 0.8, 0)  # オレンジ
        
        # その他の変更
        if any(keyword in change_type_upper for keyword in ['REPLACEMENT', 'UPDATE', 'EDIT']):
            return (1, 1, 0)  # 黄色
        
        # 該当しない場合
        return None
    
    def _add_safe_annotation(self, page, rect: fitz.Rect, color: tuple, change_type: str, diff_index: int) -> bool:
        """安全な注釈追加（PyMuPDFのbad quads entryエラーを回避）"""
        try:
            # 方法1: draw_rectを使用（最も安全）
            try:
                page.draw_rect(rect, color=color, width=2)
                logger.debug(f"差分{diff_index}: draw_rect成功")
                return True
            except Exception as rect_error:
                logger.debug(f"差分{diff_index}: draw_rect失敗 - {rect_error}")
                pass
            
            # 方法2: add_rect_annotを使用
            try:
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=color)
                annot.set_border(width=2)
                annot.update()
                logger.debug(f"差分{diff_index}: add_rect_annot成功")
                return True
            except Exception as annot_error:
                logger.debug(f"差分{diff_index}: add_rect_annot失敗 - {annot_error}")
                pass
            
            # 方法3: 塗りつぶし矩形（フォールバック）
            try:
                # より薄い色で塗りつぶし
                fill_color = tuple(c * 0.3 for c in color)  # 30%の透明度相当
                page.draw_rect(rect, color=color, fill=fill_color, width=1)
                logger.debug(f"差分{diff_index}: fill_rect成功")
                return True
            except Exception as fill_error:
                logger.debug(f"差分{diff_index}: fill_rect失敗 - {fill_error}")
                pass
            
            logger.warning(f"差分{diff_index}: 全ての注釈方法が失敗")
            return False
            
        except Exception as e:
            logger.debug(f"差分{diff_index}: 注釈追加の予期しないエラー - {e}")
            return False
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """テキストを指定長で切り詰め"""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."


if __name__ == "__main__":
    # テスト用の基本的な実行例
    handler = EnhancedOutputHandlerV34()
    print("Enhanced Output Handler v3.4 initialized successfully")