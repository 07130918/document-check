# coding: utf-8
"""
LLM文書差分検出システム v3.4 テストスクリプト
Document Intelligenceのセクション階層と座標情報を活用した高度な差分検出
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
from datetime import datetime

# プロジェクトルートをPATHに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.settings import Settings
from services.azure_service_structured import StructuredAzureService
from core.text_preprocessing import StructuredTextPreprocessorV4
from core.structured_diff_detector_v4 import StructuredDiffDetectorV4
from handlers.output_handler import OutputHandler
from handlers.enhanced_output_handler_v3_4 import EnhancedOutputHandlerV34

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('v3_4_debug_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class LLMDocsDiffV4:
    """LLM文書差分検出システム v3.4 メインクラス"""
    
    def __init__(self, use_enhanced_output: bool = True):
        """初期化"""
        self.azure_service = StructuredAzureService()
        self.preprocessor = StructuredTextPreprocessorV4()
        self.diff_detector = StructuredDiffDetectorV4()
        self.output_handler = OutputHandler()
        self.enhanced_output_handler = EnhancedOutputHandlerV34() if use_enhanced_output else None
        
        # 分割文字結合前処理器を追加
        from core.text_preprocessing import MergeSplitCharacterPreProcessor
        self.merge_processor = MergeSplitCharacterPreProcessor()
        
        # 出力ディレクトリの作成
        Settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("LLM文書差分検出システム v3.4 初期化完了")
        if use_enhanced_output:
            logger.info("拡張出力機能が有効化されています")
    
    def analyze_documents(self, 
                         doc1_path: str, 
                         doc2_path: str,
                         pages: Optional[str] = None,
                         output_tag: str = "default") -> Dict[str, Any]:
        """2つの文書の差分分析を実行
        
        Args:
            doc1_path: 文書1のパス
            doc2_path: 文書2のパス
            pages: 分析対象ページ（例: "2"）
            output_tag: 出力ファイルのタグ
            
        Returns:
            分析結果
        """
        logger.info(f"差分分析開始 (v3.4)")
        logger.info(f"文書1: {doc1_path}")
        logger.info(f"文書2: {doc2_path}")
        if pages:
            logger.info(f"対象ページ: {pages}")
        
        # 1. Document Intelligence構造化分析
        logger.info("ステップ1: Document Intelligence構造化分析")
        
        # pagesパラメータの有無で処理を分岐
        if pages is None:
            # デフォルト：ページごと処理
            logger.info("ページごと処理を実行します")
            doc1_analysis, doc1_word_data = self._analyze_document_by_pages(doc1_path)
            doc2_analysis, doc2_word_data = self._analyze_document_by_pages(doc2_path)
        else:
            # 従来の処理：指定ページのみ
            logger.info(f"指定ページ処理を実行します: {pages}")
            doc1_analysis, doc1_word_data = self.azure_service.analyze_document_structured(doc1_path, pages)
            doc2_analysis, doc2_word_data = self.azure_service.analyze_document_structured(doc2_path, pages)
        
        doc1_analysis['source_file'] = doc1_path
        doc2_analysis['source_file'] = doc2_path
        
        # 2. 分割文字結合前処理
        logger.info("ステップ2: 分割文字結合前処理")
        
        combined_doc1_analysis = self.merge_processor.process_document_analysis(doc1_analysis)
        combined_doc2_analysis = self.merge_processor.process_document_analysis(doc2_analysis)
        
        logger.info(f"結合処理結果: 文書1={len(combined_doc1_analysis.get('sections', []))}セクション, "
                   f"文書2={len(combined_doc2_analysis.get('sections', []))}セクション")
        
        # 2.5. 文言正規化処理
        logger.info("ステップ2.5: 文言正規化処理")
        
        combined_doc1_analysis = self._normalize_document_text(combined_doc1_analysis)
        combined_doc2_analysis = self._normalize_document_text(combined_doc2_analysis)
        doc1_word_data = self._normalize_word_data(doc1_word_data)
        doc2_word_data = self._normalize_word_data(doc2_word_data)
        
        logger.info("文言正規化処理完了")
        
        # 2.7. ページマッチング処理
        logger.info("ステップ2.7: ページマッチング処理")
        
        page_matches = self._match_pages_by_content(combined_doc1_analysis, combined_doc2_analysis)
        logger.info(f"ページマッチング結果: {len(page_matches)}件のマッチ")
        
        # 3. 構造化差分検出（ページマッチング結果を使用）
        logger.info("ステップ3: 構造化差分検出（ページマッチベース）")
        
        differences = self._detect_differences_by_page_matches(page_matches, combined_doc1_analysis, combined_doc2_analysis, doc1_word_data, doc2_word_data)
        
        # 差分結果をCSVで保存
        self._save_differences_csv(differences, output_tag)

        # ここでマッチセクションごとにその中のパラフラフを文言と位置の類似度に基づいて判定を行う
        
        # 4. 結果の整理と出力
        logger.info("ステップ4: 結果の整理と出力")
        
        analysis_result = {
            "version": "v3.4",
            "analysis_type": "structured_document_intelligence",
            "timestamp": datetime.now().isoformat(),
            "input_files": {
                "document1": doc1_path,
                "document2": doc2_path,
                "pages": pages
            },
            "document_analysis": {
                "document1": combined_doc1_analysis,
                "document2": combined_doc2_analysis
            },

            "differences": [
                {
                    "change_type": str(diff.change_type),
                    "page": diff.page,
                    "page_doc1": diff.page_doc1,
                    "page_doc2": diff.page_doc2,
                    "semantic_similarity": diff.semantic_similarity,
                    "original_text": diff.original_bbox.get('content', '') if diff.original_bbox else '',
                    "modified_text": diff.modified_bbox.get('content', '') if diff.modified_bbox else '',
                    "original_coordinates": diff.original_bbox.get('coordinates') if diff.original_bbox else None,
                    "modified_coordinates": diff.modified_bbox.get('coordinates') if diff.modified_bbox else None,
                    "structural_info": getattr(diff, 'structural_info', {})
                }
                for diff in differences
            ],
            "summary": {
                "total_differences": len(differences),
                "modifications": len([d for d in differences if d.change_type.name == 'MODIFICATION']),
                "additions": len([d for d in differences if d.change_type.name == 'ADDITION']),
                "deletions": len([d for d in differences if d.change_type.name == 'DELETION'])
            }
        }
        
        # 結果をファイルに保存（従来の基本出力）
        self._save_results(analysis_result, output_tag)
        
        # 拡張出力を生成（有効な場合）
        if self.enhanced_output_handler:
            try:
                logger.info("拡張出力を生成します")
                enhanced_files = self.enhanced_output_handler.generate_enhanced_output(
                    analysis_result, output_tag, doc1_path, doc2_path
                )
                logger.info(f"拡張出力完了: {len(enhanced_files)}個のファイルを生成")
                analysis_result["enhanced_output_files"] = enhanced_files
            except Exception as e:
                logger.error(f"拡張出力生成中にエラーが発生しましたが、処理を継続します: {e}")
        
        logger.info(f"差分分析完了: {len(differences)}個の差分を検出")
        logger.info(f"変更: {analysis_result['summary']['modifications']}, "
                   f"追加: {analysis_result['summary']['additions']}, "
                   f"削除: {analysis_result['summary']['deletions']}")
        
        return analysis_result

    def _analyze_document_by_pages(self, doc_path: str) -> Tuple[Dict[str, Any], Any]:
        """ページごとにDocument Intelligence分析を実行
        
        Args:
            doc_path: 文書のパス
            
        Returns:
            統合された分析結果とワードデータ
        """
        logger.info(f"ページごと分析開始: {doc_path}")
        
        # PDFのページ数を取得
        page_count = self._get_pdf_page_count(doc_path)
        if page_count == 0:
            raise ValueError(f"ページ数を取得できませんでした: {doc_path}")
        
        logger.info(f"総ページ数: {page_count}")
        
        # 各ページを個別に分析
        page_analyses = []
        page_word_data = []
        
        for page_num in range(1, page_count + 1):  # 1-indexedページ番号
            logger.info(f"ページ {page_num}/{page_count} を分析中...")
            
            try:
                # ページごとにDocument Intelligence分析を実行
                page_str = str(page_num)
                analysis, word_data = self.azure_service.analyze_document_structured(doc_path, page_str)
                
                # ページ情報を追加
                analysis['page_number'] = page_num
                page_analyses.append(analysis)
                page_word_data.append(word_data)
                
                logger.info(f"ページ {page_num} 分析完了: "
                           f"{len(analysis.get('sections', []))}セクション")
                
            except Exception as e:
                logger.error(f"ページ {page_num} の分析中にエラー: {e}")
                # エラーが発生したページは空の結果を追加
                empty_analysis = {
                    'sections': [],
                    'page_number': page_num,
                    'summary': {'total_sections': 0, 'total_paragraphs': 0}
                }
                page_analyses.append(empty_analysis)
                page_word_data.append([])  # 空のワードデータ
        
        # 分析結果を統合
        merged_analysis = self._merge_page_analyses(page_analyses)
        merged_word_data = self._merge_word_data(page_word_data)
        
        logger.info(f"ページごと分析完了: {doc_path}")
        logger.info(f"統合結果: {len(merged_analysis.get('sections', []))}セクション")
        
        return merged_analysis, merged_word_data

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """PDFファイルのページ数を取得
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            ページ数
        """
        try:
            from utils.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            return pdf_processor.get_page_count_from_path(pdf_path)
        except Exception as e:
            logger.error(f"PDFページ数取得エラー: {e}")
            return 0
    
    def _normalize_document_text(self, doc_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """文書分析結果のテキストを正規化
        
        Args:
            doc_analysis: 文書分析結果
            
        Returns:
            正規化後の文書分析結果
        """
        import re
        
        def normalize_text(text: str) -> str:
            """テキストを正規化"""
            if not text:
                return text
            
            # 空白の統一
            text = re.sub(r'\s+', ' ', text)  # 複数空白を1つに
            text = text.strip()
            
            # 記号の統一
            text = text.replace('·', '・')    # 中点の統一
            text = text.replace('−', '-')     # マイナス記号の統一
            text = text.replace('～', '〜')   # 波線の統一
            
            # 全角半角の統一（数字・英字）
            text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
            text = text.translate(str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
            text = text.translate(str.maketrans('ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', 'abcdefghijklmnopqrstuvwxyz'))
            
            return text
        
        # ディープコピーして元データを保持
        import copy
        normalized_analysis = copy.deepcopy(doc_analysis)
        
        # セクション内の段落テキストを正規化
        for section in normalized_analysis.get('sections', []):
            for paragraph in section.get('paragraphs', []):
                if 'content' in paragraph:
                    paragraph['content'] = normalize_text(paragraph['content'])
            
            # para_contents_listも正規化
            if 'para_contents_list' in section:
                section['para_contents_list'] = [
                    normalize_text(content) for content in section['para_contents_list']
                ]
        
        logger.debug("文書テキスト正規化完了")
        return normalized_analysis
    
    def _normalize_word_data(self, word_data: List[Dict]) -> List[Dict]:
        """words_dataのテキストを正規化
        
        Args:
            word_data: 文字レベルのデータリスト
            
        Returns:
            正規化後のwords_data
        """
        import re
        import copy
        
        def normalize_text(text: str) -> str:
            """テキストを正規化"""
            if not text:
                return text
            
            # 記号の統一
            text = text.replace('·', '・')
            text = text.replace('−', '-')
            text = text.replace('～', '〜')
            
            # 全角半角の統一
            text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
            text = text.translate(str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
            text = text.translate(str.maketrans('ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', 'abcdefghijklmnopqrstuvwxyz'))
            
            return text
        
        # ディープコピーして元データを保持
        normalized_word_data = copy.deepcopy(word_data)
        
        # 各ページのwords内のcontentを正規化
        for page_data in normalized_word_data:
            if 'words' in page_data:
                for word in page_data['words']:
                    if 'content' in word:
                        word['content'] = normalize_text(word['content'])
        
        logger.debug("words_data正規化完了")
        return normalized_word_data
    
    def _bbox_to_coords(self, bbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """bbox形式を座標形式に変換"""
        if not bbox_data:
            return None
        
        # 元の座標情報がある場合はそれを優先
        if 'coordinates' in bbox_data and bbox_data['coordinates']:
            coords = bbox_data['coordinates']
            return {
                "left": coords.get('left', 0),
                "top": coords.get('top', 0),
                "right": coords.get('right', coords.get('left', 0) + coords.get('width', 0)),
                "bottom": coords.get('bottom', coords.get('top', 0) + coords.get('height', 0)),
                "width": coords.get('width', 0),
                "height": coords.get('height', 0)
            }
        
        # fallback: x, y, width, heightから座標を計算
        x = bbox_data.get('x', 0)
        y = bbox_data.get('y', 0)
        width = bbox_data.get('width', 0)
        height = bbox_data.get('height', 0)
        
        return {
            "left": x,
            "top": y,
            "right": x + width,
            "bottom": y + height,
            "width": width,
            "height": height
        }

    
    def _save_results(self, analysis_result: Dict[str, Any], output_tag: str):
        """分析結果をファイルに保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON形式で詳細結果を保存
        json_filename = f"llm_diff_v3_4_{output_tag}_{timestamp}.json"
        json_path = Settings.OUTPUT_DIR / json_filename
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        # CSV形式で差分リストを保存
        import csv
        csv_filename = f"llm_diff_v3_4_{output_tag}_{timestamp}.csv"
        csv_path = Settings.OUTPUT_DIR / csv_filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'change_type', 'page', 'page_doc1', 'page_doc2', 'semantic_similarity',
                'original_text', 'modified_text',
                'original_x', 'original_y', 'modified_x', 'modified_y',
                'section_title', 'paragraph_role'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for diff in analysis_result['differences']:
                writer.writerow({
                    'change_type': diff['change_type'],
                    'page': diff['page'],
                    'page_doc1': diff['page_doc1'],
                    'page_doc2': diff['page_doc2'],
                    'semantic_similarity': diff['semantic_similarity'],
                    'original_text': diff['original_text'][:100] + ('...' if len(diff['original_text']) > 100 else ''),
                    'modified_text': diff['modified_text'][:100] + ('...' if len(diff['modified_text']) > 100 else ''),
                    'original_x': diff['original_coordinates']['raw_coordinates'][0] if diff['original_coordinates'] and diff['original_coordinates'].get('raw_coordinates') else '',
                    'original_y': diff['original_coordinates']['raw_coordinates'][1] if diff['original_coordinates'] and diff['original_coordinates'].get('raw_coordinates') else '',
                    'modified_x': diff['modified_coordinates']['raw_coordinates'][0] if diff['modified_coordinates'] and diff['modified_coordinates'].get('raw_coordinates') else '',
                    'modified_y': diff['modified_coordinates']['raw_coordinates'][1] if diff['modified_coordinates'] and diff['modified_coordinates'].get('raw_coordinates') else '',
                    'section_title': diff['structural_info'].get('section_title', ''),
                    'paragraph_role': diff['structural_info'].get('paragraph_role', '')
                })
        
        logger.info(f"結果保存完了:")
        logger.info(f"  JSON: {json_path}")
        logger.info(f"  CSV: {csv_path}")

    def _save_differences_csv(self, differences: List, output_tag: str):
        """差分結果をCSVファイルに保存
        
        Args:
            differences: DiffResultのリスト
            output_tag: 出力ファイルのタグ
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"differences_{output_tag}_{timestamp}.csv"
        csv_path = Settings.OUTPUT_DIR / csv_filename
        
        import csv
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'change_type', 'page', 'page_doc1', 'page_doc2', 'semantic_similarity',
                'original_content', 'modified_content',
                'original_x', 'original_y', 'modified_x', 'modified_y',
                'paragraph_index_1', 'paragraph_index_2', 'role', 'importance',
                'original_section_title', 'modified_section_title',
                'original_para_content', 'modified_para_content'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, diff in enumerate(differences):
                # 新しい座標形式に対応した座標取得
                def get_coord_value(coords_dict, key):
                    if not coords_dict:
                        return ''
                    if 'raw_coordinates' in coords_dict and coords_dict.get('raw_coordinates'):
                        raw_coords = coords_dict['raw_coordinates']
                        if len(raw_coords) >= 8:
                            x_coords = [raw_coords[i] for i in range(0, 8, 2)]
                            y_coords = [raw_coords[i] for i in range(1, 8, 2)]
                            bounds = {
                                'left': min(x_coords), 'top': min(y_coords),
                                'right': max(x_coords), 'bottom': max(y_coords)
                            }
                            return f"{bounds.get(key, 0):.4f}"
                    elif 'bounds' in coords_dict:
                        return f"{coords_dict['bounds'].get(key, 0):.4f}"
                    return f"{coords_dict.get(key, 0):.4f}"
                
                original_coords = diff.original_bbox.get('coordinates') if diff.original_bbox else None
                modified_coords = diff.modified_bbox.get('coordinates') if diff.modified_bbox else None
                
                writer.writerow({
                    'change_type': str(diff.change_type)[11:],
                    'page': diff.page,
                    'page_doc1': diff.page_doc1,
                    'page_doc2': diff.page_doc2,
                    'semantic_similarity': f"{diff.semantic_similarity:.3f}",
                    'original_content': diff.original_bbox.get('content', '') if diff.original_bbox else '',
                    'modified_content': diff.modified_bbox.get('content', '') if diff.modified_bbox else '',
                    'original_x': get_coord_value(original_coords, 'left'),
                    'original_y': get_coord_value(original_coords, 'top'),
                    'modified_x': get_coord_value(modified_coords, 'left'),
                    'modified_y': get_coord_value(modified_coords, 'top'),
                    'paragraph_index_1': diff.original_bbox.get('paragraph_index', '') if diff.original_bbox else '',
                    'paragraph_index_2': diff.modified_bbox.get('paragraph_index', '') if diff.modified_bbox else '',
                    'role': diff.original_bbox.get('role', '') if diff.original_bbox else (diff.modified_bbox.get('role', '') if diff.modified_bbox else ''),
                    'importance': diff.original_bbox.get('importance', '') if diff.original_bbox else (diff.modified_bbox.get('importance', '') if diff.modified_bbox else ''),
                    'original_section_title': diff.original_section.get('title', '') if diff.original_section else '',
                    'modified_section_title': diff.modified_section.get('title', '') if diff.modified_section else '',
                    'original_para_content': diff.original_paragraph.get('content', '')[:200] if diff.original_paragraph else '',
                    'modified_para_content': diff.modified_paragraph.get('content', '')[:200] if diff.modified_paragraph else ''
                })
        
        logger.info(f"差分詳細CSV保存: {csv_path}")
        return csv_path

    def _match_pages_by_content(self, doc1_analysis, doc2_analysis):
        """ページ内容の類似度に基づいてページをマッチング
        
        Args:
            doc1_analysis: 文書1の解析結果
            doc2_analysis: 文書2の解析結果
            
        Returns:
            List[dict]: ページマッチング結果
        """
        doc1_sections = doc1_analysis.get('sections', [])
        doc2_sections = doc2_analysis.get('sections', [])
        
        # ページごとにセクションをグループ化
        doc1_pages = self._group_sections_by_page(doc1_sections)
        doc2_pages = self._group_sections_by_page(doc2_sections)
        
        logger.info(f"ページグループ化結果: 文書1={len(doc1_pages)}ページ, 文書2={len(doc2_pages)}ページ")
        
        page_matches = []
        
        # 各ページの内容を結合してテキスト化
        doc1_page_contents = {}
        for page_num, sections in doc1_pages.items():
            content = self._extract_page_content(sections)
            doc1_page_contents[page_num] = content
        
        doc2_page_contents = {}
        for page_num, sections in doc2_pages.items():
            content = self._extract_page_content(sections)
            doc2_page_contents[page_num] = content
        
        # 全組み合わせでページ内容の類似度を計算
        matches = []
        for page1, content1 in doc1_page_contents.items():
            for page2, content2 in doc2_page_contents.items():
                if not content1 or not content2:
                    continue
                
                similarity = self._calculate_content_similarity(content1, content2)
                if similarity >= 0.3:  # ページマッチングは低い閾値を使用
                    matches.append((page1, page2, similarity))
        
        # 類似度でソートして最適なマッチングを選択
        matches.sort(key=lambda x: x[2], reverse=True)
        
        # 1対1対応でマッチング
        used_pages1 = set()
        used_pages2 = set()
        
        for page1, page2, similarity in matches:
            if page1 not in used_pages1 and page2 not in used_pages2:
                page_match = {
                    'doc1_page': page1,
                    'doc2_page': page2,
                    'similarity': similarity,
                    'doc1_sections': doc1_pages[page1],
                    'doc2_sections': doc2_pages[page2]
                }
                page_matches.append(page_match)
                used_pages1.add(page1)
                used_pages2.add(page2)
                
                logger.info(f"ページマッチ: {page1} ↔ {page2} (類似度: {similarity:.3f})")
        
        # マッチしなかったページをログ出力
        unmatched_pages1 = set(doc1_pages.keys()) - used_pages1
        unmatched_pages2 = set(doc2_pages.keys()) - used_pages2
        
        if unmatched_pages1:
            logger.info(f"文書1のアンマッチページ: {sorted(unmatched_pages1)}")
        if unmatched_pages2:
            logger.info(f"文書2のアンマッチページ: {sorted(unmatched_pages2)}")
        
        return page_matches

    def _group_sections_by_page(self, sections):
        """セクションをページ番号でグループ化"""
        pages = {}
        for section in sections:
            page_num = section.get('page', 1)
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(section)
        return pages

    def _extract_page_content(self, sections):
        """ページ内の全セクションから内容を抽出"""
        all_content = []
        for section in sections:
            paragraphs = section.get('paragraphs', [])
            for para in paragraphs:
                content = para.get('content', '').strip()
                if content:
                    all_content.append(content)
        return ' '.join(all_content)

    def _detect_differences_by_page_matches(self, page_matches, doc1_analysis, doc2_analysis, doc1_word_data, doc2_word_data):
        """ページマッチング結果を使用して差分検出"""
        all_differences = []
        
        for page_match in page_matches:
            doc1_page_sections = page_match['doc1_sections']
            doc2_page_sections = page_match['doc2_sections']
            
            logger.info(f"ページ{page_match['doc1_page']}↔{page_match['doc2_page']}の差分検出開始")
            
            # ページ内セクションのみを含む一時的な解析結果を作成
            temp_doc1_analysis = {
                'sections': doc1_page_sections,
                'source_file': doc1_analysis.get('source_file', '')
            }
            temp_doc2_analysis = {
                'sections': doc2_page_sections,
                'source_file': doc2_analysis.get('source_file', '')
            }
            
            # このページペアでの差分検出
            page_differences = self.diff_detector.detect_easy_differences(
                temp_doc1_analysis, temp_doc2_analysis, doc1_word_data, doc2_word_data
            )
            
            logger.info(f"ページ{page_match['doc1_page']}↔{page_match['doc2_page']}: {len(page_differences)}件の差分")
            all_differences.extend(page_differences)
        
        # マッチしなかったページの処理も追加可能
        # TODO: アンマッチページの全セクションを追加/削除として処理
        
        return all_differences

    def _calculate_content_similarity(self, text1, text2):
        """コンテンツの類似度を計算（数値差分を無視）"""
        import difflib
        
        # 数値を除去したテキストで類似度計算
        text1_without_numbers = self._remove_numbers_from_text(text1)
        text2_without_numbers = self._remove_numbers_from_text(text2)
        
        # 数値除去後のテキストが空でない場合は、数値を除外した類似度を使用
        if text1_without_numbers.strip() and text2_without_numbers.strip():
            return difflib.SequenceMatcher(None, text1_without_numbers, text2_without_numbers).ratio()
        else:
            # 数値のみのテキストの場合は、元のテキストで比較
            return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _remove_numbers_from_text(self, text):
        """テキストから数値を除去"""
        import re
        
        if not text:
            return text
        
        # 全ての数字を「NUM」に置換
        cleaned_text = re.sub(r'\d+', 'NUM', text)
        
        # 連続する空白を単一の空白に変換
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        return cleaned_text.strip()

    def _merge_page_analyses(self, page_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """複数ページの分析結果を統合
        
        Args:
            page_analyses: 各ページの分析結果リスト
            
        Returns:
            統合された分析結果
        """
        if not page_analyses:
            return {
                'sections': [],
                'summary': {'total_sections': 0, 'total_paragraphs': 0}
            }
        
        # 全セクションを統合
        all_sections = []
        total_paragraphs = 0
        
        for page_analysis in page_analyses:
            sections = page_analysis.get('sections', [])
            for section in sections:
                # セクションにページ番号を追加
                section['source_page'] = page_analysis.get('page_number', 1)
                all_sections.append(section)
                
                # パラグラフ数をカウント
                total_paragraphs += len(section.get('paragraphs', []))
        
        # 統合された結果を作成
        merged_result = {
            'sections': all_sections,
            'summary': {
                'total_sections': len(all_sections),
                'total_paragraphs': total_paragraphs
            }
        }
        
        # 最初のページの他の情報を継承
        if page_analyses:
            first_page = page_analyses[0]
            for key, value in first_page.items():
                if key not in ['sections', 'summary', 'page_number']:
                    merged_result[key] = value
        
        logger.info(f"ページ分析統合完了: {len(all_sections)}セクション, {total_paragraphs}パラグラフ")
        return merged_result

    def _merge_word_data(self, page_word_data: List[Any]) -> List[Any]:
        """複数ページのワードデータを統合
        
        Args:
            page_word_data: 各ページのワードデータリスト
            
        Returns:
            統合されたワードデータ
        """
        if not page_word_data:
            return []
        
        # 全ページのワードデータを統合
        merged_words = []
        
        for page_data in page_word_data:
            if page_data:  # 空でない場合のみ追加
                if isinstance(page_data, list):
                    merged_words.extend(page_data)
                else:
                    merged_words.append(page_data)
        
        logger.info(f"ワードデータ統合完了: {len(merged_words)}ページ分")
        return merged_words


def main():
    """メイン処理"""
    print("=== LLM文書差分検出システム v3.4 ===")
    print("Document Intelligenceのセクション階層と座標情報を活用")
    
    # テスト用のファイルパス
    doc1_path = "/home/dev/prj-ms-document-check.worktree/worktree1/data/data5/sougou/サンプル②2024.pdf"
    doc2_path = "/home/dev/prj-ms-document-check.worktree/worktree1/data/data5/sougou/サンプル②2025.pdf"
    
    # システムの初期化
    system = LLMDocsDiffV4()
    
    try:
        # 全ページを分析
        result = system.analyze_documents(
            doc1_path=doc1_path,
            doc2_path=doc2_path,
            pages=None,  # 全ページを対象
            output_tag="sougou_all_pages"
        )
        
        print(f"\n=== 分析結果サマリー ===")
        print(f"総差分数: {result['summary']['total_differences']}")
        print(f"変更: {result['summary']['modifications']}")
        print(f"追加: {result['summary']['additions']}")
        print(f"削除: {result['summary']['deletions']}")
        
        # 主要な変更を表示
        print(f"\n=== 主要な変更（上位5件） ===")
        for i, diff in enumerate(result['differences'][:5]):
            print(f"{i+1}. {diff['change_type']}")
            print(f"   類似度: {diff['semantic_similarity']:.3f}")
            if diff['original_text']:
                print(f"   元: {diff['original_text'][:80]}...")
            if diff['modified_text']:
                print(f"   新: {diff['modified_text'][:80]}...")
            print()
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    main()