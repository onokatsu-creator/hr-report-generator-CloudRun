# 1. ベースイメージの指定
# Cloud Runと互換性の高い、軽量なDebian OS上でPython 3.11を動かす環境を土台にします。
FROM python:3.11-slim

# 2. 環境変数の設定
# Pythonが出力するログがすぐに表示されるようにするおまじないです。
ENV PYTHONUNBUFFERED=True

# 3. 作業ディレクトリの作成と設定
# コンテナの中に、これから作業する場所として「/app」というフォルダを作ります。
WORKDIR /app

# 4. 依存関係のインストール
# まずrequirements.txtだけをコピーして、ライブラリを先にインストールします。
# これにより、コードを少し変更しただけでは、毎回ライブラリをインストールし直す必要がなくなり、ビルドが高速になります。
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 5. アプリケーションコードのコピー
# プロジェクトフォルダにある全てのファイル（app.pyなど）を、コンテナの「/app」フォルダにコピーします。
COPY . .

# 6. 実行コマンドの指定
# このコンテナが起動したときに、どのコマンドを実行するかを指定します。
# Cloud Runは、環境変数PORTで指定されたポートでリッスンすることを期待します。
# gunicornは、本番環境でよく使われる高機能なWebサーバーです。
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]