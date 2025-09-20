"""FastAPI application entry point."""
from fastapi import FastAPI
from api.routers import hello

# FastAPIインスタンスの作成
app = FastAPI(
    title="Document Check API",
    description="API for document checking service",
    version="1.0.0"
)

# ルーターの追加
app.include_router(hello.router, prefix="/api", tags=["hello"])


@app.get("/")
async def root():
    """
    Root endpoint.
    
    Returns:
        dict: A welcome message.
    """
    return {"message": "Welcome to Document Check API"}