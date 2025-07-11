#!/usr/bin/env python3
"""
ベースライン実装テスト
現在の実装をベースラインとして、機能の動作確認を行う
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.document_diff_system.core import DocumentComparisonPipeline


def test_baseline():
    """
    ベースライン実装のテスト
    5ページ制限付きで文書比較を実行し、すべての出力ファイルが正しく生成されることを確認
    """
    print("=== ベースライン実装テスト ===")
    print("5ページ制限で文書比較を実行します\n")
    
    # 入力ファイル
    file1 = project_root / "docs" / "img" / "2023.pdf"
    file2 = project_root / "docs" / "img" / "2024.pdf"
    
    if not (file1.exists() and file2.exists()):
        print("Error: 入力ファイルが見つかりません")
        print(f"  - {file1}")
        print(f"  - {file2}")
        return False
    
    # 出力ディレクトリ
    output_dir = project_root / "output" / "baseline_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # パイプライン実行（現在の設定をベースラインとする）
    pipeline = DocumentComparisonPipeline(
        use_layout_aware_diff=False,        # レイアウト認識差分検出は無効
        use_sentence_aware_diff=True,       # 文章単位→単語単位の2段階差分検出を使用
        max_pages=5                         # 5ページに制限
    )
    
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
        expected_files = [
            ("PDFs", "2023_compared.pdf"),
            ("PDFs", "2024_compared.pdf"), 
            ("PDFs", "2023_original_order.pdf"),
            ("PDFs", "2024_original_order.pdf"),
            ("PDFs", "2023_reading_order.pdf"),
            ("PDFs", "2024_reading_order.pdf"),
            ("reports", "sentence_info.json"),
            ("reports", "reading_order.json"),
            ("reports", "execution_report.json"),
            ("reports", "execution_report.md"),
            ("debug", "2023_reading_order_original.csv"),
            ("debug", "2023_reading_order_estimated.csv"),
            ("debug", "2024_reading_order_original.csv"),
            ("debug", "2024_reading_order_estimated.csv")
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