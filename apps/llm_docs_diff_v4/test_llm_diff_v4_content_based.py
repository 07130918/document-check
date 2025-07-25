"""
LLM Diff Test v4 Content Based - 内容ベースの単語レベル差分検出
位置の違いは無視し、テキスト内容の変化のみを検出
"""
import os
import sys
from pathlib import Path
import time
import logging
import argparse
from dotenv import load_dotenv

# ログ設定
logging.basicConfig(level=logging.DEBUG)

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parents[2]
sys.path.insert(0, str(project_root))

from apps.llm_docs_diff_v4.services.azure_service_enhanced import AzureDocumentServiceEnhanced
from apps.llm_docs_diff_v4.services.azure_service_cached import AzureDocumentServiceCached
from apps.llm_docs_diff_v4.core.text_preprocessing import TextPreprocessor
from apps.llm_docs_diff_v4.utils.pdf_utils import PDFProcessor

from apps.llm_docs_diff_v4.core.diff_detector_v4_content_based import ContentBasedDiffDetector
from apps.llm_docs_diff_v3.models.bbox_models import DiffResult, ChangeType
from apps.llm_docs_diff_v4.models.bbox_models import ComparisonResult
from apps.llm_docs_diff_v4.handlers.output_handler import OutputHandler

# 環境変数の読み込み
load_dotenv()

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description='LLM Diff Test v4 Content Based - 内容ベース差分検出')
    parser.add_argument('--dataset', type=str, choices=['default', 'sougou'], default='default',
                        help='使用するデータセット (default: docs/img/2023.pdf & 2024.pdf, sougou: data/sougou/)')
    parser.add_argument('--pdf1', type=str, help='比較元のPDFファイルパス（任意）')
    parser.add_argument('--pdf2', type=str, help='比較先のPDFファイルパス（任意）')
    parser.add_argument('--phrase-length', type=int, default=3,
                        help='フレーズ検出のn-gram長（デフォルト: 3単語）')
    return parser.parse_args()


def extract_word_data(hierarchy):
    """階層データから単語データを抽出"""
    words = []
    
    # 既存の単語データがある場合
    if 'words' in hierarchy:
        for word in hierarchy['words']:
            if isinstance(word, dict):
                bbox = word.get('bbox', [0, 0, 0, 0])
                text = word.get('text', word.get('content', ''))
                
                if isinstance(bbox, list) and len(bbox) >= 4:
                    words.append({
                        'x': bbox[0],
                        'y': bbox[1],
                        'width': bbox[2],
                        'height': bbox[3],
                        'text': text,
                        'page': word.get('page', 0),
                        'bbox': bbox
                    })
    
    # 単語データがない場合は行データから生成
    elif 'lines' in hierarchy:
        print("単語データが見つかりません。行データから単語を抽出します...")
        for line in hierarchy.get('lines', []):
            text = line.get('content', line.get('text', ''))
            if text:
                # 簡易的な単語分割（スペースで分割）
                word_texts = text.split()
                if word_texts:
                    line_bbox = line.get('bbox', [0, 0, 0, 0])
                    # 各単語に均等に幅を割り当て
                    word_width = line_bbox[2] / len(word_texts) if len(word_texts) > 0 else line_bbox[2]
                    
                    for i, word_text in enumerate(word_texts):
                        words.append({
                            'x': line_bbox[0] + i * word_width,
                            'y': line_bbox[1],
                            'width': word_width,
                            'height': line_bbox[3],
                            'text': word_text,
                            'page': line.get('page', 0),
                            'bbox': [
                                line_bbox[0] + i * word_width,
                                line_bbox[1],
                                word_width,
                                line_bbox[3]
                            ]
                        })
    
    return words


def main():
    start_time = time.time()
    args = parse_arguments()
    
    # データセットに基づいてPDFパスを設定
    if args.pdf1 and args.pdf2:
        # カスタムパスが指定された場合
        pdf1_path = Path(args.pdf1)
        pdf2_path = Path(args.pdf2)
    elif args.dataset == 'sougou':
        # sougouデータセットを使用
        data_dir = project_root / "data" / "sougou"
        pdf1_path = data_dir / "サンプル②2024 .pdf"
        pdf2_path = data_dir / "サンプル②2025.pdf"
    else:
        # デフォルトのテストデータを使用
        pdf1_path = project_root / "docs" / "img" / "2023.pdf"
        pdf2_path = project_root / "docs" / "img" / "2024.pdf"
    
    # ファイルの存在確認
    if not pdf1_path.exists() or not pdf2_path.exists():
        print(f"エラー: テストファイルが見つかりません")
        if not pdf1_path.exists():
            print(f"  PDF1が存在しません: {pdf1_path}")
        if not pdf2_path.exists():
            print(f"  PDF2が存在しません: {pdf2_path}")
        return
    
    # 出力ディレクトリ（内容ベース検出用）
    if args.dataset == 'sougou':
        output_dir = project_root / "output" / "llm_diff_test_v4_content_based" / "sougou"
    elif args.pdf1 and args.pdf2:
        output_dir = project_root / "output" / "llm_diff_test_v4_content_based" / "custom"
    else:
        output_dir = project_root / "output" / "llm_diff_test_v4_content_based" / "default"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # PDFを読み込み
    with open(pdf1_path, 'rb') as f:
        pdf1_bytes = f.read()
    with open(pdf2_path, 'rb') as f:
        pdf2_bytes = f.read()
    
    print(f"PDF1: {pdf1_path.name} ({len(pdf1_bytes)} バイト)")
    print(f"PDF2: {pdf2_path.name} ({len(pdf2_bytes)} バイト)")
    
    # Azure Document Intelligenceサービス（キャッシュ付き）
    azure_service = AzureDocumentServiceCached(
        cache_dir=str(output_dir / "cache")
    )
    
    # 1. PDFから階層構造を抽出
    print("\n=== PDFから階層構造を抽出 ===")
    try:
        # バッチ処理で階層構造を抽出
        pdf1_hierarchy = azure_service.extract_layout_with_hierarchy_batch(pdf1_bytes)
        pdf2_hierarchy = azure_service.extract_layout_with_hierarchy_batch(pdf2_bytes)
        
        print(f"\nPDF1 抽出結果:")
        print(f"  段落数: {len(pdf1_hierarchy.get('paragraphs', []))}")
        print(f"  行数: {len(pdf1_hierarchy.get('lines', []))}")
        print(f"  単語数: {len(pdf1_hierarchy.get('words', []))}")
        
        print(f"\nPDF2 抽出結果:")
        print(f"  段落数: {len(pdf2_hierarchy.get('paragraphs', []))}")
        print(f"  行数: {len(pdf2_hierarchy.get('lines', []))}")
        print(f"  単語数: {len(pdf2_hierarchy.get('words', []))}")
        
    except Exception as e:
        print(f"エラー: Azure抽出に失敗しました: {e}")
        return
    
    # 2. 単語データを抽出
    print("\n=== 単語データを抽出 ===")
    pdf1_words = extract_word_data(pdf1_hierarchy)
    pdf2_words = extract_word_data(pdf2_hierarchy)
    
    print(f"PDF1: {len(pdf1_words)} 単語")
    print(f"PDF2: {len(pdf2_words)} 単語")
    
    # デバッグ：単語データのサンプルを表示
    if pdf1_words:
        print(f"\nPDF1単語サンプル: {pdf1_words[0]}")
    
    # 3. 内容ベースの差分検出
    print("\n=== 内容ベースの差分検出 ===")
    detector = ContentBasedDiffDetector()
    
    # 単語レベルの差分
    word_diff_results = detector.detect_differences(pdf1_words, pdf2_words)
    
    # フレーズレベルの差分
    phrase_diff_results = detector.detect_phrase_differences(
        pdf1_words, pdf2_words, phrase_length=args.phrase_length
    )
    
    # 4. 結果のサマリー
    word_summary = detector.generate_content_diff_summary(word_diff_results)
    phrase_summary = detector.generate_content_diff_summary(phrase_diff_results)
    
    print(f"\n=== 内容ベース差分検出結果 ===")
    print(f"\n単語レベル:")
    print(f"  総変更数: {word_summary['total_content_changes']}")
    print(f"  追加: {word_summary['words_added']} 回")
    print(f"  削除: {word_summary['words_deleted']} 回")
    print(f"  ユニーク追加単語数: {len(word_summary['unique_words_added'])}")
    print(f"  ユニーク削除単語数: {len(word_summary['unique_words_deleted'])}")
    
    if word_summary['most_frequent_additions']:
        print(f"\n  最も頻繁に追加された単語:")
        for word, count in word_summary['most_frequent_additions'][:5]:
            print(f"    '{word}': {count}回")
    
    if word_summary['most_frequent_deletions']:
        print(f"\n  最も頻繁に削除された単語:")
        for word, count in word_summary['most_frequent_deletions'][:5]:
            print(f"    '{word}': {count}回")
    
    print(f"\n{args.phrase_length}単語フレーズレベル:")
    print(f"  総変更数: {phrase_summary['total_content_changes']}")
    print(f"  追加: {phrase_summary['words_added']} 回")
    print(f"  削除: {phrase_summary['words_deleted']} 回")
    
    # 5. 詳細な差分をCSVに出力
    import csv
    from collections import Counter
    
    # 単語レベルの差分（集計結果）
    word_csv_path = output_dir / "content_based_word_differences.csv"
    with open(word_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ChangeType', 'Word', 'Count'])
        
        # 頻度順に出力（上位50単語まで）
        for word, count in word_summary['most_frequent_additions'][:50]:
            writer.writerow(['ADDITION', word, count])
        
        for word, count in word_summary['most_frequent_deletions'][:50]:
            writer.writerow(['DELETION', word, count])
    
    print(f"\n単語レベル差分結果を保存: {word_csv_path}")
    
    # フレーズレベルの差分
    phrase_csv_path = output_dir / f"content_based_phrase_{args.phrase_length}gram_differences.csv"
    with open(phrase_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ChangeType', 'Phrase', 'Count'])
        
        # フレーズを集計
        phrase_added_counter = Counter()
        phrase_deleted_counter = Counter()
        
        for result in phrase_diff_results:
            if result.change_type == ChangeType.ADDITION and result.modified_bbox:
                phrase = result.modified_bbox.get('text', '').strip()
                phrase_added_counter[phrase] += 1
            elif result.change_type == ChangeType.DELETION and result.original_bbox:
                phrase = result.original_bbox.get('text', '').strip()
                phrase_deleted_counter[phrase] += 1
        
        # 追加されたフレーズを出力
        for phrase, count in phrase_added_counter.most_common():
            writer.writerow(['ADDITION', phrase, count])
        
        # 削除されたフレーズを出力
        for phrase, count in phrase_deleted_counter.most_common():
            writer.writerow(['DELETION', phrase, count])
    
    print(f"フレーズレベル差分結果を保存: {phrase_csv_path}")
    
    # 6. 実行時間
    elapsed_time = time.time() - start_time
    print(f"\n処理時間: {elapsed_time:.2f} 秒")
    
    # 7. 統計情報を保存
    import json
    stats_path = output_dir / "content_based_statistics.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump({
            'word_summary': word_summary,
            'phrase_summary': phrase_summary,
            'settings': {
                'phrase_length': args.phrase_length,
                'content_based_only': True
            },
            'processing_time': elapsed_time,
            'pdf1': str(pdf1_path),
            'pdf2': str(pdf2_path)
        }, f, ensure_ascii=False, indent=2)
    
    print(f"統計情報を保存: {stats_path}")
    
    # 8. PDF出力（ハイライト付き）
    print("\n=== PDF出力を生成 ===")
    
    # PDFプロセッサーを初期化
    pdf_processor = PDFProcessor()
    
    # ハイライト付きPDFを作成（削除された単語を赤、追加された単語を緑でハイライト）
    pdf1_highlighted_path = output_dir / "PDFs" / "2023_content_changes.pdf"
    pdf2_highlighted_path = output_dir / "PDFs" / "2024_content_changes.pdf"
    
    # PDFディレクトリを作成
    (output_dir / "PDFs").mkdir(exist_ok=True)
    
    # 削除された単語のハイライトを作成（PDF1）
    pdf1_highlights = []
    deletion_count = 0
    addition_count = 0
    
    for result in word_diff_results:
        if result.change_type == ChangeType.DELETION:
            deletion_count += 1
        elif result.change_type == ChangeType.ADDITION:
            addition_count += 1
    
    print(f"\n差分タイプ別カウント - 削除: {deletion_count}, 追加: {addition_count}")
    
    # デバッグ：最初の数件の差分タイプを確認
    for i, result in enumerate(word_diff_results[:5]):
        print(f"  結果{i+1}: change_type={result.change_type}, "
              f"DELETION={ChangeType.DELETION}, "
              f"equals={result.change_type == ChangeType.DELETION}")
    
    for result in word_diff_results:
        if result.change_type == ChangeType.DELETION and result.original_bbox:
            bbox = result.original_bbox.get('bbox', [])
            if bbox and len(bbox) >= 4:
                # bboxはリスト形式のまま渡す
                highlight = {
                    'bbox': bbox,  # [x, y, width, height]
                    'page': result.page,
                    'color': 'red',
                    'label': 'Deleted'
                }
                pdf1_highlights.append(highlight)
    
    # 追加された単語のハイライトを作成（PDF2）
    pdf2_highlights = []
    for result in word_diff_results:
        if result.change_type == ChangeType.ADDITION and result.modified_bbox:
            bbox = result.modified_bbox.get('bbox', [])
            if bbox and len(bbox) >= 4:
                # bboxはリスト形式のまま渡す
                highlight = {
                    'bbox': bbox,  # [x, y, width, height]
                    'page': result.page,
                    'color': 'green',
                    'label': 'Added'
                }
                pdf2_highlights.append(highlight)
    
    # デバッグ：ハイライト数を表示
    print(f"\nハイライト数 - PDF1削除: {len(pdf1_highlights)}, PDF2追加: {len(pdf2_highlights)}")
    
    # デバッグ：差分結果の詳細を確認
    if len(word_diff_results) > 0:
        print("\n差分結果サンプル（最初の5件）:")
        for i, result in enumerate(word_diff_results[:5]):
            print(f"  {i+1}. Type: {result.change_type}")
            print(f"     Page: {result.page}")
            if result.original_bbox:
                print(f"     Original: {result.original_bbox}")
            if result.modified_bbox:
                print(f"     Modified: {result.modified_bbox}")
    
    # ハイライト付きPDFを作成
    if pdf1_highlights:
        print(f"PDF1ハイライトサンプル: {pdf1_highlights[0] if pdf1_highlights else 'なし'}")
        pdf1_highlighted = pdf_processor.create_highlighted_pdf(
            pdf1_bytes, pdf1_highlights
        )
        # ファイルに保存
        with open(pdf1_highlighted_path, 'wb') as f:
            f.write(pdf1_highlighted)
        print(f"PDF1（削除箇所ハイライト）: {pdf1_highlighted_path}")
    else:
        print("PDF1のハイライト対象がありません")
    
    if pdf2_highlights:
        print(f"PDF2ハイライトサンプル: {pdf2_highlights[0] if pdf2_highlights else 'なし'}")
        pdf2_highlighted = pdf_processor.create_highlighted_pdf(
            pdf2_bytes, pdf2_highlights
        )
        # ファイルに保存
        with open(pdf2_highlighted_path, 'wb') as f:
            f.write(pdf2_highlighted)
        print(f"PDF2（追加箇所ハイライト）: {pdf2_highlighted_path}")
    else:
        print("PDF2のハイライト対象がありません")
    
    # 並列表示PDFも作成
    side_by_side_path = output_dir / "PDFs" / "content_changes_side_by_side.pdf"
    try:
        import fitz
        
        # 新しいPDFドキュメントを作成
        side_by_side_doc = fitz.open()
        doc1 = fitz.open(stream=pdf1_bytes, filetype="pdf")
        doc2 = fitz.open(stream=pdf2_bytes, filetype="pdf")
        
        # 最初の5ページのみ処理
        max_pages = min(5, max(len(doc1), len(doc2)))
        
        for page_num in range(max_pages):
            # A3横向きのページを作成
            new_page = side_by_side_doc.new_page(width=842, height=595)  # A3 landscape
            
            # 左側にPDF1のページを配置
            if page_num < len(doc1):
                page1 = doc1[page_num]
                page1_rect = fitz.Rect(10, 10, 411, 585)  # 左半分
                new_page.show_pdf_page(page1_rect, doc1, page_num)
                
                # 削除箇所をハイライト
                for highlight in pdf1_highlights:
                    if highlight['page'] == page_num:
                        bbox = highlight['bbox']
                        # 座標を調整（リスト形式のbbox: [x, y, width, height]）
                        hl_rect = fitz.Rect(
                            10 + bbox[0] * 401 / page1.rect.width,
                            10 + bbox[1] * 575 / page1.rect.height,
                            10 + (bbox[0] + bbox[2]) * 401 / page1.rect.width,
                            10 + (bbox[1] + bbox[3]) * 575 / page1.rect.height
                        )
                        new_page.add_highlight_annot(hl_rect)
                        annot = new_page.first_annot
                        if annot:
                            annot.set_colors(stroke=(1, 0, 0))  # 赤
                            annot.update()
            
            # 右側にPDF2のページを配置
            if page_num < len(doc2):
                page2 = doc2[page_num]
                page2_rect = fitz.Rect(431, 10, 832, 585)  # 右半分
                new_page.show_pdf_page(page2_rect, doc2, page_num)
                
                # 追加箇所をハイライト
                for highlight in pdf2_highlights:
                    if highlight['page'] == page_num:
                        bbox = highlight['bbox']
                        # 座標を調整（リスト形式のbbox: [x, y, width, height]）
                        hl_rect = fitz.Rect(
                            431 + bbox[0] * 401 / page2.rect.width,
                            10 + bbox[1] * 575 / page2.rect.height,
                            431 + (bbox[0] + bbox[2]) * 401 / page2.rect.width,
                            10 + (bbox[1] + bbox[3]) * 575 / page2.rect.height
                        )
                        new_page.add_highlight_annot(hl_rect)
                        annot = new_page.first_annot
                        if annot:
                            annot.set_colors(stroke=(0, 1, 0))  # 緑
                            annot.update()
            
            # ページ番号を追加
            text = f"Page {page_num + 1}: Left=2023 (Deletions in Red), Right=2024 (Additions in Green)"
            new_page.insert_text(fitz.Point(421, 590), text, fontsize=10)
        
        # PDFを保存
        side_by_side_doc.save(str(side_by_side_path))
        side_by_side_doc.close()
        doc1.close()
        doc2.close()
        
        print(f"並列表示PDF: {side_by_side_path}")
        
    except Exception as e:
        print(f"並列表示PDF作成エラー: {e}")


if __name__ == "__main__":
    main()