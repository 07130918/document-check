# PDF差分検出システム - フル機能版Docker環境
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
    poppler-utils \
    # 画像処理用
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # LibreOffice（Word/PowerPoint変換用）
    libreoffice \
    # コンパイル用
    gcc \
    g++ \
    make \
    # その他
    curl \
    git \
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
COPY pyproject.toml poetry.lock* README.md ./

# 依存関係インストール（まず依存関係のみ）
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --with dev,test --extras "full" \
    && rm -rf $POETRY_CACHE_DIR

# MeCab辞書設定
ENV MECAB_CHARSET=utf8

# アプリケーションコード追加
COPY . .

# プロジェクト自体をインストール（開発モード）
RUN poetry install --only-root

# 環境変数のテンプレートファイルを作成
RUN echo "# Azure Document Intelligence設定" > .env.template && \
    echo "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=" >> .env.template && \
    echo "AZURE_DOCUMENT_INTELLIGENCE_KEY=" >> .env.template && \
    echo "" >> .env.template && \
    echo "# OpenAI API設定" >> .env.template && \
    echo "OPENAI_API_KEY=" >> .env.template && \
    echo "" >> .env.template && \
    echo "# その他の設定" >> .env.template && \
    echo "LOG_LEVEL=INFO" >> .env.template && \
    echo "DEBUG=False" >> .env.template

# ポート公開（将来のWebAPI用）
EXPOSE 8000

# デフォルトコマンド
CMD ["python", "-m", "apps.llm_docs_diff_v5.test_llm_diff_v5"]