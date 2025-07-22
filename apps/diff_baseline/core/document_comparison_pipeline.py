"""
Document Comparison Pipeline - 統合パイプライン
"""
from typing import Tuple, Dict, Any
from pathlib import Path
import json
import csv
from ..services import (
    DocumentAnalysisEngine,
    ReadingOrderEstimator,
    BBoxBasedDiffDetector,
    OutputGenerator,
    LayoutAwareDiffDetector,
    ReportGenerator
)


class DocumentComparisonPipeline:
    """文書比較の統合パイプライン"""
    
    def __init__(self, use_layout_aware_diff=True, use_sentence_aware_diff=False, max_pages=None):
        self.doc_engine = DocumentAnalysisEngine(max_pages=max_pages)
        self.reading_order = ReadingOrderEstimator()
        # 差分検出器の選択
        if use_sentence_aware_diff:
            # 文章単位→単語単位の2段階差分検出
            from ..services import SentenceAwareDiffDetector
            self.diff_detector = SentenceAwareDiffDetector()
        elif use_layout_aware_diff:
            self.diff_detector = LayoutAwareDiffDetector()
        else:
            self.diff_detector = BBoxBasedDiffDetector()
        self.output_generator = OutputGenerator()
        self.report_generator = ReportGenerator()
        self.use_layout_aware_diff = use_layout_aware_diff
    
    def process_document_comparison(self, 
                                  file1: bytes, 
                                  file2: bytes,
                                  file_type: str,
                                  save_sentence_info: bool = True) -> Tuple[bytes, bytes, Dict[str, Any]]:
        """
        文書比較の完全なパイプラインを実行
        
        Args:
            file1: 1つ目のファイルのバイトデータ
            file2: 2つ目のファイルのバイトデータ
            file_type: ファイルタイプ ("pdf", "docx", "pptx")
            save_sentence_info: 文章リストと読み順序を別ファイルに保存するか
            
        Returns:
            (ハイライト付きファイル1, ハイライト付きファイル2, 結果サマリー)
        """
        # レポートタイマー開始
        self.report_generator.start_timer()
        
        # 1. bbox_text_data抽出
        print("[1/5] Extracting text data...")
        self.report_generator.start_phase("bbox_extraction")
        doc1_bbox_list = self.doc_engine.extract_bbox_text_data(file1, file_type)
        doc2_bbox_list = self.doc_engine.extract_bbox_text_data(file2, file_type)
        self.report_generator.end_phase()
        
        # 2. 読み順序推定（文章単位）
        print("[2/5] Estimating reading order...")
        self.report_generator.start_phase("reading_order_estimation")
        doc1_ordered = self.reading_order.estimate_reading_order(doc1_bbox_list)
        doc2_ordered = self.reading_order.estimate_reading_order(doc2_bbox_list)
        self.report_generator.end_phase()
        
        # 文章情報を保存（オプション）
        sentence_info = None
        if save_sentence_info:
            sentence_info = {
                'doc1': self._extract_sentence_info(doc1_bbox_list, doc1_ordered),
                'doc2': self._extract_sentence_info(doc2_bbox_list, doc2_ordered)
            }
        
        # 3. 差分検出（単語単位）
        print("[3/5] Detecting differences...")
        self.report_generator.start_phase("diff_detection")
        differences = self.diff_detector.detect_differences(doc1_ordered, doc2_ordered)
        self.report_generator.end_phase()
        
        # レイアウト変更情報を取得（可能な場合）
        layout_changes = None
        if self.use_layout_aware_diff and hasattr(self.diff_detector, 'get_layout_changes'):
            # マッチング情報を再取得（簡易版）
            matches = self.diff_detector._find_text_matches(doc1_ordered, doc2_ordered)
            layout_changes = self.diff_detector.get_layout_changes(doc1_ordered, doc2_ordered, matches)
        
        # 4. 差分サマリー生成
        diff_summary = self.diff_detector.get_diff_summary(differences)
        
        # 5. ハイライト付きファイル生成
        print("[4/5] Generating output files...")
        self.report_generator.start_phase("output_generation")
        
        # SimpleDiffDetectorを使用している場合は、SimpleOutputGeneratorを使用
        if hasattr(self.diff_detector, '__class__') and self.diff_detector.__class__.__name__ == 'SimpleDiffDetector':
            from ..services.simple_output_generator import SimpleOutputGenerator
            simple_output = SimpleOutputGenerator()
            highlighted_file1, highlighted_file2 = simple_output.generate_comparison_report(
                file1, file2, file_type, doc1_ordered, doc2_ordered, differences
            )
        else:
            highlighted_file1, highlighted_file2 = self.output_generator.generate_comparison_report(
                file1, file2, file_type, differences
            )
        
        self.report_generator.end_phase()
        
        # レポートタイマー終了
        self.report_generator.end_timer()
        
        # 文書情報を整理
        doc1_info = {
            'word_count': len(doc1_bbox_list),
            'page_count': max([b['page'] for b in doc1_bbox_list]) + 1 if doc1_bbox_list else 0,
            'bbox_list': doc1_bbox_list
        }
        
        doc2_info = {
            'word_count': len(doc2_bbox_list),
            'page_count': max([b['page'] for b in doc2_bbox_list]) + 1 if doc2_bbox_list else 0,
            'bbox_list': doc2_bbox_list
        }
        
        # 結果サマリー
        result_summary = {
            'doc1_words': doc1_info['word_count'],
            'doc2_words': doc2_info['word_count'],
            'differences': diff_summary,
            'pages_doc1': doc1_info['page_count'],
            'pages_doc2': doc2_info['page_count'],
        }
        
        if sentence_info:
            result_summary['sentence_info'] = sentence_info
        
        # レポートに必要な情報を追加
        result_summary['_doc1_info'] = doc1_info
        result_summary['_doc2_info'] = doc2_info
        result_summary['_differences'] = differences
        result_summary['_layout_changes'] = layout_changes
        
        return highlighted_file1, highlighted_file2, result_summary
    
    def compare_files(self, 
                     file1_path: str, 
                     file2_path: str,
                     output_dir: str = None,
                     quiet: bool = True) -> Dict[str, Any]:
        """
        ファイルパスから比較を実行（便利メソッド）
        
        Args:
            file1_path: 1つ目のファイルパス
            file2_path: 2つ目のファイルパス
            output_dir: 出力ディレクトリ（省略時は入力ファイルと同じディレクトリ）
            
        Returns:
            結果サマリー
        """
        file1_path = Path(file1_path)
        file2_path = Path(file2_path)
        
        # ファイルタイプをチェック
        if file1_path.suffix != file2_path.suffix:
            raise ValueError("Both files must have the same file type")
        
        file_type = file1_path.suffix.lower().lstrip('.')
        
        # ファイルを読み込み
        with open(file1_path, 'rb') as f:
            file1_bytes = f.read()
        with open(file2_path, 'rb') as f:
            file2_bytes = f.read()
        
        # 比較実行
        highlighted1, highlighted2, summary = self.process_document_comparison(
            file1_bytes, file2_bytes, file_type, save_sentence_info=True
        )
        
        print("[5/5] Saving results...")
        
        # 出力ディレクトリの決定
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = file1_path.parent
        
        # サブディレクトリを作成
        pdfs_dir = output_dir / "PDFs"
        debug_dir = output_dir / "debug"
        reports_dir = output_dir / "reports"
        
        pdfs_dir.mkdir(exist_ok=True)
        debug_dir.mkdir(exist_ok=True)
        reports_dir.mkdir(exist_ok=True)
        
        # PDFファイルを保存
        output1_name = f"{file1_path.stem}_compared.{file_type}"
        output2_name = f"{file2_path.stem}_compared.{file_type}"
        
        output1_path = pdfs_dir / output1_name
        output2_path = pdfs_dir / output2_name
        
        with open(output1_path, 'wb') as f:
            f.write(highlighted1)
        with open(output2_path, 'wb') as f:
            f.write(highlighted2)
        
        print(f"\nOutput files saved:")
        print(f"  [PDFs]")
        print(f"    - {output1_path.name}")
        print(f"    - {output2_path.name}")
        
        # 文章情報を別ファイルに保存
        if 'sentence_info' in summary:
            sentence_info_path = reports_dir / 'sentence_info.json'
            with open(sentence_info_path, 'w', encoding='utf-8') as f:
                json.dump(summary['sentence_info'], f, ensure_ascii=False, indent=2)
            
            # ページごとの読み順序を保存
            reading_order_path = reports_dir / 'reading_order.json'
            reading_order_data = self._extract_reading_order_by_page(summary['sentence_info'])
            with open(reading_order_path, 'w', encoding='utf-8') as f:
                json.dump(reading_order_data, f, ensure_ascii=False, indent=2)
            
            print(f"  [Reports]")
            print(f"    - sentence_info.json")
            print(f"    - reading_order.json")
        
        # 読み順序番号付きPDFを生成
        if file_type == 'pdf':
            # PDFハンドラーを使用
            from ..handlers.pdf_handler import PyMuPDFService
            pdf_handler = PyMuPDFService()
            
            # 元のPDFを読み込み
            with open(file1_path, 'rb') as f:
                pdf1_bytes = f.read()
            with open(file2_path, 'rb') as f:
                pdf2_bytes = f.read()
            
            # 1. 順序変換前（元の順序）のPDF
            original_order_info1 = self.reading_order.get_original_order_info(summary['_doc1_info']['bbox_list'])
            original_order_info2 = self.reading_order.get_original_order_info(summary['_doc2_info']['bbox_list'])
            
            pdf1_original_order = pdf_handler.add_reading_order_numbers(pdf1_bytes, original_order_info1)
            pdf2_original_order = pdf_handler.add_reading_order_numbers(pdf2_bytes, original_order_info2)
            
            original1_path = pdfs_dir / f"{file1_path.stem}_original_order.pdf"
            original2_path = pdfs_dir / f"{file2_path.stem}_original_order.pdf"
            
            with open(original1_path, 'wb') as f:
                f.write(pdf1_original_order)
            with open(original2_path, 'wb') as f:
                f.write(pdf2_original_order)
            
            print(f"    - {original1_path.name}")
            print(f"    - {original2_path.name}")
            
            # 2. 順序変換後（推定された読み順序）のPDF
            reading_order_info1 = self.reading_order.get_sentence_reading_order(summary['_doc1_info']['bbox_list'])
            reading_order_info2 = self.reading_order.get_sentence_reading_order(summary['_doc2_info']['bbox_list'])
            
            pdf1_with_order = pdf_handler.add_reading_order_numbers(pdf1_bytes, reading_order_info1)
            pdf2_with_order = pdf_handler.add_reading_order_numbers(pdf2_bytes, reading_order_info2)
            
            order1_path = pdfs_dir / f"{file1_path.stem}_reading_order.pdf"
            order2_path = pdfs_dir / f"{file2_path.stem}_reading_order.pdf"
            
            with open(order1_path, 'wb') as f:
                f.write(pdf1_with_order)
            with open(order2_path, 'wb') as f:
                f.write(pdf2_with_order)
            
            print(f"    - {order1_path.name}")
            print(f"    - {order2_path.name}")
            
            # デバッグ用CSVファイルを出力
            self._save_reading_order_debug_csv(
                original_order_info1, reading_order_info1, 
                debug_dir / f"{file1_path.stem}_reading_order"
            )
            self._save_reading_order_debug_csv(
                original_order_info2, reading_order_info2,
                debug_dir / f"{file2_path.stem}_reading_order"
            )
            
            print(f"  [Debug]")
            print(f"    - {file1_path.stem}_reading_order_original.csv")
            print(f"    - {file1_path.stem}_reading_order_estimated.csv")
            print(f"    - {file2_path.stem}_reading_order_original.csv")
            print(f"    - {file2_path.stem}_reading_order_estimated.csv")
        
        # 詳細レポートを生成
        if '_doc1_info' in summary and '_doc2_info' in summary:
            report = self.report_generator.generate_report(
                summary['_doc1_info'],
                summary['_doc2_info'],
                summary['_differences'],
                summary.get('_layout_changes'),
                reports_dir
            )
            
            # 差分検出のデバッグ用CSVファイルを出力
            self._save_diff_debug_csv(
                summary['_differences'], 
                debug_dir, 
                file1_path.stem, 
                file2_path.stem,
                summary['_doc1_info']['bbox_list'],
                summary['_doc2_info']['bbox_list']
            )
            
            print(f"    - execution_report.json")
            print(f"    - execution_report.md")
            
            # 生成された差分CSVファイルを表示
            diff_files = []
            file1_diff = debug_dir / f"{file1_path.stem}_diff.csv"
            file2_diff = debug_dir / f"{file2_path.stem}_diff.csv"
            
            if file1_diff.exists():
                diff_files.append(f"{file1_path.stem}_diff.csv")
            if file2_diff.exists():
                diff_files.append(f"{file2_path.stem}_diff.csv")
            
            for diff_file in diff_files:
                print(f"    - {diff_file}")
            
            # 内部情報をサマリーから削除
            for key in ['_doc1_info', '_doc2_info', '_differences', '_layout_changes']:
                summary.pop(key, None)
        
        # サマリーに出力パスを追加
        summary['output_files'] = {
            'file1': str(output1_path),
            'file2': str(output2_path)
        }
        
        return summary
    
    def _extract_sentence_info(self, bbox_list, ordered_list):
        """
        文章情報を抽出
        
        Args:
            bbox_list: 元のbboxリスト
            ordered_list: 読み順序推定後のリスト
            
        Returns:
            ページごとの文章情報
        """
        # ページごとにグループ化
        page_sentences = {}
        current_page = -1
        current_sentence = []
        sentence_list = []
        
        for bbox_data in ordered_list:
            page = bbox_data['page']
            
            # ページが変わった場合
            if page != current_page:
                if current_sentence:
                    sentence_list.append(' '.join(current_sentence))
                if current_page >= 0 and sentence_list:
                    page_sentences[current_page] = sentence_list
                
                current_page = page
                sentence_list = []
                current_sentence = []
            
            # 単語を追加
            current_sentence.append(bbox_data['text'])
            
            # 文章の区切りを判定（簡易版）
            if bbox_data['text'] in ['。', '!', '？', '.', '?']:
                sentence_list.append(' '.join(current_sentence))
                current_sentence = []
        
        # 最後の文章を追加
        if current_sentence:
            sentence_list.append(' '.join(current_sentence))
        if current_page >= 0 and sentence_list:
            page_sentences[current_page] = sentence_list
        
        return page_sentences
    
    def _save_reading_order_debug_csv(self, original_order, reading_order, base_path):
        """
        読み順序のデバッグ情報を別々のCSVファイルに保存
        
        Args:
            original_order: 元の順序情報
            reading_order: 推定された読み順序情報
            base_path: 出力ファイルのベースパス（拡張子なし）
        """
        # 元の順序を保存
        original_path = base_path.parent / f"{base_path.stem}_original.csv"
        with open(original_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['order_id', 'page', 'sentence'])
            for item in original_order:
                writer.writerow([item['order'], item['page'], item['text']])
        
        # 推定された読み順序を保存
        estimated_path = base_path.parent / f"{base_path.stem}_estimated.csv"
        with open(estimated_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['order_id', 'page', 'sentence'])
            for item in reading_order:
                writer.writerow([item['order'], item['page'], item['text']])
    
    def _save_diff_debug_csv(self, differences, debug_dir, file1_name, file2_name, doc1_bbox_list, doc2_bbox_list):
        """
        差分検出のデバッグ情報をファイルごとのCSVファイルに保存
        
        Args:
            differences: 差分リスト（DiffResultのリスト）
            debug_dir: デバッグディレクトリのパス
            file1_name: ファイル1の名前（拡張子なし）
            file2_name: ファイル2の名前（拡張子なし）
            doc1_bbox_list: 文書1のbboxリスト（読み順序情報のため）
            doc2_bbox_list: 文書2のbboxリスト（読み順序情報のため）
        """
        from ..models.bbox_models import ChangeType
        
        # 読み順序を推定
        doc1_ordered = self.reading_order.estimate_reading_order(doc1_bbox_list)
        doc2_ordered = self.reading_order.estimate_reading_order(doc2_bbox_list)
        
        # bboxから読み順序へのマッピングを作成
        doc1_order_map = {}
        doc2_order_map = {}
        
        for i, bbox in enumerate(doc1_ordered):
            key = (bbox['page'], bbox['bbox'][0], bbox['bbox'][1], bbox['text'])
            doc1_order_map[key] = i
            
        for i, bbox in enumerate(doc2_ordered):
            key = (bbox['page'], bbox['bbox'][0], bbox['bbox'][1], bbox['text'])
            doc2_order_map[key] = i
        
        # ファイル1の差分（削除と変更）
        file1_diffs = []
        # ファイル2の差分（追加と変更）
        file2_diffs = []
        
        for diff in differences:
            # SimpleDiffDetectorの場合
            if hasattr(diff.change_type, 'value') and diff.change_type.value == 'difference':
                # 文書1の差分
                if diff.original_bbox:
                    bbox = diff.original_bbox
                    key = (bbox['page'], bbox['bbox'][0], bbox['bbox'][1], bbox['text'])
                    order = doc1_order_map.get(key, 999999)
                    
                    file1_diffs.append({
                        'order': order,
                        'id': len(file1_diffs) + 1,
                        'type': '差分',
                        'word': bbox['text'],
                        'page': diff.page
                    })
                
                # 文書2の差分
                if diff.modified_bbox:
                    bbox = diff.modified_bbox
                    key = (bbox['page'], bbox['bbox'][0], bbox['bbox'][1], bbox['text'])
                    order = doc2_order_map.get(key, 999999)
                    
                    file2_diffs.append({
                        'order': order,
                        'id': len(file2_diffs) + 1,
                        'type': '差分',
                        'word': bbox['text'],
                        'page': diff.page
                    })
            
            elif diff.change_type == ChangeType.DELETION:
                # ファイル1での削除
                bbox = diff.original_bbox
                key = (bbox['page'], bbox['bbox'][0], bbox['bbox'][1], bbox['text'])
                order = doc1_order_map.get(key, 999999)
                
                file1_diffs.append({
                    'order': order,
                    'id': len([d for d in file1_diffs if d['type'] == '削除']) + 1,
                    'type': '削除',
                    'word': bbox['text'],
                    'page': diff.page
                })
                
            elif diff.change_type == ChangeType.ADDITION:
                # ファイル2での追加
                bbox = diff.modified_bbox
                key = (bbox['page'], bbox['bbox'][0], bbox['bbox'][1], bbox['text'])
                order = doc2_order_map.get(key, 999999)
                
                file2_diffs.append({
                    'order': order,
                    'id': len([d for d in file2_diffs if d['type'] == '追加']) + 1,
                    'type': '追加',
                    'word': bbox['text'],
                    'page': diff.page
                })
                
            elif diff.change_type == ChangeType.MODIFICATION:
                # ファイル1での変更（元のテキスト）
                bbox1 = diff.original_bbox
                key1 = (bbox1['page'], bbox1['bbox'][0], bbox1['bbox'][1], bbox1['text'])
                order1 = doc1_order_map.get(key1, 999999)
                
                file1_diffs.append({
                    'order': order1,
                    'id': len([d for d in file1_diffs if d['type'] == '変更']) + 1,
                    'type': '変更',
                    'word': f"{bbox1['text']} → {diff.modified_bbox['text']}",
                    'page': diff.page
                })
                
                # ファイル2での変更（新しいテキスト）
                bbox2 = diff.modified_bbox
                key2 = (bbox2['page'], bbox2['bbox'][0], bbox2['bbox'][1], bbox2['text'])
                order2 = doc2_order_map.get(key2, 999999)
                
                file2_diffs.append({
                    'order': order2,
                    'id': len([d for d in file2_diffs if d['type'] == '変更']) + 1,
                    'type': '変更',
                    'word': f"{diff.original_bbox['text']} → {bbox2['text']}",
                    'page': diff.page
                })
        
        # 読み順序でソート
        file1_diffs.sort(key=lambda x: x['order'])
        file2_diffs.sort(key=lambda x: x['order'])
        
        # ファイル1の差分を保存
        if file1_diffs:
            with open(debug_dir / f'{file1_name}_diff.csv', 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['diff_id', 'type', 'word', 'page'])
                for item in file1_diffs:
                    writer.writerow([item['id'], item['type'], item['word'], item['page']])
        
        # ファイル2の差分を保存
        if file2_diffs:
            with open(debug_dir / f'{file2_name}_diff.csv', 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['diff_id', 'type', 'word', 'page'])
                for item in file2_diffs:
                    writer.writerow([item['id'], item['type'], item['word'], item['page']])
    
    def _extract_reading_order_by_page(self, sentence_info):
        """
        ページごとの読み順序情報を抽出
        
        Args:
            sentence_info: 文章情報
            
        Returns:
            ページごとの読み順序
        """
        reading_order_data = {
            'doc1': {},
            'doc2': {}
        }
        
        for doc_key in ['doc1', 'doc2']:
            if doc_key in sentence_info:
                for page, sentences in sentence_info[doc_key].items():
                    reading_order_data[doc_key][str(page)] = {
                        'sentence_count': len(sentences),
                        'sentences': sentences,
                        'reading_order': list(range(len(sentences)))
                    }
        
        return reading_order_data