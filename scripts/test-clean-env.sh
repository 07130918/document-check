#!/bin/bash
# クリーンな環境でのテストスクリプト

set -e

echo "=== クリーン環境テスト開始 ==="

# 1. 一時的な作業ディレクトリを作成
TEMP_DIR=$(mktemp -d)
echo "作業ディレクトリ: $TEMP_DIR"

# 2. 必要なファイルのみをコピー
echo "必要なファイルをコピー中..."
cp -r apps $TEMP_DIR/
cp -r data $TEMP_DIR/
cp -r docs $TEMP_DIR/
cp pyproject.toml $TEMP_DIR/
cp poetry.lock $TEMP_DIR/
cp Dockerfile $TEMP_DIR/
cp docker-compose.yml $TEMP_DIR/
cp .dockerignore $TEMP_DIR/
cp -r scripts $TEMP_DIR/
cp README.md $TEMP_DIR/

# .env.templateをコピー
if [ -f .env.template ]; then
    cp .env.template $TEMP_DIR/
else
    # .env.templateを作成
    cat > $TEMP_DIR/.env.template << 'EOF'
# Azure Document Intelligence設定
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=
AZURE_DOCUMENT_INTELLIGENCE_KEY=

# OpenAI API設定
OPENAI_API_KEY=

# その他の設定
LOG_LEVEL=INFO
DEBUG=False
EOF
fi

# 3. 環境変数をコピー（存在する場合）
if [ -f .env ]; then
    cp .env $TEMP_DIR/
    echo "既存の.envファイルをコピーしました"
else
    echo "警告: .envファイルが見つかりません"
    echo "テスト前に $TEMP_DIR/.env を作成してAPIキーを設定してください"
fi

# 4. 作業ディレクトリに移動
cd $TEMP_DIR

# 5. 出力ディレクトリを作成
mkdir -p output notebooks test-results

# 6. Dockerイメージをクリーンビルド
echo "Dockerイメージをクリーンビルド中..."
docker compose build --no-cache pdf-diff-v5

echo ""
echo "=== クリーン環境の準備完了 ==="
echo ""
echo "テスト環境: $TEMP_DIR"
echo ""
echo "次のステップ:"
echo "1. cd $TEMP_DIR"
echo "2. .envファイルを確認・編集"
echo "3. docker compose run pdf-diff-v5"
echo ""
echo "クリーンアップ:"
echo "rm -rf $TEMP_DIR"