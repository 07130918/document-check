# LLM Diff Test 設計ドキュメント

## 概要

LLM Diff Testは、PDF文書の差分を検出するシステムです。3つのバージョンがあり、それぞれ異なるアプローチと特徴を持っています。

## バージョン一覧

### [v1: 基本実装](./v1_technical_specification.md)
- Azure Document Intelligenceを使用した基本的な差分検出
- 高精度OCRによる文字認識
- 変更検出は未実装（削除・追加のみ）

### [v2: 高速・効率化版](./v2_technical_specification.md)
- PyMuPDFによるローカル処理
- テキスト前処理による効率化
- 位置ベースの高度な差分検出

### [v3: 内容ベース版](./v3_technical_specification.md)
- 位置に依存しない内容ベースの差分検出
- テキストの移動を正しく認識
- side-by-side比較PDFの生成

## 比較ドキュメント

- [v1とv2の比較](./v1_v2_comparison.md) - v1からv2への改善点
- [v1, v2, v3の完全比較](./v1_v2_v3_comparison.md) - 3バージョンの包括的な比較

## クイックリファレンス

### 選択ガイド

| 要件 | 推奨バージョン | 理由 |
|-----|--------------|------|
| 高速処理 | v2 | ローカル処理で10-15秒 |
| 高精度（移動認識） | v3 | 内容ベース検出 |
| 低コスト | v2 | API不要 |
| Azure Free Tier | v3 | バッチ処理対応 |
| シンプルな実装 | v1 | 基本機能のみ |

### 主要指標比較

| 指標 | v1 | v2 | v3 |
|------|----|----|-----|
| 処理時間 | 40-50秒 | 10-15秒 | 40-50秒 |
| 変更検出 | 0件 | 16件 | 53件 |
| 偽陽性 | 高 | 中 | 低 |
| APIコスト | 高 | なし | 中 |

## ディレクトリ構造

```
LLM_doc_diff/
├── README.md                    # このファイル
├── v1_technical_specification.md # v1技術仕様
├── v2_technical_specification.md # v2技術仕様
├── v3_technical_specification.md # v3技術仕様
├── v1_v2_comparison.md          # v1とv2の比較
├── v1_v2_v3_comparison.md       # 全バージョン比較
├── design.md                    # 初期設計
├── task.md                      # タスク管理
└── technical_design.md          # 技術設計
```

## 実装場所

- v1: `/root/AICE/prj-ms-document-check/apps/llm_docs_diff/`
- v2: `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v2/`
- v3: `/root/AICE/prj-ms-document-check/apps/llm_docs_diff_v3/`

## 今後の展望

- v4: v3の精度とv2の速度を組み合わせたハイブリッド版
- クラウド版: Web APIとしての提供
- 多言語対応: 英語・中国語への拡張

## 更新履歴

- 2024/07/18: v3実装完了、ドキュメント作成
- 2024/07/XX: v2実装、高速化達成
- 2024/07/XX: v1初期実装