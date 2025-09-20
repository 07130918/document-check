.PHONY: help build up down shell api diff logs clean

help:
	@echo "使用可能なコマンド:"
	@echo "  build   - Dockerイメージをビルド"
	@echo "  up      - FastAPI開発サーバーを起動"
	@echo "  up-d    - FastAPI開発サーバーをバックグラウンドで起動"
	@echo "  bash     - 実行中のAPIコンテナに入る"
	@echo "  down    - サービスを停止"
	@echo "  logs    - ログを表示"
	@echo "  clean   - コンテナとボリュームを削除"
	@echo "  health-check - ヘルスチェック"

build:
	docker compose build

up:
	docker compose up

up-d:
	docker compose up -d

bash:
	docker compose exec api /bin/bash

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	rm -rf apps/__pycache__ apps/**/__pycache__ apps/**/**/__pycache__

health-check:
	curl http://localhost:8000/api/health
