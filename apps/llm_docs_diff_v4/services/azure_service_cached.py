"""
Azure Document Intelligenceサービス（キャッシュ付き拡張版）
"""
import hashlib
import json
import pickle
import time
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from apps.llm_docs_diff_v4.services.azure_service_enhanced import AzureDocumentServiceEnhanced

logger = logging.getLogger(__name__)

class AzureDocumentServiceCached(AzureDocumentServiceEnhanced):
    """キャッシュ機能付きAzure Document Intelligenceサービス"""
    
    def __init__(self, cache_dir: str = ".cache/azure_responses"):
        """初期化"""
        super().__init__()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_enabled = True
        logger.info(f"Cache directory: {self.cache_dir}")
    
    def _get_cache_key(self, pdf_bytes: bytes, method: str) -> str:
        """PDFのハッシュ値からキャッシュキーを生成"""
        # PDFの最初と最後の1MBをハッシュ化（高速化のため）
        sample_size = 1024 * 1024  # 1MB
        if len(pdf_bytes) > sample_size * 2:
            sample = pdf_bytes[:sample_size] + pdf_bytes[-sample_size:]
        else:
            sample = pdf_bytes
        
        pdf_hash = hashlib.md5(sample).hexdigest()
        return f"{method}_{pdf_hash}_{len(pdf_bytes)}"
    
    def _load_from_cache(self, cache_key: str) -> Dict[str, Any]:
        """キャッシュから読み込み"""
        if not self.cache_enabled:
            return None
            
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    logger.info(f"Loading from cache: {cache_key}")
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache {cache_key}: {e}")
                return None
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]):
        """キャッシュに保存"""
        if not self.cache_enabled:
            return
            
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved to cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_key}: {e}")
    
    def extract_layout_with_hierarchy_batch(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """PDFから階層構造でレイアウト情報を抽出（キャッシュ付き）"""
        # キャッシュチェック
        cache_key = self._get_cache_key(pdf_bytes, "hierarchy_batch")
        cached_data = self._load_from_cache(cache_key)
        
        if cached_data is not None:
            logger.info("Using cached Azure response")
            return cached_data
        
        # キャッシュがない場合は親クラスのメソッドを呼び出し
        logger.info("Processing with Azure API (not cached)")
        start_time = time.time()
        result = super().extract_layout_with_hierarchy_batch(pdf_bytes)
        processing_time = time.time() - start_time
        logger.info(f"Azure API processing time: {processing_time:.1f}s")
        
        # 結果をキャッシュに保存
        self._save_to_cache(cache_key, result)
        
        return result
    
    def clear_cache(self):
        """キャッシュをクリア"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Cache cleared")
    
    def get_cached_result(self, pdf_bytes: bytes) -> Optional[Any]:
        """キャッシュからAzure結果を取得（生の結果）
        
        Note: 現在の実装ではraw_resultsは保存されていないため、
        階層データのみを返します。
        
        Args:
            pdf_bytes: PDFファイルのバイトデータ
            
        Returns:
            キャッシュされた階層データ
        """
        # キャッシュキーを生成
        cache_key = self._get_cache_key(pdf_bytes, "hierarchy_batch")
        cached_data = self._load_from_cache(cache_key)
        
        if cached_data is not None:
            logger.info("Returning cached hierarchy data")
            # 階層データを返す（Azure結果の代わり）
            return cached_data
        
        return None