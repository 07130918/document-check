"""
表検出のデバッグ情報を出力するハンドラー
"""
import json
from pathlib import Path
from typing import List, Dict, Any
import logging

from ..models.table_models import TableDiffResult
from .table_matcher import TableMatch

logger = logging.getLogger(__name__)


class TableDebugHandler:
    """表検出のデバッグ情報を管理"""
    
    def __init__(self, debug_dir: Path):
        """
        Args:
            debug_dir: デバッグ情報を保存するディレクトリ
        """
        self.debug_dir = debug_dir
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        # 表用のサブディレクトリを作成
        self.tables_dir = debug_dir / "tables"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
    
    def save_table_detection_debug(self, 
                                 tables1: List[Dict], 
                                 tables2: List[Dict],
                                 matches: List[TableMatch],
                                 table_diffs: List[TableDiffResult]):
        """表検出のデバッグ情報を保存
        
        Args:
            tables1: 文書1の表リスト
            tables2: 文書2の表リスト
            matches: マッチング結果
            table_diffs: 表の差分結果
        """
        # 1. 表の検出結果を保存
        self._save_detected_tables(tables1, tables2)
        
        # 2. マッチング結果を保存
        self._save_matching_results(tables1, tables2, matches)
        
        # 3. 表の差分詳細を保存
        self._save_table_diffs(table_diffs)
        
        # 4. 表のサンプルをCSV形式で保存
        self._save_table_samples(tables1, tables2)
    
    def _save_detected_tables(self, tables1: List[Dict], tables2: List[Dict]):
        """検出された表の情報を保存"""
        detection_info = {
            "document1": {
                "total_tables": len(tables1),
                "tables": []
            },
            "document2": {
                "total_tables": len(tables2),
                "tables": []
            }
        }
        
        # 文書1の表情報
        for i, table in enumerate(tables1):
            table_info = {
                "index": i,
                "page": table['page'] + 1,  # 1-indexed
                "rows": table['row_count'],
                "columns": table['column_count'],
                "cell_count": len(table['cells']),
                "header": self._get_header_row(table)
            }
            detection_info["document1"]["tables"].append(table_info)
        
        # 文書2の表情報
        for i, table in enumerate(tables2):
            table_info = {
                "index": i,
                "page": table['page'] + 1,  # 1-indexed
                "rows": table['row_count'],
                "columns": table['column_count'],
                "cell_count": len(table['cells']),
                "header": self._get_header_row(table)
            }
            detection_info["document2"]["tables"].append(table_info)
        
        # JSONファイルとして保存
        output_path = self.debug_dir / "table_detection.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(detection_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved table detection debug info to {output_path}")
    
    def _save_matching_results(self, tables1: List[Dict], tables2: List[Dict], matches: List[TableMatch]):
        """マッチング結果を保存"""
        matching_info = {
            "total_matches": len(matches),
            "matches": [],
            "unmatched_tables1": [],
            "unmatched_tables2": []
        }
        
        # マッチした表
        matched_indices1 = set()
        matched_indices2 = set()
        
        for match in matches:
            matched_indices1.add(match.table1_index)
            matched_indices2.add(match.table2_index)
            
            table1 = tables1[match.table1_index]
            table2 = tables2[match.table2_index]
            
            match_info = {
                "table1_index": match.table1_index,
                "table2_index": match.table2_index,
                "table1_page": table1['page'] + 1,
                "table2_page": table2['page'] + 1,
                "similarity_score": match.similarity_score,
                "header_matches": match.header_matches if isinstance(match.header_matches, int) else len(match.header_matches),
                "structure_similarity": match.structure_similarity,
                "position_distance": match.position_distance,
                "table1_size": f"{table1['row_count']}x{table1['column_count']}",
                "table2_size": f"{table2['row_count']}x{table2['column_count']}"
            }
            matching_info["matches"].append(match_info)
        
        # マッチしなかった表
        for i, table in enumerate(tables1):
            if i not in matched_indices1:
                matching_info["unmatched_tables1"].append({
                    "index": i,
                    "page": table['page'] + 1,
                    "size": f"{table['row_count']}x{table['column_count']}",
                    "header": self._get_header_row(table)
                })
        
        for i, table in enumerate(tables2):
            if i not in matched_indices2:
                matching_info["unmatched_tables2"].append({
                    "index": i,
                    "page": table['page'] + 1,
                    "size": f"{table['row_count']}x{table['column_count']}",
                    "header": self._get_header_row(table)
                })
        
        # JSONファイルとして保存
        output_path = self.debug_dir / "table_matching.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(matching_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved table matching debug info to {output_path}")
    
    def _save_table_diffs(self, table_diffs: List[TableDiffResult]):
        """表の差分詳細を保存"""
        diff_info = {
            "total_diffs": len(table_diffs),
            "diffs": []
        }
        
        for diff in table_diffs:
            diff_detail = {
                "table1_index": diff.table_index1,
                "table2_index": diff.table_index2,
                "change_type": diff.change_type.value,
                "summary": diff.summary,
                "structure_changes": diff.structure_changes,
                "cell_changes": diff.cell_changes[:10] if diff.cell_changes else []  # 最初の10件
            }
            diff_info["diffs"].append(diff_detail)
        
        # JSONファイルとして保存
        output_path = self.debug_dir / "table_diffs.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(diff_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved table diffs debug info to {output_path}")
    
    def _save_table_samples(self, tables1: List[Dict], tables2: List[Dict]):
        """表のサンプルをCSV形式で保存"""
        # 文書1の表サンプル
        for i, table in enumerate(tables1):
            self._save_single_table_csv(table, f"table1_{i+1}.csv")
        
        # 文書2の表サンプル
        for i, table in enumerate(tables2):
            self._save_single_table_csv(table, f"table2_{i+1}.csv")
    
    def _save_single_table_csv(self, table: Dict, filename: str):
        """単一の表をCSV形式で保存"""
        output_path = self.tables_dir / filename
        
        # 表を再構築
        grid = [['' for _ in range(table['column_count'])] for _ in range(table['row_count'])]
        
        for cell in table['cells']:
            row = cell['row']
            col = cell['column']
            if row < table['row_count'] and col < table['column_count']:
                grid[row][col] = cell['text']
        
        # CSVとして保存
        with open(output_path, 'w', encoding='utf-8') as f:
            for row in grid:
                # CSVエスケープ
                escaped_row = []
                for cell in row:
                    if ',' in cell or '"' in cell or '\n' in cell:
                        escaped_row.append(f'"{cell.replace('"', '""')}"')
                    else:
                        escaped_row.append(cell)
                f.write(','.join(escaped_row) + '\n')
        
        # 詳細な表構造をJSONで保存（kind情報を含む）
        json_path = self.tables_dir / filename.replace('.csv', '_structure.json')
        table_structure = {
            "size": f"{table['row_count']}x{table['column_count']}",
            "page": table['page'] + 1,
            "cells": []
        }
        
        for cell in table['cells']:
            cell_info = {
                "row": cell['row'],
                "column": cell['column'],
                "text": cell['text'],
                "kind": cell.get('kind', 'content'),  # セルの種類
                "row_span": cell.get('row_span', 1),
                "column_span": cell.get('column_span', 1)
            }
            table_structure["cells"].append(cell_info)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(table_structure, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved table sample to {output_path} and structure to {json_path}")
    
    def _get_header_row(self, table: Dict) -> List[str]:
        """表の最初の行（ヘッダー）を取得"""
        header_cells = []
        for cell in table['cells']:
            if cell['row'] == 0:
                header_cells.append((cell['column'], cell['text']))
        
        # 列順でソート
        header_cells.sort(key=lambda x: x[0])
        return [text for _, text in header_cells]