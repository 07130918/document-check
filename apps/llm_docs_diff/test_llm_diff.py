"""
LLM文書差分検出システムのテストスクリプト
"""
import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.llm_docs_diff.core.document_analyzer import DocumentAnalyzer
from apps.llm_docs_diff.handlers.output_handler import OutputHandler
from apps.llm_docs_diff.config.settings import settings

# テスト用に最大ページ数を設定
settings.TEST_MAX_PAGES = 5

# ロギング設定
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_llm_diff_detection():
    """LLM差分検出のテスト実行"""
    
    # 設定の検証
    if not settings.validate():
        logger.error("Configuration validation failed")
        return
    
    # テストファイルのパス
    # docs/imgディレクトリのPDFファイルを使用（2023.pdf と 2024.pdf）
    test_dir = project_root / "docs" / "img"
    
    file1_path = str(test_dir / "2023.pdf")
    file2_path = str(test_dir / "2024.pdf")
    
    # ファイルの存在確認
    if not Path(file1_path).exists() or not Path(file2_path).exists():
        logger.error("テストPDFファイルが見つかりません。")
        logger.info(f"期待されるファイル:")
        logger.info(f"- {file1_path}")
        logger.info(f"- {file2_path}")
        
        # 代替として他のPDFファイルを探す
        pdf_files = list(project_root.glob("**/*.pdf"))
        if len(pdf_files) >= 2:
            file1_path = str(pdf_files[0])
            file2_path = str(pdf_files[1])
            logger.info(f"代替ファイルを使用:")
            logger.info(f"- {file1_path}")
            logger.info(f"- {file2_path}")
        else:
            return
    
    logger.info(f"テストファイル1: {file1_path}")
    logger.info(f"テストファイル2: {file2_path}")
    
    try:
        # DocumentAnalyzerを初期化
        analyzer = DocumentAnalyzer()
        
        # 文書を解析
        logger.info("文書解析を開始します...")
        result, pdf1_bytes, pdf2_bytes = analyzer.analyze_documents(file1_path, file2_path)
        
        # 結果を出力（読み順序PDFも生成）
        output_handler = OutputHandler()
        saved_files = output_handler.save_comparison_result(result, "llm_test", pdf1_bytes, pdf2_bytes)
        
        # ハイライト付きPDFの生成は削除
        # （output_handler.save_comparison_result内で2023_compared.pdfと2024_compared.pdfが既に生成されているため）
        
        logger.info("解析完了！")
        logger.info(f"検出された差分数: {len(result.diff_results)}")
        logger.info("保存されたファイル:")
        for file_type, file_path in saved_files.items():
            logger.info(f"  - {file_type}: {file_path}")
        
        # LLM解析結果のサマリーを表示
        if result.llm_analysis:
            logger.info("\n=== LLM解析結果 ===")
            logger.info(f"文書要約: {result.llm_analysis.document_summary}")
            logger.info("主要な変更点:")
            for i, change in enumerate(result.llm_analysis.key_changes[:5], 1):
                logger.info(f"  {i}. {change}")
            
            logger.info("リスク評価:")
            for risk_type, score in result.llm_analysis.risk_assessment.items():
                logger.info(f"  - {risk_type}: {score:.2%}")
        
        # 主要な差分の表示
        logger.info("\n=== 主要な差分（最初の5件） ===")
        
        for i, diff in enumerate(result.diff_results[:5], 1):
            logger.info(f"\n{i}. {diff.change_type.value}")
            logger.info(f"   ページ: {diff.page + 1}")
            if diff.original_bbox:
                logger.info(f"   元: {diff.original_bbox['text']}")
            if diff.modified_bbox:
                logger.info(f"   後: {diff.modified_bbox['text']}")
            if diff.llm_explanation:
                logger.info(f"   説明: {diff.llm_explanation}")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}", exc_info=True)


def test_word_powerpoint_conversion():
    """Word/PowerPoint変換のテスト"""
    from apps.llm_docs_diff.services.pdf_converter import PDFConverterFactory
    
    logger.info("\n=== Word/PowerPoint変換テスト ===")
    
    # テスト用のWord/PowerPointファイルを探す
    test_files = []
    for ext in ['*.docx', '*.doc', '*.pptx', '*.ppt']:
        test_files.extend(list(Path(".").glob(f"**/{ext}")))
    
    if not test_files:
        logger.info("Word/PowerPointファイルが見つかりません。スキップします。")
        return
    
    converter = PDFConverterFactory.create_converter("libreoffice")
    
    for file_path in test_files[:2]:  # 最初の2ファイルのみテスト
        logger.info(f"\n変換テスト: {file_path}")
        try:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            file_type = file_path.suffix[1:]  # .を除く
            pdf_bytes = converter.convert_to_pdf(file_bytes, file_type)
            
            output_path = settings.OUTPUT_DIR / f"converted_{file_path.stem}.pdf"
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            
            logger.info(f"  ✓ 変換成功: {output_path}")
            
        except Exception as e:
            logger.error(f"  ✗ 変換失敗: {e}")


if __name__ == "__main__":
    # メインテストを実行
    test_llm_diff_detection()
    
    # オプション: Word/PowerPoint変換テスト
    # test_word_powerpoint_conversion()