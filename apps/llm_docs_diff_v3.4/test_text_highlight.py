#!/usr/bin/env python3
# coding: utf-8
"""
文字指定ベースハイライトテスト
「約147億円」の文字をハイライトする
"""

import fitz  # PyMuPDF
import logging
from pathlib import Path

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def highlight_text_by_content(pdf_path: str, target_text: str, output_path: str):
    """文字内容ベースでハイライトを追加
    
    Args:
        pdf_path: 入力PDFファイルのパス
        target_text: ハイライトする文字列
        output_path: 出力PDFファイルのパス
    """
    logger.info(f"PDF読み込み: {pdf_path}")
    logger.info(f"ハイライト対象文字: '{target_text}'")
    
    # PDFを開く
    pdf_document = fitz.open(pdf_path)
    highlight_count = 0
    
    try:
        # 各ページを処理
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            logger.info(f"ページ {page_num + 1} を処理中...")
            
            # 方法1: search_for()を使用してテキストを検索
            text_instances = page.search_for(target_text)
            logger.info(f"  '{target_text}' を {len(text_instances)} 件発見")
            
            # 検索された各インスタンスをハイライト
            for i, rect in enumerate(text_instances):
                try:
                    # より目立つハイライト注釈を追加
                    highlight = page.add_highlight_annot(rect)
                    highlight.set_colors(stroke=[1, 0, 0], fill=[1, 1, 0])  # 赤枠、黄色背景
                    highlight.set_opacity(0.5)  # 透明度を設定
                    highlight.update()
                    highlight_count += 1
                    logger.info(f"    {i+1}: ハイライト追加 at {rect}")
                    
                    # 追加で赤い枠線も描画（確実に見えるように）
                    page.draw_rect(rect, color=(1, 0, 0), width=3.0, fill=None)
                    logger.info(f"    {i+1}: 赤枠追加 at {rect}")
                    
                except Exception as e:
                    logger.error(f"    {i+1}: ハイライト追加失敗 at {rect}: {e}")
            
            # 方法2: 詳細なテキスト調査
            text_dict = page.get_text("dict")
            logger.info("  詳細テキスト調査:")
            
            for block in text_dict["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text_content = span["text"]
                            if "147" in text_content or "億" in text_content:
                                bbox = span["bbox"]
                                logger.info(f"    発見: '{text_content}' at bbox={bbox}")
                                
                                # この文字をハイライト
                                try:
                                    rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                                    page.draw_rect(rect, color=(0, 1, 0), width=2.0, fill=None)  # 緑枠
                                    logger.info(f"    緑枠追加: '{text_content}'")
                                except Exception as e:
                                    logger.error(f"    緑枠追加失敗: {e}")
            
            # 方法3: 様々なバリエーションで検索
            search_variations = [
                "約147億円",
                "147億円", 
                "約147",
                "147億",
                "億円",
                "147"
            ]
            
            for variation in search_variations:
                instances = page.search_for(variation)
                if instances:
                    logger.info(f"  バリエーション検索: '{variation}' → {len(instances)}件")
                    for j, rect in enumerate(instances):
                        # 違う色で区別
                        color_map = {
                            "約147億円": (1, 0, 0),  # 赤
                            "147億円": (0, 1, 0),   # 緑
                            "約147": (0, 0, 1),     # 青
                            "147億": (1, 0, 1),     # マゼンタ
                            "億円": (1, 0.5, 0),    # オレンジ
                            "147": (0, 1, 1)        # シアン
                        }
                        color = color_map.get(variation, (0.5, 0.5, 0.5))
                        page.draw_rect(rect, color=color, width=1.5, fill=None)
                        logger.info(f"    {variation}[{j+1}]: 枠追加 at {rect}")
        
        # 結果を保存
        logger.info(f"ハイライト追加完了: {highlight_count} 件")
        pdf_document.save(output_path)
        logger.info(f"保存完了: {output_path}")
        
        return output_path, highlight_count
        
    finally:
        pdf_document.close()


def main():
    """メイン処理"""
    # ファイルパス設定
    input_pdf = "/home/dev/prj-ms-document-check.worktree/worktree1/data/data1/sougou/サンプル②2024 -1.pdf"
    output_pdf = "/home/dev/prj-ms-document-check.worktree/worktree1/apps/llm_docs_diff_v3.4/output/text_highlight_test.pdf"
    target_text = "約147億円"
    
    # 出力ディレクトリを作成
    output_dir = Path(output_pdf).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # ハイライト処理を実行
        result_path, count = highlight_text_by_content(input_pdf, target_text, output_pdf)
        
        print(f"=== ハイライトテスト結果 ===")
        print(f"対象文字: '{target_text}'")
        print(f"ハイライト数: {count} 件")
        print(f"出力PDF: {result_path}")
        print(f"=========================")
        
        # ファイルが存在するかチェック
        if Path(result_path).exists():
            file_size = Path(result_path).stat().st_size
            print(f"ファイルサイズ: {file_size:,} bytes")
        else:
            print("エラー: 出力ファイルが作成されませんでした")
            
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    main()