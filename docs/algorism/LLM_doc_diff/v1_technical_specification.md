# LLM Diff Test v1 技術仕様書

## 概要

LLM Diff Test v1は、Azure Document Intelligenceを活用したPDF文書の差分検出システムです。高精度なOCR機能と基本的な差分検出機能を提供します。

## システムアーキテクチャ

### 主要コンポーネント

1. **DocumentAnalyzer**
   - PDF文書の解析とレイアウト抽出
   - Azure Document Intelligenceとの連携
   - 差分検出の統合処理

2. **AzureDocumentIntelligenceService**
   - Azure APIとの通信
   - OCR処理とレイアウト解析
   - 文字単位での高精度抽出

3. **DiffDetector**
   - 基本的な差分検出アルゴリズム
   - 追加・削除の検出（変更検出は限定的）

4. **OutputHandler**
   - 結果の出力とレポート生成
   - ハイライト付きPDFの作成

## 技術的特徴

### 1. Azure Document Intelligence統合

```python
# Azure APIによる高精度OCR
result = document_intelligence_client.begin_analyze_document(
    "prebuilt-layout",
    analyze_request=pdf_bytes,
    content_type="application/octet-stream"
).result()
```

#### 利点
- 高精度な文字認識
- レイアウト情報の保持
- 表構造の認識

#### 制限事項
- APIコストが発生
- 処理速度の制約
- 文字単位での抽出によるノイズ

### 2. 日本語文字グループ化

```python
# 単一文字を意味のある単語にグループ化
def group_japanese_characters(words: List[DocumentWord]) -> List[DocumentWord]:
    # 連続する日本語文字を結合
    # ひらがな、カタカナ、漢字を認識
```

### 3. 差分検出アルゴリズム

#### 検出可能な変更タイプ
- **削除（deletion）**: 旧文書にのみ存在
- **追加（addition）**: 新文書にのみ存在
- **変更（modification）**: v1では検出精度が低い

#### アルゴリズムの流れ
1. 両文書の要素を抽出
2. 位置情報なしでテキストマッチング
3. マッチしない要素を差分として記録

### 4. LLM解析

```python
# GPT-4による文書解析
- 文書要約の生成
- 主要な変更点の特定
- リスク評価の実施
```

## 出力構造

```
/root/AICE/prj-ms-document-check/output/llm_diff_test_v1/
├── PDFs/
│   ├── 2023_compared.pdf          # 文書1の差分ハイライト
│   ├── 2024_compared.pdf          # 文書2の差分ハイライト
│   ├── 2023_reading_order.pdf     # 読み取り順序表示
│   └── 2024_reading_order.pdf     # 読み取り順序表示
├── reports/
│   ├── execution_report.json      # 実行レポート
│   ├── execution_report.md        # Markdown形式レポート
│   └── llm_diff_test_v1_differences.csv  # 差分CSV
├── azure/
│   ├── 2023_azure_extraction.json # Azure抽出結果
│   ├── 2024_azure_extraction.json # Azure抽出結果
│   └── extraction_comparison.json  # 抽出結果比較
└── debug/
    └── llm_diff_test_v1/
        ├── reading_order.json      # 読み取り順序情報
        └── sentence_info.json      # 文情報
```

## パフォーマンス特性

### 処理時間
- Azure API呼び出し: 約10-15秒/文書
- 差分検出: 約1-2秒
- 全体処理: 約40-50秒

### リソース使用
- メモリ: 中程度（要素数に依存）
- CPU: 低（主にAPI待機時間）

## 制限事項

1. **前処理の欠如**
   - ノイズの多い抽出結果
   - 文字単位の抽出による非効率性
   - 10,000要素以上の処理

2. **差分検出の精度**
   - 変更検出がほぼ機能しない（0件）
   - 位置変動への対応が不十分
   - 類似度計算の欠如

3. **読み取り順序**
   - LLMによる推定の失敗が多い
   - JSONパースエラーの発生
   - フォールバックが頻繁

## v1システムの統計（実行例）

```json
{
  "version": "v1",
  "statistics": {
    "total_differences": 235,
    "deletions": 122,
    "additions": 113,
    "modifications": 0
  }
}
```

## 使用例

```python
# v1システムの実行
analyzer = DocumentAnalyzer()
result, pdf1_bytes, pdf2_bytes = analyzer.analyze_documents(
    "2023.pdf", 
    "2024.pdf"
)

# 結果の保存
output_handler = OutputHandler()
output_handler.output_dir = V1_OUTPUT_DIR
saved_files = output_handler.save_comparison_result(
    result, 
    "llm_diff_test_v1", 
    pdf1_bytes, 
    pdf2_bytes
)
```

## まとめ

v1は基本的な差分検出機能を提供しますが、以下の課題があります：
- 前処理の欠如によるノイズ
- 変更検出の機能不全
- 処理効率の低さ

これらの課題はv2で改善されています。