# コードスタイルと規約

## 全般的なルール
- **Pythonバージョン**: 3.11+
- **型ヒント**: 必須（mypy strict mode）
- **コメント言語**:
  - ドキュメンテーション（JSDoc, Docstring）: 英語
  - 実装説明のコメント: 日本語
  - 絵文字は使用しない

## コードフォーマット
- **フォーマッター**: Black（line-length: 88）
- **インポート整理**: isort（profile: black）
- **リンター**: flake8

## 命名規則
- **ファイル名**: snake_case（例: `diff_detector.py`）
- **クラス名**: PascalCase（例: `DocumentAnalyzer`）
- **関数/メソッド**: snake_case（例: `detect_differences`）
- **定数**: UPPER_SNAKE_CASE（例: `MAX_PAGE_SIZE`）

## ディレクトリ構造パターン
各アプリケーションは以下の構造を持つ：
```
app_name/
├── __init__.py
├── core/         # コアロジック
├── services/     # ビジネスロジック
├── handlers/     # I/O処理
├── models/       # データモデル
├── config/       # 設定
└── utils/        # ユーティリティ
```

## 型ヒント規約
- すべての関数に戻り値の型を明示
- 引数にも型ヒントを必須
- Optional, List, Dict, Tupleなどは typingから import
- TypeScriptでは`any`や`unknown`を使用しない

## エラーハンドリング
- カスタムエラークラスはErrorクラスを継承
- 適切な例外処理とログ出力