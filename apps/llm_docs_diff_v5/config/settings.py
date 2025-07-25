"""
LLM Docs Diff v5の設定
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込む（プロジェクトルートから）
project_root = Path(__file__).parent.parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


class Settings:
    """v5システム設定"""
    
    # OpenAI設定
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Azure Document Intelligence設定
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    
    # 処理設定
    MERGE_THRESHOLD: float = 10.0  # ブロックマージの距離閾値
    MIN_BLOCK_AREA: float = 100.0  # 最小ブロック面積
    COLUMN_THRESHOLD: float = 50.0  # カラム検出の閾値
    LINE_HEIGHT_RATIO: float = 0.5  # 同一行判定の高さ比率
    USE_VISUAL_CUES: bool = True  # 視覚的手がかりを使用
    
    # 差分検出設定
    POSITION_WEIGHT: float = 0.3  # 位置の類似度の重み
    CONTENT_WEIGHT: float = 0.5  # コンテンツの類似度の重み
    TYPE_WEIGHT: float = 0.2  # ブロックタイプの類似度の重み
    SIMILARITY_THRESHOLD: float = 0.7  # ブロックが同一とみなされる類似度の閾値
    POSITION_TOLERANCE: float = 20.0  # 位置の許容誤差（ピクセル）


# シングルトンインスタンス
settings = Settings()