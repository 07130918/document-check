"""
LLM文書差分検出システムの設定
"""
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込む（プロジェクトルートから）
project_root = Path(__file__).parent.parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


class Settings:
    """システム設定"""
    
    # プロジェクトルート
    PROJECT_ROOT = Path(__file__).parent.parent
    OUTPUT_DIR = PROJECT_ROOT.parent.parent / "output" / "llm_diff_test_v3-3"
    
    # OpenAI設定
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.3
    
    # Azure Document Intelligence設定
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2024-02-29-preview")
    USE_AZURE_FOR_OCR: bool = os.getenv("USE_AZURE_FOR_OCR", "False").lower() == "true"
    USE_AZURE_FOR_COMPLEX_LAYOUTS: bool = os.getenv("USE_AZURE_FOR_COMPLEX_LAYOUTS", "True").lower() == "true"
    
    # High Resolution OCR設定
    USE_HIGH_RESOLUTION_OCR: bool = os.getenv("USE_HIGH_RESOLUTION_OCR", "True").lower() == "true"
    
    # 処理設定
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "40"))
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "100"))
    TEST_MAX_PAGES: Optional[int] = None  # テスト時の最大ページ数制限（Noneで無制限）
    PARALLEL_WORKERS: int = int(os.getenv("PARALLEL_WORKERS", "4"))
    MEMORY_LIMIT_MB: int = int(os.getenv("MEMORY_LIMIT_MB", "2048"))
    PROCESSING_TIMEOUT_SECONDS: int = int(os.getenv("PROCESSING_TIMEOUT_SECONDS", "600"))  # High Resolution使用時は処理時間が増加するため
    
    # LLM処理設定
    LLM_BATCH_SIZE: int = 10  # LLMへのバッチ処理サイズ
    LLM_RETRY_COUNT: int = 3  # LLM APIリトライ回数
    LLM_RETRY_DELAY: float = 1.0  # リトライ間隔（秒）
    LLM_PAGE_CHUNK_SIZE: int = 50  # 一度に処理するページ数の上限
    
    # キャッシュ設定
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHING", "True").lower() == "true"
    CACHE_TTL_SECONDS: int = 3600  # 1時間
    CACHE_DIR: Path = OUTPUT_DIR / "cache"
    
    # 表結合設定
    ENABLE_TABLE_MERGING: bool = os.getenv("ENABLE_TABLE_MERGING", "True").lower() == "true"
    TABLE_MERGE_VERTICAL_THRESHOLD: float = float(os.getenv("TABLE_MERGE_VERTICAL_THRESHOLD", "0.05"))  # ページ高さの5%
    TABLE_MERGE_HORIZONTAL_THRESHOLD: float = float(os.getenv("TABLE_MERGE_HORIZONTAL_THRESHOLD", "0.8"))  # 80%の重なり
    TABLE_MERGE_COLUMN_THRESHOLD: float = float(os.getenv("TABLE_MERGE_COLUMN_THRESHOLD", "0.7"))  # 70%の列一致
    
    # デバッグ設定
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    AZURE_LOG_LEVEL: str = os.getenv("AZURE_LOG_LEVEL", "WARNING")  # Azureログレベル
    
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