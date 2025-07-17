"""
文書解析エンジン（ベースラインから継承）
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import time
from pathlib import Path

from ..models.bbox_models import (
    BBoxTextData, ComparisonResult, DiffResult, 
    ChangeType, LLMAnalysisResult
)
from ..services.llm_service import LLMService
from ..services.azure_service import AzureDocumentService
from ..services.pdf_converter import PDFConverterFactory
from ..config.settings import settings
from ..utils.pdf_utils import PDFProcessor
from .diff_detector import EnhancedDiffDetector
from .text_grouping import group_text_elements, split_by_spreads

logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """LLM強化文書解析エンジン"""
    
    def __init__(self):
        """初期化"""
        self.llm_service = LLMService()
        self.azure_service = AzureDocumentService() if settings.USE_AZURE_FOR_OCR else None
        self.pdf_converter = PDFConverterFactory.create_converter("libreoffice")
        self.pdf_processor = PDFProcessor()
        self.diff_detector = EnhancedDiffDetector()
        
        # 出力ディレクトリ作成
        settings.create_output_directories()
    
    def analyze_documents(self, file1_path: str, file2_path: str) -> Tuple[ComparisonResult, bytes, bytes]:
        """2つの文書を比較解析
        
        Args:
            file1_path: 比較元文書のパス
            file2_path: 比較先文書のパス
            
        Returns:
            Tuple[ComparisonResult, bytes, bytes]: 比較結果とPDFバイトデータ
        """
        start_time = time.time()
        
        try:
            # ファイル読み込みとPDF変換
            logger.info(f"Loading documents: {file1_path}, {file2_path}")
            pdf1_bytes = self._load_and_convert(file1_path)
            pdf2_bytes = self._load_and_convert(file2_path)
            
            # BBoxデータ抽出
            logger.info("Extracting layout information...")
            bbox_list1 = self._extract_bbox_data(pdf1_bytes)
            bbox_list2 = self._extract_bbox_data(pdf2_bytes)
            
            # 読み順序推定
            logger.info("Estimating reading order...")
            ordered_bbox1 = self._estimate_reading_order(bbox_list1)
            ordered_bbox2 = self._estimate_reading_order(bbox_list2)
            
            # 差分検出
            logger.info("Detecting differences...")
            diff_results = self.diff_detector.detect_differences(
                ordered_bbox1, ordered_bbox2
            )
            
            # 重要度評価をスキップ
            
            # LLM解析
            logger.info("Performing LLM analysis...")
            llm_analysis = self._perform_llm_analysis(
                ordered_bbox1, ordered_bbox2, diff_results
            )
            
            execution_time = time.time() - start_time
            
            # 結果をまとめる
            result = ComparisonResult(
                diff_results=diff_results,
                reading_order_doc1=ordered_bbox1,
                reading_order_doc2=ordered_bbox2,
                llm_analysis=llm_analysis,
                execution_time=execution_time,
                metadata={
                    "file1": file1_path,
                    "file2": file2_path,
                    "doc1_pages": max(b["page"] for b in bbox_list1) + 1 if bbox_list1 else 0,
                    "doc2_pages": max(b["page"] for b in bbox_list2) + 1 if bbox_list2 else 0,
                    "total_differences": len(diff_results),
                    "llm_model": settings.OPENAI_MODEL,
                    "azure_ocr_used": settings.USE_AZURE_FOR_OCR,
                    "doc1_boxes": bbox_list1,  # 元の順序のデータ
                    "doc2_boxes": bbox_list2   # 元の順序のデータ
                }
            )
            
            logger.info(f"Analysis completed in {execution_time:.2f} seconds")
            return result, pdf1_bytes, pdf2_bytes
            
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            raise
    
    def _load_and_convert(self, file_path: str) -> bytes:
        """ファイルを読み込み、必要に応じてPDFに変換
        
        Args:
            file_path: ファイルパス
            
        Returns:
            PDFのバイトデータ
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # ファイルサイズチェック
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File size ({file_size_mb:.1f}MB) exceeds limit "
                f"({settings.MAX_FILE_SIZE_MB}MB)"
            )
        
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        
        # PDFの場合はそのまま返す
        if path.suffix.lower() == '.pdf':
            return file_bytes
        
        # Word/PowerPointの場合はPDFに変換
        if path.suffix.lower() in ['.docx', '.doc']:
            logger.info("Converting Word document to PDF...")
            return self.pdf_converter.convert_to_pdf(file_bytes, 'docx')
        elif path.suffix.lower() in ['.pptx', '.ppt']:
            logger.info("Converting PowerPoint document to PDF...")
            return self.pdf_converter.convert_to_pdf(file_bytes, 'pptx')
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    
    def _extract_bbox_data(self, pdf_bytes: bytes) -> List[BBoxTextData]:
        """PDFからBBoxデータを抽出
        
        Args:
            pdf_bytes: PDFのバイトデータ
            
        Returns:
            BBoxTextDataのリスト
        """
        # Azure Document Intelligenceを使用する場合
        if self.azure_service and settings.USE_AZURE_FOR_OCR:
            logger.info("Using Azure Document Intelligence for extraction...")
            bbox_list = self.azure_service.extract_layout_from_pdf(pdf_bytes)
        else:
            # 通常のPDF処理
            logger.info("Using standard PDF extraction...")
            bbox_list = self.pdf_processor.extract_bbox_data(pdf_bytes)
        
        # ページ数制限（テスト用）
        max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
        if max_pages:
            # 指定ページ数までのデータのみを使用
            filtered_list = [bbox for bbox in bbox_list if bbox["page"] < max_pages]
            logger.info(f"Limited to {max_pages} pages for testing (filtered from {len(bbox_list)} to {len(filtered_list)} boxes)")
            return filtered_list
        
        return bbox_list
    
    def _estimate_reading_order(self, bbox_list: List[BBoxTextData]) -> List[BBoxTextData]:
        """LLMを使用して読み順序を推定（見開き単位）
        
        Args:
            bbox_list: BBoxTextDataのリスト
            
        Returns:
            順序付けされたBBoxTextDataのリスト
        """
        if not bbox_list:
            return []
        
        # 斜め文字や近接する要素をグループ化
        logger.info("Grouping text elements...")
        grouped_list = group_text_elements(bbox_list)
        
        # ページごとにグループ化
        pages = {}
        for bbox_data in grouped_list:
            page = bbox_data["page"]
            if page not in pages:
                pages[page] = []
            pages[page].append(bbox_data)
        
        # 見開き（2ページ）単位に分割
        spreads = split_by_spreads(pages)
        logger.info(f"Processing {len(spreads)} spreads")
        
        ordered_list = []
        current_global_index = 0  # 全体の通し番号
        
        # 各見開きごとに読み順序を推定
        for spread_idx, spread_data in enumerate(spreads):
            if not spread_data:
                continue
            
            # 見開きのページ範囲を特定
            page_nums = sorted(set(item["page"] for item in spread_data))
            if len(page_nums) == 1:
                # 単独ページ（表紙または最終ページ）
                if page_nums[0] == 0:
                    spread_desc = "表紙（ページ1）"
                else:
                    spread_desc = f"ページ{page_nums[0] + 1}"
            else:
                # 見開きページ
                spread_desc = f"見開きページ{page_nums[0] + 1}-{page_nums[-1] + 1}"
            
            logger.info(f"Processing {spread_desc} with {len(spread_data)} elements (starting from global index {current_global_index + 1})")
            
            try:
                # LLMで読み順序を推定（開始番号を伝える）
                order_indices = self.llm_service.estimate_reading_order(
                    spread_data,
                    spread_desc,
                    is_spread=(len(page_nums) > 1),
                    start_number=current_global_index + 1
                )
                
                # インデックスに従って並び替え
                if isinstance(order_indices, list) and all(isinstance(i, int) for i in order_indices):
                    # 正しく並び替えられた要素を追加
                    ordered_spread = []
                    included_indices = set()
                    
                    for idx in order_indices:
                        if idx < len(spread_data) and idx not in included_indices:
                            # グループ化された要素の場合、元の要素に展開
                            item = spread_data[idx]
                            # 全体の順序番号を付与
                            item = item.copy()
                            item["global_order"] = current_global_index + len(ordered_spread) + 1
                            ordered_spread.append(item)
                            included_indices.add(idx)
                    
                    # LLMが返さなかった要素を追加
                    for i in range(len(spread_data)):
                        if i not in included_indices:
                            item = spread_data[i].copy()
                            item["global_order"] = current_global_index + len(ordered_spread) + 1
                            ordered_spread.append(item)
                    
                    # 現在の全体インデックスを更新
                    current_global_index += len(ordered_spread)
                    ordered_list.extend(ordered_spread)
                else:
                    # エラーの場合は元の順序を使用
                    logger.warning(f"Failed to get valid order for {spread_desc}, using original order")
                    for item in spread_data:
                        item = item.copy()
                        item["global_order"] = current_global_index + 1
                        current_global_index += 1
                        ordered_list.append(item)
                
            except Exception as e:
                logger.warning(f"Failed to estimate reading order for {spread_desc}: {e}")
                # フォールバック: 元の順序を使用
                for item in spread_data:
                    item = item.copy()
                    item["global_order"] = current_global_index + 1
                    current_global_index += 1
                    ordered_list.append(item)
        
        return ordered_list
    
    def _process_pages_individually(self, pages: Dict[int, List[BBoxTextData]]) -> List[BBoxTextData]:
        """ページごとに読み順序を推定（フォールバック用）
        
        Args:
            pages: ページ番号をキーとするBBoxデータの辞書
            
        Returns:
            順序付けされたBBoxTextDataのリスト
        """
        ordered_list = []
        
        for page in sorted(pages.keys()):
            page_bboxes = pages[page]
            
            try:
                order_indices = self.llm_service.estimate_reading_order(
                    page_bboxes,
                    f"ページ{page + 1}のレイアウト"
                )
                
                if isinstance(order_indices, list) and all(isinstance(i, int) for i in order_indices):
                    ordered_page = [page_bboxes[i] for i in order_indices 
                                  if i < len(page_bboxes)]
                    # 不足分を追加
                    included_indices = set(order_indices)
                    for i in range(len(page_bboxes)):
                        if i not in included_indices:
                            ordered_page.append(page_bboxes[i])
                    ordered_list.extend(ordered_page)
                else:
                    ordered_list.extend(page_bboxes)
                
            except Exception as e:
                logger.warning(f"Failed to estimate reading order for page {page}: {e}")
                ordered_list.extend(page_bboxes)
        
        return ordered_list
    
    
    def _perform_llm_analysis(self, bbox_list1: List[BBoxTextData], 
                            bbox_list2: List[BBoxTextData],
                            diff_results: List[DiffResult]) -> LLMAnalysisResult:
        """LLMによる総合的な文書解析
        
        Args:
            bbox_list1: 文書1のBBoxデータ
            bbox_list2: 文書2のBBoxデータ
            diff_results: 差分結果
            
        Returns:
            LLM解析結果
        """
        try:
            # 文書構造解析
            structure1 = self.llm_service.analyze_document_structure(bbox_list1)
            structure2 = self.llm_service.analyze_document_structure(bbox_list2)
            
            # 変更要約
            key_changes = self.llm_service.summarize_changes(diff_results)
            
            # リスク評価
            risk_assessment = self._assess_risks(diff_results)
            
            # 文書要約
            doc_summary = f"文書タイプ: {structure2.get('document_type', '不明')}\n"
            doc_summary += f"要約: {structure2.get('summary', '')}"
            
            return LLMAnalysisResult(
                document_summary=doc_summary,
                structure_analysis={
                    "original": structure1,
                    "modified": structure2
                },
                key_changes=key_changes,
                risk_assessment=risk_assessment
            )
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # 最小限の結果を返す
            return LLMAnalysisResult(
                document_summary="解析に失敗しました",
                structure_analysis={},
                key_changes=["変更内容の解析に失敗しました"],
                risk_assessment={"error": 1.0}
            )
    
    def _assess_risks(self, diff_results: List[DiffResult]) -> Dict[str, float]:
        """変更のリスクを評価
        
        Args:
            diff_results: 差分結果
            
        Returns:
            リスク評価の辞書
        """
        if not diff_results:
            return {"overall": 0.0}
        
        # 変更タイプ別の集計
        type_counts = {}
        for diff in diff_results:
            change_type = diff.change_type.value
            type_counts[change_type] = type_counts.get(change_type, 0) + 1
        
        # リスク評価（変更タイプの割合に基づく）
        risk_assessment = {
            "overall": min(len(diff_results) / 100, 1.0),  # 変更数に基づく評価
            "deletion_ratio": type_counts.get("deletion", 0) / max(len(diff_results), 1),
            "modification_ratio": type_counts.get("modification", 0) / max(len(diff_results), 1),
            "addition_ratio": type_counts.get("addition", 0) / max(len(diff_results), 1)
        }
        
        return risk_assessment