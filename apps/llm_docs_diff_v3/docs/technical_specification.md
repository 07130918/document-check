# llm_docs_diff_v3 技術仕様書

## 1. システム概要

llm_docs_diff_v3は、PDF文書間の差分を検出するシステムです。Azure Document Intelligenceを使用してPDFから高精度なテキスト抽出を行い、位置ベースの差分検出アルゴリズムにより、文書の変更点を特定します。

### 主な特徴

- **位置非依存の内容ベース差分検出**: テキストの移動を正しく認識し、真の追加・削除・変更のみを検出
- **高精度な日本語文書処理**: 日本語特有の文字処理とOCR誤認識修正
- **LLM統合（オプション）**: 読み順序推定と変更内容の要約生成
- **多様な出力形式**: JSON、CSV、PDF、Markdownでの結果出力

## 2. システムアーキテクチャ

### 2.1 ディレクトリ構造

```
llm_docs_diff_v3/
├── config/          # 設定管理
├── core/            # コアアルゴリズム
├── handlers/        # 出力処理
├── models/          # データモデル
├── services/        # 外部サービス連携
└── utils/           # ユーティリティ
```

### 2.2 主要コンポーネント

#### コアモジュール (core/)

1. **ContentBasedDiffDetector** (`diff_detector_v3.py`)
   - 位置非依存の内容ベース差分検出
   - テキストの移動認識
   - 類似度ベースのマッチング

2. **SimpleDiffDetectorV3** (`simple_diff_detector_v3.py`)
   - 簡易版差分検出器
   - すべての差分を単一タイプとして扱う
   - difflibベースの実装

3. **TextPreprocessor** (`text_preprocessing.py`)
   - Unicode正規化（NFC形式）
   - 全角・半角文字の統一
   - OCR誤認識の修正
   - 日本語テキストのスペース正規化

4. **ReadingOrderEstimatorV2** (`reading_order_v2.py`)
   - 読み順序の推定
   - 行内要素のグループ化
   - ページごとの処理

#### サービス層 (services/)

1. **AzureDocumentServiceEnhanced** (`azure_service_enhanced.py`)
   - Azure Document Intelligence統合
   - 階層的データ抽出（段落・行・単語）
   - バッチ処理による制限回避

2. **LLMService** (`llm_service.py`)
   - OpenAI API統合
   - 読み順序推定
   - 文書構造解析
   - 変更内容要約

## 3. 差分検出アルゴリズム

### 3.1 ContentBasedDiffDetectorの処理フロー

1. **完全一致テキストの検出**
   - 両文書で完全に一致するテキストをグループ化
   - 位置が大きく変化した場合は「移動」として記録

2. **類似度マトリクスの計算**
   - 残りのアイテムで類似度を計算
   - 複数の類似度計算手法を組み合わせ

3. **最適マッチングの決定**
   - 貪欲法による最適ペアの選択
   - 閾値（デフォルト0.8）以上のみマッチ

### 3.2 類似度計算の詳細

```python
# 類似度計算の優先順位
1. 完全一致: スコア 1.0
2. 80%以上の共通部分: スコア 0.95
3. 数字のみ異なる: スコア 0.85
4. 編集距離ベース: 0.0～1.0
5. 日本語n-gram類似度: 0.0～1.0
6. 共通キーワードボーナス: +0.1
```

### 3.3 移動検出の基準

```python
# 移動と判定される条件
if doc1_item['page'] != doc2_item['page']:
    # 異なるページにある場合
    is_movement = True
elif abs(doc1_item['bbox'][1] - doc2_item['bbox'][1]) > doc1_item['bbox'][3] * 3:
    # 同じページでもY座標の差が要素の高さの3倍以上
    is_movement = True
```

## 4. データモデル

### 4.1 BBoxTextData
```python
class BBoxTextData:
    bbox: List[float]  # [x, y, width, height]
    text: str         # 単語テキスト
    page: int         # ページ番号
    confidence: Optional[float]  # OCR信頼度
```

### 4.2 DiffResult
```python
class DiffResult:
    change_type: ChangeType  # ADDITION, DELETION, MODIFICATION
    original_bbox: Optional[BBoxTextData]
    modified_bbox: Optional[BBoxTextData]
    page: int
    confidence: float
    movement_info: Optional[Dict]  # 移動情報
```

## 5. 設定管理

### 5.1 環境変数
```bash
# Azure Document Intelligence
AZURE_DOCUMENT_KEY=<your_key>
AZURE_DOCUMENT_ENDPOINT=<your_endpoint>

# OpenAI (LLM統合時のみ)
OPENAI_API_KEY=<your_key>
```

### 5.2 処理パラメータ
```python
# 差分検出設定
SIMILARITY_THRESHOLD = 0.8  # 類似度閾値
POSITION_WEIGHT = 0.1      # 位置の重み
MAX_PAGES = 100           # 最大ページ数

# LLM設定
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 4000
LLM_TEMPERATURE = 0.1
```

## 6. 使用方法

### 6.1 基本的な使用（LLMなし）
```bash
python test_llm_diff_v3.py --pdf1 path/to/pdf1.pdf --pdf2 path/to/pdf2.pdf
```

### 6.2 LLM統合版の使用
```bash
python test_llm_diff_v3_with_llm.py \
    --pdf1 path/to/pdf1.pdf \
    --pdf2 path/to/pdf2.pdf \
    --use-llm-order \
    --use-llm-summary
```

### 6.3 データセットの使用
```bash
# 事前定義されたデータセットを使用
python test_llm_diff_v3.py --dataset dantai
```

## 7. 出力形式

### 7.1 ディレクトリ構造
```
output/llm_diff_test_v3/
├── reports/
│   ├── execution_report.json    # 実行結果
│   ├── execution_report.md      # Markdownレポート
│   └── reading_order.json       # 読み順序データ
├── PDFs/
│   ├── 2023_compared.pdf        # 差分ハイライト
│   ├── 2024_compared.pdf
│   └── side_by_side_comparison.pdf
└── *.csv                        # 差分一覧
```

### 7.2 CSV出力形式
```csv
ファイル名,種別,ページ,変更前,変更後,備考
report.pdf,追加,5,,新規追加テキスト,
report.pdf,削除,3,削除されたテキスト,,
report.pdf,変更,7,旧テキスト,新テキスト,
```

## 8. パフォーマンス考慮事項

### 8.1 メモリ使用量
- 大規模PDFの処理時は、ページごとのバッチ処理を実施
- 最大メモリ使用量: 約2GB（100ページのPDFの場合）

### 8.2 処理時間
- Azure API呼び出し: 1ページあたり約2-3秒
- 差分検出: 100ページで約10-20秒
- LLM処理: 追加で20-30秒

## 9. 制限事項

1. **Azure Document Intelligenceの制限**
   - 1リクエストあたり最大2ページ
   - バッチ処理で回避

2. **位置調整の非実装**
   - 移動検出後の相対位置調整は行われない
   - 各要素は独立して処理される

3. **メモリ制限**
   - 非常に大きなPDF（500ページ以上）では注意が必要

## 10. 今後の拡張可能性

1. **相対位置の追跡**
   - 移動したセクション後の要素の位置調整

2. **より高度な構造認識**
   - 表、図、リストなどの構造要素の認識

3. **マルチモーダル対応**
   - 画像や図表の差分検出

4. **WebAPI化**
   - RESTful APIとしての提供