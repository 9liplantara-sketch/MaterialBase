# オンラインデプロイガイド

このプロトタイプをオンラインで動かすためのデプロイ方法を説明します。

## 方法1: Streamlit Cloud（推奨・最も簡単）

Streamlit Cloudは無料でStreamlitアプリをホスティングできます。

### 手順

1. **GitHubにリポジトリを作成**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/material-database.git
   git push -u origin main
   ```

2. **Streamlit Cloudにアクセス**
   - https://streamlit.io/cloud にアクセス
   - GitHubアカウントでログイン

3. **アプリをデプロイ**
   - "New app" をクリック
   - リポジトリを選択
   - Main file path: `app.py` を指定
   - "Deploy!" をクリック

4. **完了！**
   - 数分でアプリがオンラインで利用可能になります
   - URLは `https://your-app-name.streamlit.app` の形式

### 必要なファイル

プロジェクトルートに以下のファイルが必要です：

- `app.py` - Streamlitアプリのメインファイル
- `requirements.txt` - 依存パッケージ
- `database.py` - データベースモデル
- `models.py` - Pydanticモデル
- `card_generator.py` - カード生成モジュール

## 方法2: Render

Renderは無料プランでWebアプリをホスティングできます。

### 手順

1. **render.yaml を作成**
   ```yaml
   services:
     - type: web
       name: material-database
       env: python
       buildCommand: pip install -r requirements.txt
       startCommand: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
       envVars:
         - key: PYTHON_VERSION
           value: 3.10.0
   ```

2. **Renderにデプロイ**
   - https://render.com にアクセス
   - GitHubリポジトリを接続
   - New Web Service を選択
   - 設定を入力してデプロイ

## 方法3: Heroku

### 手順

1. **Procfile を作成**
   ```
   web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```

2. **Heroku CLIでデプロイ**
   ```bash
   heroku create your-app-name
   git push heroku main
   ```

## 方法4: Railway

### 手順

1. **railway.json を作成**
   ```json
   {
     "build": {
       "builder": "NIXPACKS"
     },
     "deploy": {
       "startCommand": "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0",
       "restartPolicyType": "ON_FAILURE",
       "restartPolicyMaxRetries": 10
     }
   }
   ```

2. **Railwayにデプロイ**
   - https://railway.app にアクセス
   - GitHubリポジトリを接続
   - 自動的にデプロイが開始されます

## ローカルでのテスト

デプロイ前にローカルでテスト：

```bash
# Streamlitアプリを起動
streamlit run app.py

# ブラウザで http://localhost:8501 にアクセス
```

## データベースの永続化

**重要**: 現在の実装ではSQLiteを使用していますが、クラウド環境ではデータが失われる可能性があります。

### 解決策

1. **PostgreSQLを使用**（推奨）
   - Render、Heroku、RailwayなどはPostgreSQLを提供
   - `database.py`をPostgreSQL用に変更

2. **外部ストレージを使用**
   - AWS S3、Google Cloud Storageなどにデータベースファイルを保存

3. **Streamlit Cloudの場合**
   - データベースファイルをGitHubにコミット（小規模データの場合）
   - または外部データベースサービスを使用

## 環境変数の設定

必要に応じて環境変数を設定：

```bash
# 例: データベースURL
DATABASE_URL=postgresql://user:password@host:port/dbname
```

## トラブルシューティング

### ポートエラー

Streamlitアプリはデフォルトでポート8501を使用しますが、クラウド環境では環境変数`PORT`を使用する必要があります：

```python
# app.pyの先頭に追加
import os
port = int(os.environ.get("PORT", 8501))
```

### データベースパス

クラウド環境では絶対パスを使用：

```python
# database.pyで
import os
db_path = os.path.join(os.getcwd(), "materials.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
```

## セキュリティ考慮事項

- 本番環境では認証を追加
- 環境変数で機密情報を管理
- HTTPSを使用（多くのクラウドサービスで自動提供）

## 推奨デプロイ方法

**小規模プロトタイプ**: Streamlit Cloud（最も簡単）
**本格運用**: Render または Railway（PostgreSQL対応）

