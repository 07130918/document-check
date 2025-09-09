"""
LLM Document Difference Detection Test v3.3
前処理改善版 + 高度差分検出器のテストスクリプト
"""
import sys
import os
from pathlib import Path
import argparse
import logging
import json
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# v3.3用のインポート（前処理改善版 + 高度差分検出器）
from apps.llm_docs_diff_v3.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from apps.llm_docs_diff_v3_3.core.text_preprocessing import TextPreprocessorV3_1  # v3.1前処理クラス（改善版）
from apps.llm_docs_diff_v3.core.reading_order_v2 import ReadingOrderEstimatorV2
from apps.llm_docs_diff_v3.core.diff_detector_v3 import ContentBasedDiffDetector  # 高度差分検出器を使用
from apps.llm_docs_diff_v3.handlers.output_handler import OutputHandler
from apps.llm_docs_diff_v3.models.bbox_models import ComparisonResult, DiffResult, ChangeType

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(
        description="LLM Document Difference Detection v3.3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python test_llm_diff_v3_3.py pdf1.pdf pdf2.pdf --output-prefix sougou
  python test_llm_diff_v3_3.py pdf1.pdf pdf2.pdf --max-pages 10 --debug
        """
    )
    
    parser.add_argument("pdf1", help="比較対象PDF1のパス（2023年版）")
    parser.add_argument("pdf2", help="比較対象PDF2のパス（2024年版）")
    parser.add_argument("--output-prefix", default="test", help="出力ファイルのプレフィックス")
    parser.add_argument("--max-pages", type=int, help="処理する最大ページ数")
    parser.add_argument("--debug", action="store_true", help="デバッグモードを有効にする")
    
    return parser.parse_args()

def main():
    """メイン処理"""
    args = parse_arguments()
    
    # ロギング設定
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # PDFファイルのパス設定
        pdf1_path = Path(args.pdf1)
        pdf2_path = Path(args.pdf2)
        
        # ファイル存在チェック
        if not pdf1_path.exists():
            logger.error(f"PDF1が見つかりません: {pdf1_path}")
            return
        if not pdf2_path.exists():
            logger.error(f"PDF2が見つかりません: {pdf2_path}")
            return
        
        logger.info("=" * 80)
        logger.info("LLM Document Difference Detection v3.3 開始")
        logger.info(f"PDF1: {pdf1_path.name}")
        logger.info(f"PDF2: {pdf2_path.name}")
        logger.info("=" * 80)
        
        # ステップ1: PDFからテキストとレイアウト情報を抽出
        logger.info("Step 1: PDFからレイアウト情報を抽出中...")
        azure_service = AzureDocumentServiceEnhanced()
        
        # PDFファイルをバイトで読み込み
        with open(pdf1_path, 'rb') as f:
            pdf1_bytes = f.read()
        with open(pdf2_path, 'rb') as f:
            pdf2_bytes = f.read()
        
        # 行ベースのデータを取得
        line_bbox_list1 = azure_service.extract_layout_from_lines(pdf1_bytes)
        line_bbox_list2 = azure_service.extract_layout_from_lines(pdf2_bytes)
        
        # ページ数制限の適用
        if args.max_pages:
            line_bbox_list1 = [item for item in line_bbox_list1 if item.get('page', 1) <= args.max_pages]
            line_bbox_list2 = [item for item in line_bbox_list2 if item.get('page', 1) <= args.max_pages]
        
        logger.info(f"PDF1から {len(line_bbox_list1)} 個の要素を抽出")
        logger.info(f"PDF2から {len(line_bbox_list2)} 個の要素を抽出")
        
        # 出力ディレクトリを先に設定
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = project_root / "output" / f"llm_diff_test_v3_3_{timestamp}" / args.output_prefix
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Azure抽出データのログ出力（P24/P26関連）
        azure_log_path = output_dir / "azure_extraction_debug.log"
        with open(azure_log_path, 'w', encoding='utf-8') as f:
            f.write("=== Azure Document Intelligence 抽出結果 ===\n\n")
            
            f.write("## PDF1 (2024年) - P24/P26/大家さん関連要素:\n")
            for i, item in enumerate(line_bbox_list1):
                text = item.get('text', '')
                if any(keyword in text for keyword in ['P24', 'P26', '大家さん', 'ファミリー', 'パーソナル']):
                    f.write(f"[{i}] '{text}' page={item.get('page', 0)} bbox={item.get('bbox', [])}\n")
            
            f.write("\n## PDF2 (2025年) - P24/P26/大家さん関連要素:\n")
            for i, item in enumerate(line_bbox_list2):
                text = item.get('text', '')
                if any(keyword in text for keyword in ['P24', 'P26', '大家さん', 'ファミリー', 'パーソナル']):
                    f.write(f"[{i}] '{text}' page={item.get('page', 0)} bbox={item.get('bbox', [])}\n")
        
        logger.info(f"Azure抽出データログ: {azure_log_path}")
        
        # ログ設定を前処理実行前に移動
        # ログフォーマッターを先に定義
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # TextPreprocessorV3_1専用ロガーを事前設定
        preproc_logger = logging.getLogger('apps.llm_docs_diff_v3_3.core.text_preprocessing')
        preproc_logger.setLevel(logging.DEBUG)
        preproc_logger.propagate = False
        
        # 既存ハンドラーを削除
        for handler in preproc_logger.handlers[:]:
            preproc_logger.removeHandler(handler)
        
        preproc_log_path = output_dir / "text_preprocessing_debug.log"
        preproc_handler = logging.FileHandler(preproc_log_path, mode='w', encoding='utf-8')
        preproc_handler.setLevel(logging.DEBUG)
        preproc_handler.setFormatter(formatter)
        preproc_logger.addHandler(preproc_handler)
        
        # コンソールハンドラーも追加
        preproc_console = logging.StreamHandler()
        preproc_console.setLevel(logging.INFO)
        preproc_console.setFormatter(formatter)
        preproc_logger.addHandler(preproc_console)
        
        logger.info(f"TextPreprocessorロガー事前設定完了: {preproc_log_path}")
        
        # ステップ2: v3.3前処理（ページ番号参照保護版）
        logger.info("Step 2: テキスト前処理中 (v3.3: ページ番号参照保護版)...")
        text_preprocessor = TextPreprocessorV3_1()  # v3.1前処理クラス使用（改善版維持）
        
        bbox_list1 = text_preprocessor.preprocess_bbox_list(line_bbox_list1)
        bbox_list2 = text_preprocessor.preprocess_bbox_list(line_bbox_list2)
        
        logger.info(f"前処理後: PDF1 {len(bbox_list1)} 要素")
        logger.info(f"前処理後: PDF2 {len(bbox_list2)} 要素")
        
        # 前処理後データのログ出力（P24/P26関連）
        preprocess_log_path = output_dir / "preprocessing_comparison_debug.log"
        with open(preprocess_log_path, 'w', encoding='utf-8') as f:
            f.write("=== 前処理前後の比較 ===\n\n")
            
            f.write("## PDF1 (2024年) - 前処理後 P24/P26/大家さん関連要素:\n")
            for i, item in enumerate(bbox_list1):
                text = item.get('text', '')
                if any(keyword in text for keyword in ['P24', 'P26', '大家さん', 'ファミリー', 'パーソナル']):
                    original_text = item.get('original_text', 'N/A')
                    f.write(f"[{i}] '{text}' (元: '{original_text}') page={item.get('page', 0)} bbox={item.get('bbox', [])}\n")
            
            f.write("\n## PDF2 (2025年) - 前処理後 P24/P26/大家さん関連要素:\n")
            for i, item in enumerate(bbox_list2):
                text = item.get('text', '')
                if any(keyword in text for keyword in ['P24', 'P26', '大家さん', 'ファミリー', 'パーソナル']):
                    original_text = item.get('original_text', 'N/A')
                    f.write(f"[{i}] '{text}' (元: '{original_text}') page={item.get('page', 0)} bbox={item.get('bbox', [])}\n")
        
        logger.info(f"前処理比較ログ: {preprocess_log_path}")
        
        # ページ番号参照要素の保持状況を確認
        page_refs_1 = [item for item in bbox_list1 if _contains_page_reference(item['text'])]
        page_refs_2 = [item for item in bbox_list2 if _contains_page_reference(item['text'])]
        
        logger.info(f"ページ番号参照保持: PDF1 {len(page_refs_1)}件, PDF2 {len(page_refs_2)}件")
        
        # ステップ3: 読み順序推定
        logger.info("Step 3: 読み順序を推定中...")
        reading_estimator = ReadingOrderEstimatorV2()
        
        ordered_bbox_list1 = reading_estimator.estimate_reading_order(bbox_list1)
        ordered_bbox_list2 = reading_estimator.estimate_reading_order(bbox_list2)
        
        logger.info(f"読み順序推定完了: PDF1 {len(ordered_bbox_list1)} 要素")
        logger.info(f"読み順序推定完了: PDF2 {len(ordered_bbox_list2)} 要素")
        
        # ステップ4: 高度差分検出
        logger.info("Step 4: 高度差分検出を実行中...")
        
        # 出力ディレクトリを設定（デバッグログ用）
        # output_dirは既に上で設定済み
        
        # ログフォーマッターを先に定義
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # ContentBasedDiffDetector専用ロガーを設定
        diff_logger = logging.getLogger('apps.llm_docs_diff_v3.core.diff_detector_v3')
        diff_logger.setLevel(logging.DEBUG)
        diff_logger.propagate = False  # 親ロガーへの伝播を停止
        
        # 既存ハンドラーを全て削除
        for handler in diff_logger.handlers[:]:
            diff_logger.removeHandler(handler)
        
        debug_log_path = output_dir / "contentbased_diffdetector_debug.log"
        file_handler = logging.FileHandler(debug_log_path, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        diff_logger.addHandler(file_handler)
        
        # コンソールハンドラーも追加（デバッグ用）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        diff_logger.addHandler(console_handler)
        
        logger.info(f"ContentBasedDiffDetectorデバッグログ: {debug_log_path}")
        
        # ReadingOrderEstimatorV2専用ロガーも設定
        reading_logger = logging.getLogger('apps.llm_docs_diff_v3.core.reading_order_v2')
        reading_logger.setLevel(logging.DEBUG)
        reading_logger.propagate = False
        
        # 既存ハンドラーを削除
        for handler in reading_logger.handlers[:]:
            reading_logger.removeHandler(handler)
        
        reading_log_path = output_dir / "reading_order_grouping_debug.log"
        reading_handler = logging.FileHandler(reading_log_path, mode='w', encoding='utf-8')
        reading_handler.setLevel(logging.DEBUG)
        reading_handler.setFormatter(formatter)
        reading_logger.addHandler(reading_handler)
        
        # コンソールハンドラーも追加
        reading_console = logging.StreamHandler()
        reading_console.setLevel(logging.INFO)
        reading_console.setFormatter(formatter)
        reading_logger.addHandler(reading_console)
        
        logger.info(f"ReadingOrderグループ化ログ: {reading_log_path}")
        
        # 重複したロガー設定（後で削除予定）- 以下は削除対象
        
        logger.info(f"TextPreprocessorデバッグログ: {preproc_log_path}")
        
        diff_detector = ContentBasedDiffDetector(max_page=args.max_pages)
        differences = diff_detector.detect_differences(ordered_bbox_list1, ordered_bbox_list2)
        
        logger.info(f"検出された差分: {len(differences)} 件")
        
        # ステップ5: 結果の構築と出力
        logger.info("Step 5: 結果を出力中...")
        
        # DiffResultV3 は DiffResult と互換性があるため、直接使用可能
        diff_results = differences
        
        # ComparisonResult を作成
        comparison_result = ComparisonResult(
            diff_results=diff_results,
            reading_order_doc1=ordered_bbox_list1,
            reading_order_doc2=ordered_bbox_list2,
            metadata={
                "doc1_total_words": len(ordered_bbox_list1),
                "doc2_total_words": len(ordered_bbox_list2),
                "total_differences": len(differences),
                "doc1_name": pdf1_path.name,
                "doc2_name": pdf2_path.name,
                "version": "v3.3",
                "preprocessing_class": "TextPreprocessorV3_1",
                "diff_detector_class": "ContentBasedDiffDetector",
                "page_refs_preserved_doc1": len(page_refs_1),
                "page_refs_preserved_doc2": len(page_refs_2),
                "processing_timestamp": datetime.now().isoformat()
            }
        )
        
        # 出力ディレクトリを設定（v3.3専用）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = project_root / "output" / f"llm_diff_test_v3_3_{timestamp}" / args.output_prefix
        base_output_name = f"llm_diff_test_v3_3_{timestamp}"
        
        # 出力ディレクトリを作成
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # settings.OUTPUT_DIRを設定（OutputHandlerが使用）
        from apps.llm_docs_diff_v3.config.settings import settings
        settings.OUTPUT_DIR = output_dir
        
        # OutputHandlerを使用して全ての出力を生成
        output_handler = OutputHandler()
        saved_files = output_handler.save_comparison_result(
            comparison_result,
            base_output_name,
            pdf1_bytes=pdf1_bytes,
            pdf2_bytes=pdf2_bytes,
            pdf1_name=pdf1_path.name,
            pdf2_name=pdf2_path.name
        )
        
        logger.info("生成されたファイル:")
        for key, path in saved_files.items():
            logger.info(f"  - {key}: {Path(path).name}")
        
        logger.info("=" * 80)
        logger.info("v3.3処理完了!")
        logger.info(f"出力ディレクトリ: {output_dir}")
        logger.info(f"検出された差分: {len(differences)} 件")
        logger.info(f"ページ番号参照保持: {len(page_refs_1) + len(page_refs_2)} 件")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}", exc_info=True)
        raise

def _contains_page_reference(text: str) -> bool:
    """テキストがページ番号参照を含むかチェック"""
    import re
    return bool(re.search(r'P\d+', text))

if __name__ == "__main__":
    main()