# PDF差分検出システム - ベースライン実装 Makefile

.PHONY: help build run test clean dev shell

# デフォルトターゲット
help:
	@echo "Available commands:"
	@echo "  build     - Docker imageをビルド"
	@echo "  run       - ベースラインテストを実行"
	@echo "  dev       - 開発用コンテナを起動"
	@echo "  shell     - コンテナ内でシェルを起動"
	@echo "  test      - テストを実行"
	@echo "  clean     - Docker imageとvolumeを削除"
	@echo "  install   - Poetry依存関係をローカルにインストール"
	@echo "  format    - コードフォーマット実行"
	@echo "  lint      - コードリント実行"

# Docker image ビルド
build:
	docker-compose build pdf-diff-system

# ベースラインテスト実行
run:
	docker-compose run --rm pdf-diff-system

# 開発用コンテナ起動
dev:
	docker-compose run --rm pdf-diff-dev

# シェル起動
shell:
	docker-compose run --rm pdf-diff-dev /bin/bash

# テスト実行
test:
	docker-compose run --rm pdf-diff-test

# クリーンアップ
clean:
	docker-compose down --volumes --remove-orphans
	docker image rm $$(docker images -q pdf-diff-system*) 2>/dev/null || true
	docker volume prune -f

# ローカル環境構築（Poetry使用）
install:
	poetry install --with dev,test --extras "full"

# コードフォーマット
format:
	poetry run black baseline/ evaluation/ *.py
	poetry run isort baseline/ evaluation/ *.py

# コードリント
lint:
	poetry run flake8 baseline/ evaluation/ *.py
	poetry run mypy baseline/ evaluation/

# MeCabテスト（動作確認）
test-mecab:
	docker-compose run --rm pdf-diff-dev python -c "import MeCab; print('MeCab動作確認OK')"

# 依存関係更新
update:
	poetry update

# Phase 1以降用のターゲット（将来使用）
phase1:
	@echo "Phase 1: 改良アルゴリズム基盤構築（未実装）"

phase2:
	@echo "Phase 2: LLM読み順序推定 + MeCab差分検出（未実装）"

phase3:
	@echo "Phase 3: 並列処理最適化（未実装）"

phase4:
	@echo "Phase 4: 最終A/Bテスト（未実装）"

# 全テストケース実行
full-test:
	docker-compose run --rm pdf-diff-system python -c "
from evaluation import TestDataGenerator, ComparisonEvaluator
from baseline import SequenceMatcherDiffDetector
generator = TestDataGenerator()
cases = generator.generate_test_cases()
detector = SequenceMatcherDiffDetector()
evaluator = ComparisonEvaluator(detector)
result = evaluator.run_ab_test(cases)
print(f'全30ケーステスト完了: 真陽性率={result.baseline_metrics.recall:.3f}')
"