# HRパーソナル診断 レポート生成アプリ 操作ガイド

このプロジェクトのセットアップ、テスト、デプロイに必要な主要なコマンドをまとめたドキュメントです。

## 1. セットアップ

Cloud Shell環境を新しく開いた際や、ライブラリを追加した後に実行します。

```bash
# 仮想環境を有効化
source venv/bin/activate

# 必要なPythonライブラリをインストールします
pip install -r requirements.txt
```

## 2. ローカルでのテスト実行

Cloud Runにデプロイする前に、Cloud Shell上でアプリケーションを一時的に動かして動作確認をする場合に使用します。

```bash
# 開発用のWebサーバーを起動します
python main.py
```
実行後、Cloud Shell上部に表示される「ウェブでプレビュー」ボタンから動作を確認できます。
停止する際は、ターミナルで `Ctrl + C` を押します。

## 3. AIの知識ベース更新

AIがレポート生成時に参照する情報の元データを更新した場合に実行します。
`/data` ディレクトリ内のPDFファイルを変更・追加・削除した後に、このコマンドを実行してください。

```bash
# /data ディレクトリのPDFからベクトルデータベースを再構築します
python build_index.py
```

## 4. Cloud Runへのデプロイ

アプリケーションのコード（`main.py`など）を修正し、本番環境に反映させる際に実行します。

```bash
# Cloud Runにソースコードから直接デプロイします
gcloud run deploy hr-report-generator \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars="USER_PASSWORD=YOUR_USER_PASSWORD,ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD,OPENAI_API_KEY=YOUR_OPENAI_API_KEY,SPREADSHEET_ID=YOUR_SPREADSHEET_ID,SHEET_NAME=FB,SERVICE_ACCOUNT_FILE=service_account.json"
```

**【重要】** 上記コマンドの `YOUR_...` の部分を、実際の値に置き換えてから実行してください。コマンドに直接パスワードを記述すると履歴に残るため、テキストエディタでコマンドを完成させてからターミナルに貼り付けて実行することをお勧めします。

## 5. デプロイ後のログ確認

アプリケーションがうまく動作しない場合や、エラーの原因を調査する際に使用します。

```bash
# Cloud Runのログをリアルタイムで表示します
gcloud run services logs tail hr-report-generator --region asia-northeast1
```
このコマンドを実行すると、アプリケーションへのアクセスやエラーのログが流れてきます。停止する際は `Ctrl + C` を押します。

## 6. Git 運用コマンド

-   **変更内容の確認**: `git status`
-   **変更をコミット対象に追加**: `git add .`
-   **変更内容を記録 (コミット)**: `git commit -m "変更内容の要約"`
-   **GitHubへ変更を送信 (プッシュ)**: `git push`