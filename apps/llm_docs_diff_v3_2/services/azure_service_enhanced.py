"""
Azure Document Intelligenceサービス（拡張版）
段落、行、単語の階層構造を保持
"""
from typing import List, Optional, Dict, Any, Union
import logging
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential

from ..config.settings import settings
from ..models.bbox_models import BBoxTextData
from ..utils.page_splitter import PageSplitter

logger = logging.getLogger(__name__)


class AzureDocumentServiceEnhanced:
    """Azure Document Intelligenceサービス（拡張版）"""
    
    def __init__(self):
        """初期化"""
        if not settings.USE_AZURE_FOR_OCR:
            logger.info("Azure Document Intelligence is disabled")
            self.client = None
            return
            
        if not settings.AZURE_DOCUMENT_INTELLIGENCE_KEY or not settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT:
            raise ValueError(
                "Azure Document Intelligence credentials are not set. "
                "Please set AZURE_DOCUMENT_INTELLIGENCE_KEY and AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
            )
        
        self.client = DocumentIntelligenceClient(
            endpoint=settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_DOCUMENT_INTELLIGENCE_KEY)
        )
    
    def extract_layout_with_hierarchy(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """PDFからレイアウト情報を階層構造で抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            階層構造を持つレイアウト情報
            {
                "paragraphs": 段落情報のリスト,
                "lines": 行情報のリスト,
                "words": 単語情報のリスト,
                "raw_result": 生のAnalyzeResult
            }
        """
        if not self.client:
            raise RuntimeError("Azure Document Intelligence is not configured")
        
        try:
            # PDFサイズをチェックし、大きすぎる場合は最初の5ページのみを処理
            from ..utils.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            
            # 有料版では制限なし - 全ページを処理
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            print(f"[DEBUG] Processing all {total_pages} pages with Azure Document Intelligence")
            
            # Document Intelligenceでレイアウト解析
            print(f"[DEBUG] Sending {len(pdf_bytes)} bytes to Azure Document Intelligence")
            
            # High Resolution機能を有効化（バイナリ形式を維持）
            features = []
            if settings.USE_HIGH_RESOLUTION_OCR:
                # Azure Document Intelligenceの正しいfeature名を使用
                features.append("ocr.highResolution")
                logger.info("Azure Document Intelligence: High Resolution OCR enabled")
            else:
                logger.info("Azure Document Intelligence: Standard resolution OCR")
            
            try:
                poller = self.client.begin_analyze_document(
                    "prebuilt-layout",
                    body=pdf_bytes,
                    content_type="application/pdf",
                    features=features if features else None,  # High Resolution OCRを有効化
                    locale="ja-JP"  # 日本語を明示的に指定
                )
                # タイムアウトを増やして結果を取得
                result: AnalyzeResult = poller.result(timeout=300)  # 5分のタイムアウト
            except Exception as e:
                print(f"[DEBUG] Azure API error: {e}")
                raise
            
            # Azureから返されたページ数を確認
            if hasattr(result, 'pages') and result.pages:
                print(f"[DEBUG] Azure returned {len(result.pages)} pages")
                logger.info(f"Azure returned {len(result.pages)} pages")
                for idx, page in enumerate(result.pages):
                    print(f"[DEBUG] Page {idx}: page_number={getattr(page, 'page_number', 'N/A')}, "
                          f"lines={len(page.lines) if hasattr(page, 'lines') else 0}, "
                          f"words={len(page.words) if hasattr(page, 'words') else 0}")
            else:
                print(f"[DEBUG] Azure result has no pages attribute or pages is empty")
                logger.warning("Azure result has no pages attribute or pages is empty")
            
            # 結果のその他の属性を確認
            print(f"[DEBUG] Result attributes: {dir(result)}")
            if hasattr(result, 'content') and result.content:
                print(f"[DEBUG] Result content length: {len(result.content)}")
            if hasattr(result, 'paragraphs') and result.paragraphs:
                # 段落からページ番号を取得
                page_nums = set()
                for para in result.paragraphs:
                    if hasattr(para, 'bounding_regions'):
                        for region in para.bounding_regions:
                            if hasattr(region, 'page_number'):
                                page_nums.add(region.page_number)
                print(f"[DEBUG] Unique page numbers from paragraphs: {sorted(page_nums)}")
            
            # 階層構造で情報を整理
            hierarchy = {
                "paragraphs": self._extract_paragraphs(result),
                "lines": self._extract_lines(result),
                "words": self._extract_words(result),
                "raw_result": result
            }
            
            logger.info(f"Extracted hierarchy: {len(hierarchy['paragraphs'])} paragraphs, "
                       f"{len(hierarchy['lines'])} lines, {len(hierarchy['words'])} words")
            
            return hierarchy
            
        except Exception as e:
            logger.error(f"Azure Document Intelligence extraction failed: {e}")
            raise
    
    def extract_layout_with_hierarchy_batch(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """PDFから階層構造でレイアウト情報を抽出（2ページずつバッチ処理）
        
        無料プランの2ページ制限を回避するため、PDFを2ページずつに分割して処理
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            階層構造の辞書（全ページの結果を統合）
        """
        if not self.client:
            raise RuntimeError("Azure Document Intelligence is not configured")
        
        try:
            import fitz
            from ..utils.pdf_utils import PDFProcessor
            pdf_processor = PDFProcessor()
            
            # PDFのページ数を確認
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            
            # テスト用に最大ページ数を制限
            max_pages = getattr(settings, 'TEST_MAX_PAGES', 5)
            if max_pages and total_pages > max_pages:
                print(f"[DEBUG] Limiting PDF to {max_pages} pages")
                pdf_bytes = pdf_processor.limit_pdf_pages(pdf_bytes, max_pages)
                total_pages = max_pages
            
            print(f"[DEBUG] Processing {total_pages} pages in batches of 2")
            
            # 結果を統合するためのリスト
            all_paragraphs = []
            all_lines = []
            all_words = []
            
            # 2ページずつ処理
            for start_page in range(0, total_pages, 2):
                end_page = min(start_page + 1, total_pages - 1)
                print(f"[DEBUG] Processing pages {start_page+1}-{end_page+1}")
                
                # 指定ページ範囲のPDFを作成
                source_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
                chunk_pdf = fitz.open()
                chunk_pdf.insert_pdf(source_pdf, from_page=start_page, to_page=end_page)
                
                # バイトデータに変換
                import io
                buffer = io.BytesIO()
                chunk_pdf.save(buffer)
                chunk_bytes = buffer.getvalue()
                
                source_pdf.close()
                chunk_pdf.close()
                
                # Azure Document Intelligenceで処理
                # High Resolution機能を有効化（バイナリ形式を維持）
                features = []
                if settings.USE_HIGH_RESOLUTION_OCR:
                    features.append("ocr.highResolution")
                
                try:
                    poller = self.client.begin_analyze_document(
                        "prebuilt-layout",
                        body=chunk_bytes,
                        content_type="application/pdf",
                        features=features if features else None,  # High Resolution OCRを有効化
                        locale="ja-JP"  # 日本語を明示的に指定
                    )
                    result = poller.result(timeout=300)
                    
                    # 段落を抽出して追加
                    chunk_paragraphs = self._extract_paragraphs(result)
                    for para in chunk_paragraphs:
                        # ページ番号を調整
                        para['page'] = para.get('page', 0) + start_page
                        all_paragraphs.append(para)
                    
                    # 行を抽出して追加
                    chunk_lines = self._extract_lines(result)
                    for line in chunk_lines:
                        line['page'] = line.get('page', 0) + start_page
                        all_lines.append(line)
                    
                    # 単語を抽出して追加
                    chunk_words = self._extract_words(result)
                    for word in chunk_words:
                        word['page'] = word.get('page', 0) + start_page
                        all_words.append(word)
                    
                    print(f"[DEBUG] Processed chunk: {len(result.pages) if hasattr(result, 'pages') else 0} pages")
                    
                except Exception as e:
                    print(f"[DEBUG] Error processing pages {start_page+1}-{end_page+1}: {e}")
                    continue
            
            # 統合された結果を返す
            print(f"[DEBUG] Total processed: {len(all_paragraphs)} paragraphs, "
                  f"{len(all_lines)} lines, {len(all_words)} words")
            
            return {
                "paragraphs": all_paragraphs,
                "lines": all_lines,
                "words": all_words
            }
            
        except Exception as e:
            logger.error(f"Batch Azure extraction failed: {e}")
            raise
    
    def _extract_paragraphs(self, result: AnalyzeResult) -> List[Dict[str, Any]]:
        """段落情報を抽出"""
        paragraphs = []
        
        if hasattr(result, 'paragraphs') and result.paragraphs:
            for idx, para in enumerate(result.paragraphs):
                para_info = {
                    "id": idx,
                    "content": para.content,
                    "page": para.bounding_regions[0].page_number - 1 if para.bounding_regions else 0,
                    "role": getattr(para, 'role', None),
                }
                
                # バウンディングボックスを計算
                if para.bounding_regions and para.bounding_regions[0].polygon:
                    polygon = para.bounding_regions[0].polygon
                    para_info["bbox"] = self._polygon_to_bbox(polygon)
                
                paragraphs.append(para_info)
        
        return paragraphs
    
    def _extract_lines(self, result: AnalyzeResult) -> List[Dict[str, Any]]:
        """行情報を抽出"""
        lines = []
        line_id = 0
        
        for page_idx, page in enumerate(result.pages):
            if hasattr(page, 'lines') and page.lines:
                for line in page.lines:
                    line_info = {
                        "id": line_id,
                        "content": line.content,
                        "page": page_idx,
                    }
                    
                    # バウンディングボックスを計算
                    if hasattr(line, 'polygon') and line.polygon:
                        line_info["bbox"] = self._polygon_to_bbox(line.polygon)
                    
                    lines.append(line_info)
                    line_id += 1
        
        return lines
    
    def _extract_words(self, result: AnalyzeResult) -> List[BBoxTextData]:
        """単語情報を抽出（既存の形式で）"""
        bbox_data_list = []
        
        for page_idx, page in enumerate(result.pages):
            for word in page.words:
                # バウンディングボックスを正規化
                if hasattr(word, 'polygon') and word.polygon:
                    points = word.polygon
                elif hasattr(word, 'bounding_box') and word.bounding_box:
                    points = word.bounding_box
                else:
                    logger.warning(f"Word without polygon or bounding_box: {word.content}")
                    continue
                
                bbox = self._polygon_to_bbox(points)
                
                bbox_data = BBoxTextData(
                    bbox=bbox,
                    text=word.content,
                    page=page_idx
                )
                bbox_data_list.append(bbox_data)
        
        return bbox_data_list
    
    def _polygon_to_bbox(self, polygon: Union[List[float], List[Any]]) -> List[float]:
        """ポリゴンからバウンディングボックスを計算
        
        Args:
            polygon: ポリゴンデータ
            
        Returns:
            [x, y, width, height] 形式のバウンディングボックス
        """
        # ポイントからバウンディングボックスを計算
        if isinstance(polygon, list) and len(polygon) >= 8:
            # [x1,y1,x2,y2,x3,y3,x4,y4] 形式
            x_coords = [polygon[i] for i in range(0, 8, 2)]
            y_coords = [polygon[i] for i in range(1, 8, 2)]
        else:
            # オブジェクトのリストの場合
            x_coords = [p.x if hasattr(p, 'x') else p[0] for p in polygon]
            y_coords = [p.y if hasattr(p, 'y') else p[1] for p in polygon]
        
        x_min = min(x_coords)
        y_min = min(y_coords)
        width = max(x_coords) - x_min
        height = max(y_coords) - y_min
        
        # インチからポイントに変換（1インチ = 72ポイント）
        return [x_min * 72, y_min * 72, width * 72, height * 72]
    
    def extract_layout_from_lines(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """PDFから行ベースでレイアウト情報を抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            行ベースのBBoxデータのリスト
        """
        # 有料版では一度に全ページを処理
        hierarchy = self.extract_layout_with_hierarchy(pdf_bytes)
        
        # 行データを既存の形式に変換
        line_bbox_list = []
        for line in hierarchy["lines"]:
            if "bbox" in line:
                line_data = {
                    "text": line["content"],
                    "bbox": line["bbox"],
                    "x": line["bbox"][0],
                    "y": line["bbox"][1],
                    "width": line["bbox"][2],
                    "height": line["bbox"][3],
                    "page": line["page"],
                    "is_line": True  # 行データであることを示すフラグ
                }
                line_bbox_list.append(line_data)
        
        return line_bbox_list
    
    def extract_layout_from_paragraphs(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """PDFから段落ベースでレイアウト情報を抽出
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            段落ベースのBBoxデータのリスト
        """
        # 有料版では一度に全ページを処理
        hierarchy = self.extract_layout_with_hierarchy(pdf_bytes)
        
        # 段落データを既存の形式に変換
        para_bbox_list = []
        for para in hierarchy["paragraphs"]:
            if "bbox" in para:
                para_data = {
                    "text": para["content"],
                    "bbox": para["bbox"],
                    "x": para["bbox"][0],
                    "y": para["bbox"][1],
                    "width": para["bbox"][2],
                    "height": para["bbox"][3],
                    "page": para["page"],
                    "is_paragraph": True,  # 段落データであることを示すフラグ
                    "role": para.get("role")  # 段落の役割（タイトル、本文など）
                }
                para_bbox_list.append(para_data)
        
        return para_bbox_list
    
    def extract_layout_from_lines_with_split(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """PDFから行ベースでレイアウト情報を抽出（ページ分割版）
        
        各ページを上下2分割してOCR精度を向上させる
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            行ベースのBBoxデータのリスト
        """
        if not self.client:
            raise RuntimeError("Azure Document Intelligence is not configured")
        
        try:
            import fitz
            from ..utils.pdf_utils import PDFProcessor
            
            # ページ分割器を初期化（10%の重複領域）
            splitter = PageSplitter(overlap_ratio=0.1, scale_factor=2.0)
            
            # PDFのページ数を確認
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            
            # テスト用に最大ページ数を制限
            max_pages = getattr(settings, 'TEST_MAX_PAGES', None)
            if max_pages and total_pages > max_pages:
                print(f"[DEBUG] Limiting PDF to {max_pages} pages for split OCR")
                pdf_processor = PDFProcessor()
                pdf_bytes = pdf_processor.limit_pdf_pages(pdf_bytes, max_pages)
                total_pages = max_pages
            
            print(f"[DEBUG] Processing {total_pages} pages with 2-way (top/bottom) split")
            
            # 全ページの結果を格納
            all_lines = []
            
            # 各ページを処理
            for page_num in range(total_pages):
                print(f"[DEBUG] Processing page {page_num + 1}/{total_pages} with 2-way split")
                
                # ページを上下2分割
                regions = splitter.split_page_to_regions(pdf_bytes, page_num)
                
                # 各領域のOCR結果を格納
                region_results = []
                
                for region_data in regions:
                    region = region_data['region']
                    image_bytes = region_data['image_bytes']
                    
                    try:
                        # 画像としてAzure Document Intelligenceに送信
                        print(f"[DEBUG] Processing {region['quadrant']} region of page {page_num + 1}")
                        
                        # High Resolution機能を有効化
                        features = []
                        if settings.USE_HIGH_RESOLUTION_OCR:
                            features.append("ocr.highResolution")
                        
                        poller = self.client.begin_analyze_document(
                            "prebuilt-read",  # 画像用のモデル
                            body=image_bytes,
                            content_type="image/png",
                            features=features if features else None,
                            locale="ja-JP"
                        )
                        
                        result = poller.result(timeout=300)
                        
                        # 行情報を抽出
                        lines = []
                        if hasattr(result, 'pages') and result.pages:
                            for page in result.pages:
                                if hasattr(page, 'lines') and page.lines:
                                    for line in page.lines:
                                        if hasattr(line, 'content') and line.content.strip():
                                            # 画像OCRの場合、polygonはピクセル座標で返される
                                            if hasattr(line, 'polygon') and line.polygon:
                                                # ピクセル座標のまま保存（後で変換）
                                                x_coords = [line.polygon[i] for i in range(0, len(line.polygon), 2)]
                                                y_coords = [line.polygon[i] for i in range(1, len(line.polygon), 2)]
                                                x_min = min(x_coords)
                                                y_min = min(y_coords)
                                                width = max(x_coords) - x_min
                                                height = max(y_coords) - y_min
                                                line_bbox = [x_min, y_min, width, height]
                                            else:
                                                line_bbox = [0, 0, 0, 0]
                                            
                                            lines.append({
                                                'text': line.content,
                                                'bbox': line_bbox
                                            })
                        
                        region_results.append({
                            'region': region,
                            'text_items': lines
                        })
                        
                        print(f"[DEBUG] Found {len(lines)} lines in {region['quadrant']} region")
                        
                    except Exception as e:
                        print(f"[DEBUG] Error processing {region['quadrant']} region: {e}")
                        continue
                
                # 2つの領域の結果をマージ
                if region_results:
                    # マージ前に各領域の「補」を含む行数をカウント
                    for i, result in enumerate(region_results):
                        ho_count = sum(1 for item in result['text_items'] if '補' in item['text'])
                        print(f"[DEBUG] Page {page_num + 1}, {result['region']['quadrant']} region: {ho_count} lines containing '補'")
                    
                    merged_lines = splitter.merge_ocr_results(region_results)
                    
                    # マージ後の「補」を含む行数をカウント
                    ho_count_after = sum(1 for line in merged_lines if '補' in line['text'])
                    print(f"[DEBUG] Page {page_num + 1} after merging: {ho_count_after} lines containing '補'")
                    
                    # ページ番号を追加して形式を整える
                    for line in merged_lines:
                        line['page'] = page_num
                        line['is_line'] = True
                        all_lines.append(line)
                    
                    print(f"[DEBUG] Total {len(merged_lines)} unique lines after merging for page {page_num + 1}")
            
            # 全体の「補」を含む行数をカウント
            total_ho_count = sum(1 for line in all_lines if '補' in line['text'])
            print(f"[DEBUG] Total lines extracted with split OCR: {len(all_lines)}")
            print(f"[DEBUG] Total lines containing '補': {total_ho_count}")
            
            return all_lines
            
        except Exception as e:
            logger.error(f"Split OCR extraction failed: {e}")
            # フォールバック: 通常のOCRを使用
            print(f"[DEBUG] Falling back to standard OCR due to error: {e}")
            return self.extract_layout_from_lines(pdf_bytes)