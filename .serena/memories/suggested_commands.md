# 推奨コマンド一覧

## 開発環境セットアップ
```bash
# Poetry環境セットアップ
poetry install --with dev,test --extras "full"

# Poetry仮想環境に入る
poetry shell
```

## テスト実行
```bash
# ベースライン実装テスト
poetry run python apps/diff_baseline/test_baseline.py

# LLM実装テスト（各バージョン）
poetry run python apps/llm_docs_diff_v1/test_llm_diff_v1.py
poetry run python apps/llm_docs_diff_v2/test_llm_diff_v2.py
poetry run python apps/llm_docs_diff_v3/test_llm_diff_v3.py
poetry run python apps/llm_docs_diff_v4/test_llm_diff_v4.py
poetry run python apps/llm_docs_diff_v5/test_llm_diff_v5.py

# pytest実行
poetry run pytest
```

## コード品質チェック
```bash
# フォーマット
poetry run black apps/
poetry run isort apps/

# リント
poetry run flake8 apps/
poetry run mypy apps/

# すべてを実行
make format && make lint
```

## MeCab動作確認
```bash
poetry run python -c "import MeCab; print('MeCab動作確認OK')"
```

## Git操作
```bash
# ブランチ作成
git checkout -b feature/<task-name>

# 状態確認
git status
git diff

# コミット
git add .
git commit -m "コミットメッセージ"
```

## 出力確認
```bash
# 出力ディレクトリ確認
ls -la output/baseline_test/
ls -la output/llm_diff_test/
```