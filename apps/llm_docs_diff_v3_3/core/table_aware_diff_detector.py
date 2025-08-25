"""
表構造を考慮した差分検出器
"""
from typing import List, Dict, Any, Tuple, Optional
import logging
from pathlib import Path

from .diff_detector_v3 import ContentBasedDiffDetector
from .table_matcher import TableMatcher, TableMatch
from .table_debug_handler import TableDebugHandler
from ..models.bbox_models import DiffResult, ChangeType, BBoxTextData
from ..models.table_models import TableDiffResult
from ..services.azure_service import AzureDocumentService

logger = logging.getLogger(__name__)


class TableAwareDiffDetector:
    """表構造を考慮した差分検出器"""
    
    def __init__(self, text_diff_detector: ContentBasedDiffDetector = None,
                 table_matcher: TableMatcher = None,
                 debug_dir: Optional[Path] = None):
        """
        Args:
            text_diff_detector: 通常テキスト用の差分検出器
            table_matcher: 表マッチング器
            debug_dir: デバッグ情報を保存するディレクトリ
        """
        self.text_diff_detector = text_diff_detector or ContentBasedDiffDetector(
            similarity_threshold=0.8,
            position_weight=0.0
        )
        self.table_matcher = table_matcher or TableMatcher()
        self.azure_service = AzureDocumentService()
        self.debug_handler = TableDebugHandler(debug_dir) if debug_dir else None
        # MeCab解析を有効化
        self.use_detailed_analysis = True
        if self.use_detailed_analysis:
            try:
                from .cell_text_analyzer import CellTextAnalyzer
                self.cell_analyzer = CellTextAnalyzer()
            except Exception as e:
                logger.warning(f"CellTextAnalyzer initialization failed: {e}")
                self.cell_analyzer = None
                self.use_detailed_analysis = False
        else:
            self.cell_analyzer = None
    
    def detect_differences_with_tables(self, 
                                     pdf1_bytes: bytes, 
                                     pdf2_bytes: bytes,
                                     all_text1: List[Dict[str, Any]], 
                                     all_text2: List[Dict[str, Any]]) -> Tuple[List[DiffResult], List[TableDiffResult]]:
        """表構造を考慮して差分を検出
        
        Args:
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            all_text1: 文書1の全テキスト（行またはパラグラフ）
            all_text2: 文書2の全テキスト（行またはパラグラフ）
            
        Returns:
            (通常テキストの差分, 表の差分)
        """
        # 1. 表を抽出
        logger.info("表を抽出中...")
        print("\n表の検出を開始...")
        tables1 = self.azure_service.extract_tables(pdf1_bytes)
        tables2 = self.azure_service.extract_tables(pdf2_bytes)
        logger.info(f"文書1: {len(tables1)}個の表, 文書2: {len(tables2)}個の表")
        print(f"\n検出された表の数:")
        print(f"  文書1: {len(tables1)}個の表")
        print(f"  文書2: {len(tables2)}個の表")
        
        # デバッグ: 各表の詳細を表示
        if tables1:
            print(f"\n文書1の表:")
            for i, table in enumerate(tables1[:5]):  # 最初の5個まで
                print(f"  表{i+1}: ページ{table['page']+1}, {table['row_count']}行×{table['column_count']}列")
                # 最初の行（ヘッダー）を表示
                header_cells = [cell for cell in table['cells'] if cell['row'] == 0]
                if header_cells:
                    header_texts = [cell['text'][:20] + '...' if len(cell['text']) > 20 else cell['text'] 
                                  for cell in sorted(header_cells, key=lambda x: x['column'])]
                    print(f"    ヘッダー: {' | '.join(header_texts)}")
        
        if tables2:
            print(f"\n文書2の表:")
            for i, table in enumerate(tables2[:5]):  # 最初の5個まで
                print(f"  表{i+1}: ページ{table['page']+1}, {table['row_count']}行×{table['column_count']}列")
                # 最初の行（ヘッダー）を表示
                header_cells = [cell for cell in table['cells'] if cell['row'] == 0]
                if header_cells:
                    header_texts = [cell['text'][:20] + '...' if len(cell['text']) > 20 else cell['text'] 
                                  for cell in sorted(header_cells, key=lambda x: x['column'])]
                    print(f"    ヘッダー: {' | '.join(header_texts)}")
        
        # 2. 表の差分を検出（先にマッチングを実行）
        logger.info("表の差分を検出中...")
        print("\n表のマッチングを開始...")
        table_diffs, matches = self._detect_table_differences(tables1, tables2)
        print(f"\n表の差分検出結果: {len(table_diffs)}件")
        
        # 3. マッチングした表のみを抽出
        matched_tables1 = []
        matched_tables2 = []
        for match in matches:
            matched_tables1.append(tables1[match.table1_index])
            matched_tables2.append(tables2[match.table2_index])
        
        # 4. テキストを表内・表外に分類（すべての表を使用して、表内テキストを除外）
        logger.info("テキストを表内・表外に分類中...")
        all_table_text1, non_table_text1 = self._classify_texts(all_text1, tables1)
        all_table_text2, non_table_text2 = self._classify_texts(all_text2, tables2)
        
        # マッチングした表のテキストのみを抽出
        matched_table_text1, _ = self._classify_texts(all_text1, matched_tables1)
        matched_table_text2, _ = self._classify_texts(all_text2, matched_tables2)
        
        logger.info(f"文書1: 表外テキスト{len(non_table_text1)}個, 全表内テキスト{len(all_table_text1)}個, マッチした表内テキスト{len(matched_table_text1)}個")
        logger.info(f"文書2: 表外テキスト{len(non_table_text2)}個, 全表内テキスト{len(all_table_text2)}個, マッチした表内テキスト{len(matched_table_text2)}個")
        
        # デバッグ情報を保存
        if self.debug_handler:
            logger.info("表検出のデバッグ情報を保存中...")
            self.debug_handler.save_table_detection_debug(tables1, tables2, matches, table_diffs)
        
        # 5. 表外テキストの差分を検出（マッチングしなかった表のテキストを含む）
        logger.info("表外テキストの差分を検出中...")
        text_diffs = self.text_diff_detector.detect_differences(non_table_text1, non_table_text2)
        
        # 表情報を保存（PDFハイライト用）
        self.tables1 = tables1
        self.tables2 = tables2
        
        return text_diffs, table_diffs
    
    def _classify_texts(self, all_texts: List[Dict[str, Any]], tables: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """テキストを表内・表外に分類"""
        table_regions = []
        for table in tables:
            # 各表の領域を記録（バウンディングボックスも含む）
            table_bbox = self._get_table_bounding_box(table)
            table_regions.append({
                'page': table['page'],
                'bbox': table_bbox,
                'cells': table['cells']
            })
        
        table_texts = []
        non_table_texts = []
        
        for text in all_texts:
            if self._is_inside_any_table(text, table_regions):
                table_texts.append(text)
            else:
                non_table_texts.append(text)
        
        logger.info(f"テキスト分類結果: 表内={len(table_texts)}, 表外={len(non_table_texts)}")
        
        return table_texts, non_table_texts
    
    def _get_table_bounding_box(self, table: Dict) -> List[float]:
        """表全体のバウンディングボックスを計算"""
        if not table.get('cells'):
            return [0, 0, 0, 0]
        
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for cell in table['cells']:
            bbox = cell.get('bbox', [])
            if len(bbox) >= 4:
                min_x = min(min_x, bbox[0])
                min_y = min(min_y, bbox[1])
                max_x = max(max_x, bbox[0] + bbox[2])
                max_y = max(max_y, bbox[1] + bbox[3])
        
        # 少しマージンを追加
        margin = 5
        return [
            max(0, min_x - margin),
            max(0, min_y - margin),
            max_x - min_x + 2 * margin,
            max_y - min_y + 2 * margin
        ]
    
    def _is_inside_any_table(self, text: Dict[str, Any], table_regions: List[Dict]) -> bool:
        """テキストが表内にあるかをバウンディングボックスで判定"""
        text_page = text.get('page', 0)
        text_bbox = text.get('bbox', [])
        
        if len(text_bbox) < 4:
            # バウンディングボックスがない場合は従来の方法にフォールバック
            logger.warning(f"テキストにバウンディングボックスがありません: {text.get('text', '')[:50]}")
            return False
        
        for region in table_regions:
            if region['page'] == text_page:
                table_bbox = region['bbox']
                if self._is_bbox_inside(text_bbox, table_bbox):
                    return True
        
        return False
    
    def _is_bbox_inside(self, inner_bbox: List[float], outer_bbox: List[float]) -> bool:
        """内側のバウンディングボックスが外側のバウンディングボックスに含まれるかチェック
        
        Args:
            inner_bbox: [x, y, width, height] 形式
            outer_bbox: [x, y, width, height] 形式
        """
        if len(inner_bbox) < 4 or len(outer_bbox) < 4:
            return False
        
        inner_x1, inner_y1 = inner_bbox[0], inner_bbox[1]
        inner_x2 = inner_x1 + inner_bbox[2]
        inner_y2 = inner_y1 + inner_bbox[3]
        
        outer_x1, outer_y1 = outer_bbox[0], outer_bbox[1]
        outer_x2 = outer_x1 + outer_bbox[2]
        outer_y2 = outer_y1 + outer_bbox[3]
        
        # 内側のボックスの中心点が外側のボックス内にあるかチェック
        inner_center_x = (inner_x1 + inner_x2) / 2
        inner_center_y = (inner_y1 + inner_y2) / 2
        
        return (outer_x1 <= inner_center_x <= outer_x2 and
                outer_y1 <= inner_center_y <= outer_y2)
    
    def _detect_table_differences(self, tables1: List[Dict], tables2: List[Dict]) -> Tuple[List[TableDiffResult], List[TableMatch]]:
        """表の差分を検出
        
        Returns:
            (表の差分リスト, マッチングリスト)
        """
        table_diffs = []
        
        # 表をマッチング
        matches = self.table_matcher.match_tables(tables1, tables2)
        
        print(f"\nマッチング結果: {len(matches)}個の表ペア")
        for match in matches[:5]:  # 最初の5件を表示
            t1 = tables1[match.table1_index]
            t2 = tables2[match.table2_index]
            print(f"  マッチ: 文書1の表{match.table1_index+1}(ページ{t1['page']+1}) ↔ 文書2の表{match.table2_index+1}(ページ{t2['page']+1})")
            # header_matchesが整数の場合とリストの場合の両方に対応
            header_match_count = match.header_matches if isinstance(match.header_matches, int) else len(match.header_matches)
            print(f"    類似度: {match.similarity_score:.2f}, ヘッダーマッチ: {header_match_count}個")
        
        # マッチした表の処理
        matched_indices1 = set()
        matched_indices2 = set()
        
        for match in matches:
            matched_indices1.add(match.table1_index)
            matched_indices2.add(match.table2_index)
            
            # マッチした表同士を比較
            table1 = tables1[match.table1_index]
            table2 = tables2[match.table2_index]
            
            diff = self._compare_matched_tables(table1, table2, match)
            if diff:
                table_diffs.append(diff)
                print(f"  差分検出: {diff.summary}")
        
        # マッチしなかった表は削除/追加として扱う
        unmatched1 = [i for i in range(len(tables1)) if i not in matched_indices1]
        unmatched2 = [i for i in range(len(tables2)) if i not in matched_indices2]
        
        if unmatched1:
            print(f"\nマッチしなかった文書1の表: {len(unmatched1)}個")
            for i in unmatched1[:3]:  # 最初の3件
                table = tables1[i]
                print(f"  表{i+1}: ページ{table['page']+1}, {table['row_count']}行×{table['column_count']}列")
        
        if unmatched2:
            print(f"\nマッチしなかった文書2の表: {len(unmatched2)}個")
            for i in unmatched2[:3]:  # 最初の3件
                table = tables2[i]
                print(f"  表{i+1}: ページ{table['page']+1}, {table['row_count']}行×{table['column_count']}列")
        
        for i in unmatched1:
            table = tables1[i]
            table_diffs.append(TableDiffResult(
                table_index1=i,
                table_index2=None,
                change_type=ChangeType.DELETION,
                structure_changes=[],
                cell_changes=[],
                summary=f"表が削除されました（{table['row_count']}行×{table['column_count']}列）"
            ))
        
        for i in unmatched2:
            table = tables2[i]
            table_diffs.append(TableDiffResult(
                table_index1=None,
                table_index2=i,
                change_type=ChangeType.ADDITION,
                structure_changes=[],
                cell_changes=[],
                summary=f"表が追加されました（{table['row_count']}行×{table['column_count']}列）"
            ))
        
        return table_diffs, matches
    
    def _compare_matched_tables(self, table1: Dict, table2: Dict, match: TableMatch) -> Optional[TableDiffResult]:
        """マッチした表同士を比較"""
        structure_changes = []
        cell_changes = []
        
        print(f"\n[デバッグ] 表の詳細比較: 表1-{match.table1_index+1} vs 表2-{match.table2_index+1}")
        print(f"  サイズ: {table1['row_count']}×{table1['column_count']} → {table2['row_count']}×{table2['column_count']}")
        
        # 構造の変更を検出
        if table1['row_count'] != table2['row_count']:
            diff = table2['row_count'] - table1['row_count']
            if diff > 0:
                structure_changes.append(f"{diff}行追加")
            else:
                structure_changes.append(f"{-diff}行削除")
        
        if table1['column_count'] != table2['column_count']:
            diff = table2['column_count'] - table1['column_count']
            if diff > 0:
                structure_changes.append(f"{diff}列追加")
            else:
                structure_changes.append(f"{-diff}列削除")
        
        # セル内容の比較
        cells1_map = self._create_cell_map(table1)
        cells2_map = self._create_cell_map(table2)
        
        print(f"  セル数: 表1={len(cells1_map)}, 表2={len(cells2_map)}")
        
        # ヘッダー行の差分を特別に表示
        header_changes = []
        for col in range(max(table1.get('column_count', 0), table2.get('column_count', 0))):
            cell1 = cells1_map.get((0, col))
            cell2 = cells2_map.get((0, col))
            
            if cell1 and cell2 and cell1['text'] != cell2['text']:
                header_changes.append(f"\u5217{col}: '{cell1['text']}' → '{cell2['text']}'")
            elif cell1 and not cell2:
                header_changes.append(f"\u5217{col}: '{cell1['text']}' が削除")
            elif not cell1 and cell2:
                header_changes.append(f"\u5217{col}: '{cell2['text']}' が追加")
        
        if header_changes:
            print(f"  ヘッダー変更: {', '.join(header_changes[:3])}{'...' if len(header_changes) > 3 else ''}")
        
        # 行見出し（1列目）でマッチングを行う
        row_mapping = self._match_rows_by_headers(table1, table2, cells1_map, cells2_map)
        
        print(f"  行マッチング: {len(row_mapping)}組")
        
        # マッチングに基づいてセル差分を検出
        matched_rows1 = set()
        matched_rows2 = set()
        modified_count = 0
        
        for row1, row2 in row_mapping.items():
            matched_rows1.add(row1)
            matched_rows2.add(row2)
            
            # 各列で比較
            for col in range(max(table1.get('column_count', 0), table2.get('column_count', 0))):
                cell1 = cells1_map.get((row1, col))
                cell2 = cells2_map.get((row2, col))
                
                if cell1 and cell2:
                    if cell1['text'] != cell2['text']:
                        # 詳細な差分情報
                        cell_change_data = {
                            'row': row1,  # 表1の行番号
                            'row2': row2,  # 表2の行番号を追加
                            'column': col,
                            'old_text': cell1['text'],
                            'new_text': cell2['text'],
                            'change_type': 'modified'
                        }
                        
                        # MeCab解析が有効な場合は詳細解析を追加
                        if self.use_detailed_analysis and self.cell_analyzer:
                            try:
                                detailed_diff = self.cell_analyzer.analyze_cell_diff(
                                    cell1['text'], 
                                    cell2['text']
                                )
                                cell_change_data['detailed_diff'] = detailed_diff
                            except Exception as e:
                                logger.warning(f"Detailed analysis failed: {e}")
                        
                        cell_changes.append(cell_change_data)
                        modified_count += 1
                        
                        # 最初の3件をデバッグ表示
                        if modified_count <= 3:
                            print(f"    セル[{row1},{col}]変更: '{cell1['text'][:30]}...' → '{cell2['text'][:30]}...'")
                            if self.use_detailed_analysis and 'detailed_diff' in cell_change_data:
                                detailed_diff = cell_change_data['detailed_diff']
                                if detailed_diff.get('segments'):
                                    print(f"      差分タイプ: {detailed_diff['diff_type']}")
                                    for seg in detailed_diff['segments'][:2]:  # 最初の2セグメント
                                        if seg['type'] != 'unchanged':
                                            text_to_show = seg.get('old_text') or seg.get('text') or seg.get('new_text') or ''
                                            print(f"      - {seg['type']}: {text_to_show[:20]}...")
                elif cell1 and not cell2:
                    # 列が削除された
                    cell_changes.append({
                        'row': row1,
                        'column': col,
                        'old_text': cell1['text'],
                        'new_text': None,
                        'change_type': 'deleted'
                    })
                elif not cell1 and cell2:
                    # 列が追加された
                    cell_changes.append({
                        'row': row1,  # 表1の行番号（存在しないが一貫性のため）
                        'row2': row2,  # 表2の行番号
                        'column': col,
                        'old_text': None,
                        'new_text': cell2['text'],
                        'change_type': 'added'
                    })
        
        # マッチしなかった行を処理
        for row in range(table1['row_count']):
            if row not in matched_rows1:
                # 行全体が削除された
                for col in range(table1['column_count']):
                    cell = cells1_map.get((row, col))
                    if cell:
                        cell_changes.append({
                            'row': row,
                            'column': col,
                            'old_text': cell['text'],
                            'new_text': None,
                            'change_type': 'deleted'
                        })
        
        for row in range(table2['row_count']):
            if row not in matched_rows2:
                # 行全体が追加された
                for col in range(table2['column_count']):
                    cell = cells2_map.get((row, col))
                    if cell:
                        cell_changes.append({
                            'row': None,  # 表1には存在しない
                            'row2': row,  # 表2の行番号
                            'column': col,
                            'old_text': None,
                            'new_text': cell['text'],
                            'change_type': 'added'
                        })
        
        # 変更がない場合はNoneを返す
        if not structure_changes and not cell_changes:
            print(f"  → 変更なし")
            return None
        
        print(f"  変更サマリー: 構造変更={len(structure_changes)}, セル変更={len(cell_changes)}")
        
        # サマリーを作成
        summary_parts = []
        if structure_changes:
            summary_parts.append(f"構造変更: {', '.join(structure_changes)}")
        if cell_changes:
            summary_parts.append(f"セル変更: {len(cell_changes)}個")
        
        result = TableDiffResult(
            table_index1=match.table1_index,
            table_index2=match.table2_index,
            change_type=ChangeType.MODIFICATION,
            structure_changes=structure_changes,
            cell_changes=cell_changes,
            summary='; '.join(summary_parts)
        )
        
        print(f"  → {result.summary}")
        return result
    
    def _create_cell_map(self, table: Dict) -> Dict[Tuple[int, int], Dict]:
        """セルの位置をキーとしたマップを作成"""
        cell_map = {}
        for cell in table['cells']:
            key = (cell['row'], cell['column'])
            cell_map[key] = cell
        return cell_map
    
    def _match_rows_by_headers(self, table1: Dict, table2: Dict, 
                               cells1_map: Dict, cells2_map: Dict) -> Dict[int, int]:
        """行見出し（1列目）を使って行をマッチング
        
        Returns:
            {table1の行番号: table2の行番号} のマッピング
        """
        from .table_matcher import TableMatcher
        
        # 各表の行見出しを抽出（0行目はヘッダーなので1行目から）
        rows1_headers = []
        for row in range(1, table1['row_count']):  # ヘッダー行をスキップ
            cell = cells1_map.get((row, 0))  # 1列目
            if cell:
                rows1_headers.append((row, cell['text']))
        
        rows2_headers = []
        for row in range(1, table2['row_count']):  # ヘッダー行をスキップ
            cell = cells2_map.get((row, 0))  # 1列目
            if cell:
                rows2_headers.append((row, cell['text']))
        
        print(f"  行見出し: 表1={len(rows1_headers)}行, 表2={len(rows2_headers)}行")
        
        # TableMatcherのインスタンスを使用してテキスト類似度を計算
        matcher = TableMatcher()
        
        # 全ペアの類似度を計算
        valid_matches = []
        for i, (row1, text1) in enumerate(rows1_headers):
            for j, (row2, text2) in enumerate(rows2_headers):
                similarity = matcher._text_similarity(text1, text2)
                
                if similarity >= matcher.cell_similarity_threshold:  # 0.8以上
                    valid_matches.append({
                        'row1': row1,
                        'row2': row2,
                        'text1': text1,
                        'text2': text2,
                        'similarity': similarity
                    })
        
        # 類似度の高い順にソート
        valid_matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        # 最適なマッチングを選択（各行は一度だけマッチ）
        row_mapping = {}
        used_rows2 = set()
        
        for match in valid_matches:
            if match['row1'] not in row_mapping and match['row2'] not in used_rows2:
                row_mapping[match['row1']] = match['row2']
                used_rows2.add(match['row2'])
                if len(row_mapping) <= 3:  # 最初の3件をデバッグ表示
                    print(f"    行マッチ: 行{match['row1']} '{match['text1'][:20]}...' ↔ 行{match['row2']} '{match['text2'][:20]}...' (類似度: {match['similarity']:.2f})")
        
        # ヘッダー行（0行目）は常にマッチさせる
        row_mapping[0] = 0
        
        return row_mapping