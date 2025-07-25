"""
Output Handler v4 - 改善された出力処理
v2のOutputHandlerをベースに、v4の要件に合わせて調整
"""
from pathlib import Path
import json
import csv
from typing import Dict, List, Any, Optional
import fitz  # PyMuPDF
from datetime import datetime

from apps.llm_docs_diff_v4.models.bbox_models import ComparisonResult, DiffResult


class OutputHandler:
    """v4用の出力ハンドラー"""
    
    def __init__(self, output_dir: Path):
        """初期化
        
        Args:
            output_dir: 出力ディレクトリ
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # サブディレクトリを作成
        self.reports_dir = self.output_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        self.pdfs_dir = self.output_dir / "PDFs"
        self.pdfs_dir.mkdir(exist_ok=True)
        
        self.debug_dir = self.output_dir / "debug"
        self.debug_dir.mkdir(exist_ok=True)
    
    def save_all_outputs(self, 
                        comparison_result: ComparisonResult,
                        ordered_list1: List[Dict[str, Any]],
                        ordered_list2: List[Dict[str, Any]],
                        pdf1_bytes: bytes,
                        pdf2_bytes: bytes) -> Dict[str, Path]:
        """すべての出力を保存
        
        Args:
            comparison_result: 比較結果
            ordered_list1: 文書1の読み取り順序
            ordered_list2: 文書2の読み取り順序
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            
        Returns:
            保存されたファイルパスの辞書
        """
        saved_files = {}
        
        # 1. 差分CSVを保存
        diff_csv_path = self._save_diff_csv(comparison_result)
        saved_files['diff_csv'] = diff_csv_path
        
        # 2. 実行レポートを保存
        report_path = self._save_execution_report(comparison_result)
        saved_files['report'] = report_path
        
        # 3. 読み取り順序CSVを保存
        order_csv1 = self._save_reading_order_csv(ordered_list1, "2023")
        order_csv2 = self._save_reading_order_csv(ordered_list2, "2024")
        saved_files['order_csv1'] = order_csv1
        saved_files['order_csv2'] = order_csv2
        
        # 4. ハイライト付きPDFを作成
        if pdf1_bytes and pdf2_bytes:
            highlighted_pdfs = self._create_highlighted_pdfs(
                comparison_result, pdf1_bytes, pdf2_bytes
            )
            saved_files.update(highlighted_pdfs)
            
            # 並列表示PDFを作成
            side_by_side_path = self._create_side_by_side_pdf(
                pdf1_bytes, pdf2_bytes, comparison_result
            )
            if side_by_side_path:
                saved_files['side_by_side_pdf'] = side_by_side_path
        
        # 5. 統計情報を保存
        stats_path = self._save_statistics(comparison_result)
        saved_files['statistics'] = stats_path
        
        # 6. 読み取り順序を可視化したPDFを作成
        if pdf1_bytes and pdf2_bytes:
            order_pdf1 = self.create_reading_order_pdf(pdf1_bytes, ordered_list1, "2023_order")
            order_pdf2 = self.create_reading_order_pdf(pdf2_bytes, ordered_list2, "2024_order")
            if order_pdf1:
                saved_files['order_pdf1'] = order_pdf1
            if order_pdf2:
                saved_files['order_pdf2'] = order_pdf2
        
        return saved_files
    
    def _save_diff_csv(self, result: ComparisonResult) -> Path:
        """差分をCSV形式で保存"""
        csv_path = self.output_dir / "llm_diff_test_v4_differences.csv"
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Type', 'Page', 'Text', 'Original_X', 'Original_Y', 
                           'Modified_X', 'Modified_Y', 'Similarity'])
            
            for diff_result in result.diff_results:
                change_type = diff_result.change_type.value
                page = diff_result.page + 1  # 1-indexed
                
                # 元の位置情報
                if diff_result.original_bbox:
                    orig_text = diff_result.original_bbox.get('text', '')
                    orig_x = diff_result.original_bbox.get('x', 0)
                    orig_y = diff_result.original_bbox.get('y', 0)
                else:
                    orig_text = ""
                    orig_x = orig_y = 0
                
                # 変更後の位置情報
                if diff_result.modified_bbox:
                    mod_text = diff_result.modified_bbox.get('text', '')
                    mod_x = diff_result.modified_bbox.get('x', 0)
                    mod_y = diff_result.modified_bbox.get('y', 0)
                else:
                    mod_text = ""
                    mod_x = mod_y = 0
                
                # テキストは元のものか変更後のものを使用
                text = orig_text if orig_text else mod_text
                
                # 類似度
                similarity = getattr(diff_result, 'semantic_similarity', 0.0)
                
                writer.writerow([
                    change_type, page, text,
                    f"{orig_x:.1f}", f"{orig_y:.1f}",
                    f"{mod_x:.1f}", f"{mod_y:.1f}",
                    f"{similarity:.3f}"
                ])
        
        return csv_path
    
    def _save_execution_report(self, result: ComparisonResult) -> Path:
        """実行レポートを保存"""
        report_path = self.reports_dir / "execution_report.json"
        
        # 統計情報を計算
        stats = {
            'additions': 0,
            'deletions': 0,
            'modifications': 0,
            'total': 0
        }
        
        for diff_result in result.diff_results:
            change_type = diff_result.change_type.value
            if change_type == 'addition':
                stats['additions'] += 1
            elif change_type == 'deletion':
                stats['deletions'] += 1
            elif change_type == 'modification':
                stats['modifications'] += 1
            stats['total'] += 1
        
        report = {
            'version': 'v4',
            'description': '改善された位置ベースの差分検出',
            'timestamp': datetime.now().isoformat(),
            'statistics': stats,
            'total_differences': stats['total']
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report_path
    
    def _save_reading_order_csv(self, ordered_list: List[Dict[str, Any]], 
                               doc_name: str) -> Path:
        """読み取り順序をCSV形式で保存"""
        csv_path = self.output_dir / f"{doc_name}_reading_order.csv"
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Index', 'Page', 'Text', 'X', 'Y', 'Width', 'Height'])
            
            for idx, item in enumerate(ordered_list):
                text = item.get('text', '')
                page = item.get('page', 0)
                
                # bbox形式の確認
                if 'bbox' in item:
                    x, y, w, h = item['bbox']
                else:
                    x = item.get('x', 0)
                    y = item.get('y', 0)
                    w = item.get('width', 0)
                    h = item.get('height', 0)
                
                writer.writerow([
                    idx, page, text,
                    f"{x:.1f}", f"{y:.1f}", f"{w:.1f}", f"{h:.1f}"
                ])
        
        return csv_path
    
    def _create_highlighted_pdfs(self, result: ComparisonResult,
                                pdf1_bytes: bytes, pdf2_bytes: bytes) -> Dict[str, Path]:
        """ハイライト付きPDFを作成"""
        saved_files = {}
        
        # 文書1のハイライトPDF
        pdf1_path = self._create_single_highlighted_pdf(
            pdf1_bytes, result.diff_results, "2023", is_doc1=True
        )
        saved_files['highlighted_pdf1'] = pdf1_path
        
        # 文書2のハイライトPDF
        pdf2_path = self._create_single_highlighted_pdf(
            pdf2_bytes, result.diff_results, "2024", is_doc1=False
        )
        saved_files['highlighted_pdf2'] = pdf2_path
        
        return saved_files
    
    def _create_single_highlighted_pdf(self, pdf_bytes: bytes, 
                                     diff_results: List[DiffResult],
                                     doc_name: str, is_doc1: bool) -> Path:
        """単一のハイライト付きPDFを作成"""
        output_path = self.pdfs_dir / f"{doc_name}_highlighted.pdf"
        
        try:
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # 差分をページごとにグループ化
            page_diffs = {}
            for diff in diff_results:
                page = diff.page
                if page not in page_diffs:
                    page_diffs[page] = []
                page_diffs[page].append(diff)
            
            # 各ページにハイライトを追加
            for page_num, diffs in page_diffs.items():
                if page_num >= len(pdf_doc):
                    continue
                
                page = pdf_doc[page_num]
                
                for diff in diffs:
                    # ハイライトする箇所を決定
                    if is_doc1 and diff.original_bbox:
                        bbox_data = diff.original_bbox
                    elif not is_doc1 and diff.modified_bbox:
                        bbox_data = diff.modified_bbox
                    else:
                        continue
                    
                    # 座標を取得
                    x = bbox_data.get('x', 0)
                    y = bbox_data.get('y', 0)
                    w = bbox_data.get('width', 0)
                    h = bbox_data.get('height', 0)
                    
                    # ハイライトの色を決定
                    change_type = diff.change_type.value
                    if change_type == 'deletion':
                        color = (1, 0, 0)  # 赤
                    elif change_type == 'addition':
                        color = (0, 1, 0)  # 緑
                    elif change_type == 'modification':
                        color = (1, 1, 0)  # 黄
                    else:
                        color = (0.5, 0.5, 0.5)  # グレー
                    
                    # 赤枠を追加（ハイライトの代わりに）
                    rect = fitz.Rect(x, y, x + w, y + h)
                    # 常に赤色の枠線を描画
                    page.draw_rect(rect, color=(1, 0, 0), width=2.0, fill=None)
            
            # PDFを保存
            pdf_doc.save(str(output_path))
            pdf_doc.close()
            
        except Exception as e:
            print(f"Error creating highlighted PDF: {e}")
            return None
        
        return output_path
    
    def _create_side_by_side_pdf(self, pdf1_bytes: bytes, pdf2_bytes: bytes,
                                 result: ComparisonResult) -> Optional[Path]:
        """2つのPDFを並べて表示する並列表示PDFを作成
        
        Args:
            pdf1_bytes: 文書1のPDFバイトデータ
            pdf2_bytes: 文書2のPDFバイトデータ
            result: 比較結果
            
        Returns:
            生成されたPDFのパス（失敗時はNone）
        """
        output_path = self.pdfs_dir / "side_by_side_comparison.pdf"
        
        try:
            # まずハイライト付きPDFを作成
            highlighted1_path = self._create_single_highlighted_pdf(
                pdf1_bytes, result.diff_results, "2023_temp", is_doc1=True
            )
            highlighted2_path = self._create_single_highlighted_pdf(
                pdf2_bytes, result.diff_results, "2024_temp", is_doc1=False
            )
            
            # ハイライト付きPDFを読み込む
            pdf1 = fitz.open(str(highlighted1_path))
            pdf2 = fitz.open(str(highlighted2_path))
            
            # 新しいPDFを作成
            output_pdf = fitz.open()
            
            # 最大5ページまで
            max_pages = min(5, max(len(pdf1), len(pdf2)))
            
            for page_idx in range(max_pages):
                # 左右のページを取得
                left_page = pdf1[page_idx] if page_idx < len(pdf1) else None
                right_page = pdf2[page_idx] if page_idx < len(pdf2) else None
                
                if left_page is None and right_page is None:
                    continue
                
                # ページサイズを計算（A4の2倍幅）
                page_width = 595 * 2 + 20  # A4幅 * 2 + 間隔
                page_height = 842  # A4高さ
                
                # 新しいページを作成
                new_page = output_pdf.new_page(width=page_width, height=page_height)
                
                # 左側のページを配置
                if left_page:
                    # ページラベルを追加
                    label_rect = fitz.Rect(10, 10, 300, 30)
                    new_page.insert_textbox(label_rect, f"2023年版 - ページ {page_idx + 1}",
                                          fontsize=12, fontname="helv", 
                                          color=(0, 0, 0))
                    
                    # ページコンテンツを配置
                    left_rect = fitz.Rect(0, 40, 595, page_height)
                    new_page.show_pdf_page(left_rect, pdf1, page_idx)
                
                # 右側のページを配置
                if right_page:
                    # ページラベルを追加
                    label_rect = fitz.Rect(615, 10, 915, 30)
                    new_page.insert_textbox(label_rect, f"2024年版 - ページ {page_idx + 1}",
                                          fontsize=12, fontname="helv", 
                                          color=(0, 0, 0))
                    
                    # ページコンテンツを配置
                    right_rect = fitz.Rect(615, 40, 615 + 595, page_height)
                    new_page.show_pdf_page(right_rect, pdf2, page_idx)
            
            # PDFを保存
            output_pdf.save(str(output_path))
            output_pdf.close()
            
            # クリーンアップ
            pdf1.close()
            pdf2.close()
            
            # 一時ファイルを削除
            if highlighted1_path.exists():
                highlighted1_path.unlink()
            if highlighted2_path.exists():
                highlighted2_path.unlink()
            
            return output_path
            
        except Exception as e:
            print(f"Error creating side-by-side PDF: {e}")
            return None
    
    def _save_statistics(self, result: ComparisonResult) -> Path:
        """統計情報を保存"""
        stats_path = self.output_dir / "v4_statistics.json"
        
        # ページごとの統計を計算
        by_page = {}
        for diff in result.diff_results:
            page = diff.page
            if page not in by_page:
                by_page[page] = {
                    'additions': 0,
                    'deletions': 0,
                    'modifications': 0
                }
            
            change_type = diff.change_type.value
            if change_type == 'addition':
                by_page[page]['additions'] += 1
            elif change_type == 'deletion':
                by_page[page]['deletions'] += 1
            elif change_type == 'modification':
                by_page[page]['modifications'] += 1
        
        # 全体の統計
        total_stats = {
            'additions': sum(p['additions'] for p in by_page.values()),
            'deletions': sum(p['deletions'] for p in by_page.values()),
            'modifications': sum(p['modifications'] for p in by_page.values())
        }
        total_stats['total'] = sum(total_stats.values())
        
        statistics = {
            'total': total_stats['total'],
            'additions': total_stats['additions'],
            'deletions': total_stats['deletions'],
            'modifications': total_stats['modifications'],
            'by_page': by_page
        }
        
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(statistics, f, ensure_ascii=False, indent=2)
        
        return stats_path
    
    def create_reading_order_pdf(self, pdf_bytes: bytes, ordered_list: List[Dict[str, Any]], 
                                doc_name: str) -> Path:
        """読み取り順序を可視化したPDFを作成"""
        output_path = self.pdfs_dir / f"{doc_name}_reading_order.pdf"
        
        try:
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # ページごとにアイテムをグループ化
            page_items = {}
            for idx, item in enumerate(ordered_list):
                page = item.get('page', 0)
                if page not in page_items:
                    page_items[page] = []
                page_items[page].append((idx, item))
            
            # 各ページに順序番号を追加
            for page_num in page_items:
                if page_num >= len(pdf_doc):
                    continue
                
                page = pdf_doc[page_num]
                
                for idx, item in page_items[page_num]:
                    # バウンディングボックスを取得
                    bbox = item.get('bbox', [0, 0, 0, 0])
                    x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
                    
                    # 順序番号を追加（赤色の小さな円と番号）
                    # 円の中心をテキストの左上に配置
                    circle_center = fitz.Point(x - 10, y + h/2)
                    
                    # 赤い円を描画
                    page.draw_circle(circle_center, 8, color=(1, 0, 0), fill=(1, 0, 0))
                    
                    # 白色で順序番号を描画
                    text_rect = fitz.Rect(circle_center.x - 8, circle_center.y - 8, 
                                         circle_center.x + 8, circle_center.y + 8)
                    page.insert_textbox(text_rect, str(idx + 1), 
                                      fontsize=8, 
                                      color=(1, 1, 1),
                                      align=fitz.TEXT_ALIGN_CENTER)
                    
                    # オプション：バウンディングボックスの枠線を描画
                    rect = fitz.Rect(x, y, x + w, y + h)
                    page.draw_rect(rect, color=(0, 0, 1), width=0.5)
            
            # PDFを保存
            pdf_doc.save(str(output_path))
            pdf_doc.close()
            
            return output_path
            
        except Exception as e:
            print(f"Error creating reading order PDF: {e}")
            return None