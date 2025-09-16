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


@dataclass
class UnmatchedSection:
    """マッチしなかったセクション情報"""
    index: int
    document: str  # 'doc1' or 'doc2'
    title: str
    paragraph_count: int
    contents: List[str]  # 段落の内容リスト
    section_type: str  # 'deleted' or 'added'
    
    def __repr__(self):
        content_preview = ' | '.join(content[:20] + '...' if len(content) > 20 else content 
                                   for content in self.contents[:3])
        return f"UnmatchedSection[{self.document}:{self.index}]: '{self.title}' ({self.paragraph_count}段落) - {content_preview}"


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
                 similarity_threshold: float = 0.6,
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
        self.debug_unmatched_sections: List[UnmatchedSection] = []
    
    def detect_easy_differences(self, 
                      doc1_analysis: Dict[str, Any], 
                      doc2_analysis: Dict[str, Any],
                      doc1_word_data,
                      doc2_word_data) -> List[DiffResult]:
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
                para1_page = para1["page"]
                para2_page = para2["page"]

                # 変数を初期化
                para1_word_data = []
                para2_word_data = []

                for item in doc1_word_data:
                    if item.get("page_number") == para1_page:
                        para1_word_data = item.get("words", [])
                        break

                for item in doc2_word_data:
                    if item.get("page_number") == para2_page:
                        para2_word_data = item.get("words", [])
                        break
                
                
                logger.debug(f"  段落マッチ詳細: {paragraph_match}")
                
                
                if paragraph_match.content1 != paragraph_match.content2:
                    # 詳細な文字列差分を抽出
                    text_differences = self._extract_text_differences(para1, para2, para1_word_data, para2_word_data)
                    
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
                            page_doc1=para1.get('page', section1.get('page', 2)),
                            page_doc2=para2.get('page', section2.get('page', 2)),
                            original_bbox=original_bbox,
                            modified_bbox=modified_bbox,
                            semantic_similarity=paragraph_match.similarity,
                            original_paragraph=diff_detail.get('original_paragraph'),
                            modified_paragraph=diff_detail.get('modified_paragraph'),
                            original_section=section1,
                            modified_section=section2
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
                        page_doc1=para.get('page', section1.get('page', 2)),
                        page_doc2=None,
                        original_bbox=para,
                        modified_bbox=None,
                        semantic_similarity=0.0,
                        original_paragraph=para,
                        modified_paragraph=None,
                        original_section=section1,
                        modified_section=None
                    )
                    results.append(result)
            
            for para_idx, para in enumerate(paragraphs2):
                if para_idx not in matched_para_indices2:
                    result = DiffResult(
                        change_type=ChangeType.ADDITION,
                        page=para.get('page', section2.get('page', 2)),
                        page_doc1=None,
                        page_doc2=para.get('page', section2.get('page', 2)),
                        original_bbox=None,
                        modified_bbox=para,
                        semantic_similarity=0.0,
                        original_paragraph=None,
                        modified_paragraph=para,
                        original_section=None,
                        modified_section=section2
                    )
                    results.append(result)
            
            matched_section_indices1.add(section_match.index1)
            matched_section_indices2.add(section_match.index2)
        
        # 3. マッチしなかったセクション全体の処理（セクション削除/追加）
        unmatched_count1 = 0
        for sec_idx, section in enumerate(doc1_sections):
            if sec_idx not in matched_section_indices1:
                if unmatched_count1 == 0:
                    logger.info("マッチしなかった文書1のセクション:")
                unmatched_count1 += 1
                
                # セクション全体の削除
                for para in section.get('paragraphs', []):
                    result = DiffResult(
                        change_type=ChangeType.DELETION,
                        page=para.get('page', section.get('page', 2)),
                        page_doc1=para.get('page', section.get('page', 2)),
                        page_doc2=None,
                        original_bbox=para,
                        modified_bbox=None,
                        semantic_similarity=0.0,
                        original_paragraph=para,
                        modified_paragraph=None,
                        original_section=section,
                        modified_section=None
                    )
                    results.append(result)
                    
                section_title = section.get('title', '(タイトルなし)')
                para_count = section.get('paragraph_count', len(section.get('paragraphs', [])))
                logger.info(f"  削除セクション[{sec_idx+1}]: '{section_title}' ({para_count}段落)")
        
        if unmatched_count1 == 0:
            logger.info("文書1: 全セクションがマッチしました")
        
        unmatched_count2 = 0
        for sec_idx, section in enumerate(doc2_sections):
            if sec_idx not in matched_section_indices2:
                if unmatched_count2 == 0:
                    logger.info("マッチしなかった文書2のセクション:")
                unmatched_count2 += 1
                
                # セクション全体の追加
                for para in section.get('paragraphs', []):
                    result = DiffResult(
                        change_type=ChangeType.ADDITION,
                        page=para.get('page', section.get('page', 2)),
                        page_doc1=None,
                        page_doc2=para.get('page', section.get('page', 2)),
                        original_bbox=None,
                        modified_bbox=para,
                        semantic_similarity=0.0,
                        original_paragraph=None,
                        modified_paragraph=para,
                        original_section=None,
                        modified_section=section
                    )
                    results.append(result)
                    
                section_title = section.get('title', '(タイトルなし)')
                para_count = section.get('paragraph_count', len(section.get('paragraphs', [])))
                logger.info(f"  追加セクション[{sec_idx+1}]: '{section_title}' ({para_count}段落)")
        
        if unmatched_count2 == 0:
            logger.info("文書2: 全セクションがマッチしました")
        
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
                            page_doc1=para1.get('page', section1.get('page', 2)),
                            page_doc2=para2.get('page', section2.get('page', 2)),
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
                        page_doc1=para.get('page', section1.get('page', 2)),
                        page_doc2=None,
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
                        page_doc1=None,
                        page_doc2=para.get('page', section2.get('page', 2)),
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
                # paragraphsからcontentを抽出してリスト化
                paragraphs1 = section1.get('paragraphs', [])
                paragraphs2 = section2.get('paragraphs', [])
                
                contents1 = [para.get('content', '') for para in paragraphs1]
                contents2 = [para.get('content', '') for para in paragraphs2]
                
                # 空のコンテンツリストはスキップ
                if not contents1 or not contents2:
                    continue
                
                # セクション内容を結合してテキスト化
                text1 = ' '.join(contents1).strip()
                text2 = ' '.join(contents2).strip()
                
                if not text1 or not text2:
                    continue
                
                # 数値を除去したテキストで類似度を計算
                text1_without_numbers = self._remove_numbers_from_text(text1)
                text2_without_numbers = self._remove_numbers_from_text(text2)
                
                # 完全一致の場合は高スコア（数値除去後で判定）
                if text1_without_numbers == text2_without_numbers and text1_without_numbers.strip():
                    similarity = 1.0 + self.exact_match_bonus
                else:
                    # 数値除去後のテキストで類似度計算
                    if text1_without_numbers.strip() and text2_without_numbers.strip():
                        similarity = difflib.SequenceMatcher(None, text1_without_numbers, text2_without_numbers).ratio()
                    else:
                        # 数値のみの場合は元のテキストで比較
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
                # paragraphsからcontentを抽出（マッチング処理と同じ方式）
                paragraphs1 = section1.get('paragraphs', [])
                paragraphs2 = section2.get('paragraphs', [])
                match_contents1 = [para.get('content', '') for para in paragraphs1]
                match_contents2 = [para.get('content', '') for para in paragraphs2]
                
                # RichSectionMatchオブジェクトを作成
                rich_match = RichSectionMatch(
                    index1=i, index2=j, similarity=sim,
                    title1=section1.get('title', ''),
                    title2=section2.get('title', ''),
                    contents1=match_contents1,
                    contents2=match_contents2,
                    paragraph_count1=section1.get('paragraph_count', 0),
                    paragraph_count2=section2.get('paragraph_count', 0)
                )
                final_matches.append(rich_match)
                used_i.add(i)
                used_j.add(j)
        
        # マッチしなかったセクションを収集
        unmatched_sections = []
        
        # 文書1のアンマッチセクション
        for i, section1 in enumerate(doc1_sections):
            if i not in used_i:
                paragraphs1 = section1.get('paragraphs', [])
                contents1 = [para.get('content', '') for para in paragraphs1]
                unmatched_section = UnmatchedSection(
                    index=i,
                    document='doc1',
                    title=section1.get('title', '(タイトルなし)'),
                    paragraph_count=len(paragraphs1),
                    contents=contents1,
                    section_type='deleted'
                )
                unmatched_sections.append(unmatched_section)
        
        # 文書2のアンマッチセクション
        for j, section2 in enumerate(doc2_sections):
            if j not in used_j:
                paragraphs2 = section2.get('paragraphs', [])
                contents2 = [para.get('content', '') for para in paragraphs2]
                unmatched_section = UnmatchedSection(
                    index=j,
                    document='doc2',
                    title=section2.get('title', '(タイトルなし)'),
                    paragraph_count=len(paragraphs2),
                    contents=contents2,
                    section_type='added'
                )
                unmatched_sections.append(unmatched_section)
        
        # ログ出力
        logger.info(f"セクションマッチング完了: マッチ={len(final_matches)}件, アンマッチ={len(unmatched_sections)}件")
        
        if unmatched_sections:
            logger.info("マッチしなかったセクション:")
            for unmatched in unmatched_sections:
                logger.info(f"  {unmatched}")
        else:
            logger.info("全セクションがマッチしました")
        
        # デバッガー用に保存
        self.debug_section_matches = final_matches
        self.debug_unmatched_sections = unmatched_sections
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

    def _tokenize_with_mecab(self, text: str) -> List[Dict[str, Any]]:
        """MeCabを使用して形態素分割（位置情報付き）
        
        Args:
            text: 分割対象のテキスト
            
        Returns:
            形態素情報のリスト
            [
                {
                    'surface': '194年',      # 表層形
                    'features': ['名詞', '一般', ...],  # 品詞情報  
                    'start_pos': 0,          # 元文字列での開始位置
                    'end_pos': 4,            # 元文字列での終了位置
                    'length': 4
                },
                ...
            ]
        """
        try:
            import MeCab
        except ImportError:
            logger.warning("MeCabがインストールされていません。文字レベル分割にフォールバック")
            return self._fallback_tokenize(text)
        
        try:
            # 詳細情報付きでMeCab実行（環境変数から設定ファイルパスを取得）
            import os
            mecabrc_path = os.environ.get('MECABRC')
            if mecabrc_path and os.path.exists(mecabrc_path):
                tagger = MeCab.Tagger(f'-r {mecabrc_path} -F%m,%f[0],%f[1],%f[2],%f[3],%f[4],%f[5],%f[6]')
            else:
                # 環境変数が設定されていない場合はデフォルト設定を使用
                tagger = MeCab.Tagger('-F%m,%f[0],%f[1],%f[2],%f[3],%f[4],%f[5],%f[6]')
            result = tagger.parseToNode(text)
            
            morphemes = []
            current_pos = 0
            
            while result:
                if result.surface:  # 表層形が存在する場合のみ
                    features = result.feature.split(',')
                    start_pos = current_pos
                    end_pos = current_pos + len(result.surface)
                    
                    morphemes.append({
                        'surface': result.surface,
                        'features': features,
                        'start_pos': start_pos,
                        'end_pos': end_pos,
                        'length': len(result.surface),
                        'pos': features[0] if len(features) > 0 else '',  # 品詞
                        'pos_detail': features[1] if len(features) > 1 else ''  # 品詞詳細
                    })
                    
                    current_pos = end_pos
                
                result = result.next
            
            return morphemes
            
        except Exception as e:
            logger.warning(f"MeCab実行エラー: {e}、フォールバック使用")
            return self._fallback_tokenize(text)
    
    def _fallback_tokenize(self, text: str) -> List[Dict[str, Any]]:
        """MeCab利用不可時のフォールバック形態素分割"""
        import re
        
        # 正規表現パターンで意味単位分割
        patterns = [
            (r'\d+年度?', '数詞_年'),
            (r'\d+億円', '数詞_金額'),
            (r'P\d+', '記号_P番号'),
            (r'[ぁ-ん]+', 'ひらがな'),
            (r'[ァ-ン]+', 'カタカナ'),
            (r'[一-龯]+', '漢字'),
            (r'[A-Za-z]+', '英語'),
            (r'\d+', '数字'),
            (r'[、。！？]', '句読点'),
            (r'[^\w\s]', '記号')
        ]
        
        morphemes = []
        current_pos = 0
        remaining_text = text
        
        while remaining_text and current_pos < len(text):
            matched = False
            
            for pattern, pos_type in patterns:
                match = re.match(pattern, remaining_text)
                if match:
                    surface = match.group(0)
                    start_pos = current_pos
                    end_pos = current_pos + len(surface)
                    
                    morphemes.append({
                        'surface': surface,
                        'features': [pos_type],
                        'start_pos': start_pos,
                        'end_pos': end_pos,
                        'length': len(surface),
                        'pos': pos_type,
                        'pos_detail': ''
                    })
                    
                    current_pos = end_pos
                    remaining_text = remaining_text[len(surface):]
                    matched = True
                    break
            
            if not matched:
                # どのパターンにもマッチしない場合、1文字進める
                if remaining_text:
                    surface = remaining_text[0]
                    morphemes.append({
                        'surface': surface,
                        'features': ['その他'],
                        'start_pos': current_pos,
                        'end_pos': current_pos + 1,
                        'length': 1,
                        'pos': 'その他',
                        'pos_detail': ''
                    })
                    current_pos += 1
                    remaining_text = remaining_text[1:]
        
        return morphemes
    
    def _map_morphemes_to_words_data(self, morphemes: List[Dict], 
                                    paragraph_content: str, words_data: List[Dict]) -> Dict[int, Tuple[int, int]]:
        """廃止予定：旧式の形態素インデックスマッピング
        
        注意：このメソッドは文字位置ベースの不正確なマッピングを行うため、
        新しい _find_and_get_morpheme_coordinates メソッドの使用を推奨
        """
        logger.warning("廃止予定の _map_morphemes_to_words_data が呼ばれました。新しいメソッドの使用を推奨します。")
        
        # 段落範囲を特定
        paragraph_range = self._find_paragraph_range_in_words_data(paragraph_content, words_data)
        if paragraph_range[0] is None:
            logger.debug(f"段落範囲特定失敗、形態素マッピング不可")
            return {}
        
        morpheme_map = {}
        para_start_idx = paragraph_range[0]
        
        for morph_idx, morpheme in enumerate(morphemes):
            char_start = morpheme['start_pos']
            char_end = morpheme['end_pos']
            
            # 文字位置をwords_dataインデックスに変換
            word_start_idx = para_start_idx + char_start
            word_end_idx = para_start_idx + char_end
            
            # 範囲チェック
            if word_end_idx <= len(words_data):
                morpheme_map[morph_idx] = (word_start_idx, word_end_idx)
                # logger.debug(f"形態素マッピング: '{morpheme['surface']}' → words_data[{word_start_idx}:{word_end_idx}]")
            else:
                logger.warning(f"形態素範囲超過: '{morpheme['surface']}' → [{word_start_idx}:{word_end_idx}] > {len(words_data)}")
        
        return morpheme_map
    
    def _get_morpheme_range_coordinates(self, morphemes: List[Dict], 
                                       morpheme_map: Dict[int, Tuple[int, int]], 
                                       words_data: List[Dict]) -> Dict:
        """廃止予定：旧式の形態素範囲統合座標取得
        
        注意：このメソッドは旧式のmorpheme_mapに依存するため、
        新しい _find_and_get_morpheme_coordinates メソッドの使用を推奨
        """
        logger.warning("廃止予定の _get_morpheme_range_coordinates が呼ばれました。新しいメソッドの使用を推奨します。")
        
        if not morphemes or not morpheme_map:
            return None
        
        all_polygons = []
        
        # 全形態素の座標を収集
        for i, morpheme in enumerate(morphemes):
            if i in morpheme_map:
                word_start, word_end = morpheme_map[i]
                # この形態素に対応するwords_dataから座標を取得
                morpheme_coords = self._extract_coordinates_from_words_range(
                    words_data, word_start, word_end
                )
                if morpheme_coords:
                    all_polygons.append(morpheme_coords)
        
        # 複数形態素の座標を結合
        if all_polygons:
            combined_polygon = self._combine_polygons(all_polygons)
            return {
                'type': 'morpheme_polygon',
                'raw_coordinates': combined_polygon,
                'morpheme_count': len(morphemes),
                'morpheme_surfaces': [m['surface'] for m in morphemes]
            }
        
        return None

    def _extract_text_differences(self, para1: Dict[str, Any], para2: Dict[str, Any], 
                                 para1_words_data: List[Dict], para2_words_data: List[Dict]) -> List[Dict[str, Any]]:
        """最適化版：差分検出→該当形態素のみwords_dataマッピング
        
        Args:
            para1: 文書1の段落
            para2: 文書2の段落
            para1_words_data: 文書1の文字レベルデータ
            para2_words_data: 文書2の文字レベルデータ
            
        Returns:
            形態素レベル差分箇所のリスト
        """
        
        content1 = para1.get('content', '')
        content2 = para2.get('content', '')
        
        if content1 == content2:
            return []
        
        # 1. 形態素分割（words_dataマッピングなし）
        morphemes1 = self._tokenize_with_mecab(content1)
        morphemes2 = self._tokenize_with_mecab(content2)
        
        # 2. 形態素レベルでの差分検出（座標なし）
        differences = self._detect_morpheme_differences_only(morphemes1, morphemes2)
        
        # 3. 差分のある形態素のみwords_dataで検索・座標取得
        enriched_differences = []
        
        for diff in differences:
            # 差分のある形態素情報を取得
            original_morphemes = diff.get('original_morphemes', [])
            modified_morphemes = diff.get('modified_morphemes', [])
            
            # 該当する形態素のみwords_dataで検索・座標取得
            original_coords = None
            if original_morphemes:
                original_coords = self._find_and_get_morpheme_coordinates(
                    original_morphemes, content1, para1_words_data
                )
            
            modified_coords = None  
            if modified_morphemes:
                modified_coords = self._find_and_get_morpheme_coordinates(
                    modified_morphemes, content2, para2_words_data
                )
            
            # 座標情報を付加した差分データを作成
            enriched_diff = {
                **diff,  # 既存の差分情報
                'original_coordinates': original_coords,
                'modified_coordinates': modified_coords,
                'original_paragraph': para1,
                'modified_paragraph': para2
            }
            enriched_differences.append(enriched_diff)
            
            logger.debug(f"形態素差分検出: '{diff['original_content']}' → '{diff['modified_content']}' ({diff['change_type']})")
        
        return enriched_differences
    
    def _create_words_data_string_and_mapping(self, words_data: List[Dict]) -> Tuple[str, List[int]]:
        """廃止予定：words_dataを文字列化し、位置マッピングを作成
        
        注意：このメソッドは旧式の文字位置ベースアプローチで使用されていましたが、
        新しい文言マッチング方式では不要です。下位互換性のため残していますが使用は推奨されません。
        """
        logger.warning("廃止予定の _create_words_data_string_and_mapping が呼ばれました。")
        
        words_string = ""
        char_to_word_index = []  # 文字位置 → words_dataインデックス
        
        for word_idx, word_data in enumerate(words_data):
            content = word_data.get('content', '')
            for char in content:
                words_string += char
                char_to_word_index.append(word_idx)
        
        logger.debug(f"words_data文字列化完了: {len(words_string)}文字, {len(words_data)}要素")
        return words_string, char_to_word_index
    
    def _verify_full_paragraph_match(self, paragraph_content: str, words_string: str, start_pos: int) -> float:
        """廃止予定：指定位置から段落全体のマッチング率を計算
        
        注意：このメソッドは旧式の文字位置ベースアプローチで使用されていましたが、
        新しい文言マッチング方式では不要です。下位互換性のため残していますが使用は推奨されません。
        """
        logger.warning("廃止予定の _verify_full_paragraph_match が呼ばれました。")
        
        para_length = len(paragraph_content)
        end_pos = start_pos + para_length
        
        if end_pos > len(words_string):
            return 0.0
        
        # 該当範囲の文字列を抽出
        target_string = words_string[start_pos:end_pos]
        
        # difflib で類似度計算
        import difflib
        similarity = difflib.SequenceMatcher(None, paragraph_content, target_string).ratio()
        
        return similarity

    def _find_paragraph_range_in_words_data(self, paragraph_content: str, words_data: List[Dict]) -> Tuple[Optional[int], Optional[int]]:
        """文言マッチングベースでの段落範囲特定
        
        Args:
            paragraph_content: 段落の全テキスト
            words_data: 文字単位のデータリスト
            
        Returns:
            (start_idx, end_idx): 段落に対応するwords_dataの範囲、見つからない場合は(None, None)
        """
        if not paragraph_content or not words_data:
            return None, None
        
        # 1. 完全一致検索（正規化後）
        result = self._find_exact_text_match(paragraph_content, words_data)
        if result:
            logger.debug(f"段落範囲特定成功(完全一致): '{paragraph_content[:20]}...' → words_data[{result[0]}:{result[1]}]")
            return result
        
        # 2. 部分一致検索（段落の先頭・末尾で一致）
        result = self._find_partial_text_match(paragraph_content, words_data)
        if result:
            logger.debug(f"段落範囲特定成功(部分一致): '{paragraph_content[:20]}...' → words_data[{result[0]}:{result[1]}]")
            return result
        
        # 3. fuzzy一致検索（最低7割一致）
        result = self._find_fuzzy_text_match(paragraph_content, words_data, min_ratio=0.7)
        if result:
            logger.debug(f"段落範囲特定成功(fuzzy一致): '{paragraph_content[:20]}...' → words_data[{result[0]}:{result[1]}]")
            return result
        
        logger.warning(f"段落範囲特定完全失敗: '{paragraph_content[:30]}...'")
        return None, None

    def _find_exact_text_match(self, target_text: str, words_data: List[Dict]) -> Optional[Tuple[int, int]]:
        """完全一致検索"""
        normalized_target = self._normalize_text(target_text)
        
        for start_idx in range(len(words_data)):
            accumulated_text = ""
            
            for end_idx in range(start_idx, min(start_idx + len(normalized_target) * 2, len(words_data))):
                accumulated_text += words_data[end_idx].get('content', '')
                normalized_accumulated = self._normalize_text(accumulated_text)
                
                if normalized_accumulated == normalized_target:
                    return (start_idx, end_idx + 1)
                elif len(normalized_accumulated) > len(normalized_target) * 1.5:
                    break  # 明らかに長すぎる場合は打ち切り
        
        return None

    def _find_partial_text_match(self, target_text: str, words_data: List[Dict]) -> Optional[Tuple[int, int]]:
        """部分一致検索（先頭・末尾基準）"""
        normalized_target = self._normalize_text(target_text)
        
        # 先頭20文字と末尾20文字で検索
        target_head = normalized_target[:20]
        target_tail = normalized_target[-20:] if len(normalized_target) > 20 else normalized_target
        
        for start_idx in range(len(words_data)):
            for end_idx in range(start_idx + 10, min(start_idx + 200, len(words_data) + 1)):
                
                candidate_text = self._extract_text_from_words_range(words_data, start_idx, end_idx)
                normalized_candidate = self._normalize_text(candidate_text)
                
                # 先頭と末尾が一致するかチェック
                if (normalized_candidate.startswith(target_head) and 
                    normalized_candidate.endswith(target_tail)):
                    
                    # 長さも近似している場合のみ採用
                    length_ratio = len(normalized_candidate) / len(normalized_target)
                    if 0.8 <= length_ratio <= 1.2:
                        return (start_idx, end_idx)
        
        return None

    def _find_fuzzy_text_match(self, target_text: str, words_data: List[Dict], min_ratio: float = 0.7) -> Optional[Tuple[int, int]]:
        """fuzzy一致検索"""
        import difflib
        
        normalized_target = self._normalize_text(target_text)
        best_match = None
        best_ratio = min_ratio
        
        # 効率化：大まかな長さで範囲を絞る
        target_length = len(normalized_target)
        search_window = max(50, target_length // 5)
        
        for start_idx in range(0, len(words_data), search_window // 2):  # オーバーラップ付きスキップ
            for window_size in [target_length // 2, target_length, target_length * 2]:
                end_idx = min(start_idx + window_size, len(words_data))
                
                candidate_text = self._extract_text_from_words_range(words_data, start_idx, end_idx)
                normalized_candidate = self._normalize_text(candidate_text)
                
                similarity = difflib.SequenceMatcher(None, normalized_target, normalized_candidate).ratio()
                
                if similarity > best_ratio:
                    best_ratio = similarity
                    best_match = (start_idx, end_idx)
        
        return best_match

    def _extract_text_from_words_range(self, words_data: List[Dict], start_idx: int, end_idx: int) -> str:
        """words_dataの指定範囲からテキストを抽出"""
        return ''.join(word.get('content', '') for word in words_data[start_idx:end_idx])

    def _normalize_text(self, text: str) -> str:
        """テキスト正規化（比較用）"""
        import re
        # 空白・改行削除、全角半角統一など
        normalized = re.sub(r'\s+', '', text)  # 全空白削除
        normalized = normalized.replace('　', '')  # 全角スペース削除
        return normalized.lower()

    def _is_numeric(self, text: str) -> bool:
        """テキストが数値かどうかを判定"""
        import re
        # 数字のみ、または数字と記号/文字の組み合わせで数字が含まれているかチェック
        return bool(re.search(r'\d+', text))
    
    def _extract_numeric_part(self, text: str) -> str:
        """テキストから数値部分を抽出"""
        import re
        numbers = re.findall(r'\d+', text)
        return ''.join(numbers) if numbers else ""
    
    def _numeric_partial_match(self, target_text: str, content_text: str) -> bool:
        """数値部分での部分マッチング判定"""
        if not self._is_numeric(target_text) or not self._is_numeric(content_text):
            return False
        
        target_numeric = self._extract_numeric_part(target_text)
        content_numeric = self._extract_numeric_part(content_text)
        
        # 数値部分が完全一致すればマッチとする
        return target_numeric == content_numeric and len(target_numeric) > 0

    def _find_morpheme_with_difflib(self, morpheme_text: str, words_data: List[Dict],
                                    para_start_idx: int, para_end_idx: int) -> Optional[Tuple[int, int]]:
        """difflibを使用して形態素位置を特定"""
        from difflib import SequenceMatcher
        
        # 段落範囲のcontentを抽出
        paragraph_contents = [words_data[i].get('content', '') for i in range(para_start_idx, para_end_idx)]
        paragraph_text = ''.join(paragraph_contents)
        
        # 1. 完全一致での検索
        matcher = SequenceMatcher(None, paragraph_text, morpheme_text)
        match = matcher.find_longest_match(0, len(paragraph_text), 0, len(morpheme_text))
        
        if match.size == len(morpheme_text):
            # 完全一致の場合、文字位置からwords_dataインデックスに変換
            char_start = match.a
            char_end = match.a + match.size
            return self._convert_char_range_to_words_range(char_start, char_end, paragraph_contents, para_start_idx)
        
        # 2. 数値部分マッチング
        if self._is_numeric(morpheme_text):
            target_numeric = self._extract_numeric_part(morpheme_text)
            if target_numeric:
                # 段落内で数値パターンを検索
                import re
                for match_obj in re.finditer(r'\d+', paragraph_text):
                    if match_obj.group() == target_numeric:
                        char_start = match_obj.start()
                        char_end = match_obj.end()
                        return self._convert_char_range_to_words_range(char_start, char_end, paragraph_contents, para_start_idx)
        
        # 3. 正規化後の検索
        normalized_paragraph = self._normalize_text(paragraph_text)
        normalized_target = self._normalize_text(morpheme_text)
        
        matcher = SequenceMatcher(None, normalized_paragraph, normalized_target)
        match = matcher.find_longest_match(0, len(normalized_paragraph), 0, len(normalized_target))
        
        if match.size == len(normalized_target):
            # 正規化前の文字位置を推定（近似）
            char_start = match.a
            char_end = match.a + match.size
            return self._convert_char_range_to_words_range(char_start, char_end, paragraph_contents, para_start_idx)
        
        return None
    
    def _convert_char_range_to_words_range(self, char_start: int, char_end: int, 
                                           paragraph_contents: List[str], para_start_idx: int) -> Tuple[int, int]:
        """文字範囲をwords_data範囲に変換"""
        current_char_pos = 0
        words_start_idx = None
        words_end_idx = None
        
        for i, content in enumerate(paragraph_contents):
            content_start = current_char_pos
            content_end = current_char_pos + len(content)
            
            # 開始インデックスの特定
            if words_start_idx is None and char_start >= content_start and char_start < content_end:
                words_start_idx = para_start_idx + i
            
            # 終了インデックスの特定
            if char_end > content_start and char_end <= content_end:
                words_end_idx = para_start_idx + i + 1
                break
            
            current_char_pos = content_end
        
        # 開始は見つかったが終了が見つからない場合
        if words_start_idx is not None and words_end_idx is None:
            words_end_idx = words_start_idx + 1
        
        # 両方見つからない場合は最も近い位置を推定
        if words_start_idx is None:
            words_start_idx = para_start_idx + min(char_start // max(1, len(''.join(paragraph_contents)) // len(paragraph_contents)), len(paragraph_contents) - 1)
            words_end_idx = words_start_idx + 1
        
        return (words_start_idx, words_end_idx)

    def _find_and_get_morpheme_coordinates(self, target_morphemes: List[Dict], 
                                          paragraph_content: str, words_data: List[Dict]) -> Optional[Dict]:
        """差分のある形態素のみwords_dataで検索して座標取得
        
        Args:
            target_morphemes: 対象形態素リスト
            paragraph_content: 段落内容
            words_data: words_dataリスト
            
        Returns:
            座標情報辞書、見つからない場合はNone
        """
        if not target_morphemes:
            return None
        
        # 1. 段落範囲特定
        paragraph_range = self._find_paragraph_range_in_words_data(paragraph_content, words_data)
        if not paragraph_range or paragraph_range[0] is None:
            return None
        
        # 2. 対象形態素の文言を結合
        target_text = ''.join(m['surface'] for m in target_morphemes)
        
        # 3. words_data内で該当範囲を検索
        word_range = self._find_morpheme_range_in_paragraph(
            target_text, words_data, paragraph_range[0], paragraph_range[1]
        )
        
        if word_range:
            # 4. 座標情報を取得
            coordinates = self._extract_coordinates_from_words_range(
                words_data, word_range[0], word_range[1]
            )
            
            return {
                'type': 'morpheme_polygon',
                'raw_coordinates': coordinates,
                'morpheme_count': len(target_morphemes),
                'morpheme_surfaces': [m['surface'] for m in target_morphemes],
                'words_data_range': word_range,  # デバッグ用
                'words_data_content': [words_data[i].get('content', '') for i in range(word_range[0], word_range[1])]  # 実際の文言
            }
        
        return None

    def _find_morpheme_range_in_paragraph(self, morpheme_text: str, words_data: List[Dict],
                                        para_start_idx: int, para_end_idx: int) -> Optional[Tuple[int, int]]:
        """段落範囲内で特定の形態素範囲を検索
        
        Args:
            morpheme_text: 検索対象の形態素文言
            words_data: words_dataリスト  
            para_start_idx: 段落開始インデックス
            para_end_idx: 段落終了インデックス
            
        Returns:
            (start_idx, end_idx): 形態素に対応するwords_dataの範囲、見つからない場合はNone
        """
        
        # 新しいdifflibベースの検索を最初に実行
        result = self._find_morpheme_with_difflib(morpheme_text, words_data, para_start_idx, para_end_idx)
        if result:
            logger.debug(f"形態素範囲検索成功(difflib): '{morpheme_text}' → words_data[{result[0]}:{result[1]}]")
            return result
        
        # 従来の方法もフォールバックとして保持
        
        # 1. 完全一致検索（単一words_data要素）
        for i in range(para_start_idx, para_end_idx):
            if words_data[i].get('content', '') == morpheme_text:
                logger.debug(f"形態素範囲検索成功(完全一致): '{morpheme_text}' → words_data[{i}:{i+1}]")
                return (i, i + 1)
        
        # 2. 数値部分マッチング検索（単一要素）
        if self._is_numeric(morpheme_text):
            for i in range(para_start_idx, para_end_idx):
                content = words_data[i].get('content', '')
                if self._numeric_partial_match(morpheme_text, content):
                    logger.debug(f"形態素範囲検索成功(数値部分一致): '{morpheme_text}' → '{content}' words_data[{i}:{i+1}]")
                    return (i, i + 1)
        
        # 3. 複数要素にまたがる場合の検索（制限を緩和）
        for start_idx in range(para_start_idx, para_end_idx):
            accumulated_text = ""
            
            for end_idx in range(start_idx, min(start_idx + 15, para_end_idx)):  # 最大15要素まで拡張
                accumulated_text += words_data[end_idx].get('content', '')
                
                if accumulated_text == morpheme_text:
                    logger.debug(f"形態素範囲検索成功(複数要素): '{morpheme_text}' → words_data[{start_idx}:{end_idx+1}]")
                    return (start_idx, end_idx + 1)
                elif len(accumulated_text) > len(morpheme_text) * 2:  # 終了条件を緩和
                    break
        
        # 4. 正規化一致検索（制限を緩和）
        normalized_target = self._normalize_text(morpheme_text)
        
        for start_idx in range(para_start_idx, para_end_idx):
            accumulated_text = ""
            
            for end_idx in range(start_idx, min(start_idx + 15, para_end_idx)):
                accumulated_text += words_data[end_idx].get('content', '')
                normalized_accumulated = self._normalize_text(accumulated_text)
                
                if normalized_accumulated == normalized_target:
                    logger.debug(f"形態素範囲検索成功(正規化一致): '{morpheme_text}' → words_data[{start_idx}:{end_idx+1}]")
                    return (start_idx, end_idx + 1)
                elif len(normalized_accumulated) > len(normalized_target) * 3:  # 終了条件を大幅緩和
                    break
        
        logger.warning(f"形態素範囲検索失敗: '{morpheme_text}' in paragraph range [{para_start_idx}:{para_end_idx}]")
        return None

    def _detect_morpheme_differences_only(self, morphemes1: List[Dict], morphemes2: List[Dict]) -> List[Dict]:
        """形態素レベル差分検出（座標情報なし）
        
        Args:
            morphemes1: 文書1の形態素リスト
            morphemes2: 文書2の形態素リスト
            
        Returns:
            座標情報なしの差分リスト
        """
        import difflib
        
        morpheme_surfaces1 = [m['surface'] for m in morphemes1]
        morpheme_surfaces2 = [m['surface'] for m in morphemes2]
        
        matcher = difflib.SequenceMatcher(None, morpheme_surfaces1, morpheme_surfaces2)
        differences = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ['replace', 'delete', 'insert']:
                
                original_morphemes = morphemes1[i1:i2] if tag in ['replace', 'delete'] else []
                modified_morphemes = morphemes2[j1:j2] if tag in ['replace', 'insert'] else []
                
                original_text = ''.join(m['surface'] for m in original_morphemes)
                modified_text = ''.join(m['surface'] for m in modified_morphemes)
                
                if original_text != modified_text:  # 実際に差分がある場合のみ
                    differences.append({
                        'change_type': self._determine_change_type(tag),
                        'original_content': original_text,
                        'modified_content': modified_text,
                        'original_morphemes': original_morphemes,  # 形態素オブジェクト保持
                        'modified_morphemes': modified_morphemes,  # 形態素オブジェクト保持
                        'original_pos_info': [{'surface': m['surface'], 'pos': m['pos']} for m in original_morphemes],
                        'modified_pos_info': [{'surface': m['surface'], 'pos': m['pos']} for m in modified_morphemes],
                        'morpheme_level': True,  # 形態素レベル差分フラグ
                        # coordinates は後で付加
                    })
        
        return differences
    
    def _combine_polygons(self, polygons: List[List[float]]) -> List[float]:
        """複数のポリゴンを結合して単一の外接矩形を作成
        
        Args:
            polygons: ポリゴン座標のリスト（各要素は8要素のリスト: [x1,y1,x2,y2,x3,y3,x4,y4]）
            
        Returns:
            combined_polygon: 結合されたポリゴン座標（外接矩形）
        """
        if not polygons:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        
        # 全ポリゴンの最小・最大座標を計算
        all_x_coords = []
        all_y_coords = []
        
        for polygon in polygons:
            if len(polygon) >= 8:  # 4点分の座標（x,y * 4）
                # x座標を抽出（偶数インデックス）
                x_coords = [polygon[i] for i in range(0, 8, 2)]
                # y座標を抽出（奇数インデックス）  
                y_coords = [polygon[i] for i in range(1, 8, 2)]
                
                all_x_coords.extend(x_coords)
                all_y_coords.extend(y_coords)
        
        if not all_x_coords or not all_y_coords:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        
        # 外接矩形の座標を計算
        min_x = min(all_x_coords)
        max_x = max(all_x_coords)
        min_y = min(all_y_coords)
        max_y = max(all_y_coords)
        
        # 外接矩形のポリゴン座標を作成（左上→右上→右下→左下）
        combined_polygon = [
            min_x, min_y,  # 左上
            max_x, min_y,  # 右上
            max_x, max_y,  # 右下
            min_x, max_y   # 左下
        ]
        
        return combined_polygon
    
    def _extract_coordinates_from_words_range(self, words_data: List[Dict[str, Any]], 
                                            start_idx: int, end_idx: int) -> Optional[List[float]]:
        """words_dataの指定範囲から統合座標を作成
        
        Args:
            words_data: 文字単位のデータリスト
            start_idx: 開始インデックス
            end_idx: 終了インデックス（排他的）
            
        Returns:
            coordinates: 統合されたポリゴン座標、取得できない場合はNone
        """
        if not words_data or start_idx is None or end_idx is None:
            return None
        
        if start_idx < 0 or end_idx > len(words_data) or start_idx >= end_idx:
            logger.warning(f"不正なインデックス範囲: [{start_idx}:{end_idx}], データ長: {len(words_data)}")
            return None
        
        # 指定範囲のwords_dataからポリゴン座標を抽出
        polygons = []
        for i in range(start_idx, end_idx):
            word_data = words_data[i]
            polygon = word_data.get('polygon')
            if polygon and len(polygon) >= 8:
                polygons.append(polygon)
            else:
                logger.debug(f"words_data[{i}]にポリゴン座標がありません: {word_data}")
        
        if not polygons:
            logger.warning(f"指定範囲[{start_idx}:{end_idx}]にポリゴン座標が見つかりません")
            return None
        
        # ポリゴンを結合して統合座標を作成
        combined_polygon = self._combine_polygons(polygons)
        return combined_polygon

    def _estimate_text_coordinates(self, paragraph: Dict[str, Any], 
                                  text: str, start_pos: int, end_pos: int) -> Optional[Dict[str, Any]]:
        """段落内のテキスト位置から座標を推定（フォールバック用）
        
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
                    page_doc1=None,
                    page_doc2=para.get('page', section.get('page', 2)),
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
                    page_doc1=para.get('page', section.get('page', 2)),
                    page_doc2=None,
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
                page_doc1=None,
                page_doc2=item.get('page', 2),
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
                page_doc1=item.get('page', 2),
                page_doc2=None,
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

    def _remove_numbers_from_text(self, text):
        """テキストから数値を除去"""
        import re
        
        if not text:
            return text
        
        # 全ての数字を「NUM」に置換（単語境界を考慮）
        cleaned_text = re.sub(r'\d+', 'NUM', text)
        
        # 連続する空白を単一の空白に変換
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        return cleaned_text.strip()