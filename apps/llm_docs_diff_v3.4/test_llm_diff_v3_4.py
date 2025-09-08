# coding: utf-8
"""
LLM文書差分検出システム v3.4 テストスクリプト
Document Intelligenceのセクション階層と座標情報を活用した高度な差分検出
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
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
        
        doc1_analysis, doc1_word_data = self.azure_service.analyze_document_structured(doc1_path, pages)
        doc1_analysis['source_file'] = doc1_path
        
        doc2_analysis, doc2_word_data = self.azure_service.analyze_document_structured(doc2_path, pages)
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
        
        # 3. 構造化差分検出
        logger.info("ステップ3: 構造化差分検出")
        
        differences = self.diff_detector.detect_easy_differences(combined_doc1_analysis, combined_doc2_analysis, doc1_word_data, doc2_word_data)
        
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
                'change_type', 'page', 'semantic_similarity',
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
                'change_type', 'page', 'semantic_similarity',
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


def main():
    """メイン処理"""
    print("=== LLM文書差分検出システム v3.4 ===")
    print("Document Intelligenceのセクション階層と座標情報を活用")
    
    # テスト用のファイルパス
    doc1_path = "/home/dev/prj-ms-document-check.worktree/worktree1/data/data3/sougou/1-2Pサンプル②2024.pdf"
    doc2_path = "/home/dev/prj-ms-document-check.worktree/worktree1/data/data3/sougou/1-2Pサンプル②2025.pdf"
    
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