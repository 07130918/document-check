# 環境設定

## 環境変数（.env）
```
# OpenAI API
OPENAI_API_KEY=<your-key>
OPENAI_MODEL=gpt-4o-mini

# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_KEY=<your-key>
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://diffcheck.cognitiveservices.azure.com/

# Azure Settings
USE_AZURE_FOR_OCR=True
USE_AZURE_FOR_COMPLEX_LAYOUTS=True

# Application Settings
DEBUG=True
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=40
MAX_PAGES=100

# Performance Settings
PARALLEL_WORKERS=4
MEMORY_LIMIT_MB=2048
PROCESSING_TIMEOUT_SECONDS=300
```

## システム情報
- **OS**: Linux (WSL2)
- **作業ディレクトリ**: /home/dev/prj-ms-document-check
- **Python**: 3.12.3
- **Poetry**: インストール済み
- **MeCab**: インストール済み（日本語形態素解析）

## Docker環境
- 現在Dockerは未インストール
- 必要に応じてdocker-compose.ymlが利用可能

## 出力ディレクトリ
- ベースライン: `output/baseline_test/`
- LLM実装: `output/llm_diff_test/`
- 各バージョンごとに個別の出力ディレクトリ