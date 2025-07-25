"""
LLM Diff Test v4 Word Level - 単語レベルの位置ベース差分検出
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

from apps.llm_docs_diff_v4.core.diff_detector_v4_word_level import WordLevelDiffDetector
from apps.llm_docs_diff_v4.models.bbox_models import ComparisonResult, ChangeType
from apps.llm_docs_diff_v4.handlers.output_handler import OutputHandler

# 環境変数の読み込み
load_dotenv()

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description='LLM Diff Test v4 Word Level - 単語レベル差分検出')
    parser.add_argument('--dataset', type=str, choices=['default', 'sougou'], default='default',
                        help='使用するデータセット (default: docs/img/2023.pdf & 2024.pdf, sougou: data/sougou/)')
    parser.add_argument('--pdf1', type=str, help='比較元のPDFファイルパス（任意）')
    parser.add_argument('--pdf2', type=str, help='比較先のPDFファイルパス（任意）')
    parser.add_argument('--position-tolerance', type=float, default=5.0,
                        help='単語の位置許容誤差（ピクセル）')
    parser.add_argument('--text-similarity', type=float, default=0.8,
                        help='テキスト類似度の閾値')
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
    
    # 出力ディレクトリ（単語レベル検出用）
    if args.dataset == 'sougou':
        output_dir = project_root / "output" / "llm_diff_test_v4_word_level" / "sougou"
    elif args.pdf1 and args.pdf2:
        output_dir = project_root / "output" / "llm_diff_test_v4_word_level" / "custom"
    else:
        output_dir = project_root / "output" / "llm_diff_test_v4_word_level" / "default"
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
    
    # 3. 単語レベルの差分検出
    print("\n=== 単語レベルの差分検出 ===")
    detector = WordLevelDiffDetector(
        position_tolerance=args.position_tolerance,
        text_similarity_threshold=args.text_similarity,
        detect_all_position_changes=True  # すべての位置変化を検出
    )
    
    diff_results = detector.detect_differences(pdf1_words, pdf2_words)
    
    # 4. 結果のサマリー
    summary = detector.generate_word_diff_summary(diff_results)
    
    print(f"\n=== 単語レベル差分検出結果 ===")
    print(f"総変更単語数: {summary['total_word_changes']}")
    print(f"  追加: {summary['word_additions']} 単語")
    print(f"  削除: {summary['word_deletions']} 単語")
    print(f"  変更: {summary['word_modifications']} 単語")
    print(f"    - テキストのみ変更: {summary['text_changes']} 単語")
    print(f"    - 位置のみ変更: {summary['position_changes']} 単語")
    print(f"    - テキストと位置両方変更: {summary['text_and_position_changes']} 単語")
    
    # ページごとの結果
    print("\nページごとの結果:")
    for page, stats in summary['by_page'].items():
        print(f"  ページ {page + 1}:")
        print(f"    追加: {stats['word_additions']} 単語")
        print(f"    削除: {stats['word_deletions']} 単語")
        print(f"    変更: {stats['word_modifications']} 単語")
        print(f"    位置変更: {stats['position_changes']} 単語")
    
    # 5. 詳細な差分をCSVに出力
    import csv
    csv_path = output_dir / "word_level_differences.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Page', 'ChangeType', 'Detail', 'OriginalText', 'ModifiedText',
            'OriginalX', 'OriginalY', 'ModifiedX', 'ModifiedY',
            'DeltaX', 'DeltaY', 'Similarity'
        ])
        
        for result in diff_results:
            original_text = ''
            original_x = ''
            original_y = ''
            if result.original_bbox:
                original_text = result.original_bbox.get('text', '')
                original_x = result.original_bbox.get('bbox', [0])[0]
                original_y = result.original_bbox.get('bbox', [0, 0])[1]
            
            modified_text = ''
            modified_x = ''
            modified_y = ''
            if result.modified_bbox:
                modified_text = result.modified_bbox.get('text', '')
                modified_x = result.modified_bbox.get('bbox', [0])[0]
                modified_y = result.modified_bbox.get('bbox', [0, 0])[1]
            
            # LLM説明から変更タイプを判定
            llm_explanation = getattr(result, 'llm_explanation', '')
            if 'Text changed' in llm_explanation and 'position moved' in llm_explanation:
                detail = 'text_and_position'
            elif 'Text changed' in llm_explanation:
                detail = 'text_only'
            elif 'Position moved' in llm_explanation:
                detail = 'position_only'
            else:
                detail = result.change_type.name.lower()
            
            # 位置変化を計算
            delta_x = ''
            delta_y = ''
            if original_x and modified_x:
                delta_x = modified_x - original_x
            if original_y and modified_y:
                delta_y = modified_y - original_y
            
            writer.writerow([
                result.page + 1,
                result.change_type.name,
                detail,
                original_text,
                modified_text,
                original_x,
                original_y,
                modified_x,
                modified_y,
                delta_x,
                delta_y,
                result.semantic_similarity
            ])
    
    print(f"\n詳細な差分結果を保存: {csv_path}")
    
    # 6. 実行時間
    elapsed_time = time.time() - start_time
    print(f"\n処理時間: {elapsed_time:.2f} 秒")
    
    # 7. 統計情報を保存
    import json
    stats_path = output_dir / "word_level_statistics.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': summary,
            'settings': {
                'position_tolerance': args.position_tolerance,
                'text_similarity_threshold': args.text_similarity,
                'detect_all_position_changes': True
            },
            'processing_time': elapsed_time,
            'pdf1': str(pdf1_path),
            'pdf2': str(pdf2_path)
        }, f, ensure_ascii=False, indent=2)
    
    print(f"統計情報を保存: {stats_path}")


if __name__ == "__main__":
    main()