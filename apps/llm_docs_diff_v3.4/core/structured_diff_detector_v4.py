"""
構造化差分検出器 v4 - Document Intelligence構造化データに対応
座標に依存せず、セクション階層とテキスト類似度で差分検出
"""
from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import difflib
from models.bbox_models import DiffResult, ChangeType
import logging

logger = logging.getLogger(__name__)


@dataclass
class RichSectionMatch:
    """デバッガーで見やすいセクションマッチング結果"""
    index1: int
    index2: int  
    similarity: float
    # 文言情報
    title1: str
    title2: str
    contents1: List[str]  # para_contents_list
    contents2: List[str]
    paragraph_count1: int
    paragraph_count2: int
    
    def __repr__(self):
        return f"SectionMatch({self.title1} ↔ {self.title2}, sim={self.similarity:.3f})"


@dataclass  
class RichParagraphDiff:
    """デバッガーで見やすい段落差分結果"""
    index1: int
    index2: int
    diff_type: str  # 'modified', 'deleted', 'added'
    # 文言情報
    content1: str
    content2: str
    role1: Optional[str]
    role2: Optional[str]
    importance1: str
    importance2: str
    coordinates1: Optional[Dict]
    coordinates2: Optional[Dict]
    # 類似度スコア
    content_similarity: float
    coordinate_similarity: float
    total_similarity: float
    
    def __repr__(self):
        if self.diff_type == 'modified':
            return f"Modified: '{self.content1}' → '{self.content2}' (content={self.content_similarity:.3f}, coord={self.coordinate_similarity:.3f}, total={self.total_similarity:.3f})"
        elif self.diff_type == 'deleted':
            return f"Deleted: '{self.content1}'"
        else:
            return f"Added: '{self.content2}'"


@dataclass
class RichParagraphMatch:
    """デバッガーで見やすい段落マッチング結果"""
    index1: int
    index2: int
    similarity: float
    content_similarity: float
    coordinate_similarity: float
    # 文言情報
    content1: str
    content2: str
    role1: Optional[str] 
    role2: Optional[str]
    match_reason: str  # "完全一致", "内容類似", "座標近接"など
    
    def __repr__(self):
        return f"Match[{self.index1}↔{self.index2}]: '{self.content1[:30]}...' → '{self.content2[:30]}...' ({self.similarity:.3f})"


class MatchResult:
    """段落マッチング結果を格納するクラス（tuple互換性あり）"""
    
    def __init__(self, i: int, j: int, sim: float, content1: str, content2: str):
        self.data = (i, j, sim)
        self.content1 = content1
        self.content2 = content2
    
    def __iter__(self):
        return iter(self.data)
    
    def __getitem__(self, index):
        return self.data[index]
    
    def __repr__(self):
        content1_short = self.content1 if len(self.content1) > 30 else self.content1
        content2_short = self.content2 if len(self.content2) > 30 else self.content2
        return f"MatchResult({self.data[0]}, {self.data[1]}, {self.data[2]:.3f}, '{content1_short}', '{content2_short}')"

class StructuredDiffDetectorV4:
    """構造化データ用差分検出器"""
    
    def __init__(self, 
                 similarity_threshold: float = 0.8,
                 exact_match_bonus: float = 0.2,
                 section_weight: float = 0.3):
        """
        Args:
            similarity_threshold: 類似度の閾値
            exact_match_bonus: 完全一致時のボーナススコア
            section_weight: セクション階層の重み
        """
        self.similarity_threshold = similarity_threshold
        self.exact_match_bonus = exact_match_bonus
        self.section_weight = section_weight
        
        # デバッガー用プロパティ
        self.debug_section_matches: List[RichSectionMatch] = []
        self.debug_paragraph_diffs: List[RichParagraphDiff] = []  
        self.debug_paragraph_matches: List[RichParagraphMatch] = []
    
    def detect_easy_differences(self, 
                      doc1_analysis: Dict[str, Any], 
                      doc2_analysis: Dict[str, Any]) -> List[DiffResult]:
        """para_contents_listを使用した簡易差分検出
        
        Args:
            doc1_analysis: 文書1の解析結果（sections含む）
            doc2_analysis: 文書2の解析結果（sections含む）
            
        Returns:
            検出された差分のリスト
        """
        
        doc1_sections = doc1_analysis.get('sections', [])
        doc2_sections = doc2_analysis.get('sections', [])
        
        logger.info(f"簡易差分検出開始: 文書1={len(doc1_sections)}セクション, 文書2={len(doc2_sections)}セクション")
        
        if not doc1_sections and not doc2_sections:
            logger.warning("両文書とも検出項目がありません")
            return []
        
        if not doc1_sections:
            logger.info("文書1が空です。文書2の全項目を追加として処理")
            return self._create_additions_from_sections(doc2_sections)
        
        if not doc2_sections:
            logger.info("文書2が空です。文書1の全項目を削除として処理")
            return self._create_deletions_from_sections(doc1_sections)
        
        results = []
        
        # 1. セクションレベルでのマッチング
        section_matches = self._match_sections(doc1_sections, doc2_sections)
        logger.info(f"セクションマッチング: {len(section_matches)}件")
        
        # 2. マッチしたセクション内での段落マッチング
        matched_section_indices1 = set()
        matched_section_indices2 = set()
        
        for section_match in section_matches:
            section1 = doc1_sections[section_match.index1]
            section2 = doc2_sections[section_match.index2]
            
            # インデックス範囲チェック用
            paragraphs1 = section1.get('paragraphs', [])
            paragraphs2 = section2.get('paragraphs', [])
            
            logger.debug(f"セクションマッチ: '{section_match.title1}' -> '{section_match.title2}' (類似度: {section_match.similarity:.3f})")
            logger.debug(f"  段落数確認: section1={len(paragraphs1)}段落, section2={len(paragraphs2)}段落")
            
            # リッチな段落マッチングを使用
            paragraph_matches = self._match_paragraphs_in_section(section1, section2)
            logger.debug(f"  段落マッチング: {len(paragraph_matches)}件")
            
            # マッチした段落から差分を抽出
            matched_para_indices1 = set()
            matched_para_indices2 = set()
            
            for paragraph_match in paragraph_matches:
                para1 = paragraphs1[paragraph_match.index1]
                para2 = paragraphs2[paragraph_match.index2]
                
                logger.debug(f"  段落マッチ詳細: {paragraph_match}")
                
                if paragraph_match.content1 != paragraph_match.content2:
                    # 詳細な文字列差分を抽出
                    text_differences = self._extract_text_differences(para1, para2)
                    
                    # 各差分箇所に対してDiffResultを作成
                    for diff_detail in text_differences:
                        original_coords = diff_detail.get('original_coordinates')
                        modified_coords = diff_detail.get('modified_coordinates')
                        
                        original_bbox = None
                        if diff_detail['original_content']:
                            original_bbox = {
                                'content': diff_detail['original_content'],
                                'coordinates': original_coords,
                                'paragraph_index': para1.get('paragraph_index'),
                                'role': para1.get('role'),
                                'importance': para1.get('importance'),
                                'page': para1.get('page', section1.get('page', 2))
                            }
                        
                        modified_bbox = None
                        if diff_detail['modified_content']:
                            modified_bbox = {
                                'content': diff_detail['modified_content'],
                                'coordinates': modified_coords,
                                'paragraph_index': para2.get('paragraph_index'),
                                'role': para2.get('role'),
                                'importance': para2.get('importance'),
                                'page': para2.get('page', section2.get('page', 2))
                            }
                        
                        result = DiffResult(
                            change_type=diff_detail['change_type'],
                            page=para1.get('page', section1.get('page', 2)),
                            original_bbox=original_bbox,
                            modified_bbox=modified_bbox,
                            semantic_similarity=paragraph_match.similarity
                        )
                        
                        results.append(result)
                
                matched_para_indices1.add(paragraph_match.index1)
                matched_para_indices2.add(paragraph_match.index2)
            
            # マッチしなかった段落を削除/追加として処理
            for para_idx, para in enumerate(paragraphs1):
                if para_idx not in matched_para_indices1:
                    result = DiffResult(
                        change_type=ChangeType.DELETION,
                        page=para.get('page', section1.get('page', 2)),
                        original_bbox=para,
                        modified_bbox=None,
                        semantic_similarity=0.0
                    )
                    results.append(result)
            
            for para_idx, para in enumerate(paragraphs2):
                if para_idx not in matched_para_indices2:
                    result = DiffResult(
                        change_type=ChangeType.ADDITION,
                        page=para.get('page', section2.get('page', 2)),
                        original_bbox=None,
                        modified_bbox=para,
                        semantic_similarity=0.0
                    )
                    results.append(result)
            
            matched_section_indices1.add(section_match.index1)
            matched_section_indices2.add(section_match.index2)
        
        # 3. マッチしなかったセクション全体の処理（セクション削除/追加）
        for sec_idx, section in enumerate(doc1_sections):
            if sec_idx not in matched_section_indices1:
                # セクション全体の削除
                for para in section.get('paragraphs', []):
                    result = DiffResult(
                        change_type=ChangeType.DELETION,
                        page=para.get('page', section.get('page', 2)),
                        original_bbox=para,
                        modified_bbox=None,
                        semantic_similarity=0.0
                    )
                    results.append(result)
                logger.debug(f"セクション削除: '{section.get('title', '')}'")
        
        for sec_idx, section in enumerate(doc2_sections):
            if sec_idx not in matched_section_indices2:
                # セクション全体の追加
                for para in section.get('paragraphs', []):
                    result = DiffResult(
                        change_type=ChangeType.ADDITION,
                        page=para.get('page', section.get('page', 2)),
                        original_bbox=None,
                        modified_bbox=para,
                        semantic_similarity=0.0
                    )
                    results.append(result)
                logger.debug(f"セクション追加: '{section.get('title', '')}'")
        
        logger.info(f"簡易差分検出完了: {len(results)}件")
        return self._sort_results(results)


    def detect_differences(self, 
                          doc1_analysis: Dict[str, Any], 
                          doc2_analysis: Dict[str, Any]) -> List[DiffResult]:
        """構造化データベースで差分を検出
        
        Args:
            doc1_analysis: 文書1の解析結果（sections含む）
            doc2_analysis: 文書2の解析結果（sections含む）
            
        Returns:
            検出された差分のリスト
        """
        
        doc1_sections = doc1_analysis.get('sections', [])
        doc2_sections = doc2_analysis.get('sections', [])
        
        logger.info(f"前処理結果: 文書1={len(doc1_sections)}セクション, 文書2={len(doc2_sections)}セクション")
        
        if not doc1_sections and not doc2_sections:
            logger.warning("両文書とも検出項目がありません")
            return []
        
        if not doc1_sections:
            logger.info("文書1が空です。文書2の全項目を追加として処理")
            return self._create_additions_from_sections(doc2_sections)
        
        if not doc2_sections:
            logger.info("文書2が空です。文書1の全項目を削除として処理")
            return self._create_deletions_from_sections(doc1_sections)
        
        results = []
        
        # 1. セクションレベルでのマッチング
        section_matches = self._match_sections(doc1_sections, doc2_sections)
        logger.info(f"セクションマッチング: {len(section_matches)}件")
        
        # 2. マッチしたセクション内での段落マッチング
        matched_section_indices1 = set()
        matched_section_indices2 = set()
        
        for section_match in section_matches:
            section1 = doc1_sections[section_match.index1]
            section2 = doc2_sections[section_match.index2]
            
            logger.debug(f"セクションマッチ: '{section_match.title1}' -> '{section_match.title2}' (類似度: {section_match.similarity:.3f})")
            
            # セクション内の段落マッチング
            paragraph_matches = self._match_paragraphs_in_section(section1, section2)
            logger.debug(f"  段落マッチング: {len(paragraph_matches)}件")
            
            # 段落レベルでの差分を処理
            matched_para_indices1 = set()
            matched_para_indices2 = set()
            
            for paragraph_match in paragraph_matches:
                para1 = section1['paragraphs'][paragraph_match.index1]
                para2 = section2['paragraphs'][paragraph_match.index2]
                
                if paragraph_match.similarity < 1.0 and para1["content"] != para2["content"]:
                    # 詳細な文字列差分を抽出
                    text_differences = self._extract_text_differences(para1, para2)
                    
                    logger.debug(f"  文字列差分: {len(text_differences)}件")
                    
                    # 各差分箇所に対してDiffResultを作成
                    for diff_detail in text_differences:
                        # 差分箇所の座標を使用
                        original_coords = diff_detail.get('original_coordinates')
                        modified_coords = diff_detail.get('modified_coordinates')
                        
                        # 差分コンテンツのみを含むbboxオブジェクトを作成
                        original_bbox = None
                        if diff_detail['original_content']:
                            original_bbox = {
                                'content': diff_detail['original_content'],
                                'coordinates': original_coords,
                                'paragraph_index': para1.get('paragraph_index'),
                                'role': para1.get('role'),
                                'importance': para1.get('importance'),
                                'page': para1.get('page', section1.get('page', 2))
                            }
                        
                        modified_bbox = None
                        if diff_detail['modified_content']:
                            modified_bbox = {
                                'content': diff_detail['modified_content'],
                                'coordinates': modified_coords,
                                'paragraph_index': para2.get('paragraph_index'),
                                'role': para2.get('role'),
                                'importance': para2.get('importance'),
                                'page': para2.get('page', section2.get('page', 2))
                            }
                        
                        result = DiffResult(
                            change_type=diff_detail['change_type'],
                            page=para1.get('page', section1.get('page', 2)),
                            original_bbox=original_bbox,
                            modified_bbox=modified_bbox,
                            semantic_similarity=paragraph_match.similarity
                        )
                        
                        results.append(result)
                
                matched_para_indices1.add(paragraph_match.index1)
                matched_para_indices2.add(paragraph_match.index2)
            
            # マッチしなかった段落を削除/追加として処理
            for para_idx, para in enumerate(section1.get('paragraphs', [])):
                if para_idx not in matched_para_indices1:
                    result = DiffResult(
                        change_type=ChangeType.DELETION,
                        page=para.get('page', section1.get('page', 2)),
                        original_bbox=para,
                        modified_bbox=None,
                        semantic_similarity=0.0
                    )
                    results.append(result)
            
            for para_idx, para in enumerate(section2.get('paragraphs', [])):
                if para_idx not in matched_para_indices2:
                    result = DiffResult(
                        change_type=ChangeType.ADDITION,
                        page=para.get('page', section2.get('page', 2)),
                        original_bbox=None,
                        modified_bbox=para,
                        semantic_similarity=0.0
                    )
                    results.append(result)
            
            matched_section_indices1.add(section_match.index1)
            matched_section_indices2.add(section_match.index2)
        
        logger.info(f"差分検出: {len(results)}件")
        return self._sort_results(results)
    
    def _match_sections(self, doc1_sections: List[Dict[str, Any]], 
                       doc2_sections: List[Dict[str, Any]]) -> List[RichSectionMatch]:
        """セクション間のマッチングをpara_contents_list内容の類似度で実行
        
        Args:
            doc1_sections: 文書1のセクションリスト
            doc2_sections: 文書2のセクションリスト
            
        Returns:
            RichSectionMatchオブジェクトのリスト
        """
        matches = []
        
        # 全組み合わせでセクション内容の類似度を計算
        for i, section1 in enumerate(doc1_sections):
            for j, section2 in enumerate(doc2_sections):
                # para_contents_listを取得
                contents1 = section1.get('para_contents_list', [])
                contents2 = section2.get('para_contents_list', [])
                
                # 空のコンテンツリストはスキップ
                if not contents1 or not contents2:
                    continue
                
                # セクション内容を結合してテキスト化
                text1 = ' '.join(contents1).strip()
                text2 = ' '.join(contents2).strip()
                
                if not text1 or not text2:
                    continue
                
                # 完全一致の場合は高スコア
                if text1 == text2:
                    similarity = 1.0 + self.exact_match_bonus
                else:
                    # difflib使用のセクション内容類似度計算
                    similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
                
                if similarity >= self.similarity_threshold:
                    matches.append((i, j, similarity, section1, section2))
        
        # 類似度でソートして最適なマッチングを選択
        matches.sort(key=lambda x: x[2], reverse=True)
        
        # 重複を除去（1対1対応）
        used_i = set()
        used_j = set()
        final_matches = []
        
        for i, j, sim, section1, section2 in matches:
            if i not in used_i and j not in used_j:
                # RichSectionMatchオブジェクトを作成
                rich_match = RichSectionMatch(
                    index1=i, index2=j, similarity=sim,
                    title1=section1.get('title', ''),
                    title2=section2.get('title', ''),
                    contents1=section1.get('para_contents_list', []),
                    contents2=section2.get('para_contents_list', []),
                    paragraph_count1=section1.get('paragraph_count', 0),
                    paragraph_count2=section2.get('paragraph_count', 0)
                )
                final_matches.append(rich_match)
                used_i.add(i)
                used_j.add(j)
        
        # デバッガー用に保存
        self.debug_section_matches = final_matches
        return final_matches

    def _match_paragraphs_in_section(self, section1: Dict[str, Any], 
                               section2: Dict[str, Any]) -> List[RichParagraphMatch]:
        """セクション内の段落をcontentとcoordinatesでマッチング
        
        Args:
            section1: 文書1のセクション
            section2: 文書2のセクション
            
        Returns:
            RichParagraphMatchオブジェクトのリスト
        """
        paragraphs1 = section1.get('paragraphs', [])
        paragraphs2 = section2.get('paragraphs', [])
        
        if not paragraphs1 or not paragraphs2:
            return []
        
        matches = []
        
        # 全組み合わせで類似度を計算
        for i, para1 in enumerate(paragraphs1):
            for j, para2 in enumerate(paragraphs2):
                content_sim = self._calculate_content_similarity(para1, para2)
                coord_sim = self._calculate_coordinate_similarity(para1, para2)
                
                # ハイブリッド類似度（content重視、coordinates補助）
                hybrid_similarity = 0.7 * content_sim + 0.3 * coord_sim
                
                if hybrid_similarity >= self.similarity_threshold:
                    matches.append((i, j, hybrid_similarity, content_sim, coord_sim, para1, para2))
        
        # 類似度でソートして最適なマッチングを選択
        matches.sort(key=lambda x: x[2], reverse=True)
        
        # 重複を除去（1対1対応）
        used_i = set()
        used_j = set()
        final_matches = []
        
        for i, j, sim, content_sim, coord_sim, para1, para2 in matches:
            if i not in used_i and j not in used_j:
                # マッチ理由を判定
                match_reason = self._determine_match_reason(content_sim, coord_sim)
                
                # RichParagraphMatchオブジェクトを作成
                rich_match = RichParagraphMatch(
                    index1=i, index2=j, similarity=sim,
                    content_similarity=content_sim,
                    coordinate_similarity=coord_sim,
                    content1=para1.get('content', ''),
                    content2=para2.get('content', ''),
                    role1=para1.get('role'),
                    role2=para2.get('role'),
                    match_reason=match_reason
                )
                final_matches.append(rich_match)
                used_i.add(i)
                used_j.add(j)
        
        # デバッガー用に保存
        self.debug_paragraph_matches = final_matches
        return final_matches
    
    def _determine_match_reason(self, content_sim: float, coord_sim: float) -> str:
        """マッチング理由を分析
        
        Args:
            content_sim: コンテンツ類似度
            coord_sim: 座標類似度
            
        Returns:
            マッチング理由の説明
        """
        reasons = []
        
        if content_sim >= 0.95:
            reasons.append("内容完全一致")
        elif content_sim >= 0.9:
            reasons.append("内容ほぼ一致")
        elif content_sim >= 0.8:
            reasons.append("内容高類似")
        elif content_sim >= 0.6:
            reasons.append("内容類似")
        
        if coord_sim >= 0.9:
            reasons.append("座標完全一致")
        elif coord_sim >= 0.7:
            reasons.append("座標近接")
        elif coord_sim >= 0.5:
            reasons.append("座標類似")
        
        return " + ".join(reasons) if reasons else "低類似"
    
    def _calculate_content_similarity(self, para1: Dict[str, Any], 
                                    para2: Dict[str, Any]) -> float:
        """段落のcontent類似度を計算"""
        content1 = para1.get('content', '').strip()
        content2 = para2.get('content', '').strip()
        
        if not content1 and not content2:
            return 0.0
        if not content1 or not content2:
            return 0.0
        
        # 完全一致
        if content1 == content2:
            return 1.0
        
        # difflib使用の文字列類似度
        return difflib.SequenceMatcher(None, content1, content2).ratio()
    
    def _calculate_coordinate_similarity(self, para1: Dict[str, Any], 
                                       para2: Dict[str, Any]) -> float:
        """段落の座標類似度を計算"""
        coords1 = para1.get('coordinates', {})
        coords2 = para2.get('coordinates', {})
        
        if not coords1 or not coords2:
            return 0.0
        
        # 各座標要素の差分を計算
        left_diff = abs(coords1.get('left', 0) - coords2.get('left', 0))
        top_diff = abs(coords1.get('top', 0) - coords2.get('top', 0))
        right_diff = abs(coords1.get('right', 0) - coords2.get('right', 0))
        bottom_diff = abs(coords1.get('bottom', 0) - coords2.get('bottom', 0))
        
        # 平均差分を計算（値が小さいほど類似）
        avg_diff = (left_diff + top_diff + right_diff + bottom_diff) / 4
        
        # 差分を類似度スコアに変換（差分が0なら1.0、差分が大きいほど0に近づく）
        similarity = max(0.0, 1.0 - avg_diff)
        
        return similarity

    def _extract_text_differences(self, para1: Dict[str, Any], para2: Dict[str, Any]) -> List[Dict[str, Any]]:
        """段落間の詳細な文字列差分を抽出
        
        Args:
            para1: 文書1の段落
            para2: 文書2の段落
            
        Returns:
            差分箇所のリスト（content, coordinates含む）
        """
        import difflib
        
        content1 = para1.get('content', '')
        content2 = para2.get('content', '')
        
        if content1 == content2:
            return []
        
        differences = []
        
        # 文字レベルの差分を取得
        matcher = difflib.SequenceMatcher(None, content1, content2)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ['replace', 'delete', 'insert']:
                # 変更された部分の文字列を取得
                original_text = content1[i1:i2] if tag in ['replace', 'delete'] else ''
                modified_text = content2[j1:j2] if tag in ['replace', 'insert'] else ''
                
                # 座標を推定（文字位置に基づく）
                original_coords = self._estimate_text_coordinates(
                    para1, original_text, i1, i2
                ) if original_text else None
                
                modified_coords = self._estimate_text_coordinates(
                    para2, modified_text, j1, j2
                ) if modified_text else None
                
                differences.append({
                    'change_type': self._determine_change_type(tag),
                    'original_content': original_text,
                    'modified_content': modified_text,
                    'original_coordinates': original_coords,
                    'modified_coordinates': modified_coords,
                    'original_paragraph': para1,
                    'modified_paragraph': para2
                })
        
        return differences
    
    def _estimate_text_coordinates(self, paragraph: Dict[str, Any], 
                                  text: str, start_pos: int, end_pos: int) -> Optional[Dict[str, Any]]:
        """段落内のテキスト位置から座標を推定
        
        Args:
            paragraph: 段落データ
            text: 対象テキスト
            start_pos: テキスト開始位置
            end_pos: テキスト終了位置
            
        Returns:
            推定座標
        """
        if not paragraph.get('coordinates'):
            return None
        
        para_coords = paragraph['coordinates']
        full_content = paragraph.get('content', '')
        
        if not full_content or end_pos > len(full_content):
            return para_coords  # 推定できない場合は段落全体の座標を返す
        
        # 文字位置の比率を計算
        content_length = len(full_content)
        start_ratio = start_pos / content_length if content_length > 0 else 0
        end_ratio = end_pos / content_length if content_length > 0 else 1
        
        # 座標を比例配分で推定（横方向のみ、縦方向は段落全体を使用）
        left = para_coords.get('left', 0)
        right = para_coords.get('right', left + para_coords.get('width', 0))
        width = right - left
        
        estimated_left = left + (width * start_ratio)
        estimated_right = left + (width * end_ratio)
        
        return {
            'left': estimated_left,
            'top': para_coords.get('top', 0),
            'right': estimated_right,
            'bottom': para_coords.get('bottom', para_coords.get('top', 0) + para_coords.get('height', 0)),
            'width': estimated_right - estimated_left,
            'height': para_coords.get('height', 0)
        }
    
    def _determine_change_type(self, diff_tag: str) -> 'ChangeType':
        """差分タグから変更タイプを決定"""
        if diff_tag == 'replace':
            return ChangeType.MODIFICATION
        elif diff_tag == 'delete':
            return ChangeType.DELETION
        elif diff_tag == 'insert':
            return ChangeType.ADDITION
        else:
            return ChangeType.MODIFICATION

    def _find_paragraph_differences_by_content_list(self, section1: Dict[str, Any], 
                                                  section2: Dict[str, Any]) -> List[RichParagraphDiff]:
        """para_contents_listを使用してセクション内の段落差分を特定
        
        Args:
            section1: 文書1のセクション
            section2: 文書2のセクション
            
        Returns:
            RichParagraphDiffオブジェクトのリスト
        """
        contents1 = section1.get('para_contents_list', [])
        contents2 = section2.get('para_contents_list', [])
        paragraphs1 = section1.get('paragraphs', [])
        paragraphs2 = section2.get('paragraphs', [])
        
        if not contents1 and not contents2:
            return []
        
        differences = []
        
        # difflib.SequenceMatcherを使用してリスト間の差分を検出
        import difflib
        matcher = difflib.SequenceMatcher(None, contents1, contents2)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # 修正: 同じ範囲で内容が変更
                for k in range(max(i2-i1, j2-j1)):
                    idx1 = i1 + k if i1 + k < i2 else None
                    idx2 = j1 + k if j1 + k < j2 else None
                    
                    # 段落データを取得
                    para1 = paragraphs1[idx1] if idx1 is not None and idx1 < len(paragraphs1) else {}
                    para2 = paragraphs2[idx2] if idx2 is not None and idx2 < len(paragraphs2) else {}
                    
                    if idx1 is not None and idx2 is not None:
                        # 類似度を計算
                        content_sim = self._calculate_content_similarity(para1, para2)
                        coord_sim = self._calculate_coordinate_similarity(para1, para2)
                        total_sim = 0.7 * content_sim + 0.3 * coord_sim
                        
                        rich_diff = RichParagraphDiff(
                            index1=idx1, index2=idx2, diff_type='modified',
                            content1=para1.get('content', ''),
                            content2=para2.get('content', ''),
                            role1=para1.get('role'),
                            role2=para2.get('role'),
                            importance1=para1.get('importance', ''),
                            importance2=para2.get('importance', ''),
                            coordinates1=para1.get('coordinates'),
                            coordinates2=para2.get('coordinates'),
                            content_similarity=content_sim,
                            coordinate_similarity=coord_sim,
                            total_similarity=total_sim
                        )
                        differences.append(rich_diff)
                    elif idx1 is not None:
                        rich_diff = RichParagraphDiff(
                            index1=idx1, index2=-1, diff_type='deleted',
                            content1=para1.get('content', ''),
                            content2='',
                            role1=para1.get('role'), role2=None,
                            importance1=para1.get('importance', ''), importance2='',
                            coordinates1=para1.get('coordinates'), coordinates2=None,
                            content_similarity=0.0,
                            coordinate_similarity=0.0,
                            total_similarity=0.0
                        )
                        differences.append(rich_diff)
                    elif idx2 is not None:
                        rich_diff = RichParagraphDiff(
                            index1=-1, index2=idx2, diff_type='added',
                            content1='',
                            content2=para2.get('content', ''),
                            role1=None, role2=para2.get('role'),
                            importance1='', importance2=para2.get('importance', ''),
                            coordinates1=None, coordinates2=para2.get('coordinates'),
                            content_similarity=0.0,
                            coordinate_similarity=0.0,
                            total_similarity=0.0
                        )
                        differences.append(rich_diff)
                        
            elif tag == 'delete':
                # 削除: 文書1にのみ存在
                for k in range(i1, i2):
                    para1 = paragraphs1[k] if k < len(paragraphs1) else {}
                    rich_diff = RichParagraphDiff(
                        index1=k, index2=-1, diff_type='deleted',
                        content1=para1.get('content', ''),
                        content2='',
                        role1=para1.get('role'), role2=None,
                        importance1=para1.get('importance', ''), importance2='',
                        coordinates1=para1.get('coordinates'), coordinates2=None,
                        content_similarity=0.0,
                        coordinate_similarity=0.0,
                        total_similarity=0.0
                    )
                    differences.append(rich_diff)
                    
            elif tag == 'insert':
                # 追加: 文書2にのみ存在
                for k in range(j1, j2):
                    para2 = paragraphs2[k] if k < len(paragraphs2) else {}
                    rich_diff = RichParagraphDiff(
                        index1=-1, index2=k, diff_type='added',
                        content1='',
                        content2=para2.get('content', ''),
                        role1=None, role2=para2.get('role'),
                        importance1='', importance2=para2.get('importance', ''),
                        coordinates1=None, coordinates2=para2.get('coordinates'),
                        content_similarity=0.0,
                        coordinate_similarity=0.0,
                        total_similarity=0.0
                    )
                    differences.append(rich_diff)
        
        # デバッガー用に保存
        self.debug_paragraph_diffs = differences
        return differences

    def _create_additions_from_sections(self, sections: List[Dict[str, Any]]) -> List[DiffResult]:
        """セクションリストから全段落を追加として作成"""
        results = []
        for section in sections:
            for para in section.get('paragraphs', []):
                result = DiffResult(
                    change_type=ChangeType.ADDITION,
                    page=para.get('page', section.get('page', 2)),
                    original_bbox=None,
                    modified_bbox=para,
                    semantic_similarity=0.0
                )
                results.append(result)
        return results
    
    def _create_deletions_from_sections(self, sections: List[Dict[str, Any]]) -> List[DiffResult]:
        """セクションリストから全段落を削除として作成"""
        results = []
        for section in sections:
            for para in section.get('paragraphs', []):
                result = DiffResult(
                    change_type=ChangeType.DELETION,
                    page=para.get('page', section.get('page', 2)),
                    original_bbox=para,
                    modified_bbox=None,
                    semantic_similarity=0.0
                )
                results.append(result)
        return results
    
    def _calculate_structural_similarity(self, item1: Dict[str, Any], 
                                       item2: Dict[str, Any]) -> float:
        """構造化アイテム間の類似度を計算
        
        Args:
            item1: 文書1のアイテム
            item2: 文書2のアイテム
            
        Returns:
            類似度スコア（0.0-1.0）
        """
        # テキストの類似度（基本）
        text1 = item1.get('text', '').strip()
        text2 = item2.get('text', '').strip()
        
        if not text1 and not text2:
            return 0.0
        if not text1 or not text2:
            return 0.0
        
        # 完全一致
        if text1 == text2:
            return 1.0 + self.exact_match_bonus
        
        # difflib使用のテキスト類似度
        text_similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # 構造的類似度（タイプ、役割、セクション）
        structural_bonus = 0.0
        
        # 同じタイプ
        if item1.get('type') == item2.get('type'):
            structural_bonus += 0.1
        
        # 同じ役割
        if item1.get('role') == item2.get('role'):
            structural_bonus += 0.1
        
        # 同じセクション
        section1 = item1.get('section_context', {}).get('section_title', '')
        section2 = item2.get('section_context', {}).get('section_title', '')
        if section1 and section2 and section1 == section2:
            structural_bonus += self.section_weight
        
        # 重要度の一致
        if item1.get('importance') == item2.get('importance'):
            structural_bonus += 0.05
        
        return min(1.0, text_similarity + structural_bonus)
    
    def _create_additions(self, items: List[Dict[str, Any]]) -> List[DiffResult]:
        """全項目を追加として作成"""
        results = []
        for item in items:
            result = DiffResult(
                change_type=ChangeType.ADDITION,
                page=item.get('page', 2),
                original_bbox=None,
                modified_bbox=item,
                semantic_similarity=0.0
            )
            results.append(result)
        return results
    
    def _create_deletions(self, items: List[Dict[str, Any]]) -> List[DiffResult]:
        """全項目を削除として作成"""
        results = []
        for item in items:
            result = DiffResult(
                change_type=ChangeType.DELETION,
                page=item.get('page', 2),
                original_bbox=item,
                modified_bbox=None,
                semantic_similarity=0.0
            )
            results.append(result)
        return results
    
    def _sort_results(self, results: List[DiffResult]) -> List[DiffResult]:
        """結果をソート（ページ順、セクション順、段落順）"""
        def sort_key(result: DiffResult):
            # アイテムを取得（original_bbox または modified_bbox）
            item = result.original_bbox or result.modified_bbox
            if not item:
                return (999, 999, 999)  # 最後にソート
            
            page = item.get('page', 999)
            section_num = item.get('section_info', {}).get('section_number', 999)
            para_idx = item.get('section_context', {}).get('paragraph_index', 999)
            
            return (page, section_num, para_idx)
        
        results.sort(key=sort_key)
        return results