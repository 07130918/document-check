# PDF差分検出システム - ベースライン実装用Docker環境
FROM python:3.11-slim

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

# Poetry インストール
ENV POETRY_HOME="/opt/poetry"
ENV POETRY_BIN="/opt/poetry/bin"
ENV PATH="$POETRY_BIN:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# Poetry設定
ENV POETRY_CACHE_DIR=/opt/poetry_cache
ENV POETRY_VENV_IN_PROJECT=1
ENV POETRY_NO_INTERACTION=1

# 作業ディレクトリ設定
WORKDIR /app

# プロジェクトファイルコピー
COPY pyproject.toml poetry.lock* ./

# 依存関係インストール
RUN poetry config virtualenvs.create false \
    && poetry install --with dev,test --extras "full" \
    && rm -rf $POETRY_CACHE_DIR

# MeCab辞書設定
ENV MECAB_CHARSET=utf8

# アプリケーションコード追加
COPY . .

# ポート公開（将来のWebAPI用）
EXPOSE 8000

# デフォルトコマンド
CMD ["python", "run_baseline_test.py"]