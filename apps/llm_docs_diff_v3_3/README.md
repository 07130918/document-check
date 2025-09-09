# LLM Document Difference Detection v3.3

## 概要

v3.3は、テーブル認識機能を強化した高精度な文書差分検出システムです。Azure Document Intelligenceの高度な機能を活用し、複雑なレイアウトやテーブルを含む文書の差分を正確に検出します。

## 主な特徴

### 1. テーブル対応差分検出 (TableAwareDiffDetector)
- **テーブル構造の認識**: Azure Document Intelligenceによる正確なテーブル抽出
- **セル単位の差分検出**: テーブル内の個々のセルレベルでの変更を検出
- **ヘッダーベースのマッチング**: テーブルヘッダーの完全一致による確実な対応付け
- **テキストとテーブルの統合処理**: 通常テキストとテーブルをシームレスに処理

### 2. 高精度なテーブルマッチング
- **ヘッダー完全一致方式**: テーブルのヘッダー行が完全に一致する場合のみマッチング
- **位置情報の活用**: ページ番号と物理的位置を考慮した賢いマッチング
- **構造認識**: 行数・列数によるテーブル構造の検証

### 3. デバッグとビジュアライゼーション
- **テーブルハイライト機能**: PDF内のテーブルを視覚的にハイライト表示
- **詳細なデバッグ情報**: テーブル検出結果をJSON/CSVで出力
- **差分の可視化**: 変更・追加・削除されたコンテンツを色分けして表示

## アーキテクチャ

```
llm_docs_diff_v3_3/
├── config/
│   └── settings.py              # システム設定
├── core/
│   ├── table_aware_diff_detector.py  # テーブル対応差分検出
│   ├── table_matcher.py         # テーブルマッチングロジック
│   ├── table_debug_handler.py   # テーブルデバッグ機能
│   ├── cell_text_analyzer.py    # セル内テキスト解析
│   ├── document_analyzer.py     # 文書構造解析
│   ├── azure_text_processing.py # Azure OCR処理
│   ├── reading_order_v2.py      # 読み取り順序処理
│   ├── text_grouping.py         # テキストグループ化
│   └── text_preprocessing.py    # テキスト前処理
├── models/
│   ├── bbox_models.py           # バウンディングボックスモデル
│   └── table_models.py          # テーブルデータモデル
├── services/
│   ├── azure_service.py         # Azure Document Intelligence連携
│   ├── llm_service.py           # LLM解析サービス
│   ├── pdf_converter.py         # PDF変換処理
│   └── simple_pdf_generator_v3.py # PDF生成
├── handlers/
│   └── output_handler.py        # 出力処理
├── utils/
│   ├── pdf_utils.py             # PDFユーティリティ
│   └── page_splitter.py         # ページ分割処理
└── test_llm_diff_v3.py         # メインスクリプト
```

## 処理フロー

1. **文書読み込み**: PDFファイルを読み込み
2. **Azure OCR処理**:
   - レイアウト解析（テキスト、段落、テーブル）
   - テーブル構造の抽出
   - 読み取り順序の取得
3. **テーブルマッチング**: 両文書間でテーブルを対応付け
4. **差分検出**:
   - テキスト差分の検出
   - テーブル内セル差分の検出
5. **LLM解析**: 差分の意味的重要度を評価
6. **出力生成**:
   - ハイライト付きPDF
   - 詳細レポート（Markdown/JSON）
   - デバッグ情報

## 使用方法

```bash
# 基本的な使用方法
poetry run python apps/llm_docs_diff_v3_3/test_llm_diff_v3.py

# 特定のサンプルを処理
poetry run python apps/llm_docs_diff_v3_3/test_llm_diff_v3.py --sample sample2

# テーブルハイライトを有効化
poetry run python apps/llm_docs_diff_v3_3/test_llm_diff_v3.py --highlight-tables

# デバッグ情報を詳細に出力
poetry run python apps/llm_docs_diff_v3_3/test_llm_diff_v3.py --debug
```

## 設定オプション

`config/settings.py`で以下の設定が可能:

- **USE_HIGH_RESOLUTION_OCR**: 高解像度OCRの使用（デフォルト: True）
- **MAX_PAGES**: 処理する最大ページ数
- **AZURE_API_VERSION**: Azure APIバージョン
- **LLM_MODEL**: 使用するLLMモデル

## 出力ファイル

```
output/llm_diff_test_v3-3/[sample_name]/
├── PDFs/
│   ├── [doc1]_compared.pdf      # 差分ハイライト付きPDF（文書1）
│   ├── [doc2]_compared.pdf      # 差分ハイライト付きPDF（文書2）
│   └── side_by_side_comparison.pdf  # 並列比較PDF
├── reports/
│   ├── execution_report.json    # 実行レポート
│   └── execution_report.md      # Markdownレポート
├── debug/
│   ├── table_detection.json     # テーブル検出結果
│   ├── table_matching.json      # テーブルマッチング結果
│   └── tables/                  # 各テーブルの詳細情報
└── comparison_differences.csv   # 差分一覧
```

## テーブルマッチングアルゴリズム

### マッチング条件
1. テーブルヘッダーが完全に一致
2. 同じページまたは近隣ページに存在
3. 列数が一致

### 優先順位
1. 同じページのテーブル
2. ±1ページ以内のテーブル
3. それ以外（ヘッダー一致のみ）

## 既知の問題と制限事項

1. **テーブル分割問題**: Azure Document Intelligenceが大きなテーブルを複数の小さなテーブルとして検出することがある
2. **複雑なレイアウト**: ネストされたテーブルや複雑な構造は正確に検出できない場合がある

## 今後の改善予定

1. テーブル結合ロジックの実装（分割されたテーブルの自動結合）
2. より高度なテーブル構造認識
