#!/usr/bin/env python3
"""
LLM Docs Diff v5 テストスクリプト
ブロックベースの差分検出システムのテスト
"""
import sys
import os
import argparse
import json
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from apps.llm_docs_diff_v5.services.ocr_service import AzureOCRService
from apps.llm_docs_diff_v5.services.block_extractor import BlockExtractor
from apps.llm_docs_diff_v5.services.llm_block_extractor import LLMBlockExtractor
from apps.llm_docs_diff_v5.services.llm_block_extractor_simple import SimpleLLMBlockExtractor
from apps.llm_docs_diff_v5.core.block_reading_order import BlockReadingOrderEstimator
from apps.llm_docs_diff_v5.core.block_diff_detector import BlockDiffDetector
from apps.llm_docs_diff_v5.models.block_models import DocumentStructure, BlockDifference
from apps.llm_docs_diff_v5.handlers.output_handler import OutputHandler
from apps.llm_docs_diff_v5.handlers.output_handler_v2 import OutputHandlerV2

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('llm_diff_v5.log')
    ]
)
logger = logging.getLogger(__name__)


class LLMDocsDiffV5:
    """ブロックベース差分検出システム"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, use_llm: bool = True):
        """
        Args:
            config: 設定（Azure認証情報等）
            use_llm: LLMベースのブロック抽出を使用するか
        """
        self.config = config or {}
        self.use_llm = use_llm
        
        # 各コンポーネントを初期化
        self.ocr_service = AzureOCRService(
            endpoint=self.config.get('azure_endpoint'),
            api_key=self.config.get('azure_api_key')
        )
        
        if use_llm:
            # シンプルなLLMベースのブロック抽出を使用
            self.llm_block_extractor = SimpleLLMBlockExtractor()
        else:
            # 従来のAzureベースのブロック抽出
            self.block_extractor = BlockExtractor(
                merge_threshold=self.config.get('merge_threshold', 10.0),
                min_block_area=self.config.get('min_block_area', 100.0)
            )
            
            self.reading_order_estimator = BlockReadingOrderEstimator(
                column_threshold=self.config.get('column_threshold', 50.0),
                line_height_ratio=self.config.get('line_height_ratio', 0.5),
                use_visual_cues=self.config.get('use_visual_cues', True)
            )
        
        self.diff_detector = BlockDiffDetector(
            position_weight=self.config.get('position_weight', 0.3),
            content_weight=self.config.get('content_weight', 0.5),
            type_weight=self.config.get('type_weight', 0.2),
            similarity_threshold=self.config.get('similarity_threshold', 0.7),
            position_tolerance=self.config.get('position_tolerance', 20.0)
        )
        
        self.output_handler = OutputHandlerV2()  # V2ハンドラーを使用
    
    def analyze_document(self, pdf_path: str) -> DocumentStructure:
        """PDFを解析してブロック構造を抽出"""
        logger.info(f"Analyzing document: {pdf_path}")
        
        if self.use_llm:
            # LLMベースのブロック抽出
            doc_structure = self.llm_block_extractor.extract_blocks_with_llm(pdf_path)
            logger.info(f"Extracted {len(doc_structure.blocks)} blocks using LLM")
            
            # Azure OCR結果をOutputHandlerV2に渡す
            if hasattr(self.output_handler, 'set_azure_result') and hasattr(self.llm_block_extractor, 'azure_result'):
                self.output_handler.set_azure_result(pdf_path, self.llm_block_extractor.azure_result)
        else:
            # 画像ベースのブロック検出を使用
            from apps.llm_docs_diff_v5.services.image_block_detector import ImageBlockDetector
            
            # 1. 画像ベースでブロックを検出
            image_detector = ImageBlockDetector()
            image_blocks = image_detector.detect_blocks_from_pdf(pdf_path)
            logger.info(f"Detected {len(image_blocks)} image blocks")
            
            # 2. Azure OCRでテキストを抽出（最小限のページ数）
            max_pages = min(5, max(b['page'] for b in image_blocks) + 1) if image_blocks else 5
            azure_result = self.ocr_service.extract_layout_from_pdf(pdf_path, max_pages=max_pages)
            
            # 3. 画像ブロックをDocumentStructureに変換
            blocks = []
            for img_block in image_blocks:
                # 簡易的にBlockオブジェクトを作成
                from apps.llm_docs_diff_v5.models.block_models import Block, BlockType, BoundingBox, TextElement, LayoutRole
                
                block = Block(
                    block_id=img_block['block_id'],
                    block_type=BlockType.PARAGRAPH,  # デフォルト
                    bbox=BoundingBox(
                        x=img_block['bbox'][0] * 72.0 / image_detector.dpi,
                        y=img_block['bbox'][1] * 72.0 / image_detector.dpi,
                        width=img_block['bbox'][2] * 72.0 / image_detector.dpi,
                        height=img_block['bbox'][3] * 72.0 / image_detector.dpi
                    ),
                    elements=[],  # OCRテキストは後で追加可能
                    page=img_block['page'],
                    layout_role=LayoutRole.MAIN_CONTENT,
                    confidence=1.0
                )
                blocks.append(block)
            
            # 4. DocumentStructureを作成
            from ..models.block_models import DocumentStructure
            doc_structure = DocumentStructure(
                blocks=blocks,
                pages=max(b.page for b in blocks) + 1 if blocks else 0,
                metadata={'extraction_method': 'image_based'}
            )
            
            logger.info(f"Created document structure with {len(blocks)} blocks")
        
        return doc_structure
    
    def detect_differences(self, pdf1_path: str, pdf2_path: str) -> List[BlockDifference]:
        """2つのPDF間の差分を検出"""
        logger.info(f"Detecting differences between {pdf1_path} and {pdf2_path}")
        
        # 両方の文書を解析
        doc1 = self.analyze_document(pdf1_path)
        doc2 = self.analyze_document(pdf2_path)
        
        # 差分を検出
        differences = self.diff_detector.detect_differences(doc1, doc2)
        logger.info(f"Found {len(differences)} differences")
        
        # サマリーを生成
        summary = self.diff_detector.generate_summary(differences)
        logger.info(f"Difference summary: {summary}")
        
        return differences, doc1, doc2, summary
    
    def run_comparison(self, pdf1_path: str, pdf2_path: str, output_dir: str):
        """完全な比較プロセスを実行"""
        logger.info("Starting block-based comparison process")
        
        # 出力ディレクトリを作成
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # 差分検出
            differences, doc1, doc2, summary = self.detect_differences(pdf1_path, pdf2_path)
            
            # 結果を保存
            self.output_handler.save_results(
                differences=differences,
                doc1=doc1,
                doc2=doc2,
                summary=summary,
                pdf1_path=pdf1_path,
                pdf2_path=pdf2_path,
                output_dir=output_dir
            )
            
            logger.info(f"Results saved to {output_dir}")
            
            # 詳細レポートを生成
            report = self.output_handler.generate_detailed_report(
                differences, doc1, doc2, summary
            )
            
            report_path = output_path / "detailed_report.md"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"Detailed report saved to {report_path}")
            
        except Exception as e:
            logger.error(f"Error during comparison: {e}")
            raise


def parse_arguments():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description='LLM Docs Diff v5 - ブロックベース差分検出'
    )
    
    parser.add_argument(
        '--dataset',
        type=str,
        choices=['dantai', 'sougou'],
        default='dantai',
        help='使用するデータセット (dantai: docs/img/2023.pdf & 2024.pdf, sougou: data/sougou/)'
    )
    
    parser.add_argument(
        '--pdf1',
        type=str,
        help='比較する最初のPDFファイル（datasetを指定した場合は無視）'
    )
    
    parser.add_argument(
        '--pdf2',
        type=str,
        help='比較する2番目のPDFファイル（datasetを指定した場合は無視）'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='出力ディレクトリ（指定しない場合は自動生成）'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='設定ファイルのパス（JSON形式）'
    )
    
    parser.add_argument(
        '--use-llm',
        action='store_true',
        default=True,
        help='LLMベースのブロック抽出を使用（デフォルト: True）'
    )
    
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='LLMを使用せず、Azureのみでブロック抽出'
    )
    
    return parser.parse_args()


def load_config(config_path: Optional[str]) -> Dict[str, Any]:
    """設定ファイルを読み込む"""
    config = {
        # デフォルト設定
        'merge_threshold': 10.0,
        'min_block_area': 100.0,
        'column_threshold': 50.0,
        'line_height_ratio': 0.5,
        'use_visual_cues': True,
        'position_weight': 0.3,
        'content_weight': 0.5,
        'type_weight': 0.2,
        'similarity_threshold': 0.7,
        'position_tolerance': 20.0
    }
    
    # 環境変数からAzure認証情報を取得
    config['azure_endpoint'] = os.environ.get('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
    config['azure_api_key'] = os.environ.get('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    # 設定ファイルがあれば読み込む
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            config.update(file_config)
    
    return config


def main():
    """メイン関数"""
    args = parse_arguments()
    
    # 設定を読み込む
    config = load_config(args.config)
    
    # PDFパスを決定
    if args.pdf1 and args.pdf2:
        pdf1_path = args.pdf1
        pdf2_path = args.pdf2
        dataset_name = "custom"
    else:
        # データセットに基づいてパスを設定
        if args.dataset == 'dantai':
            pdf1_path = 'docs/img/2023.pdf'
            pdf2_path = 'docs/img/2024.pdf'
        else:  # sougou
            # 総合データセットのPDFを探す
            sougou_dir = Path('data/sougou')
            pdf_files = sorted(sougou_dir.glob('*.pdf'))
            if len(pdf_files) < 2:
                logger.error(f"総合データセットに十分なPDFファイルがありません: {len(pdf_files)} files found")
                sys.exit(1)
            pdf1_path = str(pdf_files[0])
            pdf2_path = str(pdf_files[1])
        
        dataset_name = args.dataset
    
    # 出力ディレクトリを決定
    if args.output:
        output_dir = args.output
    else:
        output_dir = f'output/llm_diff_test_v5/{dataset_name}'
    
    logger.info(f"Using dataset: {dataset_name}")
    logger.info(f"PDF1: {pdf1_path}")
    logger.info(f"PDF2: {pdf2_path}")
    logger.info(f"Output directory: {output_dir}")
    
    # LLM使用フラグを決定
    use_llm = not args.no_llm
    logger.info(f"Using LLM: {use_llm}")
    
    # v5システムを実行
    system = LLMDocsDiffV5(config, use_llm=use_llm)
    system.run_comparison(pdf1_path, pdf2_path, output_dir)
    
    logger.info("Comparison completed successfully")


if __name__ == '__main__':
    main()