"""FastAPI application entry point."""

from fastapi import FastAPI
from api.routers import diff, health

app = FastAPI(
    title="Document Check API",
    description="API for document checking service",
    version="1.0.0",
)
app.include_router(diff.router, prefix="/api", tags=["diff"])
app.include_router(health.router, prefix="/api", tags=["health"])


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {"message": "Welcome to Document Check API"}
