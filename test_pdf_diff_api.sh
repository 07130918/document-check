#!/bin/bash
#
# PDF差分検出APIテストスクリプト
# 使用方法: ./test_pdf_diff_api.sh

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
SAMPLE_DIR="apps/sample"
OUTPUT_DIR="test_output_$(date +%Y%m%d_%H%M%S)"

# .envファイルからAPI_KEYを読み込み
if [ -f "apps/.env" ]; then
    export $(grep -E '^API_KEY=' apps/.env | xargs)
fi

# API_KEYが設定されていない場合はデフォルト値を使用
API_KEY="${API_KEY:-sk-dev-885b3e15}"

printf "${BLUE}===== PDF差分検出API動作確認テスト =====${NC}\n"
printf "\n"

# 1. 事前確認
printf "${YELLOW}[1/5] 事前確認${NC}\n"

# サンプルPDFの確認
if [ ! -f "${SAMPLE_DIR}/sample-1.pdf" ] || [ ! -f "${SAMPLE_DIR}/sample-2.pdf" ]; then
    printf "${RED}Error: サンプルPDFファイルが見つかりません${NC}\n"
    printf "  必要なファイル:\n"
    printf "  - ${SAMPLE_DIR}/sample-1.pdf\n"
    printf "  - ${SAMPLE_DIR}/sample-2.pdf\n"
    exit 1
fi
printf "${GREEN}OK: サンプルPDFファイルを確認${NC}\n"

# 2. APIサーバーの確認
printf "\n"
printf "${YELLOW}[2/5] APIサーバーの確認${NC}\n"
printf "  URL: ${BASE_URL}\n"

if curl -s -f "${BASE_URL}/api/health" > /dev/null 2>&1; then
    printf "${GREEN}OK: APIサーバーは正常に動作しています${NC}\n"
    curl -s "${BASE_URL}/api/health" | python -m json.tool 2>/dev/null || echo "  Health: OK"
else
    printf "${RED}Error: APIサーバーに接続できません${NC}\n"
    printf "  FastAPIサーバーが起動していることを確認してください:\n"
    printf "  make up または docker compose up\n"
    exit 1
fi

# 3. 出力ディレクトリの作成
printf "\n"
printf "${YELLOW}[3/5] 出力ディレクトリの準備${NC}\n"
mkdir -p "${OUTPUT_DIR}"
printf "${GREEN}OK: 出力ディレクトリを作成: ${OUTPUT_DIR}${NC}\n"

# 4. PDF差分検出APIの実行
printf "\n"
printf "${YELLOW}[4/5] PDF差分検出APIの実行${NC}\n"
printf "  File1: ${SAMPLE_DIR}/sample-1.pdf\n"
printf "  File2: ${SAMPLE_DIR}/sample-2.pdf\n"

ZIP_FILE="${OUTPUT_DIR}/diff_result.zip"

# APIリクエスト送信
printf "  ${BLUE}APIリクエスト送信中...${NC}\n"
HTTP_STATUS=$(curl -s -o "${ZIP_FILE}" -w "%{http_code}" \
  -X POST \
  -H "x-api-key: ${API_KEY}" \
  -F "document1=@${SAMPLE_DIR}/sample-1.pdf" \
  -F "document2=@${SAMPLE_DIR}/sample-2.pdf" \
  "${BASE_URL}/api/diff" 2>/dev/null)

# レスポンス確認
if [ "$HTTP_STATUS" = "200" ]; then
    printf "${GREEN}OK: API実行成功 (HTTP ${HTTP_STATUS})${NC}\n"

    # ファイルサイズ確認
    FILE_SIZE=$(stat -f%z "${ZIP_FILE}" 2>/dev/null || stat -c%s "${ZIP_FILE}" 2>/dev/null || echo "0")
    printf "  ZIPファイルサイズ: %.2f MB\n" $(echo "$FILE_SIZE" | awk '{print $1/1024/1024}')

else
    printf "${RED}Error: API実行失敗 (HTTP ${HTTP_STATUS})${NC}\n"
    if [ -f "${ZIP_FILE}" ]; then
        printf "エラーレスポンス:\n"
        cat "${ZIP_FILE}"
    fi
    exit 1
fi

# 5. 結果の確認と展開
printf "\n"
printf "${YELLOW}[5/5] 結果の確認${NC}\n"

# ZIPファイルの整合性確認
if unzip -t "${ZIP_FILE}" > /dev/null 2>&1; then
    printf "${GREEN}OK: ZIPファイルの整合性確認${NC}\n"
else
    printf "${RED}Error: ZIPファイルが破損しています${NC}\n"
    exit 1
fi

# ZIPファイルの内容表示
printf "\n"
printf "${BLUE}ZIPファイルの内容:${NC}\n"
unzip -l "${ZIP_FILE}" | tail -n +4 | sed '$d'

# ZIPファイルの展開
printf "\n"
printf "${BLUE}ファイルを展開中...${NC}\n"
unzip -q "${ZIP_FILE}" -d "${OUTPUT_DIR}"

# 展開されたファイルの確認
printf "${GREEN}OK: ファイル展開完了${NC}\n"
printf "\n"
printf "${BLUE}展開されたファイル:${NC}\n"
ls -lh "${OUTPUT_DIR}"/*.pdf 2>/dev/null | awk '{print "  - " $NF " (" $5 ")"}'

# PDFファイルの存在確認
if [ -f "${OUTPUT_DIR}/document1.pdf" ] && [ -f "${OUTPUT_DIR}/document2.pdf" ]; then
    printf "\n"
    printf "${GREEN}OK: 注釈付きPDFファイルの生成を確認${NC}\n"
    printf "  - document1.pdf (注釈付き文書1)\n"
    printf "  - document2.pdf (注釈付き文書2)\n"
else
    printf "${YELLOW}Warning: 期待されるPDFファイルが見つかりません${NC}\n"
fi

printf "\n"
printf "${GREEN}===== テスト完了 =====${NC}\n"
printf "\n"
printf "結果ファイル: ${OUTPUT_DIR}/\n"
printf "\n"
printf "PDFファイルを開く:\n"
printf "  open ${OUTPUT_DIR}/document1.pdf\n"
printf "  open ${OUTPUT_DIR}/document2.pdf\n"
printf "\n"
