FROM python:3.13-slim

# システム依存関係のインストール
RUN apt-get update && apt-get install -y \
    # MeCab関連
    mecab \
    mecab-ipadic-utf8 \
    libmecab-dev \
    # PDF処理用
    libxml2-dev \
    libxslt1-dev \
    # コンパイル用
    gcc \
    g++ \
    make \
    # その他
    curl \
    && rm -rf /var/lib/apt/lists/*

# uvのインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY apps/pyproject.toml apps/uv.lock* /app/
RUN uv venv /app/.venv && \
    uv sync --frozen --no-install-project

COPY apps/ /app/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
