"""
PDF Text Extraction Utility
Extract text from PDF files page by page for difference detection
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional
import re

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

logger = logging.getLogger(__name__)


class PDFTextExtractor:
    """Extract text from PDF files page by page"""
    
    def __init__(self):
        if not HAS_PYMUPDF:
            logger.warning("PyMuPDF not available. PDF extraction will be limited.")
    
    def extract_pages_text(self, pdf_path: Path, max_pages: Optional[int] = None) -> Dict[int, str]:
        """
        Extract text from PDF pages
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum number of pages to extract (None for all)
            
        Returns:
            Dictionary mapping page numbers (1-indexed) to page text
        """
        if not HAS_PYMUPDF:
            logger.error("PyMuPDF is required for PDF text extraction")
            return {}
            
        logger.info(f"Extracting text from PDF: {pdf_path}")
        
        pages_text = {}
        
        try:
            # Open PDF document
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            
            logger.info(f"PDF has {total_pages} pages")
            
            # Determine pages to process
            pages_to_process = min(max_pages or total_pages, total_pages)
            
            for page_num in range(pages_to_process):
                try:
                    # Get page (0-indexed in PyMuPDF)
                    page = doc[page_num]
                    
                    # Extract text with layout preservation
                    text = page.get_text("text")
                    
                    # Clean and normalize text
                    cleaned_text = self._clean_extracted_text(text)
                    
                    # Store with 1-indexed page number
                    pages_text[page_num + 1] = cleaned_text
                    
                    logger.debug(f"Page {page_num + 1}: extracted {len(cleaned_text)} characters")
                    
                except Exception as e:
                    logger.error(f"Error extracting text from page {page_num + 1}: {e}")
                    continue
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Error opening PDF file {pdf_path}: {e}")
            return {}
        
        logger.info(f"Successfully extracted text from {len(pages_text)} pages")
        return pages_text
    
    def _clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted PDF text"""
        if not text:
            return ""
        
        # Remove common PDF artifacts first
        cleaned = re.sub(r'\\f', '', text)  # Form feed
        cleaned = re.sub(r'\\x0c', '', cleaned)  # Page break
        
        # Normalize line breaks to \n
        cleaned = re.sub(r'\\r\\n|\\r', '\\n', cleaned)
        
        # 全角英数字を半角に変換
        cleaned = self._normalize_fullwidth_chars(cleaned)
        
        # 改行をスペースに置換（単語の結合を防ぐ）
        cleaned = cleaned.replace('\\n', ' ')
        
        # 連続する空白を1つに正規化
        cleaned = re.sub(r'[ \\t]+', ' ', cleaned)
        
        return cleaned.strip()
    
    def _normalize_fullwidth_chars(self, text: str) -> str:
        """全角英数字を半角に変換"""
        # 全角数字を半角に変換（０-９ → 0-9）
        text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        
        # 全角英字（大文字）を半角に変換（Ａ-Ｚ → A-Z）
        text = text.translate(str.maketrans(
            'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ',
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        ))
        
        # 全角英字（小文字）を半角に変換（ａ-ｚ → a-z）
        text = text.translate(str.maketrans(
            'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            'abcdefghijklmnopqrstuvwxyz'
        ))
        
        # その他の全角記号も半角に変換
        text = text.translate(str.maketrans(
            '！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～　',
            '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '
        ))
        
        return text
    
    
    def _extract_text_with_position_sort(self, page) -> str:
        """Extract text with position-based sorting to handle vertical text correctly"""
        # Get text blocks with position information
        blocks = page.get_text("dict")["blocks"]
        
        # Collect all text spans with their positions
        text_spans = []
        
        for block in blocks:
            if "lines" in block:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        text_spans.append({
                            "text": span["text"],
                            "x0": span["bbox"][0],
                            "y0": span["bbox"][1],
                            "x1": span["bbox"][2],
                            "y1": span["bbox"][3],
                            "font_size": span["size"]
                        })
        
        # Sort spans by position (top to bottom, left to right)
        # Group by approximate Y position first (with tolerance for line height)
        sorted_spans = sorted(text_spans, key=lambda s: (round(s["y0"] / 10) * 10, s["x0"]))
        
        # Build text with proper spacing
        result_text = ""
        prev_y = None
        prev_x = None
        
        for span in sorted_spans:
            curr_y = span["y0"]
            curr_x = span["x0"]
            
            # Add newline if Y position changes significantly
            if prev_y is not None and abs(curr_y - prev_y) > 5:
                result_text += "\n"
            # Add space if on same line but with gap
            elif prev_x is not None and prev_y is not None and abs(curr_y - prev_y) <= 5:
                if curr_x - prev_x > 10:  # Gap between words
                    result_text += " "
            
            result_text += span["text"]
            prev_y = curr_y
            prev_x = span["x1"]
        
        return result_text
    
    def extract_text_blocks(self, pdf_path: Path, page_num: int) -> List[Dict]:
        """
        Extract text blocks with position information
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            
        Returns:
            List of text blocks with position and content
        """
        if not HAS_PYMUPDF:
            logger.error("PyMuPDF is required for detailed text extraction")
            return []
        
        try:
            doc = fitz.open(str(pdf_path))
            
            if page_num < 1 or page_num > len(doc):
                logger.error(f"Invalid page number: {page_num}")
                return []
            
            # Get page (convert to 0-indexed)
            page = doc[page_num - 1]
            
            # Extract text blocks with position
            blocks = page.get_text("dict")["blocks"]
            
            text_blocks = []
            
            for block in blocks:
                if "lines" in block:  # Text block
                    block_text = ""
                    bbox = block["bbox"]  # Bounding box
                    
                    for line in block["lines"]:
                        for span in line["spans"]:
                            block_text += span["text"]
                        block_text += " "
                    
                    if block_text.strip():
                        text_blocks.append({
                            "text": block_text.strip(),
                            "bbox": bbox,
                            "x0": bbox[0],
                            "y0": bbox[1], 
                            "x1": bbox[2],
                            "y1": bbox[3]
                        })
            
            doc.close()
            return text_blocks
            
        except Exception as e:
            logger.error(f"Error extracting text blocks from page {page_num}: {e}")
            return []
    
    def compare_pdf_structures(self, pdf1_path: Path, pdf2_path: Path, 
                             max_pages: Optional[int] = None) -> Dict:
        """
        Compare structure of two PDF files
        
        Returns:
            Dictionary with comparison information
        """
        logger.info(f"Comparing PDF structures: {pdf1_path} vs {pdf2_path}")
        
        # Extract page counts and basic info
        info1 = self._get_pdf_info(pdf1_path)
        info2 = self._get_pdf_info(pdf2_path)
        
        # Extract text from both PDFs
        pages1 = self.extract_pages_text(pdf1_path, max_pages)
        pages2 = self.extract_pages_text(pdf2_path, max_pages)
        
        # Compare page counts
        comparison = {
            "pdf1_info": info1,
            "pdf2_info": info2,
            "pdf1_pages": len(pages1),
            "pdf2_pages": len(pages2),
            "common_pages": list(set(pages1.keys()) & set(pages2.keys())),
            "pdf1_only_pages": list(set(pages1.keys()) - set(pages2.keys())),
            "pdf2_only_pages": list(set(pages2.keys()) - set(pages1.keys())),
            "pages_text": {
                "pdf1": pages1,
                "pdf2": pages2
            }
        }
        
        return comparison
    
    def _get_pdf_info(self, pdf_path: Path) -> Dict:
        """Get basic PDF information"""
        if not HAS_PYMUPDF:
            return {"error": "PyMuPDF not available"}
        
        try:
            doc = fitz.open(str(pdf_path))
            info = {
                "page_count": len(doc),
                "metadata": doc.metadata,
                "file_size": pdf_path.stat().st_size if pdf_path.exists() else 0
            }
            doc.close()
            return info
        except Exception as e:
            logger.error(f"Error getting PDF info for {pdf_path}: {e}")
            return {"error": str(e)}
    
    def extract_page_text_segments(self, pdf_path: Path, page_num: int, 
                                 segment_strategy: str = "paragraph") -> List[str]:
        """
        Extract text segments from a page using different strategies
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            segment_strategy: "paragraph", "sentence", or "line"
            
        Returns:
            List of text segments
        """
        page_text = self.extract_pages_text(pdf_path, max_pages=page_num).get(page_num, "")
        
        if not page_text:
            return []
        
        if segment_strategy == "paragraph":
            # Split by double newlines or major breaks
            segments = re.split(r'\\n\\s*\\n|\\n\\s*[-=]{3,}', page_text)
        elif segment_strategy == "sentence":
            # Split by sentence endings
            segments = re.split(r'[。！？]\\s*', page_text)
        elif segment_strategy == "line":
            # Split by single newlines
            segments = page_text.split('\\n')
        else:
            segments = [page_text]  # Whole page as one segment
        
        # Clean and filter empty segments
        cleaned_segments = [seg.strip() for seg in segments if seg.strip()]
        
        return cleaned_segments