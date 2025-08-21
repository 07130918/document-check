# PDF Document Difference Detection System

MS&ADインシュアランスグループ向けのPDF文書差分検出システムです。Azure Document IntelligenceとLLMを活用して、文書の変更箇所を高精度で検出し、視覚的にわかりやすく表示します。

## 🌟 特徴

- **高精度なOCR**: Azure Document Intelligenceを使用した文書解析
- **LLM統合**: OpenAI GPTを使用した差分の意味的分析と要約
- **単語レベル差分検出**: 細かい変更も見逃さない精密な比較
- **視覚的な差分表示**: 変更箇所をハイライト表示したPDF出力
- **多様な文書形式対応**: PDF、Word、PowerPointに対応
- **バッチ処理対応**: 複数ページの効率的な処理

## 📊 システムバージョン

### v5 (最新版) - LLM統合版
- Azure OCRの単語レベル情報を直接活用
- LLMによる差分の意味的分析
- 変更の重要度自動評価
- 自然言語での差分要約生成

### v4 - ブロックベース高精度版
- Azure OCRの段落認識を活用
- 高精度なブロックマッチング
- 座標系の完全な統一

### v3 - LLM実験版
- LLMによる読み順序推定
- 文書構造の自動解析
- 差分の要約生成

### v2 - 行ベース版
- Azure OCRの行認識を活用
- 行単位での差分検出

### v1 - 基本版
- 単語ベースの基本的な差分検出

### baseline - ベースライン版
- prj-meiji-document-checkアルゴリズムベース
- SequenceMatcher + レーベンシュタイン距離

## 🚀 クイックスタート

### Docker環境での実行（推奨）

```bash
# 1. 環境セットアップ
./scripts/docker-setup.sh

# 2. v5 LLM版の実行（最新・推奨）
docker compose run pdf-diff-v5-llm

# 3. 結果確認
ls -la output/llm_diff_test_v5_llm/dantai/
```

### データセットを指定して実行

```bash
# dantaiデータセット（デフォルト）
docker compose run --rm pdf-diff-v5-llm

# sample1データセット
docker compose run --rm pdf-diff-v5-llm poetry run python apps/llm_docs_diff_v5/test_llm_diff_v5_with_llm.py --dataset sample1

# sample2データセット
docker compose run --rm pdf-diff-v5-llm poetry run python apps/llm_docs_diff_v5/test_llm_diff_v5_with_llm.py --dataset sample2

# v3版でsample3を実行
docker compose run --rm pdf-diff-v3-llm poetry run python apps/llm_docs_diff_v3/test_llm_diff_v3_with_llm.py --dataset sample3
```

### ローカル環境での実行

```bash
# 1. Poetry インストール
curl -sSL https://install.python-poetry.org | python3 -

# 2. 依存関係インストール
poetry install --with dev,test --extras "full"

# 3. 環境変数設定
cp .env.template .env
# .envファイルを編集してAPIキーを設定

# 4. v5 LLM版の実行
poetry run python apps/llm_docs_diff_v5/test_llm_diff_v5_with_llm.py \
  --dataset dantai --use-llm --llm-summary
```

## 📁 プロジェクト構成

```
prj-ms-document-check/
├── apps/                        # アプリケーションバージョン
│   ├── llm_docs_diff_v5/       # v5: LLM統合版（最新）
│   │   ├── services/           # Azure OCR & LLMサービス
│   │   ├── handlers/           # 出力処理（単語レベルハイライト）
│   │   └── test_llm_diff_v5_with_llm.py  # LLM版実行スクリプト
│   ├── llm_docs_diff_v4/       # v4: ブロックベース版
│   ├── llm_docs_diff_v3/       # v3: LLM実験版
│   ├── llm_docs_diff_v2/       # v2: 行ベース版
│   ├── llm_docs_diff_v1/       # v1: 基本版
│   └── diff_baseline/          # ベースライン実装
├── data/                        # テストデータ
│   ├── dantaihoken/            # 団体保険データセット
│   ├── sample1/                # サンプル①データセット
│   ├── sample2/                # サンプル②データセット（総合保険）
│   ├── sample3/                # サンプル③データセット
│   ├── sample4/                # サンプル④データセット（アノテーション付き）
│   └── sample5/                # サンプル⑤データセット（アノテーション付き）
├── docs/
│   └── img/                    # サンプルPDF
├── output/                      # 処理結果出力先
├── scripts/                     # 実行スクリプト
│   └── docker-setup.sh         # Docker環境セットアップ
├── Dockerfile                  # Dockerfile
├── docker-compose.yml          # Docker Compose設定
├── pyproject.toml              # Poetry依存関係管理
└── .env.template               # 環境変数テンプレート
```

## 🔧 必要な環境

- Python 3.11以上
- Azure Document Intelligenceアカウント
- OpenAI APIキー（LLM機能使用時）
- Docker & Docker Compose（推奨）
- 4GB以上のメモリ

## 🛠 セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd prj-ms-document-check
```

### 2. 環境変数の設定

```bash
cp .env.template .env
```

`.env`ファイルを編集：

```env
# Azure Document Intelligence設定
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your-api-key

# OpenAI API設定（LLM機能使用時）
OPENAI_API_KEY=sk-your-openai-api-key

# その他の設定
LOG_LEVEL=INFO
DEBUG=False
```

### 3. Docker環境のセットアップ

```bash
chmod +x scripts/docker-setup.sh
./scripts/docker-setup.sh
```

## 📖 使用方法

### Docker環境での実行

#### v5 LLM版（推奨）
```bash
docker compose run pdf-diff-v5-llm
```

#### v3 LLM版
```bash
docker compose run pdf-diff-v3-llm
```

#### 開発用対話環境
```bash
docker compose run pdf-diff-dev
```

#### Jupyter Lab環境
```bash
docker compose up pdf-diff-jupyter
# ブラウザで http://localhost:8888 にアクセス
```

### コマンドラインオプション

#### 共通オプション
- `--dataset`: 使用するデータセット
  - `dantai`: 団体保険データセット（デフォルト）
  - `sample1`: サンプル①（後半部分）
  - `sample2`: サンプル②（総合保険）
  - `sample3`: サンプル③
  - `sample4`: サンプル④（アノテーション付き）
  - `sample5`: サンプル⑤（アノテーション付き）

#### v5 LLM版オプション
- `--use-llm`: LLMで差分を分析（デフォルト: True）
- `--llm-summary`: LLMで要約を生成（デフォルト: True）
- `--analyze-each`: 各差分を個別にLLMで分析
- `--max-pages`: 処理する最大ページ数（デフォルト: 5）

#### v3 LLM版オプション
- `--use-llm-order`: LLMで読み順序を推定
- `--use-llm-summary`: LLMで差分を要約
- `--analyze-structure`: LLMで文書構造を解析

## 📊 出力ファイル

処理結果は`output/`ディレクトリに保存されます：

```
output/
├── llm_diff_test_v5_llm/         # v5 LLM版の結果
│   ├── dantai/                   # 団体保険データセット
│   ├── sample1/                  # サンプル①
│   ├── sample2/                  # サンプル②
│   └── [dataset]/
│       ├── [pdf1]_highlighted.pdf   # 文書1のハイライト版
│       ├── [pdf2]_highlighted.pdf   # 文書2のハイライト版
│       ├── [pdf1]_vs_[pdf2]_highlighted.pdf  # 並列表示版
│       ├── differences.json      # 差分詳細
│       ├── summary.json          # 差分サマリー
│       ├── llm_analysis_result.json  # LLM分析結果
│       └── evaluation_document.md    # 評価用ドキュメント
└── llm_diff_test_v3_llm/         # v3 LLM版の結果
    ├── dantai/
    ├── sample1/
    ├── sample2/
    └── [dataset]/
        ├── PDFs/                  # 各種PDF出力
        ├── reports/               # レポート類
        └── debug/                 # デバッグ情報
```

## 🤖 LLM分析結果の例

### dantaiデータセットの場合
```json
{
  "overall_trend": "年度や日付の更新が中心で、情報の正確性を保つための変更",
  "key_changes": [
    "保険年度が令和5年度から令和6年度に変更",
    "申込締切日が10月25日から10月23日に変更",
    "加入者数のデータが更新"
  ],
  "formatting_changes": [
    "日付の表記が令和5年から令和6年に変更",
    "URLが更新",
    "QRコードに関する文言が追加"
  ],
  "impact_assessment": "high - 重要な日付や年度の変更が含まれているため",
  "summary": "年度更新に伴う日付、数値、リンクの変更が主な内容"
}
```

### sample2データセットの場合
```json
{
  "key_changes": [
    "2024年度版から2025年度版に変更",
    "総合医療保障プランの名称が追加",
    "改定内容の確認ページが変更",
    "書面提供からPDFファイル提供に変更",
    "保険期間と保険料支払い開始日が2026年に変更"
  ]
}
```

## 🧪 開発

### テストの実行
```bash
# Docker環境
docker compose run pdf-diff-test

# ローカル環境
poetry run pytest
```

### コードフォーマット
```bash
poetry run black .
poetry run isort .
poetry run flake8
```

### MakefileコマンドI（ベースライン版）
```bash
make build        # Dockerイメージビルド
make run          # ベースラインテスト実行
make dev          # 開発環境起動
make test         # テスト実行
make format       # コードフォーマット
make clean        # クリーンアップ
```

## 🐛 トラブルシューティング

### Azure OCRエラー
- エンドポイントとAPIキーが正しく設定されているか確認
- リージョンが正しいか確認（通常は`japaneast`）
- Azure Document Intelligenceのクォータを確認

### LLMエラー
- OpenAI APIキーが正しく設定されているか確認
- API利用制限に達していないか確認
- レート制限エラーの場合は時間をおいて再実行

### メモリ不足
- `--max-pages`オプションで処理ページ数を制限
- Dockerのメモリ割り当てを増やす
- バッチサイズを調整（Azure OCRの設定）

### 文字化け
- PDFのフォント埋め込みを確認
- Azure OCRの言語設定を確認（日本語）

## 📈 パフォーマンス

### 処理時間の目安（5ページのPDF）
- v5 LLM版: 約30秒
- v5 標準版: 約15秒
- v3 LLM版: 約90秒
- ベースライン: 約0.01秒

### メモリ使用量
- 通常: 500MB以下
- 大きなPDF（100ページ以上）: 2GB程度

## 🔒 セキュリティ

- APIキーは環境変数で管理
- 処理済みファイルは自動的に削除されません（手動管理）
- Dockerコンテナ内で隔離された環境で実行

## 📝 ライセンス

本プロジェクトは非公開プロジェクトです。MS&ADインシュアランスグループ内部での使用に限定されます。

## 🤝 貢献ガイドライン

1. フィーチャーブランチで開発
2. コミット前にフォーマット実行
3. テストを追加・実行
4. プルリクエストを作成

## 📞 お問い合わせ

技術的な質問や問題報告は、プロジェクト管理者までご連絡ください。

---

© 2025 MS&AD Insurance Group Holdings, Inc. All rights reserved.
