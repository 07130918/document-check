"""
表マッチングアルゴリズム
総当たりでヘッダーの類似度を計算し、0.8以上のセルをマッチング
"""
from typing import List, Dict, Any, Tuple, Optional
import logging
from dataclasses import dataclass
import Levenshtein
import re
import unicodedata

logger = logging.getLogger(__name__)


@dataclass
class TableMatch:
    """表のマッチング結果"""
    table1_index: int
    table2_index: int
    similarity_score: float
    header_matches: List[Dict[str, Any]]
    structure_similarity: float
    position_distance: float
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（JSON化可能）"""
        return {
            "table1_index": self.table1_index,
            "table2_index": self.table2_index,
            "similarity_score": self.similarity_score,
            "header_matches": len(self.header_matches) if isinstance(self.header_matches, list) else self.header_matches,
            "structure_similarity": self.structure_similarity,
            "position_distance": self.position_distance
        }


class TableMatcher:
    """表マッチング処理"""
    
    def __init__(self, cell_similarity_threshold: float = 0.8):
        """
        Args:
            cell_similarity_threshold: セルマッチングの閾値（デフォルト0.8）
        """
        self.cell_similarity_threshold = cell_similarity_threshold
    
    def match_tables(self, tables1: List[Dict], tables2: List[Dict]) -> List[TableMatch]:
        """2つの文書の表をマッチング
        
        Args:
            tables1: 文書1の表リスト
            tables2: 文書2の表リスト
            
        Returns:
            マッチング結果のリスト
        """
        matches = []
        
        # ステップ1: 全ての表ペアで構造的類似度を計算
        similarity_groups = self._group_by_structural_similarity(tables1, tables2)
        
        # ステップ2: 類似グループ内で位置ベースのマッチング
        for group in similarity_groups:
            if len(group['candidates']) == 1:
                # 候補が1つの場合は自動的にマッチ
                match = TableMatch(
                    table1_index=group['source_index'],
                    table2_index=group['candidates'][0]['index'],
                    similarity_score=group['candidates'][0]['similarity'],
                    header_matches=group['candidates'][0]['header_matches'],
                    structure_similarity=group['candidates'][0]['structure_similarity'],
                    position_distance=0.0
                )
                matches.append(match)
            else:
                # 複数候補がある場合は位置で判定
                best_match = self._find_best_match_by_position(
                    group['source'], 
                    group['source_index'],
                    group['candidates']
                )
                if best_match:
                    matches.append(best_match)
        
        return matches
    
    def _group_by_structural_similarity(self, tables1: List[Dict], tables2: List[Dict]) -> List[Dict]:
        """構造的類似度でグルーピング"""
        groups = []
        
        for i, t1 in enumerate(tables1):
            similar_tables = []
            
            for j, t2 in enumerate(tables2):
                # ヘッダー類似度を計算
                header_similarity, header_matches = self._calculate_header_similarity(t1, t2)
                
                # サイズ類似度を計算
                size_similarity = self._calculate_size_similarity(t1, t2)
                
                # 1列目（行見出し）の類似度も計算
                row_header_similarity = self._calculate_row_header_similarity(t1, t2)
                
                # 総合的な構造類似度（1列目の重みも追加）
                structure_similarity = header_similarity * 0.5 + row_header_similarity * 0.3 + size_similarity * 0.2
                
                # より厳格な条件：構造類似度が高く、かつヘッダーマッチが2個以上
                header_match_count = len(header_matches) if isinstance(header_matches, list) else 0
                if structure_similarity > 0.6 and header_match_count >= 2:  # 閾値を少し下げる
                    similar_tables.append({
                        'index': j,
                        'table': t2,
                        'similarity': structure_similarity,
                        'header_similarity': header_similarity,
                        'header_matches': header_match_count,
                        'structure_similarity': structure_similarity
                    })
                
                # デバッグ: 表23の場合の詳細を表示
                if i == 23 and j in [22, 27]:
                    logger.info(f"表23 vs 表{j}: ヘッダー類似度={header_similarity:.3f}, "
                              f"サイズ類似度={size_similarity:.3f}, 行見出し類似度={row_header_similarity:.3f}, "
                              f"構造類似度={structure_similarity:.3f}, ヘッダーマッチ数={header_match_count}")
            
            if similar_tables:
                # 類似度の高い順にソート
                similar_tables.sort(key=lambda x: x['similarity'], reverse=True)
                groups.append({
                    'source': t1,
                    'source_index': i,
                    'candidates': similar_tables
                })
                
                # デバッグ: 表23の候補を表示
                if i == 23:
                    logger.info(f"表23の候補数: {len(similar_tables)}")
                    for cand in similar_tables:
                        logger.info(f"  候補表{cand['index']}: 類似度={cand['similarity']:.3f}")
        
        return groups
    
    def _calculate_header_similarity(self, table1: Dict, table2: Dict) -> Tuple[float, List[Dict]]:
        """ヘッダー行の類似度を計算（総当たり）
        
        Returns:
            (類似度スコア, マッチングリスト)
        """
        header1 = self._get_first_row_cells(table1)
        header2 = self._get_first_row_cells(table2)
        
        if not header1 or not header2:
            return 0.0, []
        
        # 全セルペアの類似度を計算（閾値以上のみ）
        valid_matches = []
        
        for i, cell1 in enumerate(header1):
            for j, cell2 in enumerate(header2):
                similarity = self._text_similarity(cell1, cell2)
                
                if similarity >= self.cell_similarity_threshold:
                    valid_matches.append({
                        'index1': i,
                        'index2': j,
                        'cell1': cell1,
                        'cell2': cell2,
                        'similarity': similarity
                    })
        
        # 最適なマッチングを選択
        final_matches = self._find_best_cell_matching(valid_matches, len(header1), len(header2))
        
        # スコアを計算
        score = self._calculate_matching_score(final_matches, len(header1), len(header2))
        
        return score, final_matches
    
    def _get_first_row_cells(self, table: Dict) -> List[str]:
        """最初の行のセルテキストを取得"""
        cells = []
        for cell in table['cells']:
            if cell['row'] == 0:
                cells.append((cell['column'], cell['text']))
        
        # 列順でソート
        cells.sort(key=lambda x: x[0])
        return [text for _, text in cells]
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """テキスト類似度を計算（0～1.0）"""
        # 前処理
        text1 = self._normalize_text(text1)
        text2 = self._normalize_text(text2)
        
        # 完全一致
        if text1 == text2:
            return 1.0
        
        # 空文字列の処理
        if not text1 or not text2:
            return 0.0
        
        # 部分文字列マッチ
        if text1 in text2 or text2 in text1:
            shorter = min(len(text1), len(text2))
            longer = max(len(text1), len(text2))
            base_score = shorter / longer
            
            # 部分一致ボーナス
            if base_score > 0.7:
                return min(0.9, base_score + 0.1)
            return base_score
        
        # 編集距離ベース
        distance = Levenshtein.distance(text1, text2)
        max_len = max(len(text1), len(text2))
        similarity = 1.0 - (distance / max_len)
        
        return max(0, similarity)
    
    def _normalize_text(self, text: str) -> str:
        """テキストを正規化"""
        # 空白の統一
        text = re.sub(r'\s+', ' ', text.strip())
        # 全角・半角の統一
        text = unicodedata.normalize('NFKC', text)
        # 括弧の統一
        text = text.replace('（', '(').replace('）', ')')
        return text
    
    def _find_best_cell_matching(self, valid_matches: List[Dict], len1: int, len2: int) -> List[Dict]:
        """貪欲法で最適なマッチングを選択"""
        # 類似度の高い順にソート
        sorted_matches = sorted(valid_matches, key=lambda x: x['similarity'], reverse=True)
        
        used_indices1 = set()
        used_indices2 = set()
        final_matches = []
        
        for match in sorted_matches:
            i1 = match['index1']
            i2 = match['index2']
            
            # 両方のインデックスが未使用の場合のみ選択
            if i1 not in used_indices1 and i2 not in used_indices2:
                final_matches.append(match)
                used_indices1.add(i1)
                used_indices2.add(i2)
        
        return final_matches
    
    def _calculate_matching_score(self, matches: List[Dict], total_cells1: int, total_cells2: int) -> float:
        """マッチングスコアを計算"""
        # マッチしたセルの数
        matched_count = len(matches)
        
        if matched_count == 0:
            return 0.0
        
        # マッチしたセルの平均類似度
        avg_similarity = sum(m['similarity'] for m in matches) / matched_count
        
        # カバレッジ（どれだけのセルがマッチしたか）
        coverage1 = matched_count / total_cells1 if total_cells1 > 0 else 0
        coverage2 = matched_count / total_cells2 if total_cells2 > 0 else 0
        min_coverage = min(coverage1, coverage2)
        
        # 総合スコア
        # - 平均類似度: 50%
        # - カバレッジ: 50%
        final_score = (avg_similarity * 0.5) + (min_coverage * 0.5)
        
        return final_score
    
    def _calculate_size_similarity(self, table1: Dict, table2: Dict) -> float:
        """表サイズの類似度を計算"""
        row_diff = abs(table1['row_count'] - table2['row_count'])
        col_diff = abs(table1['column_count'] - table2['column_count'])
        
        # 差が大きいほど類似度が下がる（より厳格に）
        row_similarity = 1.0 / (1.0 + row_diff * 0.3)  # 行の違いをより重視
        col_similarity = 1.0 / (1.0 + col_diff * 0.4)  # 列の違いも重視
        
        # 行数が2倍以上違う場合は追加ペナルティ
        row_ratio = max(table1['row_count'], table2['row_count']) / max(min(table1['row_count'], table2['row_count']), 1)
        if row_ratio > 2:
            row_similarity *= 0.5
        
        return (row_similarity + col_similarity) / 2
    
    def _find_best_match_by_position(self, source_table: Dict, source_index: int, 
                                    candidates: List[Dict]) -> Optional[TableMatch]:
        """構造類似度と位置を総合的に考慮して最適なマッチを見つける"""
        best_match = None
        best_score = float('-inf')
        
        # デバッグ: 表23の場合
        if source_index == 23:
            logger.info(f"表23の位置ベースマッチング開始")
        
        for candidate in candidates:
            distance = self._calculate_position_distance(source_table, candidate['table'])
            
            # 構造類似度を主要因、位置を副要因として総合スコアを計算
            # 構造類似度: 0.0〜1.0
            # 距離ペナルティ: 距離を正規化（100で割る）
            structure_weight = 0.9  # 構造をさらに重視
            position_weight = 0.1   # 位置の影響を小さくする
            
            # 距離を0〜1の範囲に正規化（距離が大きいほど0に近づく）
            normalized_distance = 1.0 / (1.0 + distance / 100.0)
            
            # 総合スコア
            total_score = (candidate['similarity'] * structure_weight + 
                          normalized_distance * position_weight)
            
            # デバッグ: 表23の場合の詳細
            if source_index == 23:
                logger.info(f"  候補表{candidate['index']}: 構造類似度={candidate['similarity']:.3f}, "
                          f"距離={distance:.1f}, 正規化距離={normalized_distance:.3f}, "
                          f"総合スコア={total_score:.3f}")
            
            if total_score > best_score:
                best_score = total_score
                best_match = TableMatch(
                    table1_index=source_index,
                    table2_index=candidate['index'],
                    similarity_score=candidate['similarity'],
                    header_matches=candidate['header_matches'],
                    structure_similarity=candidate['structure_similarity'],
                    position_distance=distance
                )
        
        # デバッグ: 表23の最終選択
        if source_index == 23 and best_match:
            logger.info(f"表23の最終マッチ: 表{best_match.table2_index} (スコア={best_score:.3f})")
        
        return best_match
    
    def _calculate_position_distance(self, table1: Dict, table2: Dict) -> float:
        """表の位置の距離を計算"""
        # ページ番号の差
        page_diff = abs(table1['page'] - table2['page'])
        
        # ページのズレに比例したペナルティ（指数関数的ではなく線形）
        # 1ページのズレごとに100のペナルティ
        base_penalty = page_diff * 100.0
        
        # 同じページの場合、バウンディングボックスの中心点の距離も考慮
        if page_diff == 0 and table1.get('bbox') and table2.get('bbox'):
            bbox1 = table1['bbox']
            bbox2 = table2['bbox']
            
            # 中心点を計算
            center1_x = bbox1[0] + bbox1[2] / 2
            center1_y = bbox1[1] + bbox1[3] / 2
            center2_x = bbox2[0] + bbox2[2] / 2
            center2_y = bbox2[1] + bbox2[3] / 2
            
            # ユークリッド距離
            spatial_distance = ((center1_x - center2_x) ** 2 + (center1_y - center2_y) ** 2) ** 0.5
            
            # インチ単位の距離をポイント換算（1インチ = 72ポイント）
            return base_penalty + spatial_distance * 72
        
        return base_penalty
    
    def _calculate_row_header_similarity(self, table1: Dict, table2: Dict) -> float:
        """1列目（行見出し）の類似度を計算
        
        Args:
            table1: 表1
            table2: 表2
            
        Returns:
            類似度スコア（0～1.0）
        """
        # 1列目のセルを取得
        col1_cells1 = []
        col1_cells2 = []
        
        for cell in table1['cells']:
            if cell['column'] == 0 and cell['row'] > 0:  # ヘッダー行をスキップ
                col1_cells1.append((cell['row'], cell['text']))
        
        for cell in table2['cells']:
            if cell['column'] == 0 and cell['row'] > 0:  # ヘッダー行をスキップ
                col1_cells2.append((cell['row'], cell['text']))
        
        if not col1_cells1 or not col1_cells2:
            return 0.0
        
        # 行順でソート
        col1_cells1.sort(key=lambda x: x[0])
        col1_cells2.sort(key=lambda x: x[0])
        
        texts1 = [text for _, text in col1_cells1]
        texts2 = [text for _, text in col1_cells2]
        
        # マッチング数を計算
        match_count = 0
        for text1 in texts1:
            for text2 in texts2:
                if self._text_similarity(text1, text2) >= self.cell_similarity_threshold:
                    match_count += 1
                    break
        
        # 類似度スコア
        # サイズの差が大きい場合はペナルティを与える
        size_diff = abs(len(texts1) - len(texts2))
        size_penalty = 1.0 / (1.0 + size_diff * 0.2)  # サイズ差が大きいほどペナルティ
        
        # カバレッジベースのスコア（小さい方の表に対するカバレッジ）
        coverage_score = match_count / min(len(texts1), len(texts2)) if min(len(texts1), len(texts2)) > 0 else 0
        
        # 最終スコア = カバレッジ × サイズペナルティ
        score = coverage_score * size_penalty
        return score