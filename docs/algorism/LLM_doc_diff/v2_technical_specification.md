# LLM Diff Test v2 技術仕様書

## 概要

LLM Diff Test v2は、Azure Document Intelligenceを活用し、v1の課題を解決した高精度な差分検出システムです。テキスト前処理、読み取り順序の自動推定、改良された差分検出アルゴリズムを搭載しています。

## システムアーキテクチャ

### 主要コンポーネント

1. **AzureDocumentService**
   - Azure Document Intelligenceとの連携
   - 高精度な文字単位OCR
   - レイアウト情報の保持

2. **TextPreprocessor** (新規)
   - Unicode正規化とテキストクレンジング
   - 分割文字の結合
   - ノイズ除去機能

3. **ReadingOrderEstimator** (新規)
   - 座標ベースの読み取り順序推定
   - ページ単位の最適化

4. **EnhancedDiffDetector** (改良)
   - 位置と類似度を考慮した高度な検出
   - 3種類の変更タイプを正確に識別

## 技術的特徴

### 1. Azure Document Intelligenceによる抽出

```python
# 高精度OCRによる文字単位抽出
azure_bbox_data_list = azure_service.extract_layout_from_pdf(pdf_bytes)
# 例：1390文字を抽出

# 日本語文字の意味的グループ化
grouped_words = group_japanese_characters_to_words(azure_bbox_data_list)
# 例：1390文字 → 396単語にグループ化
```

#### グループ化の効果
- **文字単位 → 単語単位**: 処理単位の最適化
- **意味的な結合**: 「令」「和」「5」「年」→「令和5年」
- **処理効率向上**: 要素数を約70%削減

### 2. テキスト前処理システム

```python
class TextPreprocessor:
    def preprocess_bbox_list(self, bbox_list):
        # 1. Unicode正規化（NFKC）
        # 2. 全角→半角変換
        # 3. 空白正規化
        # 4. 分割文字の結合
        # 5. ノイズ除去
```

#### 前処理の効果
- **追加削減**: 396単語 → 324単語（18.2%削減）
- **総合効果**: 1390文字 → 324要素（76.7%削減）
- **精度向上**: ノイズ除去による誤検出の減少

### 3. 読み取り順序推定

```python
class ReadingOrderEstimator:
    def estimate_reading_order(self, bbox_list):
        # 座標ベースの決定的アルゴリズム
        # LLM依存を完全に排除
```

#### v1との違い
- **v1**: LLMによる推定（失敗率高）
- **v2**: 座標ベースの確実な推定

### 4. 改良された差分検出

```python
class EnhancedDiffDetector:
    # 位置閾値: 100ピクセル
    # 類似度閾値: 0.7
```

#### 検出結果の比較

| 項目 | v1 | v2 |
|------|----|----|
| 削除 | 122件 | 162件 |
| 追加 | 113件 | 175件 |
| 変更 | 0件 | 8件 |
| 合計 | 235件 | 345件 |

### 5. Azure出力の詳細

#### 抽出プロセス
1. **Azure OCR**: 文字単位で高精度抽出
2. **日本語グループ化**: 意味的な単語に結合
3. **前処理**: ノイズ除去と正規化
4. **最終出力**: 最適化された要素リスト

#### 出力例（2023.pdf）
```json
{
  "character_count": 1390,      // Azure OCRで抽出した文字数
  "word_count": 396,            // グループ化後の単語数
  "preprocessed_count": 324,    // 前処理後の要素数
  "reduction_rate": "18.2%",    // 前処理による削減率
  "samples": [
    {
      "text": "令和5年度",
      "bbox": [241.2, 172.8, 100.8, 21.6],
      "page": 0
    }
  ]
}
```

## 出力構造

```
/root/AICE/prj-ms-document-check/output/llm_diff_test_v2/
├── PDFs/
│   ├── 2023_compared.pdf          # 差分ハイライト
│   ├── 2024_compared.pdf          # 差分ハイライト
│   ├── 2023_reading_order.pdf     # 読み取り順序表示
│   └── 2024_reading_order.pdf     # 読み取り順序表示
├── reports/
│   ├── v2_modification_analysis.json  # 詳細変更分析
│   ├── v2_statistics.json            # v2統計情報
│   └── execution_report.md           # 実行レポート
├── azure/
│   ├── 2023_azure_extraction.json    # Azure抽出詳細
│   └── 2024_azure_extraction.json    # Azure抽出詳細
└── debug/
    └── llm_diff_test_v2/
        ├── diff_results.json         # 差分結果
        └── statistics.json           # 基本統計
```

## パフォーマンス特性

### 処理フロー
1. **Azure抽出**: 10-15秒（API呼び出し）
2. **グループ化**: 0.5秒（ローカル処理）
3. **前処理**: 0.5秒（ローカル処理）
4. **順序推定**: 0.5秒（ローカル処理）
5. **差分検出**: 1-2秒（ローカル処理）
6. **合計**: 約15-20秒

### リソース効率
- **要素数削減**: 1390 → 324（76.7%削減）
- **メモリ使用**: 大幅削減
- **処理速度**: v1比で改善

## v2の特徴的な機能

### 1. 3段階の最適化
```
Azure OCR（1390文字）
    ↓ グループ化（71.5%削減）
396単語
    ↓ 前処理（18.2%削減）
324要素（最終）
```

### 2. 変更分析の実例
```json
{
  "change_types": {
    "year_changes": {
      "count": 1,
      "examples": [{
        "before": "令和 5 年度",
        "after": "令和 6 年度",
        "similarity": 0.857
      }]
    },
    "amount_changes": {
      "count": 1,
      "examples": [{
        "before": "社員約 1.8 万人が",
        "after": "社員約 1.6 万人が",
        "similarity": 0.944
      }]
    }
  }
}
```

### 3. Azure統合の利点
- **高精度**: 文字認識率99%以上
- **レイアウト保持**: 正確な位置情報
- **日本語対応**: 完全な日本語サポート
- **表構造認識**: 複雑なレイアウト対応

## v1からの改善点まとめ

1. **変更検出の実現**: 0件 → 8件
2. **処理効率**: 76.7%の要素削減
3. **確実な順序推定**: LLM依存を排除
4. **詳細な分析**: 変更タイプの自動分類
5. **Azure最適化**: グループ化による効率化

## 技術的な実装詳細

### パラメータ設定

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| 文字間閾値 | 文字幅×0.3 | グループ化の距離 |
| 位置閾値 | 100px | 同一要素判定 |
| 類似度閾値 | 0.7 | 変更判定 |
| ハイライト透明度 | 0.3 | 可読性最適値 |

## まとめ

v2はAzure Document Intelligenceの高精度OCRを活用しつつ、以下の改善により実用的なシステムを実現：

1. **日本語グループ化**による処理単位の最適化
2. **前処理**によるノイズ除去と効率化
3. **座標ベース順序推定**による確実性
4. **高度な差分検出**による変更の正確な把握
5. **詳細な分析機能**による理解しやすい結果

これにより、企業文書の差分管理において高精度かつ効率的なソリューションを提供します。