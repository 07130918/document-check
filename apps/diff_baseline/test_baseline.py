#!/usr/bin/env python3
"""
ベースライン実装テスト
現在の実装をベースラインとして、機能の動作確認を行う
"""
import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.diff_baseline.core import DocumentComparisonPipeline
from apps.diff_baseline.services import SimpleDiffDetector


def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description='ベースライン実装テスト')
    parser.add_argument('--dataset', type=str, 
                        choices=['default', 'sample1', 'sample2', 'sample3', 'sample4', 'sample5'],
                        default='default',
                        help='使用するデータセット')
    parser.add_argument('--pdf1', type=str, help='比較元のPDFファイルパス（任意）')
    parser.add_argument('--pdf2', type=str, help='比較先のPDFファイルパス（任意）')
    return parser.parse_args()


def test_baseline():
    """
    ベースライン実装のテスト
    全ページで文書比較を実行し、すべての出力ファイルが正しく生成されることを確認
    """
    args = parse_arguments()
    
    print("=== ベースライン実装テスト ===")
    print("全ページで文書比較を実行します（有料版）\n")

    # データセットに基づいてPDFパスを設定
    if args.pdf1 and args.pdf2:
        # カスタムパスが指定された場合
        file1 = Path(args.pdf1)
        file2 = Path(args.pdf2)
    elif args.dataset == 'sample1':
        data_dir = project_root / "data" / "sample1"
        file1 = data_dir / "サンプル①2024.pdf"
        file2 = data_dir / "サンプル①2025.pdf"
    elif args.dataset == 'sample2':
        data_dir = project_root / "data" / "sample2"
        file1 = data_dir / "サンプル②2024 .pdf"
        file2 = data_dir / "サンプル②2025.pdf"
    elif args.dataset == 'sample3':
        data_dir = project_root / "data" / "sample3"
        file1 = data_dir / "サンプル③2023.pdf"
        file2 = data_dir / "サンプル③2024.pdf"
    elif args.dataset == 'sample4':
        data_dir = project_root / "data" / "sample4"
        file1 = data_dir / "サンプル④2024.pdf"
        file2 = data_dir / "サンプル④2025.pdf"
    elif args.dataset == 'sample5':
        data_dir = project_root / "data" / "sample5"
        file1 = data_dir / "サンプル⑤2024.pdf"
        file2 = data_dir / "サンプル⑤2025.pdf"
    else:
        # デフォルトのテストデータを使用
        file1 = project_root / "docs" / "img" / "2023.pdf"
        file2 = project_root / "docs" / "img" / "2024.pdf"

    if not (file1.exists() and file2.exists()):
        print("Error: 入力ファイルが見つかりません")
        print(f"  - {file1}")
        print(f"  - {file2}")
        return False

    # 出力ディレクトリ（データセットごとに分ける）
    if args.pdf1 and args.pdf2:
        output_dir = project_root / "output" / "baseline_test" / "custom"
    else:
        output_dir = project_root / "output" / "baseline_test" / args.dataset
    output_dir.mkdir(parents=True, exist_ok=True)

    # パイプライン実行（単純化版の差分検出器を使用）
    pipeline = DocumentComparisonPipeline(
        use_layout_aware_diff=False,        # レイアウト認識差分検出は無効
        use_sentence_aware_diff=False,      # 文章単位差分検出も無効
        max_pages=None                      # 有料版：全ページを処理
    )
    
    # SimpleDiffDetectorに差し替え（差分タイプを分けない）
    pipeline.diff_detector = SimpleDiffDetector()

    try:
        print(f"入力ファイル:")
        print(f"  - 文書1: {file1.name}")
        print(f"  - 文書2: {file2.name}")
        print(f"出力ディレクトリ: {output_dir}")
        print("-" * 50)

        # 比較実行
        summary = pipeline.compare_files(
            str(file1),
            str(file2),
            output_dir=str(output_dir),
            quiet=False  # 詳細な出力を表示
        )

        print("\n" + "=" * 50)
        print("✅ ベースライン実装の実行が完了しました")
        print("=" * 50)

        # 期待される出力ファイルの確認（新しいディレクトリ構造）
        base1 = file1.stem  # 拡張子なしのファイル名
        base2 = file2.stem
        expected_files = [
            ("PDFs", f"{base1}_compared.pdf"),
            ("PDFs", f"{base2}_compared.pdf"),
            ("PDFs", f"{base1}_original_order.pdf"),
            ("PDFs", f"{base2}_original_order.pdf"),
            ("PDFs", f"{base1}_reading_order.pdf"),
            ("PDFs", f"{base2}_reading_order.pdf"),
            ("PDFs", "side_by_side_comparison.pdf"),  # 並列表示PDF
            ("reports", "sentence_info.json"),
            ("reports", "reading_order.json"),
            ("reports", "execution_report.json"),
            ("reports", "execution_report.md"),
            ("debug", f"{base1}_reading_order_original.csv"),
            ("debug", f"{base1}_reading_order_estimated.csv"),
            ("debug", f"{base2}_reading_order_original.csv"),
            ("debug", f"{base2}_reading_order_estimated.csv")
        ]

        print("\n生成されたファイル:")
        missing_files = []
        for subdir, filename in expected_files:
            file_path = output_dir / subdir / filename
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  ✓ {subdir}/{filename} ({size:,} bytes)")
            else:
                print(f"  ✗ {subdir}/{filename} (見つかりません)")
                missing_files.append(f"{subdir}/{filename}")

        # サマリー情報の表示
        print(f"\n文書情報:")
        print(f"  文書1: {summary.get('doc1_words', 0)} 単語, {summary.get('pages_doc1', 0)} ページ")
        print(f"  文書2: {summary.get('doc2_words', 0)} 単語, {summary.get('pages_doc2', 0)} ページ")

        if 'differences' in summary:
            diff_info = summary['differences']
            print(f"\n差分検出結果:")
            print(f"  総差分数: {diff_info.get('total', 0)}")
            # SimpleDiffDetectorはすべて同じタイプなので、内訳は表示しない
            if 'differences' in diff_info:
                print(f"  差分数: {diff_info.get('differences', 0)}")
            else:
                # 旧形式の場合の表示
                print(f"  追加: {diff_info.get('added', 0)}")
                print(f"  削除: {diff_info.get('deleted', 0)}")
                print(f"  変更: {diff_info.get('modified', 0)}")

        # 成功判定
        if missing_files:
            print(f"\n⚠️  警告: {len(missing_files)}個のファイルが生成されませんでした")
            return False
        else:
            print("\n✅ すべての期待されるファイルが正しく生成されました")
            return True

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        print("\nトレースバック:")
        traceback.print_exc()
        return False


def main():
    """メイン実行関数"""
    print("ベースライン実装テストを開始します...\n")

    success = test_baseline()

    print("\n" + "=" * 50)
    if success:
        print("✅ ベースラインテスト: 成功")
        return 0
    else:
        print("❌ ベースラインテスト: 失敗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
