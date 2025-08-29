# PDF差分検出システム プロジェクト概要

## プロジェクトの目的
A/Bテスト用のベースライン実装とテスト基盤を提供するPDF差分検出システム。主に日本語文書（定款・報告書など）の差分を検出し、視覚的に比較可能な形で出力する。

## 技術スタック
- **言語**: Python 3.11+
- **パッケージ管理**: Poetry
- **主要ライブラリ**:
  - PyMuPDF: PDF解析・操作
  - python-Levenshtein: 文字列類似度計算
  - MeCab-python3: 日本語形態素解析
  - Azure Document Intelligence: OCR・文書解析
  - OpenAI API: LLMベースの文書解析
  - pandas, numpy: データ処理
  - scikit-learn: 機械学習
  - opencv-python: 画像処理

## プロジェクト構造
```
apps/
├── diff_baseline/         # ベースライン実装
├── llm_docs_diff_v1/     # LLMベース実装 v1
├── llm_docs_diff_v2/     # LLMベース実装 v2  
├── llm_docs_diff_v3/     # LLMベース実装 v3
├── llm_docs_diff_v4/     # LLMベース実装 v4
└── llm_docs_diff_v5/     # LLMベース実装 v5（ブロックベース）
```

## 各バージョンの特徴
- **baseline**: SequenceMatcherベースの基本実装
- **v1**: Azure Document Intelligence統合
- **v2**: 読み順序改善版
- **v3**: キャッシュ機能追加
- **v4**: ワードレベル・コンテンツベース解析
- **v5**: ブロックベース解析・画像処理対応