"""
PDF生成サービス v3 簡易版 - 文字を囲む形式
ハイライトではなく枠線で差分を表示
"""
import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SimplePDFGeneratorV3:
    """差分を枠線で表示するPDF生成サービス"""
    
    def __init__(self):
        self.colors = {
            'difference': (1, 0, 0),  # 赤色
            'default': (1, 0, 0)      # デフォルトも赤色
        }
    
    def generate_comparison_pdfs(self,
                               pdf1_path: str,
                               pdf2_path: str,
                               differences: List[Dict[str, Any]],
                               output_dir: str) -> Tuple[str, str]:
        """
        比較用PDFを生成（文字を囲む形式）
        
        Args:
            pdf1_path: 元のPDF1のパス
            pdf2_path: 元のPDF2のパス
            differences: 差分リスト
            output_dir: 出力ディレクトリ
            
        Returns:
            生成されたPDFのパス (pdf1_path, pdf2_path)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 出力ファイル名
        output1 = output_dir / f"{Path(pdf1_path).stem}_compared.pdf"
        output2 = output_dir / f"{Path(pdf2_path).stem}_compared.pdf"
        
        # 差分を文書ごとに分類
        doc1_diffs = []
        doc2_diffs = []
        
        for diff in differences:
            if 'doc1_bbox' in diff and diff['doc1_bbox']:
                doc1_diffs.append(diff)
            if 'doc2_bbox' in diff and diff['doc2_bbox']:
                doc2_diffs.append(diff)
        
        # PDF1に枠線を追加
        self._add_boxes_to_pdf(pdf1_path, doc1_diffs, output1, 'doc1')
        
        # PDF2に枠線を追加
        self._add_boxes_to_pdf(pdf2_path, doc2_diffs, output2, 'doc2')
        
        return str(output1), str(output2)
    
    def _add_boxes_to_pdf(self, 
                         input_path: str, 
                         differences: List[Dict[str, Any]], 
                         output_path: Path,
                         doc_key: str):
        """
        PDFに差分箇所の枠線を追加
        
        Args:
            input_path: 入力PDFパス
            differences: 差分リスト
            output_path: 出力PDFパス
            doc_key: 'doc1' または 'doc2'
        """
        # PDFを開く
        pdf_document = fitz.open(input_path)
        
        # 各ページの差分に枠線を追加
        for diff in differences:
            bbox_key = f'{doc_key}_bbox'
            if bbox_key not in diff:
                continue
            
            bbox_info = diff[bbox_key]
            if isinstance(bbox_info, dict):
                bbox = bbox_info.get('bbox', [])
                page_num = bbox_info.get('page', 0)
            else:
                # 旧形式の場合
                bbox = diff.get(f'{doc_key}_bbox', [])
                page_num = diff.get('page', 0)
            
            if not bbox or len(bbox) < 4:
                continue
            
            if page_num < len(pdf_document):
                page = pdf_document[page_num]
                
                # bboxの座標を取得
                x, y, width, height = bbox[0], bbox[1], bbox[2], bbox[3]
                
                # PyMuPDFの座標系に変換（左上が原点）
                rect = fitz.Rect(x, y, x + width, y + height)
                
                # 赤い枠線を描画（塗りつぶしなし）
                color = self.colors.get(diff.get('change_type', 'default'), self.colors['default'])
                page.draw_rect(rect, color=color, width=1.5)
        
        # PDFを保存
        pdf_document.save(str(output_path))
        pdf_document.close()
    
    def generate_side_by_side_pdf(self,
                                pdf1_path: str,
                                pdf2_path: str,
                                differences: List[Dict[str, Any]],
                                output_path: str) -> str:
        """
        並列比較PDFを生成（簡易版）
        
        現在は個別のPDFを生成するのみ
        TODO: 実際の並列表示実装
        """
        # 簡易実装：最初のPDFをコピー
        pdf_document = fitz.open(pdf1_path)
        pdf_document.save(output_path)
        pdf_document.close()
        
        return output_path