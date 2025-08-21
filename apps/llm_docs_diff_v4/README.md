# LLM Document Difference Detection v4

## 概要

v4は、v3から以下の点で改良されたバージョンです：

## v3からの主な変更点

### 1. ブロック抽出の改善
- **LLMBlockExtractorSimple**: Azure OCRのレイアウト情報を直接使用してブロックを抽出
- v3のような複雑なブロック統合処理を廃止し、シンプルで高速な実装に変更
- Azure OCRが認識したparagraphやtableをそのままブロックとして使用

### 2. 座標系の統一
- Azure OCRの座標系（インチ単位）からPDF座標系（ポイント単位）への変換を実装
- 1インチ = 72ポイントの変換係数を使用
- すべての座標計算で一貫した変換を適用

### 3. ブロックマッチングの改善
- **BlockMatcher**: より精度の高いブロックマッチングアルゴリズムを実装
- 位置の類似度（IoU）とテキストの類似度の両方を考慮
- 閾値ベースの柔軟なマッチング（position_threshold=0.5, text_threshold=0.8）

### 4. 差分検出の精緻化
- **DifferenceDetector**: ブロックレベルでの差分検出を改善
- added（追加）、deleted（削除）、modified（変更）の3種類の差分タイプを正確に識別
- 単語レベルの差分検出機能を追加（difflib.SequenceMatcher使用）

### 5. 出力の改善
- **OutputHandler**: より詳細な差分可視化を実装
- ブロック境界の可視化（ブロックタイプごとに色分け）
- 差分のハイライト表示（赤枠で差分箇所を強調）
- 並列PDF表示（2つのPDFを左右に並べて比較）

### 6. パフォーマンスの向上
- ブロック抽出処理の簡素化により処理速度が向上
- メモリ使用量の削減

## アーキテクチャ

```
llm_docs_diff_v4/
├── models/
│   ├── document.py        # ドキュメント構造のデータモデル
│   └── difference.py      # 差分情報のデータモデル
├── services/
│   ├── ocr_service.py     # Azure OCR連携
│   ├── llm_block_extractor_simple.py  # シンプルなブロック抽出
│   ├── block_matcher.py   # ブロックマッチング
│   └── difference_detector.py  # 差分検出
├── handlers/
│   └── output_handler.py  # 出力処理（PDF生成）
└── test_llm_diff_v4.py    # メインスクリプト
```

## 主な特徴

1. **シンプルな実装**: v3の複雑なブロック統合ロジックを廃止し、Azure OCRの結果を直接活用
2. **高精度な座標変換**: インチからポイントへの正確な座標変換
3. **柔軟な差分検出**: 位置とテキストの両方を考慮したマッチング
4. **視覚的な出力**: ブロック境界と差分箇所の可視化

## 使用方法

```bash
poetry run python apps/llm_docs_diff_v4/test_llm_diff_v4.py --dataset <dataset_name>
```

## 制限事項

- Azure OCRの処理は最初の5ページまでに制限
- PDFからテキスト位置情報を取得するためにPyMuPDFを使用（座標系の不一致の原因）