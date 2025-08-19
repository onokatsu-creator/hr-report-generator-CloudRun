# Python 3.9をベースイメージとして使用
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピー
COPY requirements.txt requirements.txt

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt
COPY fonts/ /app/fonts/
COPY prompts/ /app/prompts/
COPY vectorstore/ /app/vectorstore/

# アプリケーションのソースコードをコピー
COPY . .

# アプリケーションがリッスンするポートを8080に設定
ENV PORT 8080

# アプリケーションを実行するコマンド
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app