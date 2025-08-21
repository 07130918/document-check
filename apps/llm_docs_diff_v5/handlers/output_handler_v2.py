"""
出力ハンドラー V2 - Azure OCRの単語情報を直接使用
差分検出結果の保存と可視化
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

from ..models.block_models import (
    Block, BlockDifference, DocumentStructure, BlockType
)

logger = logging.getLogger(__name__)


class OutputHandlerV2:
    """出力処理を担当するハンドラー（Azure OCR単語情報使用版）"""
    
    def __init__(self):
        self.azure_results = {}  # PDFパスとAzure OCR結果のマッピング
    
    def set_azure_result(self, pdf_path: str, azure_result: Any):
        """Azure OCR結果を保存"""
        self.azure_results[pdf_path] = azure_result
    
    def save_results(self, 
                    differences: List[BlockDifference],
                    doc1: DocumentStructure,
                    doc2: DocumentStructure,
                    summary: Dict[str, Any],
                    pdf1_path: str,
                    pdf2_path: str,
                    output_dir: str):
        """差分検出結果を保存"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 1. JSON形式で差分を保存
        self._save_differences_json(differences, output_path / "differences.json")
        
        # 2. サマリーを保存
        self._save_summary(summary, output_path / "summary.json")
        
        # 3. 文書構造を保存
        self._save_document_structure(doc1, output_path / "doc1_structure.json")
        self._save_document_structure(doc2, output_path / "doc2_structure.json")
        
        # 4. 読み順序でのテキストを保存
        self._save_reading_order_text(doc1, output_path / "doc1_text.txt")
        self._save_reading_order_text(doc2, output_path / "doc2_text.txt")
        
        # 5. 可視化PDFを生成
        self._create_visualization_pdf(
            differences, doc1, doc2, pdf1_path, pdf2_path, output_path
        )
        
        # 6. 評価ドキュメントを生成
        self._create_evaluation_document(
            differences, summary, pdf1_path, pdf2_path, output_path
        )
    
    def _save_differences_json(self, differences: List[BlockDifference], filepath: Path):
        """差分をJSON形式で保存"""
        diff_data = [diff.to_dict() for diff in differences]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(diff_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved differences to {filepath}")
    
    def _save_summary(self, summary: Dict[str, Any], filepath: Path):
        """サマリーを保存"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved summary to {filepath}")
    
    def _save_document_structure(self, doc: DocumentStructure, filepath: Path):
        """文書構造を保存"""
        structure_data = {
            'pages': doc.pages,
            'metadata': doc.metadata,
            'blocks': [block.to_dict() for block in doc.blocks]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(structure_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved document structure to {filepath}")
    
    def _save_reading_order_text(self, doc: DocumentStructure, filepath: Path):
        """読み順序でテキストを保存"""
        from ..core.block_reading_order import BlockReadingOrderEstimator
        estimator = BlockReadingOrderEstimator()
        text = estimator.extract_text_in_reading_order(doc)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        logger.info(f"Saved reading order text to {filepath}")
    
    def _create_visualization_pdf(self,
                                 differences: List[BlockDifference],
                                 doc1: DocumentStructure,
                                 doc2: DocumentStructure,
                                 pdf1_path: str,
                                 pdf2_path: str,
                                 output_path: Path):
        """差分を可視化したPDFを生成"""
        # PDFファイル名を取得
        pdf1_name = Path(pdf1_path).stem
        pdf2_name = Path(pdf2_path).stem
        
        # 1. ブロック境界のみのPDF（差分なし）
        block1_path = output_path / f"{pdf1_name}_blocks.pdf"
        block2_path = output_path / f"{pdf2_name}_blocks.pdf"
        
        self._visualize_blocks_only(pdf1_path, doc1, block1_path)
        self._visualize_blocks_only(pdf2_path, doc2, block2_path)
        
        # 2. 差分をハイライト表示したPDF（v3スタイル）
        highlight1_path = output_path / f"{pdf1_name}_highlighted.pdf"
        highlight2_path = output_path / f"{pdf2_name}_highlighted.pdf"
        
        self._create_highlighted_pdf(pdf1_path, doc1, differences, highlight1_path, is_doc1=True)
        self._create_highlighted_pdf(pdf2_path, doc2, differences, highlight2_path, is_doc1=False)
        
        # 3. 並列表示PDF（ハイライト付き）
        parallel_path = output_path / f"{pdf1_name}_vs_{pdf2_name}_highlighted.pdf"
        self._create_parallel_pdf(highlight1_path, highlight2_path, parallel_path)
    
    def _visualize_blocks_only(self,
                              pdf_path: str,
                              doc: DocumentStructure,
                              output_path: Path):
        """ブロック境界のみを可視化（差分なし）"""
        # PDFを開く
        pdf_doc = fitz.open(pdf_path)
        
        # ブロックがあるページの最大値を取得
        max_block_page = -1
        for block in doc.blocks:
            max_block_page = max(max_block_page, block.page)
        
        # ブロックがない場合は1ページ目だけ出力
        if max_block_page == -1:
            max_block_page = 0
        
        # 新しいPDFドキュメントを作成（必要なページだけ）
        new_pdf_doc = fitz.open()
        
        # 各ページでブロックを可視化
        for page_num in range(min(max_block_page + 1, len(pdf_doc))):
            # 元のページをコピー
            page = pdf_doc[page_num]
            new_page = new_pdf_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(new_page.rect, pdf_doc, page_num)
            
            # このページのブロックを取得
            page_blocks = doc.get_blocks_by_page(page_num)
            
            # ブロックの境界を描画
            for block in page_blocks:
                rect = fitz.Rect(
                    block.bbox.x,
                    block.bbox.y,
                    block.bbox.x2,
                    block.bbox.y2
                )
                
                # ブロックタイプによって色を変える
                color = self._get_block_color(block.block_type)
                new_page.draw_rect(rect, color=color, width=1.0, fill=None)
                
                # ブロック番号を追加
                text_point = fitz.Point(block.bbox.x + 2, block.bbox.y + 10)
                new_page.insert_text(text_point, f"{block.reading_order}", fontsize=8, color=(0, 0, 0))
        
        # 保存
        new_pdf_doc.save(str(output_path))
        new_pdf_doc.close()
        pdf_doc.close()
        logger.info(f"Created blocks visualization PDF: {output_path} (pages: 1-{max_block_page + 1})")
    
    def _create_highlighted_pdf(self,
                               pdf_path: str,
                               doc: DocumentStructure,
                               differences: List[BlockDifference],
                               output_path: Path,
                               is_doc1: bool):
        """差分をハイライト表示したPDF生成（単語レベル）"""
        # PDFを開く
        pdf_doc = fitz.open(pdf_path)
        
        # Azure OCR結果を取得
        azure_result = self.azure_results.get(pdf_path)
        if not azure_result:
            logger.warning(f"No Azure OCR result found for {pdf_path}")
            # Azure OCR結果がない場合は従来のブロックレベルハイライト
            self._create_block_level_highlighted_pdf(pdf_doc, doc, differences, output_path, is_doc1)
            return
        
        # 差分があるページの最大値を取得
        max_diff_page = -1
        for diff in differences:
            if is_doc1 and diff.block1:
                max_diff_page = max(max_diff_page, diff.block1.page)
            elif not is_doc1 and diff.block2:
                max_diff_page = max(max_diff_page, diff.block2.page)
        
        # 差分がない場合は1ページ目だけ出力
        if max_diff_page == -1:
            max_diff_page = 0
        
        logger.info(f"Processing pages up to {max_diff_page + 1} (max page with differences)")
        
        # 新しいPDFドキュメントを作成（必要なページだけ）
        new_pdf_doc = fitz.open()
        
        # 各ページで差分をハイライト（max_diff_pageまで）
        for page_num in range(min(max_diff_page + 1, len(pdf_doc))):
            # 元のページをコピー
            page = pdf_doc[page_num]
            new_page = new_pdf_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(new_page.rect, pdf_doc, page_num)
            
            # Azure OCR結果がこのページにあるかチェック
            if page_num >= len(azure_result.pages):
                logger.warning(f"No Azure OCR result for page {page_num + 1}")
                continue
                
            azure_page = azure_result.pages[page_num]
            
            # ページサイズを取得
            page_rect = page.rect
            pdf_page_width = page_rect.width
            pdf_page_height = page_rect.height
            
            # Azure OCRのページサイズを取得（座標変換用）
            azure_page_width = pdf_page_width  # デフォルト
            azure_page_height = pdf_page_height
            if hasattr(azure_page, 'width') and hasattr(azure_page, 'height'):
                # Azure OCRのページサイズはインチ単位
                azure_page_width = azure_page.width * 72
                azure_page_height = azure_page.height * 72
            
            # 差分があるブロックを処理
            for diff in differences:
                # すべての差分タイプで単語レベルのハイライトを行う
                if is_doc1:
                    # doc1側の処理
                    if diff.block1 and diff.block1.page == page_num:
                        if diff.change_type == "modified" and diff.block2:
                            # modifiedの場合は両方のブロックのテキストを比較
                            self._highlight_word_differences_azure(
                                new_page, azure_page, diff.block1, diff.block2, 
                                pdf_page_width, pdf_page_height, azure_page_width, azure_page_height
                            )
                        elif diff.change_type == "deleted":
                            # deletedの場合はblock1のすべての単語をハイライト
                            self._highlight_all_words_in_block(
                                new_page, azure_page, diff.block1, 
                                pdf_page_width, pdf_page_height, azure_page_width, azure_page_height
                            )
                        # addedの場合はdoc1には表示されない
                else:
                    # doc2側の処理
                    if diff.block2 and diff.block2.page == page_num:
                        if diff.change_type == "modified" and diff.block1:
                            # modifiedの場合は両方のブロックのテキストを比較
                            self._highlight_word_differences_azure(
                                new_page, azure_page, diff.block2, diff.block1, 
                                pdf_page_width, pdf_page_height, azure_page_width, azure_page_height
                            )
                        elif diff.change_type == "added":
                            # addedの場合はblock2のすべての単語をハイライト
                            self._highlight_all_words_in_block(
                                new_page, azure_page, diff.block2, 
                                pdf_page_width, pdf_page_height, azure_page_width, azure_page_height
                            )
                        # deletedの場合はdoc2には表示されない
        
        # 保存
        new_pdf_doc.save(str(output_path))
        new_pdf_doc.close()
        pdf_doc.close()
        logger.info(f"Created highlighted PDF with word-level differences: {output_path} (pages: 1-{max_diff_page + 1})")
    
    def _highlight_word_differences_azure(self, page, azure_page, block1, block2, 
                                        pdf_page_width, pdf_page_height,
                                        azure_page_width, azure_page_height):
        """Azure OCRの単語情報を使用して単語レベルの差分をハイライト"""
        import difflib
        
        # ブロックのテキストを取得
        text1 = block1.text
        text2 = block2.text
        
        # デバッグ出力
        logger.debug(f"Block1 text: {text1[:100]}...")
        logger.debug(f"Block2 text: {text2[:100]}...")
        # ブロックの座標をPDFの座標系に変換（ブロックの座標は既にポイント単位）
        block1_x = block1.bbox.x
        block1_y = block1.bbox.y
        block1_x2 = block1.bbox.x2
        block1_y2 = block1.bbox.y2
        
        logger.debug(f"Block1 bbox (original): x={block1.bbox.x:.2f}, y={block1.bbox.y:.2f}, x2={block1.bbox.x2:.2f}, y2={block1.bbox.y2:.2f}")
        logger.debug(f"Block1 bbox (PDF coords): x={block1_x:.2f}, y={block1_y:.2f}, x2={block1_x2:.2f}, y2={block1_y2:.2f}")
        logger.debug(f"PDF page size: width={pdf_page_width:.2f}, height={pdf_page_height:.2f}")
        logger.debug(f"Azure page size: width={azure_page_width:.2f}, height={azure_page_height:.2f}")
        
        # 文字レベルで差分を検出
        matcher = difflib.SequenceMatcher(None, text1, text2)
        
        # Azure OCRのページからブロック内の単語を抽出
        azure_words_in_block = []
        if hasattr(azure_page, 'words'):
            for word in azure_page.words:
                if hasattr(word, 'content') and hasattr(word, 'polygon'):
                    # 単語の座標を取得
                    polygon = word.polygon
                    if len(polygon) >= 4:
                        # Azure OCRの座標はインチ単位なのでポイントに変換
                        # polygon = [x1, y1, x2, y2, x3, y3, x4, y4]
                        x = polygon[0] * 72
                        y = polygon[1] * 72
                        x2 = polygon[4] * 72  # 右下のx座標
                        y2 = polygon[5] * 72  # 右下のy座標
                        
                        # ブロック内の単語かチェック（PDF座標系で比較）
                        if (x >= block1_x - 5 and y >= block1_y - 5 and 
                            x2 <= block1_x2 + 5 and y2 <= block1_y2 + 5):
                            azure_words_in_block.append({
                                'text': word.content,
                                'rect': fitz.Rect(x, y, x2, y2),
                                'start_pos': text1.find(word.content)  # テキスト内での位置
                            })
                            # 最初の数単語の座標をデバッグ出力
                            if len(azure_words_in_block) <= 3:
                                logger.debug(f"Word '{word.content}': x={x:.2f}, y={y:.2f}, x2={x2:.2f}, y2={y2:.2f}")
        
        logger.debug(f"Found {len(azure_words_in_block)} Azure words in block")
        
        # 差分がある文字範囲を収集
        diff_char_ranges = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ['replace', 'delete']:
                diff_char_ranges.append((i1, i2))
        
        logger.debug(f"Diff char ranges: {diff_char_ranges}")
        
        # 差分範囲に含まれる単語をハイライト
        for azure_word in azure_words_in_block:
            word_start = azure_word['start_pos']
            if word_start >= 0:  # 単語が見つかった場合
                word_end = word_start + len(azure_word['text'])
                
                # 差分範囲と重なるかチェック
                for diff_start, diff_end in diff_char_ranges:
                    if (word_start < diff_end and word_end > diff_start):  # 重なっている
                        # 単語をハイライト
                        page.draw_rect(azure_word['rect'], color=(1, 0, 0), width=1.5, fill=None)
                        break
    
    def _highlight_all_words_in_block(self, page, azure_page, block, 
                                     pdf_page_width, pdf_page_height,
                                     azure_page_width, azure_page_height):
        """ブロック内のすべての単語をハイライト（削除/追加されたブロック用）"""
        # ブロックの座標をPDFの座標系に変換（ブロックの座標は既にポイント単位）
        block_x = block.bbox.x
        block_y = block.bbox.y
        block_x2 = block.bbox.x2
        block_y2 = block.bbox.y2
        
        # Azure OCRのページから単語を抽出
        if hasattr(azure_page, 'words'):
            for word in azure_page.words:
                if hasattr(word, 'content') and hasattr(word, 'polygon'):
                    # 単語の座標を取得
                    polygon = word.polygon
                    if len(polygon) >= 4:
                        # Azure OCRの座標はインチ単位なのでポイントに変換
                        # polygon = [x1, y1, x2, y2, x3, y3, x4, y4]
                        x = polygon[0] * 72
                        y = polygon[1] * 72
                        x2 = polygon[4] * 72  # 右下のx座標
                        y2 = polygon[5] * 72  # 右下のy座標
                        
                        # ブロック内の単語かチェック（PDF座標系で比較）
                        if (x >= block_x - 5 and y >= block_y - 5 and 
                            x2 <= block_x2 + 5 and y2 <= block_y2 + 5):
                            # 単語を赤枠で囲む
                            word_rect = fitz.Rect(x, y, x2, y2)
                            page.draw_rect(word_rect, color=(1, 0, 0), width=1.5, fill=None)
    
    def _create_block_level_highlighted_pdf(self, pdf_doc, doc, differences, output_path, is_doc1):
        """ブロックレベルの差分ハイライト（フォールバック）"""
        # 差分があるページの最大値を取得
        max_diff_page = -1
        for diff in differences:
            if is_doc1 and diff.block1:
                max_diff_page = max(max_diff_page, diff.block1.page)
            elif not is_doc1 and diff.block2:
                max_diff_page = max(max_diff_page, diff.block2.page)
        
        # 差分がない場合は1ページ目だけ出力
        if max_diff_page == -1:
            max_diff_page = 0
        
        # 新しいPDFドキュメントを作成（必要なページだけ）
        new_pdf_doc = fitz.open()
        
        for page_num in range(min(max_diff_page + 1, len(pdf_doc))):
            # 元のページをコピー
            page = pdf_doc[page_num]
            new_page = new_pdf_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(new_page.rect, pdf_doc, page_num)
            
            for diff in differences:
                block = diff.block1 if is_doc1 else diff.block2
                if block and block.page == page_num:
                    rect = fitz.Rect(
                        block.bbox.x,
                        block.bbox.y,
                        block.bbox.x2,
                        block.bbox.y2
                    )
                    new_page.draw_rect(rect, color=(1, 0, 0), width=1.5, fill=None)
        
        new_pdf_doc.save(str(output_path))
        new_pdf_doc.close()
        pdf_doc.close()
    
    def _get_block_color(self, block_type: BlockType) -> tuple:
        """ブロックタイプに応じた色を返す"""
        color_map = {
            BlockType.HEADER: (0.5, 0.5, 0.5),      # グレー
            BlockType.FOOTER: (0.5, 0.5, 0.5),      # グレー
            BlockType.TITLE: (0, 0, 0.8),          # 濃い青
            BlockType.SUBTITLE: (0, 0.5, 0.8),     # 青
            BlockType.PARAGRAPH: (0, 0, 0),        # 黒
            BlockType.TABLE: (0.5, 0, 0.5),        # 紫
            BlockType.FIGURE: (0, 0.5, 0),         # 緑
            BlockType.CAPTION: (0, 0.7, 0),        # 薄緑
            BlockType.LIST: (0.5, 0.3, 0),         # 茶色
            BlockType.SIDEBAR: (0.7, 0.7, 0),      # 黄色
            BlockType.FOOTNOTE: (0.3, 0.3, 0.3),   # ダークグレー
            BlockType.PAGE_NUMBER: (0.7, 0.7, 0.7), # ライトグレー
            BlockType.UNKNOWN: (1, 0, 1)           # マゼンタ
        }
        return color_map.get(block_type, (0, 0, 0))
    
    def _create_parallel_pdf(self, pdf1_path: Path, pdf2_path: Path, output_path: Path):
        """2つのPDFを並列表示"""
        pdf1 = fitz.open(str(pdf1_path))
        pdf2 = fitz.open(str(pdf2_path))
        
        # 新しいPDFを作成
        new_pdf = fitz.open()
        
        # 実際に存在するページ数（ハイライトPDFは既に必要なページだけになっている）
        max_pages = max(len(pdf1), len(pdf2))
        
        for page_num in range(max_pages):
            # 元のページサイズを取得
            if page_num < len(pdf1):
                page1 = pdf1[page_num]
                width1 = page1.rect.width
                height1 = page1.rect.height
            else:
                width1 = 595  # A4幅のデフォルト
                height1 = 842  # A4高さのデフォルト
            
            if page_num < len(pdf2):
                page2 = pdf2[page_num]
                width2 = page2.rect.width
                height2 = page2.rect.height
            else:
                width2 = 595
                height2 = 842
            
            # 新しいページサイズ（横に並べる）
            new_width = width1 + width2 + 20  # 20ポイントの間隔
            new_height = max(height1, height2)
            
            # 新しいページを作成
            new_page = new_pdf.new_page(width=new_width, height=new_height)
            
            # 左側にページ1を配置
            if page_num < len(pdf1):
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, width1, height1),
                    pdf1,
                    page_num
                )
            
            # 右側にページ2を配置
            if page_num < len(pdf2):
                new_page.show_pdf_page(
                    fitz.Rect(width1 + 20, 0, width1 + 20 + width2, height2),
                    pdf2,
                    page_num
                )
        
        # 保存
        new_pdf.save(str(output_path))
        new_pdf.close()
        pdf1.close()
        pdf2.close()
        
        logger.info(f"Created parallel PDF: {output_path}")
    
    def _create_evaluation_document(self,
                                   differences: List[BlockDifference],
                                   summary: Dict[str, Any],
                                   pdf1_path: str,
                                   pdf2_path: str,
                                   output_path: Path):
        """評価用ドキュメントを生成"""
        content = []
        content.append("# LLM Docs Diff v5 - ブロックベース差分検出結果\n")
        content.append(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # ファイル情報
        content.append("## 比較ファイル\n")
        content.append(f"- ファイル1: {Path(pdf1_path).name}")
        content.append(f"- ファイル2: {Path(pdf2_path).name}\n")
        
        # サマリー
        content.append("## 差分サマリー\n")
        content.append(f"- 総差分数: {summary['total']}")
        
        content.append("\n### 変更タイプ別")
        for change_type, count in summary.get('by_type', {}).items():
            content.append(f"- {change_type}: {count}")
        
        content.append("\n### ページ別")
        for page, page_changes in summary.get('by_page', {}).items():
            content.append(f"\n#### ページ {page + 1}")
            for change_type, count in page_changes.items():
                content.append(f"- {change_type}: {count}")
        
        content.append("\n### ブロックタイプ別")
        for block_type, type_changes in summary.get('by_block_type', {}).items():
            content.append(f"\n#### {block_type}")
            for change_type, count in type_changes.items():
                content.append(f"- {change_type}: {count}")
        
        # 詳細な差分リスト
        content.append("\n## 差分詳細\n")
        for i, diff in enumerate(differences):
            content.append(f"\n### 差分 {i + 1}")
            content.append(f"- タイプ: {diff.change_type}")
            content.append(f"- 類似度: {diff.similarity:.2f}")
            
            if diff.block1:
                content.append(f"\n#### ドキュメント1のブロック")
                content.append(f"- ページ: {diff.block1.page + 1}")
                content.append(f"- タイプ: {diff.block1.block_type.value}")
                content.append(f"- 位置: ({diff.block1.bbox.x:.1f}, {diff.block1.bbox.y:.1f})")
                content.append(f"- サイズ: {diff.block1.bbox.width:.1f} x {diff.block1.bbox.height:.1f}")
                content.append(f"- テキスト: {diff.block1.text[:100]}...")
            
            if diff.block2:
                content.append(f"\n#### ドキュメント2のブロック")
                content.append(f"- ページ: {diff.block2.page + 1}")
                content.append(f"- タイプ: {diff.block2.block_type.value}")
                content.append(f"- 位置: ({diff.block2.bbox.x:.1f}, {diff.block2.bbox.y:.1f})")
                content.append(f"- サイズ: {diff.block2.bbox.width:.1f} x {diff.block2.bbox.height:.1f}")
                content.append(f"- テキスト: {diff.block2.text[:100]}...")
            
            if diff.details:
                content.append(f"\n#### 詳細")
                for key, value in diff.details.items():
                    content.append(f"- {key}: {value}")
        
        # ファイルに保存
        eval_path = output_path / "evaluation_document.md"
        with open(eval_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        
        logger.info(f"Created evaluation document: {eval_path}")
    
    def generate_detailed_report(self,
                               differences: List[BlockDifference],
                               doc1: DocumentStructure,
                               doc2: DocumentStructure,
                               summary: Dict[str, Any]) -> str:
        """詳細レポートを生成"""
        report = []
        report.append("# ブロックベース差分検出 - 詳細レポート\n")
        
        # 文書構造の比較
        report.append("## 文書構造の比較\n")
        report.append(f"### ドキュメント1")
        report.append(f"- ページ数: {doc1.pages}")
        report.append(f"- ブロック数: {len(doc1.blocks)}")
        report.append(f"- 言語: {doc1.metadata.get('language', 'unknown')}\n")
        
        report.append(f"### ドキュメント2")
        report.append(f"- ページ数: {doc2.pages}")
        report.append(f"- ブロック数: {len(doc2.blocks)}")
        report.append(f"- 言語: {doc2.metadata.get('language', 'unknown')}\n")
        
        # ブロックタイプの分布
        report.append("## ブロックタイプの分布\n")
        
        type_counts1 = {}
        for block in doc1.blocks:
            type_name = block.block_type.value
            type_counts1[type_name] = type_counts1.get(type_name, 0) + 1
        
        type_counts2 = {}
        for block in doc2.blocks:
            type_name = block.block_type.value
            type_counts2[type_name] = type_counts2.get(type_name, 0) + 1
        
        all_types = set(type_counts1.keys()) | set(type_counts2.keys())
        
        report.append("| ブロックタイプ | ドキュメント1 | ドキュメント2 | 差分 |")
        report.append("|--------------|-------------|-------------|------|")
        
        for block_type in sorted(all_types):
            count1 = type_counts1.get(block_type, 0)
            count2 = type_counts2.get(block_type, 0)
            diff = count2 - count1
            report.append(f"| {block_type} | {count1} | {count2} | {diff:+d} |")
        
        report.append("\n## 差分の詳細分析\n")
        
        # 変更タイプごとの分析
        for change_type in ['added', 'deleted', 'modified']:
            type_diffs = [d for d in differences if d.change_type == change_type]
            if not type_diffs:
                continue
            
            report.append(f"### {change_type.capitalize()} ({len(type_diffs)}件)\n")
            
            # ブロックタイプ別の内訳
            block_type_counts = {}
            for diff in type_diffs:
                block = diff.block2 if diff.block2 else diff.block1
                if block:
                    bt = block.block_type.value
                    block_type_counts[bt] = block_type_counts.get(bt, 0) + 1
            
            for bt, count in sorted(block_type_counts.items()):
                report.append(f"- {bt}: {count}件")
        
        return '\n'.join(report)