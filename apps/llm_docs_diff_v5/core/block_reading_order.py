"""
ブロック内読み順序推定
各ブロック内でのテキスト要素の読み順序を推定し、ブロック間の順序も決定
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import numpy as np

from ..models.block_models import (
    Block, BlockType, LayoutRole, DocumentStructure, TextElement
)

logger = logging.getLogger(__name__)


class BlockReadingOrderEstimator:
    """ブロックベースの読み順序推定器"""
    
    def __init__(self,
                 column_threshold: float = 50.0,
                 line_height_ratio: float = 0.5,
                 use_visual_cues: bool = True):
        """
        Args:
            column_threshold: カラム検出の閾値
            line_height_ratio: 同一行判定の高さ比率
            use_visual_cues: 視覚的手がかり（フォントサイズなど）を使用するか
        """
        self.column_threshold = column_threshold
        self.line_height_ratio = line_height_ratio
        self.use_visual_cues = use_visual_cues
    
    def estimate_reading_order(self, doc_structure: DocumentStructure) -> DocumentStructure:
        """文書全体の読み順序を推定"""
        # 1. 各ブロック内の要素を並び替え
        for block in doc_structure.blocks:
            self._order_elements_in_block(block)
        
        # 2. ページごとにブロックの読み順序を決定
        for page_num in range(doc_structure.pages):
            page_blocks = doc_structure.get_blocks_by_page(page_num)
            self._order_blocks_in_page(page_blocks, page_num)
        
        return doc_structure
    
    def _order_elements_in_block(self, block: Block):
        """ブロック内の要素を読み順序で並び替え"""
        if not block.elements:
            return
        
        # ブロックタイプに応じた並び替え
        if block.block_type == BlockType.TABLE:
            # テーブルは左上から右下へ
            self._order_table_elements(block)
        elif block.block_type in [BlockType.LIST, BlockType.PARAGRAPH]:
            # リストや段落は行ごとに
            self._order_text_elements(block)
        else:
            # その他は基本的な並び替え
            self._order_text_elements(block)
    
    def _order_text_elements(self, block: Block):
        """テキスト要素を読み順序で並び替え"""
        elements = block.elements
        if len(elements) <= 1:
            return
        
        # 行にグループ化
        lines = self._group_into_lines(elements)
        
        # 行を上から下にソート
        sorted_lines = sorted(lines, key=lambda line: self._get_line_y(line))
        
        # 各行内で左から右にソート
        ordered_elements = []
        for line in sorted_lines:
            sorted_line = sorted(line, key=lambda elem: elem.bbox.x)
            ordered_elements.extend(sorted_line)
        
        # 元のリストを更新
        block.elements = ordered_elements
    
    def _order_table_elements(self, block: Block):
        """テーブル要素を並び替え（行優先）"""
        elements = block.elements
        if not elements:
            return
        
        # グリッドを検出
        rows = self._detect_table_rows(elements)
        
        ordered_elements = []
        for row in sorted(rows, key=lambda r: r['y']):
            # 行内で左から右にソート
            row_elements = sorted(row['elements'], key=lambda e: e.bbox.x)
            ordered_elements.extend(row_elements)
        
        block.elements = ordered_elements
    
    def _group_into_lines(self, elements: List[TextElement]) -> List[List[TextElement]]:
        """要素を行にグループ化"""
        if not elements:
            return []
        
        lines = []
        sorted_elements = sorted(elements, key=lambda e: (e.bbox.y, e.bbox.x))
        
        current_line = [sorted_elements[0]]
        current_y = sorted_elements[0].bbox.center_y
        
        for elem in sorted_elements[1:]:
            # 同じ行かチェック
            y_diff = abs(elem.bbox.center_y - current_y)
            height = max(elem.bbox.height, current_line[-1].bbox.height)
            
            if y_diff <= height * self.line_height_ratio:
                current_line.append(elem)
            else:
                lines.append(current_line)
                current_line = [elem]
                current_y = elem.bbox.center_y
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _detect_table_rows(self, elements: List[TextElement]) -> List[Dict[str, Any]]:
        """テーブルの行を検出"""
        rows = defaultdict(list)
        
        # Y座標でグループ化
        for elem in elements:
            # 近いY座標をグループ化
            y_key = int(elem.bbox.center_y / 10) * 10  # 10ポイント単位
            rows[y_key].append(elem)
        
        # 行情報を作成
        row_list = []
        for y_key, row_elements in rows.items():
            row_list.append({
                'y': y_key,
                'elements': row_elements
            })
        
        return row_list
    
    def _get_line_y(self, line: List[TextElement]) -> float:
        """行の代表Y座標を取得"""
        if not line:
            return 0.0
        return sum(elem.bbox.center_y for elem in line) / len(line)
    
    def _order_blocks_in_page(self, blocks: List[Block], page_num: int):
        """ページ内のブロックの読み順序を決定"""
        if not blocks:
            return
        
        # レイアウト解析
        layout_info = self._analyze_page_layout(blocks)
        
        # 読み順序を決定
        if layout_info['is_multi_column']:
            # マルチカラムレイアウト
            self._order_multi_column_blocks(blocks, layout_info)
        else:
            # シングルカラムまたは複雑なレイアウト
            self._order_single_column_blocks(blocks)
        
        # グローバルな順序を設定
        base_order = page_num * 1000  # ページごとにオフセット
        for i, block in enumerate(blocks):
            block.reading_order = base_order + i
    
    def _analyze_page_layout(self, blocks: List[Block]) -> Dict[str, Any]:
        """ページレイアウトを解析"""
        # メインコンテンツブロックのみを対象
        main_blocks = [b for b in blocks if b.layout_role == LayoutRole.MAIN_CONTENT]
        
        if len(main_blocks) < 2:
            return {'is_multi_column': False, 'columns': []}
        
        # X座標でクラスタリング
        x_positions = [b.bbox.x for b in main_blocks]
        columns = self._detect_columns(x_positions)
        
        return {
            'is_multi_column': len(columns) > 1,
            'columns': columns,
            'main_blocks': main_blocks
        }
    
    def _detect_columns(self, x_positions: List[float]) -> List[List[int]]:
        """X座標からカラムを検出"""
        if not x_positions:
            return []
        
        # 簡単なクラスタリング
        sorted_indices = sorted(range(len(x_positions)), key=lambda i: x_positions[i])
        columns = []
        current_column = [sorted_indices[0]]
        current_x = x_positions[sorted_indices[0]]
        
        for idx in sorted_indices[1:]:
            x = x_positions[idx]
            if abs(x - current_x) <= self.column_threshold:
                current_column.append(idx)
            else:
                columns.append(current_column)
                current_column = [idx]
                current_x = x
        
        if current_column:
            columns.append(current_column)
        
        return columns
    
    def _order_multi_column_blocks(self, blocks: List[Block], layout_info: Dict[str, Any]):
        """マルチカラムレイアウトのブロックを並び替え"""
        ordered_blocks = []
        
        # ヘッダーとフッターを最初と最後に
        header_blocks = [b for b in blocks if b.layout_role == LayoutRole.HEADER_CONTENT]
        footer_blocks = [b for b in blocks if b.layout_role == LayoutRole.FOOTER_CONTENT]
        main_blocks = layout_info['main_blocks']
        
        # ヘッダーを追加（上から下）
        ordered_blocks.extend(sorted(header_blocks, key=lambda b: b.bbox.y))
        
        # カラムごとに処理
        for column_indices in layout_info['columns']:
            column_blocks = [main_blocks[i] for i in column_indices if i < len(main_blocks)]
            # カラム内で上から下にソート
            ordered_blocks.extend(sorted(column_blocks, key=lambda b: b.bbox.y))
        
        # サイドコンテンツ
        side_blocks = [b for b in blocks if b.layout_role == LayoutRole.SIDE_CONTENT]
        ordered_blocks.extend(sorted(side_blocks, key=lambda b: (b.bbox.y, b.bbox.x)))
        
        # フッターを追加
        ordered_blocks.extend(sorted(footer_blocks, key=lambda b: b.bbox.y))
        
        # 順序を更新
        blocks.clear()
        blocks.extend(ordered_blocks)
    
    def _order_single_column_blocks(self, blocks: List[Block]):
        """シングルカラムレイアウトのブロックを並び替え"""
        # 役割とY座標でソート
        def sort_key(block):
            # 役割の優先順位
            role_priority = {
                LayoutRole.HEADER_CONTENT: 0,
                LayoutRole.MAIN_CONTENT: 1,
                LayoutRole.SIDE_CONTENT: 2,
                LayoutRole.FLOATING_CONTENT: 3,
                LayoutRole.FOOTER_CONTENT: 4
            }
            
            priority = role_priority.get(block.layout_role, 5)
            return (priority, block.bbox.y, block.bbox.x)
        
        blocks.sort(key=sort_key)
    
    def extract_text_in_reading_order(self, doc_structure: DocumentStructure) -> str:
        """読み順序に従ってテキストを抽出"""
        ordered_blocks = doc_structure.get_ordered_blocks()
        
        texts = []
        current_page = -1
        
        for block in ordered_blocks:
            # ページ区切り
            if block.page != current_page:
                if current_page >= 0:
                    texts.append("\n" + "="*50 + "\n")  # ページ区切り
                current_page = block.page
                texts.append(f"[Page {current_page + 1}]\n")
            
            # ブロックタイプに応じた前置き
            if block.block_type == BlockType.TITLE:
                texts.append(f"\n### {block.text} ###\n")
            elif block.block_type == BlockType.SUBTITLE:
                texts.append(f"\n## {block.text} ##\n")
            elif block.block_type == BlockType.TABLE:
                texts.append("\n[TABLE]\n")
                texts.append(block.text)
                texts.append("\n[/TABLE]\n")
            elif block.block_type == BlockType.FIGURE:
                texts.append(f"\n[FIGURE: {block.text}]\n")
            elif block.block_type == BlockType.LIST:
                texts.append(block.text + "\n")
            else:
                # 通常の段落
                texts.append(block.text + "\n")
        
        return "\n".join(texts)