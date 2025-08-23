# コード修正履歴（整理版）

このファイルは、コード修正の履歴を機能別に整理したものです。

## Azure Document Intelligence関連の変更

### 1. High Resolution OCR機能の実装

#### 1.1 設定ファイルの更新

**対象ファイル**:
- `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_1/config/settings.py`
- `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_2/config/settings.py`

**変更内容**:
```python
# High Resolution OCR設定の追加
USE_HIGH_RESOLUTION_OCR: bool = os.getenv("USE_HIGH_RESOLUTION_OCR", "True").lower() == "true"

# APIバージョンの追加（High Resolution対応）
AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2024-02-29-preview")

# タイムアウト設定の延長
PROCESSING_TIMEOUT_SECONDS: int = int(os.getenv("PROCESSING_TIMEOUT_SECONDS", "600"))

# Azureログレベル設定
AZURE_LOG_LEVEL: str = os.getenv("AZURE_LOG_LEVEL", "WARNING")
```

#### 1.2 Azure Serviceの更新

**対象ファイル**:
- `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_1/services/azure_service.py`
- `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_1/services/azure_service_enhanced.py`

**High Resolution機能の有効化**:
```python
# High Resolution機能を有効化
features = []
if settings.USE_HIGH_RESOLUTION_OCR:
    features.append("ocr.highResolution")  # 修正前: "OCR_HIGH_RESOLUTION"
    logger.info("Azure Document Intelligence: High Resolution OCR enabled")

poller = self.client.begin_analyze_document(
    "prebuilt-layout",
    body=pdf_bytes,
    content_type="application/pdf",
    features=features if features else None,
    locale="ja-JP"
)

# タイムアウトを延長
result: AnalyzeResult = poller.result(timeout=300)  # 5分のタイムアウト
```

#### 1.3 ページ分割OCR機能（v3-2のみ）

**対象ファイル**: `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_2/services/azure_service_enhanced.py`

**extract_layout_from_lines_with_split メソッドの追加**:
```python
def extract_layout_from_lines_with_split(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """各ページを上下2分割してOCR精度を向上させる"""
    # 画像OCR用のモデルを使用
    poller = self.client.begin_analyze_document(
        "prebuilt-read",  # 画像用のモデル
        body=image_bytes,
        content_type="image/png",
        features=features if features else None,
        locale="ja-JP"
    )
```

### 2. Azureログ出力の制御

**対象ファイル**:
- `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_1/test_llm_diff_v3.py`
- `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_2/test_llm_diff_v3.py`

**ログ抑制の実装**:
```python
# Azureの詳細なHTTPログを無効化
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)
```

## 差分検出アルゴリズムの改善

### 1. ContentBasedDiffDetectorの実装

**対象ファイル**: `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_1/core/diff_detector_v3.py`

**主な変更点**:
- position_weight=0.0（100%内容ベース）の実装
- matched_itemsプロパティの追加
- 完全一致テキストの1対1マッチング実装

```python
def _match_identical_texts_by_position(self, items1, items2):
    """完全一致テキストを位置の近さで1対1マッチング"""
    # 距離マトリクスを計算
    # 貪欲法で最小距離のペアを選択
```

### 2. CSV出力の拡張

**対象ファイル**: `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_1/handlers/output_handler.py`

**変更内容**:
- MATCHED（完全一致）項目の出力
- ページ番号を前年・今年で分離
- CSVフォーマットの改善

```python
headers = ["番号", "変更タイプ", "前年ページ数", "今年ページ数", "元のテキスト", "変更後のテキスト", "類似度", "説明"]
```

## ページ分割機能（v3-2専用）

### 1. PageSplitterクラスの実装

**対象ファイル**: `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3_2/utils/page_splitter.py`

**実装内容**:
- 上下2分割への変更
- 10%の重複領域
- 座標変換機能

## コマンドラインインターフェースの改善

### 1. 引数の追加と変更

**v3-1, v3-2共通**:
- `--max-pages`: 処理ページ数制限
- `--use-high-resolution` / `--no-high-resolution`: High Resolution OCR制御
- ~~`--use-azure` / `--no-azure`~~ → 削除（常にAzure使用）

**v3-2専用**:
- `--use-page-split`: ページ分割OCR有効化

### 2. 出力ディレクトリの動的変更

**ディレクトリ構造**:
```
output/
├── llm_diff_test_v3-1_high_resolution/    # v3-1 High Resolution
├── llm_diff_test_v3-1_standard/           # v3-1 標準解像度
├── llm_diff_test_v3-2_high_resolution_split/  # v3-2 分割 + High Resolution
└── llm_diff_test_v3-2_standard_split/     # v3-2 分割 + 標準解像度
```

## 効果と改善点

### OCR精度の向上
- High Resolution OCR: 小さい文字の認識精度向上
- ページ分割: 複雑なレイアウトでの精度向上
- 1対1マッチング: 重複検出の精度向上

### 処理の効率化
- Azureログ抑制: 出力の見やすさ向上
- 上下2分割: API呼び出し数の削減（4回→2回）

### ユーザビリティの向上
- 柔軟なコマンドラインオプション
- 明確な出力ディレクトリ構造
- 詳細なCSV出力（MATCHED含む）
