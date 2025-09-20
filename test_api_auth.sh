#!/bin/bash
#
# APIキー認証テストスクリプト
# 使用方法: ./test_api_auth.sh

set -e

# カラー出力（環境に応じて調整）
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    # Linux等
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
fi

# 設定
BASE_URL="${API_URL:-http://localhost:8000}"

# .envファイルからAPI_KEYを読み込み
if [ -f "apps/.env" ]; then
    export $(grep -E '^API_KEY=' apps/.env | xargs)
fi

# API_KEYが設定されていない場合はデフォルト値を使用
VALID_API_KEY="${API_KEY:-sk-dev-885b3e15}"
INVALID_API_KEY="invalid-key"

printf "${BLUE}===== APIキー認証機能テスト =====${NC}\n"
printf "\n"

# 1. 除外パスのテスト（認証なし）
printf "${YELLOW}[1/6] 除外パス認証なしテスト${NC}\n"

# ルートエンドポイント
printf "  ${BLUE}GET / (認証なし)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json "${BASE_URL}/")
if [ "$HTTP_STATUS" = "200" ]; then
    printf "  ${GREEN}✓ OK: ルートエンドポイント (HTTP ${HTTP_STATUS})${NC}\n"
else
    printf "  ${RED}✗ FAIL: ルートエンドポイント (HTTP ${HTTP_STATUS})${NC}\n"
    exit 1
fi

# ヘルスチェックエンドポイント
printf "  ${BLUE}GET /api/health (認証なし)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json "${BASE_URL}/api/health")
if [ "$HTTP_STATUS" = "200" ]; then
    printf "  ${GREEN}✓ OK: ヘルスチェックエンドポイント (HTTP ${HTTP_STATUS})${NC}\n"
else
    printf "  ${RED}✗ FAIL: ヘルスチェックエンドポイント (HTTP ${HTTP_STATUS})${NC}\n"
    exit 1
fi

# 2. 認証必須エンドポイントのテスト（認証なし）
printf "\n"
printf "${YELLOW}[2/6] 認証必須エンドポイント認証なしテスト${NC}\n"

printf "  ${BLUE}POST /api/diff (認証なし)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json -X POST "${BASE_URL}/api/diff")
if [ "$HTTP_STATUS" = "401" ]; then
    printf "  ${GREEN}✓ OK: 認証なしで401エラー (HTTP ${HTTP_STATUS})${NC}\n"
    ERROR_MSG=$(cat /tmp/response.json | jq -r '.detail' 2>/dev/null || echo "N/A")
    printf "    エラーメッセージ: ${ERROR_MSG}\n"
else
    printf "  ${RED}✗ FAIL: 期待されるHTTP 401ではなく${HTTP_STATUS}が返却${NC}\n"
    exit 1
fi

# 3. 無効なAPIキーのテスト
printf "\n"
printf "${YELLOW}[3/6] 無効なAPIキーテスト${NC}\n"

printf "  ${BLUE}POST /api/diff (無効APIキー)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
  -X POST \
  -H "x-api-key: ${INVALID_API_KEY}" \
  "${BASE_URL}/api/diff")
if [ "$HTTP_STATUS" = "401" ]; then
    printf "  ${GREEN}✓ OK: 無効APIキーで401エラー (HTTP ${HTTP_STATUS})${NC}\n"
    ERROR_MSG=$(cat /tmp/response.json | jq -r '.detail' 2>/dev/null || echo "N/A")
    printf "    エラーメッセージ: ${ERROR_MSG}\n"
else
    printf "  ${RED}✗ FAIL: 期待されるHTTP 401ではなく${HTTP_STATUS}が返却${NC}\n"
    exit 1
fi

# 4. 有効なAPIキーのテスト
printf "\n"
printf "${YELLOW}[4/6] 有効なAPIキーテスト${NC}\n"

printf "  ${BLUE}POST /api/diff (有効APIキー、ファイルなし)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
  -X POST \
  -H "x-api-key: ${VALID_API_KEY}" \
  "${BASE_URL}/api/diff")
if [ "$HTTP_STATUS" = "422" ]; then
    printf "  ${GREEN}✓ OK: 有効APIキーで認証通過、ファイル必須エラー (HTTP ${HTTP_STATUS})${NC}\n"
else
    printf "  ${RED}✗ FAIL: 期待されるHTTP 422ではなく${HTTP_STATUS}が返却${NC}\n"
    exit 1
fi

# 5. APIキーヘッダー名の検証
printf "\n"
printf "${YELLOW}[5/6] APIキーヘッダー名検証テスト${NC}\n"

# 間違ったヘッダー名
printf "  ${BLUE}POST /api/diff (間違ったヘッダー名)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
  -X POST \
  -H "api-key: ${VALID_API_KEY}" \
  "${BASE_URL}/api/diff")
if [ "$HTTP_STATUS" = "401" ]; then
    printf "  ${GREEN}✓ OK: 間違ったヘッダー名で401エラー (HTTP ${HTTP_STATUS})${NC}\n"
else
    printf "  ${RED}✗ FAIL: 期待されるHTTP 401ではなく${HTTP_STATUS}が返却${NC}\n"
    exit 1
fi

# 正しいヘッダー名
printf "  ${BLUE}POST /api/diff (正しいヘッダー名 x-api-key)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
  -X POST \
  -H "x-api-key: ${VALID_API_KEY}" \
  "${BASE_URL}/api/diff")
if [ "$HTTP_STATUS" = "422" ]; then
    printf "  ${GREEN}✓ OK: 正しいヘッダー名で認証通過 (HTTP ${HTTP_STATUS})${NC}\n"
else
    printf "  ${RED}✗ FAIL: 期待されるHTTP 422ではなく${HTTP_STATUS}が返却${NC}\n"
    exit 1
fi

# 6. 大文字小文字の確認
printf "\n"
printf "${YELLOW}[6/6] ヘッダー名大文字小文字テスト${NC}\n"

printf "  ${BLUE}POST /api/diff (X-API-KEY)${NC}\n"
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
  -X POST \
  -H "X-API-KEY: ${VALID_API_KEY}" \
  "${BASE_URL}/api/diff")
if [ "$HTTP_STATUS" = "422" ]; then
    printf "  ${GREEN}✓ OK: 大文字ヘッダーでも認証通過 (HTTP ${HTTP_STATUS})${NC}\n"
else
    printf "  ${RED}✗ FAIL: 期待されるHTTP 422ではなく${HTTP_STATUS}が返却${NC}\n"
    exit 1
fi

# 結果
printf "\n"
printf "${GREEN}===== 全認証テスト完了 =====${NC}\n"
printf "\n"
printf "${GREEN}✓ 除外パス認証なしテスト${NC}\n"
printf "${GREEN}✓ 認証必須エンドポイント認証なしテスト${NC}\n"
printf "${GREEN}✓ 無効なAPIキーテスト${NC}\n"
printf "${GREEN}✓ 有効なAPIキーテスト${NC}\n"
printf "${GREEN}✓ APIキーヘッダー名検証テスト${NC}\n"
printf "${GREEN}✓ ヘッダー名大文字小文字テスト${NC}\n"
printf "\n"
printf "APIキー認証機能は正常に動作しています。\n"
printf "\n"

# クリーンアップ
rm -f /tmp/response.json