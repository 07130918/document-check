#!/usr/bin/env python3
"""
Document Difference Detection v5 with LLM
LLMを使用した高度な差分分析
"""
import os
import sys
from pathlib import Path
import argparse
import logging
import time
import json

# プロジェクトのルートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.llm_docs_diff_v5.services.llm_block_extractor_simple import SimpleLLMBlockExtractor
from apps.llm_docs_diff_v5.services.llm_diff_service import LLMDiffService
from apps.llm_docs_diff_v5.services.block_extractor import BlockExtractor
from apps.llm_docs_diff_v5.core.block_diff_detector import BlockDiffDetector
from apps.llm_docs_diff_v5.handlers.output_handler_v2 import OutputHandlerV2
from apps.llm_docs_diff_v5.models.block_models import BlockDifference

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description='Document Diff v5 with LLM')
    parser.add_argument('--dataset', type=str, choices=['dantai', 'sample1', 'sample2', 'sample3', 'sample4', 'sample5'], default='dantai',
                        help='使用するデータセット')
    parser.add_argument('--use-llm', action='store_true', default=True,
                        help='LLMで差分を分析する（デフォルト: True）')
    parser.add_argument('--llm-summary', action='store_true', default=True,
                        help='LLMで要約を生成する（デフォルト: True）')
    parser.add_argument('--analyze-each', action='store_true',
                        help='各差分を個別にLLMで分析する')
    parser.add_argument('--max-pages', type=int, default=None,
                        help='処理する最大ページ数（指定しない場合は全ページ）')
    return parser.parse_args()


class LLMDiffTestV5:
    """LLM強化版の差分検出システム"""
    
    def __init__(self, use_llm=True):
        """初期化"""
        self.block_extractor = SimpleLLMBlockExtractor()
        self.matcher = BlockExtractor()
        self.diff_detector = BlockDiffDetector()
        self.output_handler = OutputHandlerV2()
        self.llm_service = LLMDiffService() if use_llm else None
        self.use_llm = use_llm
    
    def process_documents(self, pdf1_path: str, pdf2_path: str, args):
        """2つのPDFを比較処理"""
        logger.info("Starting block-based comparison process with LLM")
        
        # 1. ブロック抽出
        logger.info(f"Analyzing document: {pdf1_path}")
        doc1 = self.block_extractor.extract_blocks_with_llm(pdf1_path)
        logger.info(f"Extracted {len(doc1.blocks)} blocks from document 1")
        
        # Azure OCR結果をハンドラーに渡す
        if hasattr(self.output_handler, 'set_azure_result') and hasattr(self.block_extractor, 'azure_result'):
            self.output_handler.set_azure_result(pdf1_path, self.block_extractor.azure_result)
        
        logger.info(f"Analyzing document: {pdf2_path}")
        doc2 = self.block_extractor.extract_blocks_with_llm(pdf2_path)
        logger.info(f"Extracted {len(doc2.blocks)} blocks from document 2")
        
        # Azure OCR結果をハンドラーに渡す
        if hasattr(self.output_handler, 'set_azure_result') and hasattr(self.block_extractor, 'azure_result'):
            self.output_handler.set_azure_result(pdf2_path, self.block_extractor.azure_result)
        
        # 2. 差分検出
        logger.info("Detecting differences between documents")
        differences = self.diff_detector.detect_differences(doc1, doc2)
        logger.info(f"Found {len(differences)} differences")
        
        # 3. LLMによる差分分析
        llm_analysis = None
        if self.use_llm and self.llm_service:
            logger.info("Analyzing differences with LLM...")
            
            # 全体的な差分分析
            llm_analysis = self.llm_service.analyze_block_differences(
                differences,
                doc_context="保険関連文書の比較"
            )
            
            # 分析結果を表示
            print("\n===== LLM差分分析結果 =====")
            print(f"全体的な傾向: {llm_analysis.get('overall_trend', '不明')}")
            print(f"影響度評価: {llm_analysis.get('impact_assessment', '不明')}")
            print(f"要約: {llm_analysis.get('summary', 'なし')}")
            
            if llm_analysis.get('key_changes'):
                print("\n重要な変更点:")
                for i, change in enumerate(llm_analysis['key_changes'], 1):
                    print(f"  {i}. {change}")
            
            if llm_analysis.get('formatting_changes'):
                print("\n形式的な変更:")
                for i, change in enumerate(llm_analysis['formatting_changes'], 1):
                    print(f"  {i}. {change}")
            
            # 個別の差分分析（オプション）
            if args.analyze_each and len(differences) > 0:
                print("\n===== 個別差分のLLM分析 =====")
                for i, diff in enumerate(differences[:5]):  # 最初の5件
                    print(f"\n差分 {i+1}:")
                    analysis = self.llm_service.analyze_single_difference(
                        diff.block1, diff.block2
                    )
                    print(f"  類似度: {analysis.semantic_similarity:.2f}")
                    print(f"  重要度: {analysis.change_significance}")
                    print(f"  カテゴリ: {analysis.change_category}")
                    print(f"  説明: {analysis.explanation}")
                    print(f"  影響: {analysis.impact_assessment}")
            
            # 差分要約の生成
            if args.llm_summary:
                print("\n===== LLM差分要約 =====")
                summary_items = self.llm_service.generate_diff_summary(differences)
                for i, item in enumerate(summary_items, 1):
                    print(f"  {i}. {item}")
        
        # 4. 統計情報
        summary = self.diff_detector.generate_summary(differences)
        print(f"\n===== 差分統計 =====")
        print(f"総差分数: {summary['total']}")
        print(f"タイプ別: {summary['by_type']}")
        print(f"ページ別差分数: {len(summary['by_page'])} ページ")
        
        # 5. 結果を保存
        output_path = Path(f"output/llm_diff_test_v5_llm/{args.dataset}")
        output_path.mkdir(parents=True, exist_ok=True)
        
        # メタデータにLLM分析を追加
        metadata = {
            "llm_analysis": llm_analysis,
            "llm_enabled": self.use_llm,
            "dataset": args.dataset,
            "max_pages": args.max_pages
        }
        
        self.output_handler.save_results(
            differences, doc1, doc2, summary, pdf1_path, pdf2_path, str(output_path)
        )
        
        # 差分結果をJSON形式で保存
        result_data = {
            "summary": summary,
            "llm_analysis": llm_analysis,
            "differences": [
                {
                    "type": diff.change_type,
                    "page": diff.block1.page if diff.block1 else (diff.block2.page if diff.block2 else 0),
                    "block1_text": diff.block1.text[:100] if diff.block1 else None,
                    "block2_text": diff.block2.text[:100] if diff.block2 else None
                }
                for diff in differences[:20]  # 最初の20件
            ]
        }
        
        with open(output_path / "llm_analysis_result.json", "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to {output_path}")
        
        return differences, summary, llm_analysis


def main():
    """メイン関数"""
    args = parse_arguments()
    
    # データセットのパスを設定
    if args.dataset == 'dantai':
        pdf1_path = "data/dantaihoken/2023.pdf"
        pdf2_path = "data/dantaihoken/2024.pdf"
    elif args.dataset == 'sample1':
        pdf1_path = "data/sample1/サンプル①2024後半.pdf"
        pdf2_path = "data/sample1/サンプル①2025後半.pdf"
    elif args.dataset == 'sample2':
        pdf1_path = "data/sample2/サンプル②2024 .pdf"
        pdf2_path = "data/sample2/サンプル②2025.pdf"
    elif args.dataset == 'sample3':
        pdf1_path = "data/sample3/サンプル③2023.pdf"
        pdf2_path = "data/sample3/サンプル③2024.pdf"
    elif args.dataset == 'sample4':
        pdf1_path = "data/sample4/サンプル④2024_アノテーション.pdf"
        pdf2_path = "data/sample4/サンプル④2025_アノテーション.pdf"
    else:  # sample5
        pdf1_path = "data/sample5/サンプル⑤2024_アノテーション.pdf"
        pdf2_path = "data/sample5/サンプル⑤2025_アノテーション.pdf"
    
    # パスの存在確認
    pdf1_full = Path(pdf1_path)
    pdf2_full = Path(pdf2_path)
    
    if not pdf1_full.exists() or not pdf2_full.exists():
        logger.error(f"PDFファイルが見つかりません")
        if not pdf1_full.exists():
            logger.error(f"  {pdf1_full} が存在しません")
        if not pdf2_full.exists():
            logger.error(f"  {pdf2_full} が存在しません")
        return
    
    # 処理開始
    print(f"\n===== Document Diff v5 with LLM =====")
    print(f"データセット: {args.dataset}")
    print(f"PDF1: {pdf1_path}")
    print(f"PDF2: {pdf2_path}")
    print(f"LLM使用: {args.use_llm}")
    print(f"LLM要約: {args.llm_summary}")
    print(f"個別分析: {args.analyze_each}")
    
    start_time = time.time()
    
    try:
        # 差分検出システムを初期化
        diff_system = LLMDiffTestV5(use_llm=args.use_llm)
        
        # ドキュメントを処理
        differences, summary, llm_analysis = diff_system.process_documents(
            str(pdf1_full), str(pdf2_full), args
        )
        
        elapsed_time = time.time() - start_time
        print(f"\n処理完了！実行時間: {elapsed_time:.2f}秒")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()