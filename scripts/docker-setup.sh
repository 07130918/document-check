#!/bin/bash
# Docker環境セットアップスクリプト

set -e

echo "=== PDF差分検出システム Docker環境セットアップ ==="

# .envファイルの確認
if [ ! -f .env ]; then
    echo "警告: .envファイルが見つかりません"
    echo ".env.templateをコピーして.envファイルを作成してください:"
    echo "  cp .env.template .env"
    echo "そして、必要なAPIキーを設定してください"
    exit 1
fi

# 必要な環境変数の確認
required_vars=("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" "AZURE_DOCUMENT_INTELLIGENCE_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "エラー: 環境変数 $var が設定されていません"
        echo ".envファイルを確認してください"
        exit 1
    fi
done

# 出力ディレクトリの作成
echo "出力ディレクトリを作成中..."
mkdir -p output notebooks test-results

# Dockerイメージのビルド
echo "Dockerイメージをビルド中..."
docker compose build

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "使用可能なサービス:"
echo "  - pdf-diff-v5-llm    : v5 LLM版の実行"
echo "  - pdf-diff-v3-llm    : v3 LLM版の実行"
echo "  - pdf-diff-v5        : v5 標準版の実行"
echo "  - pdf-diff-dev       : 開発用対話環境"
echo "  - pdf-diff-jupyter   : Jupyter Lab環境"
echo "  - pdf-diff-test      : テスト実行"
echo ""
echo "実行例:"
echo "  docker compose run pdf-diff-v5-llm"
echo "  docker compose run pdf-diff-dev"
echo "  docker compose up pdf-diff-jupyter"