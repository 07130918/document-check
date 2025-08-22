# PDF Document Difference Detection System

MS&ADインシュアランスグループ向けのPDF文書差分検出システムです。Azure Document IntelligenceとLLMを活用して、文書の変更箇所を高精度で検出し、視覚的にわかりやすく表示します。

## 🌟 特徴

- **高精度なOCR**: Azure Document Intelligence（有料版）を使用した全ページ文書解析
- **LLM統合**: OpenAI GPTを使用した差分の意味的分析と要約
- **単語レベル差分検出**: 細かい変更も見逃さない精密な比較
- **視覚的な差分表示**: 変更箇所をハイライト表示したPDF出力
- **多様な文書形式対応**: PDF、Word、PowerPointに対応
- **全ページ処理**: Azure有料版により無制限のページ数に対応

## 📊 推奨システムバージョン

### v5 (最新版) - LLM統合版
- Azure OCRの単語レベル情報を直接活用
- LLMによる差分の意味的分析
- 変更の重要度自動評価
- 自然言語での差分要約生成
- 最も高精度で実用的

### v3 - 内容ベース差分検出版
- 内容の類似度に基づく高精度なマッチング（90%内容、10%位置）
- LLMによる差分要約生成（オプション）
- 複雑なレイアウトに対応
- 移動検出は非実装（不要と判断）

### baseline - ベースライン版
- prj-meiji-document-checkアルゴリズムベース
- SequenceMatcher + レーベンシュタイン距離
- シンプルで高速な処理
- 基本的な差分検出に最適

## 🚀 クイックスタート

### Docker環境での実行（推奨）

```bash
# 1. 環境セットアップ
./scripts/docker-setup.sh

# 2. v5 LLM版の実行（最新・推奨）
docker compose run --rm pdf-diff-v5-llm

# 3. 結果確認
ls -la output/llm_diff_test_v5_llm/dantai/
```

### 各バージョンの実行

```bash
# v5 LLM版（最高精度・推奨）
docker compose run --rm pdf-diff-v5-llm poetry run python apps/llm_docs_diff_v5/test_llm_diff_v5_with_llm.py --dataset sample1 --use-llm --llm-summary

# v3 内容ベース版（高速・実用的）
docker compose run --rm pdf-diff-v3-llm poetry run python apps/llm_docs_diff_v3/test_llm_diff_v3_with_llm.py --dataset sample1 --use-llm-summary

# baseline版（シンプル・高速）
docker compose run --rm pdf-diff-baseline poetry run python apps/diff_baseline/test_baseline.py --dataset sample1
```

### 利用可能なデータセット

```bash
# 各バージョンは以下のデータセットをサポート:
# - dantai: 団体保険データセット
# - sample1: サンプル①（保険募集資料）
# - sample2: サンプル②（総合保険）
# - sample3: サンプル③
# - sample4: サンプル④（アノテーション付き）
# - sample5: サンプル⑤（アノテーション付き）
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

# 4. 実行例
# v5 LLM版
poetry run python apps/llm_docs_diff_v5/test_llm_diff_v5_with_llm.py --dataset sample1 --use-llm --llm-summary

# v3 内容ベース版
poetry run python apps/llm_docs_diff_v3/test_llm_diff_v3_with_llm.py --dataset sample1 --use-llm-summary

# baseline版
poetry run python apps/diff_baseline/test_baseline.py --dataset sample1
```

## 📁 プロジェクト構成

```
prj-ms-document-check/
├── apps/                        # アプリケーションバージョン
│   ├── llm_docs_diff_v5/       # v5: LLM統合版（最新・推奨）
│   │   ├── services/           # Azure OCR & LLMサービス
│   │   ├── handlers/           # 出力処理（単語レベルハイライト）
│   │   └── test_llm_diff_v5_with_llm.py  # LLM版実行スクリプト
│   ├── llm_docs_diff_v3/       # v3: 内容ベース差分検出版
│   │   ├── core/               # 差分検出コア（90%内容、10%位置）
│   │   ├── services/           # Azure階層構造抽出
│   │   └── test_llm_diff_v3_with_llm.py  # 実行スクリプト
│   └── diff_baseline/          # ベースライン実装
│       ├── core/               # 基本差分検出
│       └── test_baseline.py    # 実行スクリプト
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
docker compose run --rm pdf-diff-v5-llm
```

#### v3 内容ベース版
```bash
docker compose run --rm pdf-diff-v3-llm
```

#### baseline版
```bash
docker compose run --rm pdf-diff-baseline
```

#### 開発用対話環境
```bash
docker compose run --rm pdf-diff-dev
```

#### Jupyter Lab環境
```bash
docker compose up pdf-diff-jupyter
# ブラウザで http://localhost:8888 にアクセス
```

### コマンドラインオプション

#### 共通オプション
- `--dataset`: 使用するデータセット
  - `dantai`: 団体保険データセット（v5, v3のデフォルト）
  - `sample1`: サンプル①（保険募集資料）
  - `sample2`: サンプル②（総合保険）
  - `sample3`: サンプル③
  - `sample4`: サンプル④（アノテーション付き）
  - `sample5`: サンプル⑤（アノテーション付き）
  - `default`: デフォルトテストデータ（baselineのデフォルト）

#### v5 LLM版オプション
- `--use-llm`: LLMで差分を分析（デフォルト: True）
- `--llm-summary`: LLMで要約を生成（デフォルト: True）
- `--analyze-each`: 各差分を個別にLLMで分析

#### v3 内容ベース版オプション
- `--use-llm-summary`: LLMで差分を要約（オプション）

#### baseline版オプション
- データセット選択のみ（追加オプションなし）

## 📊 出力ファイル

処理結果は`output/`ディレクトリに保存されます：

```
output/
├── llm_diff_test_v5_llm/         # v5 LLM版の結果
│   └── [dataset]/
│       ├── [pdf1]_highlighted.pdf   # 文書1のハイライト版
│       ├── [pdf2]_highlighted.pdf   # 文書2のハイライト版
│       ├── [pdf1]_vs_[pdf2]_highlighted.pdf  # 並列表示版
│       ├── differences.json      # 差分詳細
│       ├── summary.json          # 差分サマリー
│       ├── llm_analysis_result.json  # LLM分析結果
│       └── evaluation_document.md    # 評価用ドキュメント
├── llm_diff_test_v3_llm/         # v3 内容ベース版の結果
│   └── [dataset]/
│       ├── PDFs/                  # 各種PDF出力
│       ├── reports/               # レポート類
│       └── debug/                 # デバッグ情報
└── baseline_test/                # baseline版の結果
    └── [dataset]/
        ├── PDFs/                  # ハイライト付きPDF
        ├── reports/               # 差分レポート
        └── debug/                 # 読み順序CSV等
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

### 処理時間の目安（Azure有料版使用時）
#### 44ページのPDF（sample1データセット）の場合：
- v5 LLM版: 約2-3分（LLM分析含む）
- v3 内容ベース版: 約1-2分
- baseline版: 約40秒

### メモリ使用量
- 通常: 500MB-1GB
- 大きなPDF（100ページ以上）: 2-3GB程度

### 推奨用途
- **v5 LLM版**: 重要文書の詳細な差分分析、変更理由の把握が必要な場合
- **v3 内容ベース版**: 日常的な文書比較、高速処理が必要な場合
- **baseline版**: シンプルな差分検出、大量文書の一括処理

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
