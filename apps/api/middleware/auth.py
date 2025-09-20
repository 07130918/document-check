"""API Key authentication middleware for FastAPI."""

import os
from typing import List

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API Key authentication middleware.
    
    Validates requests using x-api-key header.
    Excludes certain paths from authentication.
    """

    def __init__(self, app, excluded_paths: List[str] = None):
        """Initialize middleware.

        Args:
            app: FastAPI application instance
            excluded_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.api_key = os.getenv("API_KEY", "sk-dev-885b3e15")
        self.excluded_paths = excluded_paths or ["/", "/api/health"]

    async def dispatch(self, request: Request, call_next):
        """Process request and validate API key.

        Args:
            request: FastAPI request object
            call_next: Next middleware in chain

        Returns:
            Response: Either error response or result from next middleware
        """
        # 除外パスの場合は認証をスキップ
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # APIキーヘッダーの取得
        api_key = request.headers.get("x-api-key")

        # APIキーの検証
        if not api_key or api_key != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"}
            )

        # 認証成功時は次の処理へ
        return await call_next(request)
