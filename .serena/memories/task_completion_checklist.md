# タスク完了時のチェックリスト

## 必須実行項目

### 1. コードフォーマット
```bash
poetry run black apps/
poetry run isort apps/
```

### 2. 型チェック
```bash
poetry run mypy apps/
```

### 3. リント
```bash
poetry run flake8 apps/
```

### 4. テスト実行
```bash
# 関連するテストを実行
poetry run pytest tests/ -v

# 該当アプリのテスト実行
poetry run python apps/<app_name>/test_*.py
```

### 5. 出力確認
- 生成されたPDFファイルの確認
- CSVレポートの妥当性確認
- ログファイルのエラーチェック

### 6. Git確認
```bash
# 変更内容確認
git status
git diff

# 不要なファイルが含まれていないか確認
# （.envファイル、一時ファイル、出力ファイルなど）
```

## 推奨事項
- コミットメッセージは日本語で記述
- PRを作成する際は以下を含める：
  - 変更内容の概要
  - テスト結果
  - 関連するタスク番号
- ドキュメントの更新が必要な場合は同時に実施