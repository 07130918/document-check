# LLM Document Difference Detection v3

## 概要

v3は、Azure OCRの読み取り順序を活用した高精度な差分検出を実現するバージョンです。内容ベースの差分検出を提供します。

## 主な特徴

### 1. 高度な内容ベース差分検出 (ContentBasedDiffDetector)
- **重み配分**: テキスト内容90%、位置10%
- **類似度計算**:
  - 包含関係の検出（例：「継続できます」→「♡ 継続できます」）
  - 数字パターンの認識（例：「令和5年」→「令和6年」）
  - 編集距離ベースの類似度計算

### 2. 読み取り順序の活用
- Azure OCRが提供する`readingOrder`を使用して要素を正しい順序で並べ替え
- 文書の論理的な流れに沿った差分検出が可能

### 3. 精密なマッチングアルゴリズム
- 貪欲法による最適なペアリング
- 1対1のマッチングを保証（重複なし）
- 類似度閾値（80%）による柔軟な判定

## アーキテクチャ

```
llm_docs_diff_v3/
├── core/
│   ├── document_loader.py    # 文書読み込み
│   ├── diff_detector_v3.py   # 差分検出（ContentBasedDiffDetector）
│   └── llm_analyzer.py      # LLM解析
├── models/
│   └── bbox_models.py       # データモデル
├── handlers/
│   └── output_handler.py    # 出力処理
├── utils/
│   └── bbox_utils.py        # ユーティリティ
└── test_llm_diff_v3_with_llm.py  # メインスクリプト
```

## 処理フロー

1. **文書読み込み**: DocumentLoaderがPDFを読み込み、Azure OCRで解析
2. **読み取り順序での並べ替え**: readingOrderに基づいて要素を整列
3. **差分検出**: ContentBasedDiffDetectorが内容ベースで差分を検出
4. **LLM解析**: 差分の意味的な重要度を評価
5. **出力生成**: PDFとMarkdownレポートを生成

## 使用方法

```bash
# 基本的な使用方法
poetry run python apps/llm_docs_diff_v3/test_llm_diff_v3.py --dataset dantai

# 利用可能なデータセット
--dataset dantai    # 団体保険
--dataset sample1   # サンプル1
--dataset sample2   # サンプル2
--dataset sample3   # サンプル3
--dataset sample4   # サンプル4
--dataset sample5   # サンプル5
```

## ContentBasedDiffDetectorの仕組み

### 1. テキストグループ化
同一テキストをグループ化して効率的に処理：
```python
doc1_by_text = self._group_by_text(doc1_items)
doc2_by_text = self._group_by_text(doc2_items)
```

### 2. 完全一致の処理
完全に一致するテキストは差分なしとして処理済みにマーク

### 3. 類似度マトリクスの計算
残りのアイテムについて、テキスト類似度（90%）と位置類似度（10%）を組み合わせた総合類似度を計算

### 4. 最適マッチング
類似度の高い順にペアを作成し、1対1のマッチングを実現

### 5. 差分の分類
- マッチしたペア → MODIFICATION（変更）
- マッチしなかった文書1のアイテム → DELETION（削除）
- マッチしなかった文書2のアイテム → ADDITION（追加）

## テキスト類似度計算の詳細

### 類似度スコアの算出方法
1. **完全一致**: スコア 1.0
2. **包含関係**: 80%以上が共通ならスコア 0.95、それ以外は 0.9
3. **数字パターン**: 構造が同じで数字だけ違う場合はスコア 0.85
4. **編集距離ベース**: difflibによる基本的な類似度計算

## v2からの改善点

1. **位置依存の大幅削減**: 位置の重みを10%に削減
2. **読み取り順序の活用**: Azure OCRの読み取り順序を使用
3. **シンプルな実装**: 実用的な差分検出に集中

## 制限事項

- Azure OCRの処理は最初の3ページまでに制限（設定により変更可能）
- 大きなPDFファイルではメモリ使用量が増加する可能性あり