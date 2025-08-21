"""
出力ハンドラー
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


class OutputHandler:
    """出力処理を担当するハンドラー"""
    
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
        
        # 各ページでブロックを可視化
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            
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
                page.draw_rect(rect, color=color, width=1.0, fill=None)
                
                # ブロック番号を追加
                text_point = fitz.Point(block.bbox.x + 2, block.bbox.y + 10)
                page.insert_text(text_point, f"{block.reading_order}", fontsize=8, color=(0, 0, 0))
        
        # 保存
        pdf_doc.save(str(output_path))
        pdf_doc.close()
        logger.info(f"Created blocks visualization PDF: {output_path}")
    
    def _create_highlighted_pdf(self,
                               pdf_path: str,
                               doc: DocumentStructure,
                               differences: List[BlockDifference],
                               output_path: Path,
                               is_doc1: bool):
        """差分をハイライト表示したPDF生成（単語レベル）"""
        # PDFを開く
        pdf_doc = fitz.open(pdf_path)
        
        # 各ページで差分をハイライト
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            
            # 差分があるブロックを処理
            for diff in differences:
                # 両方のブロックが存在し、modifiedタイプの場合のみ単語レベル比較
                if diff.change_type == "modified" and diff.block1 and diff.block2:
                    # どちらのドキュメントのブロックを使うか
                    block = diff.block1 if is_doc1 else diff.block2
                    other_block = diff.block2 if is_doc1 else diff.block1
                    
                    if block.page == page_num:
                        # 単語レベルの差分をハイライト
                        self._highlight_word_differences(page, block, other_block, pdf_doc)
                else:
                    # added/deletedの場合はブロック全体を赤枠で囲む
                    block = diff.block1 if is_doc1 else diff.block2
                    if block and block.page == page_num:
                        # ブロックに含まれる全ての単語を取得してハイライト
                        words = self._extract_words_from_page(page, block.bbox)
                        for word_rect in words:
                            page.draw_rect(word_rect, color=(1, 0, 0), width=1.5, fill=None)
        
        # 保存
        pdf_doc.save(str(output_path))
        pdf_doc.close()
        logger.info(f"Created highlighted PDF with word-level differences: {output_path}")
    
    def _highlight_word_differences(self, page, block1, block2, pdf_doc):
        """単語レベルの差分をハイライト"""
        import difflib
        
        # ブロックのテキストを取得
        text1 = block1.text
        text2 = block2.text
        
        # デバッグ出力
        logger.debug(f"Block1 text: {text1[:100]}...")
        logger.debug(f"Block2 text: {text2[:100]}...")
        
        # 単語に分割
        words1 = text1.split()
        words2 = text2.split()
        
        logger.debug(f"Block1 words: {words1[:10]}...")
        logger.debug(f"Block2 words: {words2[:10]}...")
        
        # 差分を検出
        matcher = difflib.SequenceMatcher(None, words1, words2)
        
        # ページから単語の位置情報を取得
        page_words = self._extract_words_from_page(page, block1.bbox)
        
        logger.debug(f"Extracted {len(page_words)} words from page within block bbox")
        logger.debug(f"Block1 bbox: x={block1.bbox.x}, y={block1.bbox.y}, x2={block1.bbox.x2}, y2={block1.bbox.y2}")
        
        # 差分がある単語のインデックスを収集
        diff_indices = set()
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ['replace', 'delete']:
                for i in range(i1, i2):
                    diff_indices.add(i)
        
        logger.debug(f"Diff indices: {diff_indices}")
        
        # 差分がある単語を赤枠で囲む
        word_index = 0
        for word_rect in page_words:
            if word_index in diff_indices:
                page.draw_rect(word_rect, color=(1, 0, 0), width=1.5, fill=None)
            word_index += 1
    
    def _extract_words_from_page(self, page, block_bbox):
        """ページから指定ブロック内の単語の位置情報を抽出"""
        # PyMuPDFのget_text("words")を使用して単語情報を取得
        words = page.get_text("words")
        
        word_rects = []
        extracted_words = []  # デバッグ用
        
        for word in words:
            # word = (x0, y0, x1, y1, "word", block_no, line_no, word_no)
            x0, y0, x1, y1 = word[:4]
            word_text = word[4]
            
            # ブロック内の単語かチェック
            if (x0 >= block_bbox.x and y0 >= block_bbox.y and 
                x1 <= block_bbox.x2 and y1 <= block_bbox.y2):
                # 空白文字は除外
                if word_text.strip():
                    word_rects.append(fitz.Rect(x0, y0, x1, y1))
                    extracted_words.append(word_text)
        
        # デバッグ出力
        logger.debug(f"Extracted words in block: {extracted_words[:10]}...")
        logger.debug(f"Total words extracted: {len(extracted_words)}")
        
        return word_rects
    
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