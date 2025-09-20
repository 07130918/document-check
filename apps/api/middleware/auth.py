"""FastAPI用のAPIキー認証ミドルウェア。"""

import os
from typing import List

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """APIキー認証ミドルウェア。

    x-api-keyヘッダーを使用してリクエストを検証する。
    特定のパスを認証から除外する。
    """

    def __init__(self, app, excluded_paths: List[str] = None):
        """ミドルウェアを初期化する。

        Args:
            app: FastAPIアプリケーションインスタンス
            excluded_paths: 認証から除外するパスのリスト
        """
        super().__init__(app)
        self.api_key = os.getenv("API_KEY")
        self.excluded_paths = excluded_paths or ["/", "/api/health"]

    async def dispatch(self, request: Request, call_next):
        """リクエストを処理しAPIキーを検証する。

        Args:
            request: FastAPIリクエストオブジェクト
            call_next: チェーン内の次のミドルウェア

        Returns:
            Response: エラーレスポンスまたは次のミドルウェアからの結果
        """
        # 除外パスの場合は認証をスキップ
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        api_key = request.headers.get("x-api-key")
        if not api_key or api_key != self.api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid API key"})

        return await call_next(request)
