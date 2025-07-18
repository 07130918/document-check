# LLM Diff Test v1とv2の比較

## 概要

本文書では、LLM Diff Testのv1とv2の違いを詳細に比較し、v2での改善点と新機能について説明します。

**注**: v3については別文書 [v3_technical_specification.md](./v3_technical_specification.md) および [v1_v2_v3_comparison.md](./v1_v2_v3_comparison.md) を参照してください。

## 主要な違いの要約

| 項目 | v1 | v2 | 改善率 |
|------|----|----|--------|
| 変更検出数 | 0件 | 245件 | ∞ |
| 処理要素数 | 10,711 | 8,248 | 23%削減 |
| 処理時間 | 40-50秒 | 10-15秒 | 約70%短縮 |
| メモリ使用量 | 高 | 低 | 約25%削減 |
| 検出精度 | 低 | 高 | 大幅向上 |

## アーキテクチャの比較

### v1のアーキテクチャ
```
Azure Document Intelligence
    ↓
DocumentAnalyzer
    ↓
DiffDetector（基本版）
    ↓
OutputHandler
```

### v2のアーキテクチャ
```
PDFProcessor（PyMuPDF）
    ↓
TextPreprocessor（前処理）
    ↓
ReadingOrderEstimator（順序推定）
    ↓
EnhancedDiffDetector（改良版）
    ↓
OutputHandler（拡張版）
    ↓
ModificationAnalyzer（変更分析）
```

## 機能比較

### 1. テキスト抽出

#### v1: Azure Document Intelligence
- **利点**
  - 高精度OCR
  - レイアウト情報の保持
  - 表構造の認識

- **欠点**
  - APIコスト発生
  - 処理速度の制約
  - 文字単位抽出によるノイズ
  - 前処理なし

#### v2: PyMuPDF + 前処理
- **利点**
  - 高速処理
  - コスト削減（ローカル処理）
  - 前処理による要素数削減（23%）
  - ノイズ除去

- **改善内容**
  ```python
  # Unicode正規化
  # 全角→半角変換
  # 空白正規化
  # 分割文字の結合
  # ヘッダー・フッター除去
  ```

### 2. 読み取り順序

#### v1: LLM依存
- LLMによる順序推定を試行
- JSONパースエラーが頻発
- フォールバックで元の順序を使用

#### v2: 座標ベースアルゴリズム
- 決定的アルゴリズム
- エラーなし
- 人間の読み方に近い順序

### 3. 差分検出

#### v1: 基本的なマッチング
```python
# 単純なテキスト比較
# 位置情報を考慮しない
# 変更検出がほぼ機能しない
```

**結果**: 削除122件、追加113件、変更0件

#### v2: 高度なマッチング
```python
# 位置ベースマッチング（100px閾値）
# 類似度計算（0.7閾値）
# 3種類の変更タイプを正確に識別
```

**結果**: 削除2,538件、追加2,461件、変更245件

### 4. 出力形式

#### v1の出力
```
llm_diff_test_v1/
├── PDFs/（基本的な差分PDF）
├── reports/（簡易レポート）
└── azure/（Azure抽出結果）
```

#### v2の出力
```
llm_diff_test_v2/
├── PDFs/（5種類の高度なPDF）
├── reports/（詳細な分析レポート）
└── debug/（デバッグ情報）
```

## 新機能（v2のみ）

### 1. 変更タイプの自動分類
```json
{
  "date_changes": 2,      // 日付の変更
  "amount_changes": 20,   // 金額の変更
  "url_changes": 2,       // URLの変更
  "year_changes": 7,      // 年度の変更
  "other_changes": 214    // その他の変更
}
```

### 2. 前処理統計
```json
{
  "preprocessing": {
    "doc1": {
      "before": 10711,
      "after": 8248,
      "reduction_rate": "23.0%"
    }
  }
}
```

### 3. 詳細な変更例
```json
{
  "before": "令和 5 年度",
  "after": "令和 6 年度",
  "similarity": 0.857,
  "page": 0
}
```

## パフォーマンス比較

### 処理時間の内訳

| 処理段階 | v1 | v2 |
|----------|----|----|
| テキスト抽出 | 20-30秒 | 2-3秒 |
| 前処理 | なし | 0.5秒 |
| 順序推定 | 5-10秒 | 0.5秒 |
| 差分検出 | 5秒 | 1-2秒 |
| レポート生成 | 10秒 | 5秒 |
| **合計** | **40-50秒** | **10-15秒** |

### リソース使用量

| リソース | v1 | v2 | 削減率 |
|----------|----|----|--------|
| メモリ | 約500MB | 約375MB | 25% |
| CPU使用率 | 低（API待機） | 中（ローカル処理） | - |
| ネットワーク | 高（API通信） | なし | 100% |

## 実装の違い

### v1の実装例
```python
# Azure API使用
analyzer = DocumentAnalyzer()
result = analyzer.analyze_documents(file1, file2)
```

### v2の実装例
```python
# ローカル処理 + 前処理
pdf_processor = PDFProcessor()
bbox_list = pdf_processor.extract_bbox_data(pdf_bytes, preprocess=True)

# 読み取り順序推定
order_estimator = ReadingOrderEstimator()
ordered_list = order_estimator.estimate_reading_order(bbox_list)

# 高度な差分検出
diff_detector = EnhancedDiffDetector()
diff_results = diff_detector.detect_differences(ordered_list1, ordered_list2)
```

## 移行ガイド

### v1からv2への移行時の注意点

1. **API依存の解消**
   - Azure APIキーが不要に
   - ローカル処理への移行

2. **出力ディレクトリの変更**
   - v1: `output/llm_diff_test_v1/`
   - v2: `output/llm_diff_test_v2/`

3. **新機能の活用**
   - 前処理による効率化
   - 詳細な変更分析の利用

## 推奨使用場面

### v1を使用すべき場合
- Azure OCRの高精度が必要
- スキャンPDFの処理
- APIコストが問題でない
- 変更検出が不要（追加・削除のみ）

### v2を使用すべき場合
- 高速処理が必要
- 変更検出が重要
- コスト削減が必要
- 詳細な分析が必要
- 大量のPDF処理

## まとめ

v2は、v1の基本機能を維持しながら、以下の点で大幅な改善を実現：

1. **性能向上**: 処理速度3倍、メモリ使用量25%削減
2. **精度向上**: 245件の変更検出（v1: 0件）
3. **効率化**: 23%の要素削減による処理効率向上
4. **新機能**: 詳細な変更分析、前処理システム
5. **コスト削減**: API不要でローカル処理

これらの改善により、v2は企業文書の差分管理において、より実用的で効率的なソリューションとなっています。