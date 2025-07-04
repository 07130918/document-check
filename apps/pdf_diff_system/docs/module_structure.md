# PDF差分検出システム モジュール構造

## 概要
PDF差分検出システムは、読み順序抽出と差分検出の2つの主要モジュールに分割されています。

## ディレクトリ構造

```
apps/pdf_diff_system/
├── app/
│   ├── modules/
│   │   ├── reading_order/       # 読み順序抽出モジュール
│   │   │   ├── pdf_text_extractor.py    # PDFテキスト抽出
│   │   │   └── reading_order_evaluator.py # 読み順序評価
│   │   │
│   │   └── diff_detection/      # 差分検出モジュール
│   │       ├── mecab_tokenizer.py        # 日本語トークナイザ
│   │       ├── text_normalizer.py        # テキスト正規化
│   │       └── phrase_based_diff_detector.py # フレーズベース差分検出
│   │
│   ├── domain/                  # ドメイン層（ビジネスロジック）
│   │   ├── interfaces/
│   │   ├── models/
│   │   └── services/
│   │
│   ├── infrastructure/          # インフラ層（外部連携）
│   │   └── evaluation/          # 評価関連
│   │       ├── annotation_loader.py      # アノテーション読み込み
│   │       └── comparison_evaluator.py   # 比較評価
│   │
│   └── application/             # アプリケーション層
│       └── services/
│           └── ab_test_service.py # A/Bテストサービス
│
├── baseline_evaluation.py       # 統合評価プログラム
├── run_annotation_test.py       # 差分検出テスト
└── evaluate_reading_order_with_annotation.py # 読み順序評価

```

## モジュール概要

### 1. 読み順序抽出モジュール (`modules/reading_order/`)
PDFから適切な読み順序でテキストを抽出する機能を提供します。

- **pdf_text_extractor.py**: PyMuPDFを使用してPDFからテキストを抽出
  - 全角半角正規化機能
  - ページ単位でのテキスト抽出
  - レイアウト情報の処理

- **reading_order_evaluator.py**: 読み順序の評価
  - アノテーションとの比較
  - スピアマン相関係数による評価
  - マッチング率の計算

### 2. 差分検出モジュール (`modules/diff_detection/`)
抽出されたテキストから意味的な差分を検出する機能を提供します。

- **mecab_tokenizer.py**: MeCabを使用した日本語形態素解析
  - 単語分割
  - 品詞情報の取得
  - トークン化処理

- **text_normalizer.py**: テキスト正規化処理
  - 文字正規化
  - 空白処理
  - 記号の統一

- **phrase_based_diff_detector.py**: フレーズベースの差分検出
  - 意味的まとまり単位での差分検出
  - 変更タイプの分類（追加/削除/変更）
  - 類似度計算

## データフロー

```
1. PDF入力
   ↓
2. 読み順序抽出モジュール
   - PDFからテキスト抽出
   - 読み順序の最適化
   - 全角半角正規化
   ↓
3. 差分検出モジュール
   - テキストのトークン化（MeCab）
   - テキスト正規化
   - フレーズ単位での差分検出
   ↓
4. 評価・レポート出力
```

## 利用方法

### 統合評価の実行
```bash
python baseline_evaluation.py
```

### 個別モジュールの利用
```python
# 読み順序抽出
from app.modules.reading_order.pdf_text_extractor import PDFTextExtractor
extractor = PDFTextExtractor()
pages_text = extractor.extract_pages_text(pdf_path)

# 差分検出
from app.modules.diff_detection.phrase_based_diff_detector import PhraseBasedDiffDetector
detector = PhraseBasedDiffDetector()
diffs = detector.detect_differences(text1, text2)
```

## 今後の拡張予定
- 読み順序抽出の高度化（レイアウト解析の改善）
- 差分検出アルゴリズムの改良
- 新しい評価指標の追加