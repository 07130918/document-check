# coding: utf-8
"""
LLM文書差分検出システム v3.4 テストスクリプト
Document Intelligenceのセクション階層と座標情報を活用した高度な差分検出
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
from datetime import datetime

# プロジェクトルートをPATHに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

# 環境変数ファイルを読み込み
from dotenv import load_dotenv
load_dotenv()

from config.settings import Settings
from services.azure_service_structured import StructuredAzureService
from core.text_preprocessing import StructuredTextPreprocessorV4
from core.structured_diff_detector_v4 import StructuredDiffDetectorV4
from handlers.output_handler import OutputHandler
from handlers.enhanced_output_handler_v3_4 import EnhancedOutputHandlerV34
from performance_tracker import PerformanceTracker, get_global_tracker

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('v3_4_debug_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class LLMDocsDiffV4:
    """LLM文書差分検出システム v3.4 メインクラス"""
    
    def __init__(self, use_enhanced_output: bool = True, batch_size: int = 1, max_workers: int = None):
        """初期化

        Args:
            use_enhanced_output: 拡張出力機能を使用するか
            batch_size: ページごと処理時のバッチサイズ（1=従来通り、>1=バッチ処理）
            max_workers: 並列実行のワーカー数（None=自動設定）
        """
        self.azure_service = StructuredAzureService()
        self.preprocessor = StructuredTextPreprocessorV4()
        self.diff_detector = StructuredDiffDetectorV4()
        self.output_handler = OutputHandler()
        self.enhanced_output_handler = EnhancedOutputHandlerV34() if use_enhanced_output else None
        
        # バッチサイズとワーカー数の設定
        self.batch_size = max(1, batch_size)  # 最小値は1
        self.max_workers = max_workers  # Noneの場合は自動設定
        
        # パフォーマンストラッカーを追加
        self.tracker = PerformanceTracker()
        
        # 分割文字結合前処理器を追加
        from core.text_preprocessing import MergeSplitCharacterPreProcessor
        self.merge_processor = MergeSplitCharacterPreProcessor()
        
        # 出力ディレクトリの作成
        Settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("LLM文書差分検出システム v3.4 初期化完了")
        if use_enhanced_output:
            logger.info("拡張出力機能が有効化されています")
        if self.batch_size > 1:
            logger.info(f"バッチ処理モード: バッチサイズ={self.batch_size}")
    
    def analyze_documents(self,
                         doc1_path: str,
                         doc2_path: str,
                         pages: Optional[str] = None,
                         output_tag: str = "default",
                         use_parallel: bool = False) -> Dict[str, Any]:
        """2つの文書の差分分析を実行
        
        Args:
            doc1_path: 文書1のパス
            doc2_path: 文書2のパス
            pages: 分析対象ページ（例: "2"）
            output_tag: 出力ファイルのタグ
            
        Returns:
            分析結果
        """
        logger.info(f"差分分析開始 (v3.4)")
        logger.info(f"文書1: {doc1_path}")
        logger.info(f"文書2: {doc2_path}")
        if pages:
            logger.info(f"対象ページ: {pages}")
        
        # 1. Document Intelligence構造化分析
        logger.info("ステップ1: Document Intelligence構造化分析")
        
        with self.tracker.measure("1_document_intelligence_分析"):
            if pages is None:
                # 全ページ処理
                logger.info("全ページ処理モード")
                doc1_analysis, doc1_word_data, doc2_analysis, doc2_word_data = self._analyze_documents_parallel(
                    doc1_path, doc2_path, use_parallel=use_parallel
                )
            elif use_parallel:
                # 指定ページでも並列処理を適用
                logger.info(f"指定ページ並列処理: {pages}")
                doc1_analysis, doc1_word_data, doc2_analysis, doc2_word_data = self._analyze_documents_parallel_with_pages(
                    doc1_path, doc2_path, pages, use_parallel=use_parallel
                )
            else:
                # 従来の逐次処理：指定ページのみ
                logger.info(f"指定ページ逐次処理: {pages}")
                with self.tracker.measure("1.1_文書1_指定ページ分析"):
                    doc1_analysis, doc1_word_data = self.azure_service.analyze_document_structured(doc1_path, pages)
                with self.tracker.measure("1.2_文書2_指定ページ分析"):
                    doc2_analysis, doc2_word_data = self.azure_service.analyze_document_structured(doc2_path, pages)
        
        doc1_analysis['source_file'] = doc1_path
        doc2_analysis['source_file'] = doc2_path
        
        # 2. 分割文字結合前処理
        logger.info("ステップ2: 分割文字結合前処理")
        
        with self.tracker.measure("2_分割文字結合前処理"):
            with self.tracker.measure("2.1_文書1_分割文字結合"):
                combined_doc1_analysis = self.merge_processor.process_document_analysis(doc1_analysis)
            with self.tracker.measure("2.2_文書2_分割文字結合"):
                combined_doc2_analysis = self.merge_processor.process_document_analysis(doc2_analysis)
        
        logger.info(f"結合処理結果: 文書1={len(combined_doc1_analysis.get('sections', []))}セクション, "
                   f"文書2={len(combined_doc2_analysis.get('sections', []))}セクション")
        
        # 2.5. 文言正規化処理
        logger.info("ステップ2.5: 文言正規化処理")
        
        with self.tracker.measure("2.5_文言正規化処理"):
            with self.tracker.measure("2.5.1_文書1_テキスト正規化"):
                combined_doc1_analysis = self._normalize_document_text(combined_doc1_analysis)
            with self.tracker.measure("2.5.2_文書2_テキスト正規化"):
                combined_doc2_analysis = self._normalize_document_text(combined_doc2_analysis)
            with self.tracker.measure("2.5.3_文書1_ワードデータ正規化"):
                doc1_word_data = self._normalize_word_data(doc1_word_data)
            with self.tracker.measure("2.5.4_文書2_ワードデータ正規化"):
                doc2_word_data = self._normalize_word_data(doc2_word_data)
        
        logger.info("文言正規化処理完了")
        
        # 2.7. ページマッチング処理
        logger.info("ステップ2.7: ページマッチング処理")
        
        with self.tracker.measure("2.7_ページマッチング処理"):
            page_matches = self._match_pages_by_content(combined_doc1_analysis, combined_doc2_analysis)
            logger.info(f"ページマッチング結果: {len(page_matches)}件のマッチ")
        
        # 3. 構造化差分検出（ページマッチング結果を使用）
        logger.info("ステップ3: 構造化差分検出（ページマッチベース）")
        
        with self.tracker.measure("3_構造化差分検出"):
            differences = self._detect_differences_by_page_matches(page_matches, combined_doc1_analysis, combined_doc2_analysis, doc1_word_data, doc2_word_data)
        
        # 差分結果をCSVで保存
        with self.tracker.measure("3.1_差分CSV保存"):
            self._save_differences_csv(differences, output_tag)

        # ここでマッチセクションごとにその中のパラフラフを文言と位置の類似度に基づいて判定を行う
        
        # 4. 結果の整理と出力
        logger.info("ステップ4: 結果の整理と出力")
        
        with self.tracker.measure("4_結果整理"):
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
        
        # 結果をファイルに保存（従来の基本出力）
        with self.tracker.measure("4.1_基本結果保存"):
            self._save_results(analysis_result, output_tag)
        
        # 拡張出力を生成（有効な場合）
        if self.enhanced_output_handler:
            try:
                logger.info("拡張出力を生成します")
                with self.tracker.measure("4.2_拡張出力生成"):
                    enhanced_files = self.enhanced_output_handler.generate_enhanced_output(
                        analysis_result, output_tag, doc1_path, doc2_path
                    )
                logger.info(f"拡張出力完了: {len(enhanced_files)}個のファイルを生成")
                analysis_result["enhanced_output_files"] = enhanced_files
            except Exception as e:
                logger.error(f"拡張出力生成中にエラーが発生しましたが、処理を継続します: {e}")
        
        logger.info(f"差分分析完了: {len(differences)}個の差分を検出")
        logger.info(f"変更: {analysis_result['summary']['modifications']}, "
                   f"追加: {analysis_result['summary']['additions']}, "
                   f"削除: {analysis_result['summary']['deletions']}")
        
        # パフォーマンスサマリーを出力
        self.tracker.print_summary()
        
        # パフォーマンスレポートを保存
        performance_report_path = Settings.OUTPUT_DIR / f"performance_report_{output_tag}.json"
        self.tracker.save_to_file(performance_report_path)
        
        # ボトルネックを特定
        bottlenecks = self.tracker.get_bottlenecks(top_n=5)
        logger.info("\n=== 処理時間ボトルネック TOP5 ===")
        for i, bottleneck in enumerate(bottlenecks, 1):
            logger.info(f"{i}. {bottleneck['operation']}: {bottleneck['total_seconds']:.3f}秒 (平均: {bottleneck['average_seconds']:.3f}秒)")
        
        return analysis_result

    def _analyze_documents_parallel(self, doc1_path: str, doc2_path: str, use_parallel: bool = True) -> Tuple[Dict[str, Any], Any, Dict[str, Any], Any]:
        """2つの文書を同時に高並列で分析

        Args:
            doc1_path: 文書1のパス
            doc2_path: 文書2のパス
            use_parallel: 並列処理を使用するか

        Returns:
            (doc1_analysis, doc1_word_data, doc2_analysis, doc2_word_data)
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import fitz  # PyMuPDF

        import math

        logger.info(f"分析開始: {doc1_path}, {doc2_path}")
        logger.info(f"バッチサイズ: {self.batch_size}, 並列処理: {use_parallel}")

        # PDFのページ数を取得
        with self.tracker.measure("1.1_ページ数取得"):
            pdf1 = fitz.open(doc1_path)
            doc1_pages = len(pdf1)
            pdf1.close()

            pdf2 = fitz.open(doc2_path)
            doc2_pages = len(pdf2)
            pdf2.close()

            total_pages = doc1_pages + doc2_pages
            logger.info(f"総ページ数: 文書1={doc1_pages}, 文書2={doc2_pages}, 合計={total_pages}")

        # タスク数の計算（バッチサイズを考慮）
        doc1_tasks = math.ceil(doc1_pages / self.batch_size)
        doc2_tasks = math.ceil(doc2_pages / self.batch_size)
        total_tasks = doc1_tasks + doc2_tasks

        # ワーカー数の決定
        if self.max_workers:
            max_workers = self.max_workers
        else:
            # 自動設定: タスク数に基づいて決定（制限なし）
            max_workers = total_tasks

        logger.info(f"タスク数: 文書1={doc1_tasks}, 文書2={doc2_tasks}, 合計={total_tasks}")
        logger.info(f"ワーカー数: {max_workers}")

        # 分析タスクの定義
        def analyze_batch(doc_path, start_page, end_page, doc_id, task_id):
            """バッチ単位でページを分析"""
            start_time = time.time()
            try:
                # ページ範囲を文字列に変換
                if start_page == end_page:
                    page_str = str(start_page)
                else:
                    page_str = f"{start_page}-{end_page}"

                logger.debug(f"タスク{task_id}: 文書{doc_id} ページ{page_str}を処理開始")
                analysis, word_data = self.azure_service.analyze_document_structured(doc_path, page_str)

                # ページ番号情報を追加
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

        with self.tracker.measure("1.2_API呼び出し"):
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
        with self.tracker.measure("1.3_結果整理"):
            doc1_results.sort(key=lambda x: x[0])  # start_pageでソート
            doc2_results.sort(key=lambda x: x[0])  # start_pageでソート

            # 分析結果とワードデータを分離
            doc1_analyses = [item[2] for item in doc1_results]  # analysis
            doc1_word_data = [item[3] for item in doc1_results]  # word_data
            doc2_analyses = [item[2] for item in doc2_results]  # analysis
            doc2_word_data = [item[3] for item in doc2_results]  # word_data

            # 統合
            doc1_merged = self._merge_page_analyses(doc1_analyses)
            doc1_merged_word = self._merge_word_data(doc1_word_data)
            doc2_merged = self._merge_page_analyses(doc2_analyses)
            doc2_merged_word = self._merge_word_data(doc2_word_data)

            logger.info(f"文書1: {len(doc1_merged.get('sections', []))}セクション")
            logger.info(f"文書2: {len(doc2_merged.get('sections', []))}セクション")

        return doc1_merged, doc1_merged_word, doc2_merged, doc2_merged_word

    def _analyze_documents_parallel_with_pages(self, doc1_path: str, doc2_path: str, pages: str, use_parallel: bool = True) -> Tuple[Dict[str, Any], Any, Dict[str, Any], Any]:
        """指定ページで2つの文書を同時に高並列で分析

        Args:
            doc1_path: 文書1のパス
            doc2_path: 文書2のパス
            pages: 分析対象ページ（例: "1-10" または "1,3,5"）
            use_parallel: 並列処理を使用するか

        Returns:
            (doc1_analysis, doc1_word_data, doc2_analysis, doc2_word_data)
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import fitz  # PyMuPDF
        import math

        logger.info(f"指定ページ並列分析開始: {doc1_path}, {doc2_path}, ページ: {pages}")
        logger.info(f"バッチサイズ: {self.batch_size}, 並列処理: {use_parallel}")

        # ページ範囲を解析
        page_list = self._parse_page_range(pages)
        if not page_list:
            raise ValueError(f"無効なページ範囲: {pages}")

        # タスク数の計算（バッチサイズを考慮）
        doc1_tasks = math.ceil(len(page_list) / self.batch_size)
        doc2_tasks = math.ceil(len(page_list) / self.batch_size)
        total_tasks = doc1_tasks + doc2_tasks

        # ワーカー数の決定
        if self.max_workers:
            max_workers = self.max_workers
        else:
            max_workers = total_tasks

        logger.info(f"対象ページ数: {len(page_list)}, タスク数: 文書1={doc1_tasks}, 文書2={doc2_tasks}, 合計={total_tasks}")
        logger.info(f"ワーカー数: {max_workers}")

        # 分析タスクの定義
        def analyze_page_batch(doc_path, page_batch, doc_id, task_id):
            """ページバッチ単位で分析"""
            start_time = time.time()
            try:
                # ページ範囲を文字列に変換
                if len(page_batch) == 1:
                    page_str = str(page_batch[0])
                else:
                    page_str = f"{page_batch[0]}-{page_batch[-1]}"

                logger.debug(f"タスク{task_id}: 文書{doc_id} ページ{page_str}を処理開始")
                analysis, word_data = self.azure_service.analyze_document_structured(doc_path, page_str)

                # ページ範囲情報を追加
                analysis['page_range'] = (page_batch[0], page_batch[-1])
                analysis['pages_in_batch'] = len(page_batch)

                elapsed = time.time() - start_time
                logger.info(f"タスク{task_id}完了: 文書{doc_id} ページ{page_str} ({elapsed:.2f}秒)")
                return (doc_id, page_batch[0], page_batch[-1], analysis, word_data, elapsed)
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"タスク{task_id}エラー: 文書{doc_id} ページ{page_batch[0]}-{page_batch[-1]} ({elapsed:.2f}秒): {e}")
                empty_analysis = {
                    'sections': [],
                    'page_range': (page_batch[0], page_batch[-1]),
                    'pages_in_batch': len(page_batch),
                    'summary': {'total_sections': 0, 'total_paragraphs': 0}
                }
                return (doc_id, page_batch[0], page_batch[-1], empty_analysis, [], elapsed)

        # バッチタスクの生成
        tasks = []
        task_id = 0

        # 文書1のタスク生成
        for i in range(0, len(page_list), self.batch_size):
            page_batch = page_list[i:i + self.batch_size]
            tasks.append((doc1_path, page_batch, 1, task_id))
            task_id += 1

        # 文書2のタスク生成
        for i in range(0, len(page_list), self.batch_size):
            page_batch = page_list[i:i + self.batch_size]
            tasks.append((doc2_path, page_batch, 2, task_id))
            task_id += 1

        # 実行
        doc1_results = []
        doc2_results = []
        total_api_time = 0

        with self.tracker.measure("1.2_指定ページAPI呼び出し"):
            start_parallel = time.time()

            if use_parallel and len(tasks) > 1:
                # 並列実行
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for task in tasks:
                        future = executor.submit(analyze_page_batch, *task)
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
                    doc_id, start_page, end_page, analysis, word_data, api_time = analyze_page_batch(*task)
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
        with self.tracker.measure("1.3_指定ページ結果整理"):
            doc1_results.sort(key=lambda x: x[0])  # start_pageでソート
            doc2_results.sort(key=lambda x: x[0])  # start_pageでソート

            # 分析結果とワードデータを分離
            doc1_analyses = [item[2] for item in doc1_results]  # analysis
            doc1_word_data = [item[3] for item in doc1_results]  # word_data
            doc2_analyses = [item[2] for item in doc2_results]  # analysis
            doc2_word_data = [item[3] for item in doc2_results]  # word_data

            # 統合
            doc1_merged = self._merge_page_analyses(doc1_analyses)
            doc1_merged_word = self._merge_word_data(doc1_word_data)
            doc2_merged = self._merge_page_analyses(doc2_analyses)
            doc2_merged_word = self._merge_word_data(doc2_word_data)

            logger.info(f"文書1: {len(doc1_merged.get('sections', []))}セクション")
            logger.info(f"文書2: {len(doc2_merged.get('sections', []))}セクション")

        return doc1_merged, doc1_merged_word, doc2_merged, doc2_merged_word

    def _parse_page_range(self, pages: str) -> List[int]:
        """ページ範囲文字列を解析してページ番号のリストを返す

        Args:
            pages: ページ範囲（例: "1-10", "1,3,5", "1-5,8,10-12"）

        Returns:
            ページ番号のリスト
        """
        page_list = []

        for part in pages.split(','):
            part = part.strip()
            if '-' in part:
                # 範囲指定（例: "1-10"）
                start, end = map(int, part.split('-'))
                page_list.extend(range(start, end + 1))
            else:
                # 単一ページ（例: "5"）
                page_list.append(int(part))

        # 重複除去と昇順ソート
        return sorted(list(set(page_list)))

    def _analyze_document_by_pages(self, doc_path: str) -> Tuple[Dict[str, Any], Any]:
        """ページごとにDocument Intelligence分析を実行
        
        Args:
            doc_path: 文書のパス
            
        Returns:
            統合された分析結果とワードデータ
        """
        logger.info(f"ページごと分析開始: {doc_path}")
        
        # PDFのページ数を取得
        page_count = self._get_pdf_page_count(doc_path)
        if page_count == 0:
            raise ValueError(f"ページ数を取得できませんでした: {doc_path}")
        
        logger.info(f"総ページ数: {page_count}")
        
        # 各ページを個別またはバッチで分析
        page_analyses = []
        page_word_data = []
        
        # バッチサイズに応じて処理
        batch_size = self.batch_size
        
        if batch_size == 1:
            # 従来の1ページずつの処理
            for page_num in range(1, page_count + 1):  # 1-indexedページ番号
                logger.info(f"ページ {page_num}/{page_count} を分析中...")
                
                try:
                    # ページごとにDocument Intelligence分析を実行
                    page_str = str(page_num)
                    analysis, word_data = self.azure_service.analyze_document_structured(doc_path, page_str)
                    
                    # ページ情報を追加
                    analysis['page_number'] = page_num
                    page_analyses.append(analysis)
                    page_word_data.append(word_data)
                    
                    logger.info(f"ページ {page_num} 分析完了: "
                               f"{len(analysis.get('sections', []))}セクション")
                    
                except Exception as e:
                    logger.error(f"ページ {page_num} の分析中にエラー: {e}")
                    # エラーが発生したページは空の結果を追加
                    empty_analysis = {
                        'sections': [],
                        'page_number': page_num,
                        'summary': {'total_sections': 0, 'total_paragraphs': 0}
                    }
                    page_analyses.append(empty_analysis)
                    page_word_data.append([])  # 空のワードデータ
        else:
            # バッチ処理
            logger.info(f"バッチ処理モード: {batch_size}ページずつ処理")
            
            for batch_start in range(1, page_count + 1, batch_size):
                batch_end = min(batch_start + batch_size - 1, page_count)
                pages_range = f"{batch_start}-{batch_end}" if batch_start != batch_end else str(batch_start)
                
                logger.info(f"バッチ処理: ページ {pages_range} ({batch_end - batch_start + 1}ページ)")
                
                try:
                    batch_analysis, batch_word_data = self.azure_service.analyze_document_structured(doc_path, pages_range)
                    
                    # バッチ結果をページごとに分割
                    self._split_batch_results(
                        batch_analysis, batch_word_data,
                        batch_start, batch_end,
                        page_analyses, page_word_data
                    )
                    
                    logger.info(f"バッチ {pages_range} 分析完了")
                    
                except Exception as e:
                    logger.error(f"バッチ {pages_range} の分析中にエラー: {e}")
                    # エラー時はバッチ内の全ページを空として追加
                    for page_num in range(batch_start, batch_end + 1):
                        empty_analysis = {
                            'sections': [],
                            'page_number': page_num,
                            'summary': {'total_sections': 0, 'total_paragraphs': 0}
                        }
                        page_analyses.append(empty_analysis)
                        page_word_data.append([])
        
        # 分析結果を統合
        merged_analysis = self._merge_page_analyses(page_analyses)
        merged_word_data = self._merge_word_data(page_word_data)
        
        logger.info(f"ページごと分析完了: {doc_path}")
        logger.info(f"統合結果: {len(merged_analysis.get('sections', []))}セクション")
        
        return merged_analysis, merged_word_data

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """PDFファイルのページ数を取得
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            ページ数
        """
        try:
            from utils.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            return pdf_processor.get_page_count_from_path(pdf_path)
        except Exception as e:
            logger.error(f"PDFページ数取得エラー: {e}")
            return 0
    
    def _normalize_document_text(self, doc_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """文書分析結果のテキストを正規化
        
        Args:
            doc_analysis: 文書分析結果
            
        Returns:
            正規化後の文書分析結果
        """
        import re
        
        def normalize_text(text: str) -> str:
            """テキストを正規化"""
            if not text:
                return text
            
            # 空白の統一
            text = re.sub(r'\s+', ' ', text)  # 複数空白を1つに
            text = text.strip()
            
            # 記号の統一
            text = text.replace('·', '・')    # 中点の統一
            text = text.replace('−', '-')     # マイナス記号の統一
            text = text.replace('～', '〜')   # 波線の統一
            
            # 全角半角の統一（数字・英字）
            text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
            text = text.translate(str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
            text = text.translate(str.maketrans('ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', 'abcdefghijklmnopqrstuvwxyz'))
            
            return text
        
        # ディープコピーして元データを保持
        import copy
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
        """words_dataのテキストを正規化
        
        Args:
            word_data: 文字レベルのデータリスト
            
        Returns:
            正規化後のwords_data
        """
        import re
        import copy
        
        def normalize_text(text: str) -> str:
            """テキストを正規化"""
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
    
    def _bbox_to_coords(self, bbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """bbox形式を座標形式に変換"""
        if not bbox_data:
            return None
        
        # 元の座標情報がある場合はそれを優先
        if 'coordinates' in bbox_data and bbox_data['coordinates']:
            coords = bbox_data['coordinates']
            return {
                "left": coords.get('left', 0),
                "top": coords.get('top', 0),
                "right": coords.get('right', coords.get('left', 0) + coords.get('width', 0)),
                "bottom": coords.get('bottom', coords.get('top', 0) + coords.get('height', 0)),
                "width": coords.get('width', 0),
                "height": coords.get('height', 0)
            }
        
        # fallback: x, y, width, heightから座標を計算
        x = bbox_data.get('x', 0)
        y = bbox_data.get('y', 0)
        width = bbox_data.get('width', 0)
        height = bbox_data.get('height', 0)
        
        return {
            "left": x,
            "top": y,
            "right": x + width,
            "bottom": y + height,
            "width": width,
            "height": height
        }

    
    def _save_results(self, analysis_result: Dict[str, Any], output_tag: str):
        """分析結果をファイルに保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON形式で詳細結果を保存
        json_filename = f"llm_diff_v3_4_{output_tag}_{timestamp}.json"
        json_path = Settings.OUTPUT_DIR / json_filename
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        # CSV形式で差分リストを保存
        import csv
        csv_filename = f"llm_diff_v3_4_{output_tag}_{timestamp}.csv"
        csv_path = Settings.OUTPUT_DIR / csv_filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'change_type', 'page', 'page_doc1', 'page_doc2', 'semantic_similarity',
                'original_text', 'modified_text',
                'original_x', 'original_y', 'modified_x', 'modified_y',
                'section_title', 'paragraph_role'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for diff in analysis_result['differences']:
                writer.writerow({
                    'change_type': diff['change_type'],
                    'page': diff['page'],
                    'page_doc1': diff['page_doc1'],
                    'page_doc2': diff['page_doc2'],
                    'semantic_similarity': diff['semantic_similarity'],
                    'original_text': diff['original_text'][:100] + ('...' if len(diff['original_text']) > 100 else ''),
                    'modified_text': diff['modified_text'][:100] + ('...' if len(diff['modified_text']) > 100 else ''),
                    'original_x': diff['original_coordinates']['raw_coordinates'][0] if diff['original_coordinates'] and diff['original_coordinates'].get('raw_coordinates') else '',
                    'original_y': diff['original_coordinates']['raw_coordinates'][1] if diff['original_coordinates'] and diff['original_coordinates'].get('raw_coordinates') else '',
                    'modified_x': diff['modified_coordinates']['raw_coordinates'][0] if diff['modified_coordinates'] and diff['modified_coordinates'].get('raw_coordinates') else '',
                    'modified_y': diff['modified_coordinates']['raw_coordinates'][1] if diff['modified_coordinates'] and diff['modified_coordinates'].get('raw_coordinates') else '',
                    'section_title': diff['structural_info'].get('section_title', ''),
                    'paragraph_role': diff['structural_info'].get('paragraph_role', '')
                })
        
        logger.info(f"結果保存完了:")
        logger.info(f"  JSON: {json_path}")
        logger.info(f"  CSV: {csv_path}")

    def _save_differences_csv(self, differences: List, output_tag: str):
        """差分結果をCSVファイルに保存
        
        Args:
            differences: DiffResultのリスト
            output_tag: 出力ファイルのタグ
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"differences_{output_tag}_{timestamp}.csv"
        csv_path = Settings.OUTPUT_DIR / csv_filename
        
        import csv
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'change_type', 'page', 'page_doc1', 'page_doc2', 'semantic_similarity',
                'original_content', 'modified_content',
                'original_x', 'original_y', 'modified_x', 'modified_y',
                'paragraph_index_1', 'paragraph_index_2', 'role', 'importance',
                'original_section_title', 'modified_section_title',
                'original_para_content', 'modified_para_content'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, diff in enumerate(differences):
                # 新しい座標形式に対応した座標取得
                def get_coord_value(coords_dict, key):
                    if not coords_dict:
                        return ''
                    if 'raw_coordinates' in coords_dict and coords_dict.get('raw_coordinates'):
                        raw_coords = coords_dict['raw_coordinates']
                        if len(raw_coords) >= 8:
                            x_coords = [raw_coords[i] for i in range(0, 8, 2)]
                            y_coords = [raw_coords[i] for i in range(1, 8, 2)]
                            bounds = {
                                'left': min(x_coords), 'top': min(y_coords),
                                'right': max(x_coords), 'bottom': max(y_coords)
                            }
                            return f"{bounds.get(key, 0):.4f}"
                    elif 'bounds' in coords_dict:
                        return f"{coords_dict['bounds'].get(key, 0):.4f}"
                    return f"{coords_dict.get(key, 0):.4f}"
                
                original_coords = diff.original_bbox.get('coordinates') if diff.original_bbox else None
                modified_coords = diff.modified_bbox.get('coordinates') if diff.modified_bbox else None
                
                writer.writerow({
                    'change_type': str(diff.change_type)[11:],
                    'page': diff.page,
                    'page_doc1': diff.page_doc1,
                    'page_doc2': diff.page_doc2,
                    'semantic_similarity': f"{diff.semantic_similarity:.3f}",
                    'original_content': diff.original_bbox.get('content', '') if diff.original_bbox else '',
                    'modified_content': diff.modified_bbox.get('content', '') if diff.modified_bbox else '',
                    'original_x': get_coord_value(original_coords, 'left'),
                    'original_y': get_coord_value(original_coords, 'top'),
                    'modified_x': get_coord_value(modified_coords, 'left'),
                    'modified_y': get_coord_value(modified_coords, 'top'),
                    'paragraph_index_1': diff.original_bbox.get('paragraph_index', '') if diff.original_bbox else '',
                    'paragraph_index_2': diff.modified_bbox.get('paragraph_index', '') if diff.modified_bbox else '',
                    'role': diff.original_bbox.get('role', '') if diff.original_bbox else (diff.modified_bbox.get('role', '') if diff.modified_bbox else ''),
                    'importance': diff.original_bbox.get('importance', '') if diff.original_bbox else (diff.modified_bbox.get('importance', '') if diff.modified_bbox else ''),
                    'original_section_title': diff.original_section.get('title', '') if diff.original_section else '',
                    'modified_section_title': diff.modified_section.get('title', '') if diff.modified_section else '',
                    'original_para_content': diff.original_paragraph.get('content', '')[:200] if diff.original_paragraph else '',
                    'modified_para_content': diff.modified_paragraph.get('content', '')[:200] if diff.modified_paragraph else ''
                })
        
        logger.info(f"差分詳細CSV保存: {csv_path}")
        return csv_path

    def _match_pages_by_content(self, doc1_analysis, doc2_analysis):
        """ページ内容の類似度に基づいてページをマッチング
        
        Args:
            doc1_analysis: 文書1の解析結果
            doc2_analysis: 文書2の解析結果
            
        Returns:
            List[dict]: ページマッチング結果
        """
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
        with self.tracker.measure("ページ類似度計算"):
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
        
        # マッチしなかったページの処理も追加可能
        # TODO: アンマッチページの全セクションを追加/削除として処理
        
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

    def _split_batch_results(self, batch_analysis, batch_word_data, 
                            batch_start, batch_end, 
                            page_analyses, page_word_data):
        """バッチ分析結果をページごとに分割
        
        Args:
            batch_analysis: バッチ分析結果
            batch_word_data: バッチのワードデータ
            batch_start: バッチ開始ページ番号
            batch_end: バッチ終了ページ番号
            page_analyses: ページごとの分析結果リスト（追加先）
            page_word_data: ページごとのワードデータリスト（追加先）
        """
        # バッチ内のセクションをページごとにグループ化
        sections_by_page = {}
        for section in batch_analysis.get('sections', []):
            page_num = section.get('page', batch_start)  # ページ番号を取得
            if page_num not in sections_by_page:
                sections_by_page[page_num] = []
            sections_by_page[page_num].append(section)
        
        # バッチ内のワードデータをページごとに分割
        words_by_page = {}
        if isinstance(batch_word_data, list):
            for page_data in batch_word_data:
                if isinstance(page_data, dict) and 'page' in page_data:
                    page_num = page_data['page']
                    words_by_page[page_num] = page_data
        
        # 各ページの結果を作成
        for page_num in range(batch_start, batch_end + 1):
            # ページごとの分析結果
            page_analysis = {
                'sections': sections_by_page.get(page_num, []),
                'page_number': page_num,
                'summary': {
                    'total_sections': len(sections_by_page.get(page_num, [])),
                    'total_paragraphs': sum(
                        len(s.get('paragraphs', [])) 
                        for s in sections_by_page.get(page_num, [])
                    )
                }
            }
            
            # バッチ分析の他の属性を継承
            for key in batch_analysis:
                if key not in ['sections', 'page_number', 'summary']:
                    page_analysis[key] = batch_analysis[key]
            
            page_analyses.append(page_analysis)
            
            # ワードデータ
            page_word = words_by_page.get(page_num, [])
            page_word_data.append(page_word)
    
    def _merge_page_analyses(self, page_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """複数ページの分析結果を統合
        
        Args:
            page_analyses: 各ページの分析結果リスト
            
        Returns:
            統合された分析結果
        """
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
        """複数ページのワードデータを統合
        
        Args:
            page_word_data: 各ページのワードデータリスト
            
        Returns:
            統合されたワードデータ
        """
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


def main():
    """メイン処理"""
    print("=== LLM文書差分検出システム v3.4 ===")
    print("Document Intelligenceのセクション階層と座標情報を活用")
    
    # テスト用のファイルパス
    doc1_path = "ms/data/sample2/サンプル②2024.pdf"
    doc2_path = "ms/data/sample2/サンプル②2025.pdf"

    # コマンドライン引数の設定
    import argparse
    parser = argparse.ArgumentParser(description='LLM文書差分検出システム v3.4')
    parser.add_argument('--batch-size', type=int, default=2,
                       help='1回のAPI呼び出しで処理するページ数（デフォルト: 1）')
    parser.add_argument('--workers', type=int, default=10,
                       help='並列実行のワーカー数（デフォルト: 自動設定）')
    parser.add_argument('--pages', type=str, default="1-20",
                       help='分析対象ページ（例: "1-10" または "1,3,5"）')
    parser.add_argument('--parallel', default=True,
                       help='並列処理を有効化（2つの文書を同時処理）')
    args = parser.parse_args()
    
    # 処理モードの情報を表示
    print(f"\n=== 処理設定 ===")
    print(f"バッチサイズ: {args.batch_size}ページ/API呼び出し")
    if args.workers:
        print(f"ワーカー数: {args.workers}")
    else:
        print(f"ワーカー数: 自動設定")
    print(f"並列処理: {'有効' if args.parallel else '無効'}")

    if args.batch_size > 1:
        estimated_reduction = (1 - 1/args.batch_size) * 100
        print(f"予想API呼び出し削減率: 約{estimated_reduction:.0f}%")

    # システムの初期化
    system = LLMDocsDiffV4(batch_size=args.batch_size, max_workers=args.workers)
    
    try:
        # ページを分析
        result = system.analyze_documents(
            doc1_path=doc1_path,
            doc2_path=doc2_path,
            pages=args.pages,  # 指定ページまたは全ページ
            output_tag=f"batch{args.batch_size}_workers{args.workers}_pages{args.pages or 'all'}",
            use_parallel=args.parallel
        )
        
        print(f"\n=== 分析結果サマリー ===")
        print(f"総差分数: {result['summary']['total_differences']}")
        print(f"変更: {result['summary']['modifications']}")
        print(f"追加: {result['summary']['additions']}")
        print(f"削除: {result['summary']['deletions']}")
        
        # 主要な変更を表示
        print(f"\n=== 主要な変更（上位5件） ===")
        for i, diff in enumerate(result['differences'][:5]):
            print(f"{i+1}. {diff['change_type']}")
            print(f"   類似度: {diff['semantic_similarity']:.3f}")
            if diff['original_text']:
                print(f"   元: {diff['original_text'][:80]}...")
            if diff['modified_text']:
                print(f"   新: {diff['modified_text'][:80]}...")
            print()
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    main()