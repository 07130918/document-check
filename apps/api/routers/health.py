"""Health check endpoint router."""

from typing import Dict, Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """APIの状態を監視するためのヘルスチェックエンドポイント。"""
    return JSONResponse(
        status_code=200,
        content={"status": "healthy"},
    )
