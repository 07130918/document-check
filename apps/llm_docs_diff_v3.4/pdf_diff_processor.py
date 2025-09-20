"""
PDF差分検出プロセッサ - API用インプロセス実装
"""
import sys
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
from datetime import datetime
from contextlib import contextmanager
import io

# プロジェクトルートをPATHに追加
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(current_dir))

from dotenv import load_dotenv
load_dotenv()

from config.settings import Settings
from services.azure_service_structured import StructuredAzureService
from core.text_preprocessing import StructuredTextPreprocessorV4
from core.structured_diff_detector_v4 import StructuredDiffDetectorV4
from handlers.output_handler import OutputHandler
from handlers.enhanced_output_handler_v3_4 import EnhancedOutputHandlerV34
from core.text_preprocessing import MergeSplitCharacterPreProcessor

logger = logging.getLogger(__name__)


class PDFDiffProcessor:
    """API用PDF差分検出プロセッサ"""

    def __init__(self, use_enhanced_output: bool = True, batch_size: int = 1, max_workers: int = None):
        """初期化

        Args:
            use_enhanced_output: 拡張出力機能を使用するか
            batch_size: ページごと処理時のバッチサイズ
            max_workers: 並列実行のワーカー数
        """
        self.azure_service = StructuredAzureService()
        self.preprocessor = StructuredTextPreprocessorV4()
        self.diff_detector = StructuredDiffDetectorV4()
        self.output_handler = OutputHandler()
        self.enhanced_output_handler = EnhancedOutputHandlerV34() if use_enhanced_output else None

        self.batch_size = max(1, batch_size)
        self.max_workers = max_workers

        self.merge_processor = MergeSplitCharacterPreProcessor()

        logger.info("PDF差分検出プロセッサ初期化完了")

    @contextmanager
    def _temp_pdf_files(self, pdf1_bytes: bytes, pdf2_bytes: bytes,
                       filename1: str = "document1.pdf", filename2: str = "document2.pdf"):
        """PDFバイナリデータを一時ファイルとして保存

        Args:
            pdf1_bytes: PDF1のバイナリデータ
            pdf2_bytes: PDF2のバイナリデータ
            filename1: PDF1のファイル名
            filename2: PDF2のファイル名

        Yields:
            Tuple[Path, Path]: 一時ファイルのパス
        """
        temp_dir = None
        try:
            # セキュアな一時ディレクトリを作成
            temp_dir = tempfile.mkdtemp(prefix="pdf_diff_")
            temp_path = Path(temp_dir)

            # PDFファイルを保存
            pdf1_path = temp_path / filename1
            pdf2_path = temp_path / filename2

            with open(pdf1_path, 'wb') as f:
                f.write(pdf1_bytes)
            with open(pdf2_path, 'wb') as f:
                f.write(pdf2_bytes)

            logger.info(f"一時PDFファイル作成: {pdf1_path}, {pdf2_path}")

            yield pdf1_path, pdf2_path

        finally:
            # 一時ファイルを削除
            if temp_dir:
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"一時ディレクトリ削除: {temp_dir}")
                except Exception as e:
                    logger.error(f"一時ディレクトリ削除エラー: {e}")

    def process_pdf_bytes(self,
                         pdf1_bytes: bytes,
                         pdf2_bytes: bytes,
                         filename1: str = "document1.pdf",
                         filename2: str = "document2.pdf",
                         pages: Optional[str] = None,
                         output_tag: str = "api_request") -> Dict[str, Any]:
        """PDFバイナリデータから差分検出を実行

        Args:
            pdf1_bytes: PDF1のバイナリデータ
            pdf2_bytes: PDF2のバイナリデータ
            filename1: PDF1のファイル名
            filename2: PDF2のファイル名
            pages: 分析対象ページ
            output_tag: 出力ファイルのタグ

        Returns:
            差分検出結果（注釈付きPDFのバイナリデータを含む）
        """
        logger.info("PDF差分検出処理開始")

        with self._temp_pdf_files(pdf1_bytes, pdf2_bytes, filename1, filename2) as (pdf1_path, pdf2_path):
            # 既存のロジックを使用して差分検出実行
            analysis_result = self._analyze_documents_internal(
                str(pdf1_path), str(pdf2_path), pages, output_tag
            )

            # 注釈付きPDFの生成とバイナリデータ取得
            annotated_pdfs = self._generate_annotated_pdfs(analysis_result, pdf1_path, pdf2_path)

            # 結果にバイナリデータを追加
            analysis_result["annotated_pdfs"] = annotated_pdfs

            logger.info("PDF差分検出処理完了")
            return analysis_result

    def _analyze_documents_internal(self,
                                  doc1_path: str,
                                  doc2_path: str,
                                  pages: Optional[str] = None,
                                  output_tag: str = "api_request") -> Dict[str, Any]:
        """内部用文書分析メソッド（test_llm_diff_v3_4.pyのロジックから移植）"""
        logger.info(f"差分分析開始")
        logger.info(f"文書1: {doc1_path}")
        logger.info(f"文書2: {doc2_path}")
        if pages:
            logger.info(f"対象ページ: {pages}")

        # 1. Document Intelligence構造化分析
        logger.info("ステップ1: Document Intelligence構造化分析")

        if pages is None:
            # 全ページ処理
            logger.info("全ページ処理モード")
            doc1_analysis, doc1_word_data, doc2_analysis, doc2_word_data = self._analyze_documents_parallel(
                doc1_path, doc2_path, use_parallel=True
            )
        else:
            # 指定ページのみ
            logger.info(f"指定ページ処理: {pages}")
            doc1_analysis, doc1_word_data = self.azure_service.analyze_document_structured(doc1_path, pages)
            doc2_analysis, doc2_word_data = self.azure_service.analyze_document_structured(doc2_path, pages)

        doc1_analysis['source_file'] = doc1_path
        doc2_analysis['source_file'] = doc2_path

        # 2. 分割文字結合前処理
        logger.info("ステップ2: 分割文字結合前処理")
        combined_doc1_analysis = self.merge_processor.process_document_analysis(doc1_analysis)
        combined_doc2_analysis = self.merge_processor.process_document_analysis(doc2_analysis)

        logger.info(f"結合処理結果: 文書1={len(combined_doc1_analysis.get('sections', []))}セクション, "
                   f"文書2={len(combined_doc2_analysis.get('sections', []))}セクション")

        # 2.5. 文言正規化処理
        logger.info("ステップ2.5: 文言正規化処理")
        combined_doc1_analysis = self._normalize_document_text(combined_doc1_analysis)
        combined_doc2_analysis = self._normalize_document_text(combined_doc2_analysis)
        doc1_word_data = self._normalize_word_data(doc1_word_data)
        doc2_word_data = self._normalize_word_data(doc2_word_data)

        logger.info("文言正規化処理完了")

        # 2.7. ページマッチング処理
        logger.info("ステップ2.7: ページマッチング処理")
        page_matches = self._match_pages_by_content(combined_doc1_analysis, combined_doc2_analysis)
        logger.info(f"ページマッチング結果: {len(page_matches)}件のマッチ")

        # 3. 構造化差分検出
        logger.info("ステップ3: 構造化差分検出（ページマッチベース）")
        differences = self._detect_differences_by_page_matches(
            page_matches, combined_doc1_analysis, combined_doc2_analysis, doc1_word_data, doc2_word_data
        )

        # 4. 結果の整理
        logger.info("ステップ4: 結果の整理")
        analysis_result = {
            "version": "v3.4",
            "analysis_type": "structured_document_intelligence",
            "timestamp": datetime.now().isoformat(),
            "input_files": {
                "document1": doc1_path,
                "document2": doc2_path,
                "pages": pages
            },
            "document_analysis": {
                "document1": combined_doc1_analysis,
                "document2": combined_doc2_analysis
            },
            "differences": [
                {
                    "change_type": str(diff.change_type),
                    "page": diff.page,
                    "page_doc1": diff.page_doc1,
                    "page_doc2": diff.page_doc2,
                    "semantic_similarity": diff.semantic_similarity,
                    "original_text": diff.original_bbox.get('content', '') if diff.original_bbox else '',
                    "modified_text": diff.modified_bbox.get('content', '') if diff.modified_bbox else '',
                    "original_coordinates": diff.original_bbox.get('coordinates') if diff.original_bbox else None,
                    "modified_coordinates": diff.modified_bbox.get('coordinates') if diff.modified_bbox else None,
                    "structural_info": getattr(diff, 'structural_info', {})
                }
                for diff in differences
            ],
            "summary": {
                "total_differences": len(differences),
                "modifications": len([d for d in differences if d.change_type.name == 'MODIFICATION']),
                "additions": len([d for d in differences if d.change_type.name == 'ADDITION']),
                "deletions": len([d for d in differences if d.change_type.name == 'DELETION'])
            }
        }

        logger.info(f"差分分析完了: {len(differences)}個の差分を検出")
        logger.info(f"変更: {analysis_result['summary']['modifications']}, "
                   f"追加: {analysis_result['summary']['additions']}, "
                   f"削除: {analysis_result['summary']['deletions']}")

        return analysis_result

    def _generate_annotated_pdfs(self, analysis_result: Dict[str, Any],
                               pdf1_path: Path, pdf2_path: Path) -> Dict[str, bytes]:
        """注釈付きPDFを生成してバイナリデータで返却

        Args:
            analysis_result: 差分分析結果
            pdf1_path: PDF1のパス
            pdf2_path: PDF2のパス

        Returns:
            注釈付きPDFのバイナリデータ辞書
        """
        logger.info("注釈付きPDF生成開始")

        annotated_pdfs = {}

        try:
            if self.enhanced_output_handler:
                # 拡張出力ハンドラーを使用
                with tempfile.TemporaryDirectory(prefix="pdf_output_") as temp_output_dir:
                    temp_output_path = Path(temp_output_dir)

                    # 一時的な出力ディレクトリを設定
                    original_output_dir = Settings.OUTPUT_DIR
                    Settings.OUTPUT_DIR = temp_output_path

                    try:
                        # 拡張出力を生成
                        enhanced_files = self.enhanced_output_handler.generate_enhanced_output(
                            analysis_result, "api_output", str(pdf1_path), str(pdf2_path)
                        )

                        # 生成されたPDFファイルをバイナリデータとして読み込み
                        for key, file_path in enhanced_files.items():
                            if not file_path:
                                continue
                            file_path_obj = Path(file_path)
                            if file_path_obj.exists() and file_path_obj.suffix.lower() == '.pdf':
                                with open(file_path_obj, 'rb') as f:
                                    file_data = f.read()

                                # キーに基づいて分類
                                if 'document1_annotated' in key:
                                    annotated_pdfs['document1'] = file_data
                                    logger.info(f"document1 PDFを読み込み: {len(file_data)}バイト")
                                elif 'document2_annotated' in key:
                                    annotated_pdfs['document2'] = file_data
                                    logger.info(f"document2 PDFを読み込み: {len(file_data)}バイト")
                                elif 'side_by_side_comparison' in key:
                                    annotated_pdfs['comparison'] = file_data
                                    logger.info(f"comparison PDFを読み込み: {len(file_data)}バイト")

                        logger.info(f"注釈付きPDF生成完了: {len(annotated_pdfs)}個のPDF")

                    finally:
                        # 出力ディレクトリを元に戻す
                        Settings.OUTPUT_DIR = original_output_dir

            else:
                # 基本的な注釈付きPDF生成（fallback）
                logger.warning("拡張出力ハンドラーが無効のため、基本出力を使用")
                # 元のPDFファイルをそのまま返却
                with open(pdf1_path, 'rb') as f:
                    annotated_pdfs['document1'] = f.read()
                with open(pdf2_path, 'rb') as f:
                    annotated_pdfs['document2'] = f.read()

        except Exception as e:
            logger.error(f"注釈付きPDF生成エラー: {e}")
            # エラー時は元のPDFファイルを返却
            with open(pdf1_path, 'rb') as f:
                annotated_pdfs['document1'] = f.read()
            with open(pdf2_path, 'rb') as f:
                annotated_pdfs['document2'] = f.read()

        return annotated_pdfs

    def create_zip_response(self, analysis_result: Dict[str, Any],
                          filename1: str = "document1.pdf",
                          filename2: str = "document2.pdf") -> bytes:
        """分析結果をZIPファイルとして作成

        Args:
            analysis_result: 差分分析結果
            filename1: PDF1のオリジナルファイル名
            filename2: PDF2のオリジナルファイル名

        Returns:
            ZIPファイルのバイナリデータ
        """
        logger.info("ZIPレスポンス作成開始")

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 注釈付きPDFを追加
            annotated_pdfs = analysis_result.get('annotated_pdfs', {})

            # document1, document2というシンプルな名前で保存
            if 'document1' in annotated_pdfs:
                zip_file.writestr("document1.pdf", annotated_pdfs['document1'])
                logger.info(f"document1.pdfをZIPに追加: {len(annotated_pdfs['document1'])}バイト")

            if 'document2' in annotated_pdfs:
                zip_file.writestr("document2.pdf", annotated_pdfs['document2'])
                logger.info(f"document2.pdfをZIPに追加: {len(annotated_pdfs['document2'])}バイト")

            if 'comparison' in annotated_pdfs:
                zip_file.writestr("side_by_side_comparison.pdf", annotated_pdfs['comparison'])

            # 差分結果JSONを追加
            result_json = {
                "version": analysis_result.get("version"),
                "timestamp": analysis_result.get("timestamp"),
                "summary": analysis_result.get("summary"),
                "differences": analysis_result.get("differences", [])
            }

            zip_file.writestr("diff_result.json",
                            json.dumps(result_json, ensure_ascii=False, indent=2))

        zip_data = zip_buffer.getvalue()
        logger.info(f"ZIPレスポンス作成完了: {len(zip_data)}バイト")

        return zip_data

    # 以下、既存のtest_llm_diff_v3_4.pyから必要なメソッドを移植

    def _analyze_documents_parallel(self, doc1_path: str, doc2_path: str, use_parallel: bool = True):
        """並列文書分析（既存ロジックから移植）"""
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import fitz
        import math

        logger.info(f"分析開始: {doc1_path}, {doc2_path}")
        logger.info(f"バッチサイズ: {self.batch_size}, 並列処理: {use_parallel}")

        # PDFのページ数を取得
        pdf1 = fitz.open(doc1_path)
        doc1_pages = len(pdf1)
        pdf1.close()

        pdf2 = fitz.open(doc2_path)
        doc2_pages = len(pdf2)
        pdf2.close()

        total_pages = doc1_pages + doc2_pages
        logger.info(f"総ページ数: 文書1={doc1_pages}, 文書2={doc2_pages}, 合計={total_pages}")

        # タスク数の計算
        doc1_tasks = math.ceil(doc1_pages / self.batch_size)
        doc2_tasks = math.ceil(doc2_pages / self.batch_size)
        total_tasks = doc1_tasks + doc2_tasks

        # ワーカー数の決定
        if self.max_workers:
            max_workers = self.max_workers
        else:
            max_workers = total_tasks

        logger.info(f"タスク数: 文書1={doc1_tasks}, 文書2={doc2_tasks}, 合計={total_tasks}")
        logger.info(f"ワーカー数: {max_workers}")

        # 分析タスクの定義
        def analyze_batch(doc_path, start_page, end_page, doc_id, task_id):
            start_time = time.time()
            try:
                if start_page == end_page:
                    page_str = str(start_page)
                else:
                    page_str = f"{start_page}-{end_page}"

                logger.debug(f"タスク{task_id}: 文書{doc_id} ページ{page_str}を処理開始")
                analysis, word_data = self.azure_service.analyze_document_structured(doc_path, page_str)

                analysis['page_range'] = (start_page, end_page)
                analysis['pages_in_batch'] = end_page - start_page + 1

                elapsed = time.time() - start_time
                logger.info(f"タスク{task_id}完了: 文書{doc_id} ページ{page_str} ({elapsed:.2f}秒)")
                return (doc_id, start_page, end_page, analysis, word_data, elapsed)
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"タスク{task_id}エラー: 文書{doc_id} ページ{start_page}-{end_page} ({elapsed:.2f}秒): {e}")
                empty_analysis = {
                    'sections': [],
                    'page_range': (start_page, end_page),
                    'pages_in_batch': end_page - start_page + 1,
                    'summary': {'total_sections': 0, 'total_paragraphs': 0}
                }
                return (doc_id, start_page, end_page, empty_analysis, [], elapsed)

        # バッチタスクの生成
        tasks = []
        task_id = 0

        # 文書1のタスク生成
        for start_page in range(1, doc1_pages + 1, self.batch_size):
            end_page = min(start_page + self.batch_size - 1, doc1_pages)
            tasks.append((doc1_path, start_page, end_page, 1, task_id))
            task_id += 1

        # 文書2のタスク生成
        for start_page in range(1, doc2_pages + 1, self.batch_size):
            end_page = min(start_page + self.batch_size - 1, doc2_pages)
            tasks.append((doc2_path, start_page, end_page, 2, task_id))
            task_id += 1

        # 実行
        doc1_results = []
        doc2_results = []
        total_api_time = 0

        start_parallel = time.time()

        if use_parallel and len(tasks) > 1:
            # 並列実行
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for task in tasks:
                    future = executor.submit(analyze_batch, *task)
                    futures.append(future)

                logger.info(f"{len(futures)}タスクを{max_workers}ワーカーで並列実行開始")

                # 結果を収集
                completed = 0
                for future in as_completed(futures):
                    doc_id, start_page, end_page, analysis, word_data, api_time = future.result()
                    total_api_time += api_time

                    if doc_id == 1:
                        doc1_results.append((start_page, end_page, analysis, word_data))
                    else:
                        doc2_results.append((start_page, end_page, analysis, word_data))

                    completed += 1
                    elapsed = time.time() - start_parallel
                    if completed % 5 == 0 or completed == len(futures):
                        logger.info(f"進捗: {completed}/{len(futures)}タスク完了 ({elapsed:.1f}秒経過)")
        else:
            # 逐次実行
            logger.info(f"{len(tasks)}タスクを逐次実行")
            for task in tasks:
                doc_id, start_page, end_page, analysis, word_data, api_time = analyze_batch(*task)
                total_api_time += api_time

                if doc_id == 1:
                    doc1_results.append((start_page, end_page, analysis, word_data))
                else:
                    doc2_results.append((start_page, end_page, analysis, word_data))

        elapsed = time.time() - start_parallel
        if use_parallel and len(tasks) > 1:
            logger.info(f"並列処理完了: {elapsed:.2f}秒 (API合計: {total_api_time:.2f}秒)")
            logger.info(f"並列化効率: {total_api_time/elapsed:.2f}x")
        else:
            logger.info(f"処理完了: {elapsed:.2f}秒")

        # ページ番号順にソート
        doc1_results.sort(key=lambda x: x[0])
        doc2_results.sort(key=lambda x: x[0])

        # 分析結果とワードデータを分離
        doc1_analyses = [item[2] for item in doc1_results]
        doc1_word_data = [item[3] for item in doc1_results]
        doc2_analyses = [item[2] for item in doc2_results]
        doc2_word_data = [item[3] for item in doc2_results]

        # 統合
        doc1_merged = self._merge_page_analyses(doc1_analyses)
        doc1_merged_word = self._merge_word_data(doc1_word_data)
        doc2_merged = self._merge_page_analyses(doc2_analyses)
        doc2_merged_word = self._merge_word_data(doc2_word_data)

        logger.info(f"文書1: {len(doc1_merged.get('sections', []))}セクション")
        logger.info(f"文書2: {len(doc2_merged.get('sections', []))}セクション")

        return doc1_merged, doc1_merged_word, doc2_merged, doc2_merged_word

    def _normalize_document_text(self, doc_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """文書分析結果のテキストを正規化"""
        import re
        import copy

        def normalize_text(text: str) -> str:
            if not text:
                return text

            # 空白の統一
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            # 記号の統一
            text = text.replace('·', '・')
            text = text.replace('−', '-')
            text = text.replace('～', '〜')

            # 全角半角の統一（数字・英字）
            text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
            text = text.translate(str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
            text = text.translate(str.maketrans('ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', 'abcdefghijklmnopqrstuvwxyz'))

            return text

        # ディープコピーして元データを保持
        normalized_analysis = copy.deepcopy(doc_analysis)

        # セクション内の段落テキストを正規化
        for section in normalized_analysis.get('sections', []):
            for paragraph in section.get('paragraphs', []):
                if 'content' in paragraph:
                    paragraph['content'] = normalize_text(paragraph['content'])

            # para_contents_listも正規化
            if 'para_contents_list' in section:
                section['para_contents_list'] = [
                    normalize_text(content) for content in section['para_contents_list']
                ]

        logger.debug("文書テキスト正規化完了")
        return normalized_analysis

    def _normalize_word_data(self, word_data: List[Dict]) -> List[Dict]:
        """words_dataのテキストを正規化"""
        import re
        import copy

        def normalize_text(text: str) -> str:
            if not text:
                return text

            # 記号の統一
            text = text.replace('·', '・')
            text = text.replace('−', '-')
            text = text.replace('～', '〜')

            # 全角半角の統一
            text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
            text = text.translate(str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
            text = text.translate(str.maketrans('ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', 'abcdefghijklmnopqrstuvwxyz'))

            return text

        # ディープコピーして元データを保持
        normalized_word_data = copy.deepcopy(word_data)

        # 各ページのwords内のcontentを正規化
        for page_data in normalized_word_data:
            if 'words' in page_data:
                for word in page_data['words']:
                    if 'content' in word:
                        word['content'] = normalize_text(word['content'])

        logger.debug("words_data正規化完了")
        return normalized_word_data

    def _match_pages_by_content(self, doc1_analysis, doc2_analysis):
        """ページ内容の類似度に基づいてページをマッチング"""
        doc1_sections = doc1_analysis.get('sections', [])
        doc2_sections = doc2_analysis.get('sections', [])

        # ページごとにセクションをグループ化
        doc1_pages = self._group_sections_by_page(doc1_sections)
        doc2_pages = self._group_sections_by_page(doc2_sections)

        logger.info(f"ページグループ化結果: 文書1={len(doc1_pages)}ページ, 文書2={len(doc2_pages)}ページ")

        page_matches = []

        # 各ページの内容を結合してテキスト化
        doc1_page_contents = {}
        for page_num, sections in doc1_pages.items():
            content = self._extract_page_content(sections)
            doc1_page_contents[page_num] = content

        doc2_page_contents = {}
        for page_num, sections in doc2_pages.items():
            content = self._extract_page_content(sections)
            doc2_page_contents[page_num] = content

        # 全組み合わせでページ内容の類似度を計算
        matches = []
        for page1, content1 in doc1_page_contents.items():
            for page2, content2 in doc2_page_contents.items():
                if not content1 or not content2:
                    continue

                similarity = self._calculate_content_similarity(content1, content2)
                if similarity >= 0.3:  # ページマッチングは低い閾値を使用
                    matches.append((page1, page2, similarity))

        # 類似度でソートして最適なマッチングを選択
        matches.sort(key=lambda x: x[2], reverse=True)

        # 1対1対応でマッチング
        used_pages1 = set()
        used_pages2 = set()

        for page1, page2, similarity in matches:
            if page1 not in used_pages1 and page2 not in used_pages2:
                page_match = {
                    'doc1_page': page1,
                    'doc2_page': page2,
                    'similarity': similarity,
                    'doc1_sections': doc1_pages[page1],
                    'doc2_sections': doc2_pages[page2]
                }
                page_matches.append(page_match)
                used_pages1.add(page1)
                used_pages2.add(page2)

                logger.info(f"ページマッチ: {page1} ↔ {page2} (類似度: {similarity:.3f})")

        # マッチしなかったページをログ出力
        unmatched_pages1 = set(doc1_pages.keys()) - used_pages1
        unmatched_pages2 = set(doc2_pages.keys()) - used_pages2

        if unmatched_pages1:
            logger.info(f"文書1のアンマッチページ: {sorted(unmatched_pages1)}")
        if unmatched_pages2:
            logger.info(f"文書2のアンマッチページ: {sorted(unmatched_pages2)}")

        return page_matches

    def _group_sections_by_page(self, sections):
        """セクションをページ番号でグループ化"""
        pages = {}
        for section in sections:
            page_num = section.get('page', 1)
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(section)
        return pages

    def _extract_page_content(self, sections):
        """ページ内の全セクションから内容を抽出"""
        all_content = []
        for section in sections:
            paragraphs = section.get('paragraphs', [])
            for para in paragraphs:
                content = para.get('content', '').strip()
                if content:
                    all_content.append(content)
        return ' '.join(all_content)

    def _detect_differences_by_page_matches(self, page_matches, doc1_analysis, doc2_analysis, doc1_word_data, doc2_word_data):
        """ページマッチング結果を使用して差分検出"""
        all_differences = []

        for page_match in page_matches:
            doc1_page_sections = page_match['doc1_sections']
            doc2_page_sections = page_match['doc2_sections']

            logger.info(f"ページ{page_match['doc1_page']}↔{page_match['doc2_page']}の差分検出開始")

            # ページ内セクションのみを含む一時的な解析結果を作成
            temp_doc1_analysis = {
                'sections': doc1_page_sections,
                'source_file': doc1_analysis.get('source_file', '')
            }
            temp_doc2_analysis = {
                'sections': doc2_page_sections,
                'source_file': doc2_analysis.get('source_file', '')
            }

            # このページペアでの差分検出
            page_differences = self.diff_detector.detect_easy_differences(
                temp_doc1_analysis, temp_doc2_analysis, doc1_word_data, doc2_word_data
            )

            logger.info(f"ページ{page_match['doc1_page']}↔{page_match['doc2_page']}: {len(page_differences)}件の差分")
            all_differences.extend(page_differences)

        return all_differences

    def _calculate_content_similarity(self, text1, text2):
        """コンテンツの類似度を計算（数値差分を無視）"""
        import difflib

        # 数値を除去したテキストで類似度計算
        text1_without_numbers = self._remove_numbers_from_text(text1)
        text2_without_numbers = self._remove_numbers_from_text(text2)

        # 数値除去後のテキストが空でない場合は、数値を除外した類似度を使用
        if text1_without_numbers.strip() and text2_without_numbers.strip():
            return difflib.SequenceMatcher(None, text1_without_numbers, text2_without_numbers).ratio()
        else:
            # 数値のみのテキストの場合は、元のテキストで比較
            return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _remove_numbers_from_text(self, text):
        """テキストから数値を除去"""
        import re

        if not text:
            return text

        # 全ての数字を「NUM」に置換
        cleaned_text = re.sub(r'\d+', 'NUM', text)

        # 連続する空白を単一の空白に変換
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)

        return cleaned_text.strip()

    def _merge_page_analyses(self, page_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """複数ページの分析結果を統合"""
        if not page_analyses:
            return {
                'sections': [],
                'summary': {'total_sections': 0, 'total_paragraphs': 0}
            }

        # 全セクションを統合
        all_sections = []
        total_paragraphs = 0

        for page_analysis in page_analyses:
            sections = page_analysis.get('sections', [])
            for section in sections:
                # セクションにページ番号を追加
                section['source_page'] = page_analysis.get('page_number', 1)
                all_sections.append(section)

                # パラグラフ数をカウント
                total_paragraphs += len(section.get('paragraphs', []))

        # 統合された結果を作成
        merged_result = {
            'sections': all_sections,
            'summary': {
                'total_sections': len(all_sections),
                'total_paragraphs': total_paragraphs
            }
        }

        # 最初のページの他の情報を継承
        if page_analyses:
            first_page = page_analyses[0]
            for key, value in first_page.items():
                if key not in ['sections', 'summary', 'page_number']:
                    merged_result[key] = value

        logger.info(f"ページ分析統合完了: {len(all_sections)}セクション, {total_paragraphs}パラグラフ")
        return merged_result

    def _merge_word_data(self, page_word_data: List[Any]) -> List[Any]:
        """複数ページのワードデータを統合"""
        if not page_word_data:
            return []

        # 全ページのワードデータを統合
        merged_words = []

        for page_data in page_word_data:
            if page_data:  # 空でない場合のみ追加
                if isinstance(page_data, list):
                    merged_words.extend(page_data)
                else:
                    merged_words.append(page_data)

        logger.info(f"ワードデータ統合完了: {len(merged_words)}ページ分")
        return merged_words
