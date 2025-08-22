"""
LLM文書差分検出システムの設定
"""
import os
from typing import Optional
from pathlib import Path
# Docker環境では環境変数は既に設定されている


class Settings:
    """システム設定"""
    
    # プロジェクトルート
    PROJECT_ROOT = Path(__file__).parent.parent
    OUTPUT_DIR = PROJECT_ROOT / "output" / "llm_diff_test"
    
    # OpenAI設定
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.3
    
    # Azure Document Intelligence設定
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2023-07-31")
    USE_AZURE_FOR_OCR: bool = os.getenv("USE_AZURE_FOR_OCR", "False").lower() == "true"
    USE_AZURE_FOR_COMPLEX_LAYOUTS: bool = os.getenv("USE_AZURE_FOR_COMPLEX_LAYOUTS", "True").lower() == "true"
    
    # 処理設定
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "40"))
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "100"))
    PARALLEL_WORKERS: int = int(os.getenv("PARALLEL_WORKERS", "4"))
    MEMORY_LIMIT_MB: int = int(os.getenv("MEMORY_LIMIT_MB", "2048"))
    PROCESSING_TIMEOUT_SECONDS: int = int(os.getenv("PROCESSING_TIMEOUT_SECONDS", "300"))
    
    # LLM処理設定
    LLM_BATCH_SIZE: int = 10  # LLMへのバッチ処理サイズ
    LLM_RETRY_COUNT: int = 3  # LLM APIリトライ回数
    LLM_RETRY_DELAY: float = 1.0  # リトライ間隔（秒）
    LLM_PAGE_CHUNK_SIZE: int = 50  # 一度に処理するページ数の上限
    
    # キャッシュ設定
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHING", "True").lower() == "true"
    CACHE_TTL_SECONDS: int = 3600  # 1時間
    CACHE_DIR: Path = OUTPUT_DIR / "cache"
    
    # デバッグ設定
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """設定の検証"""
        errors = []
        
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is not set")
        
        if cls.USE_AZURE_FOR_OCR:
            if not cls.AZURE_DOCUMENT_INTELLIGENCE_KEY:
                errors.append("AZURE_DOCUMENT_INTELLIGENCE_KEY is not set")
            if not cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT:
                errors.append("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not set")
        
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True
    
    @classmethod
    def create_output_directories(cls):
        """出力ディレクトリを作成"""
        dirs = [
            cls.OUTPUT_DIR / "PDFs",
            cls.OUTPUT_DIR / "debug",
            cls.OUTPUT_DIR / "reports",
            cls.CACHE_DIR
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)


# シングルトンインスタンス
settings = Settings()