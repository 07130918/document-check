# LLM Document Difference Detection v5

## 概要

v5は、v4からさらに改良を加えた最新バージョンです。主な改良点は、Azure OCRの単語レベル情報を直接活用することで、より精密な差分検出を実現したことです。

## v4からの主な変更点

### 1. 単語レベルの差分検出
- **OutputHandlerV2**: Azure OCRが提供する単語（word）レベルの位置情報を直接使用
- PyMuPDFへの依存を完全に排除し、座標系の不一致問題を根本的に解決
- 単語単位での精密なハイライト表示

### 2. Azure OCR情報の完全活用
- Azure OCRのAnalyzeResult全体をハンドラーに渡す新しいアーキテクチャ
- 単語ごとのポリゴン座標（8点）を使用した正確な位置特定
- ブロック内の単語情報を直接参照可能

### 3. 差分表示の統一
- ユーザーのフィードバックに基づき、削除・追加・修正の区別を廃止
- すべての差分を同じ方法（赤枠）で表示
- よりシンプルで直感的な差分表示

### 4. 出力ページの最適化
- 差分があるページの最大値を自動検出
- 必要なページのみを出力PDFに含める（ファイルサイズの削減）
- 差分がない場合は1ページ目のみ出力

### 5. 座標変換の完全性
- Azure OCRのインチ単位座標をポイント単位に正確に変換（×72）
- ブロックと単語の両方で一貫した座標変換
- 座標系の不一致によるハイライト位置のずれを完全に解消

## アーキテクチャ

```
llm_docs_diff_v5/
├── models/
│   ├── document.py        # ドキュメント構造のデータモデル
│   └── difference.py      # 差分情報のデータモデル
├── services/
│   ├── ocr_service.py     # Azure OCR連携
│   ├── llm_block_extractor_simple.py  # ブロック抽出（Azure結果保持）
│   ├── block_matcher.py   # ブロックマッチング
│   └── difference_detector.py  # 差分検出
├── handlers/
│   ├── output_handler.py  # 従来の出力処理（v4互換）
│   └── output_handler_v2.py  # 新しい単語レベル出力処理
└── test_llm_diff_v5.py    # メインスクリプト
```

## 主な特徴

1. **単語レベルの精密性**: Azure OCRの単語情報を直接使用した高精度な差分表示
2. **座標系の統一**: PyMuPDFを排除し、Azure OCRの座標系のみを使用
3. **シンプルな差分表示**: すべての変更を同一の方法で表示
4. **効率的な出力**: 必要なページのみを含むPDF生成

## 技術的な改善点

### Azure OCR結果の受け渡し
```python
# LLMBlockExtractorSimpleでAzure結果を保持
self.azure_result = result

# テストスクリプトからハンドラーに渡す
if hasattr(self.output_handler, 'set_azure_result'):
    self.output_handler.set_azure_result(pdf_path, self.llm_block_extractor.azure_result)
```

### 単語レベルのハイライト
```python
# Azure OCRの単語情報を使用
for word in azure_page.words:
    if self._is_word_in_block(word, block):
        # 単語のポリゴン座標を使用してハイライト
        x = polygon[0] * 72  # インチからポイントへ変換
        y = polygon[1] * 72
```

## 使用方法

```bash
poetry run python apps/llm_docs_diff_v5/test_llm_diff_v5.py --dataset <dataset_name>
```

## v4との互換性

- OutputHandlerV2はオプトイン方式で有効化
- 従来のOutputHandlerも引き続き利用可能
- `--use-v2-handler`フラグで新しいハンドラーを使用（デフォルトで有効）

## パフォーマンス改善

- PyMuPDFの処理を削除したことで、全体的な処理速度が向上
- 必要なページのみ出力することで、大きなPDFでもメモリ効率が改善

## 今後の拡張可能性

- 文字レベルの差分検出
- 差分の種類に応じた色分け（オプション）
- より高度な差分分析（意味的な差分検出など）