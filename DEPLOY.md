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

### 画像の外部参照で差し替える手順

画像を外部ホストで管理し、差し替え運用を行う場合：

1. **画像ホストに画像をアップロード**
   - 画像ホスト（例: AWS S3, Cloudflare R2, GitHub Pages等）に以下の構造でアップロード：
     ```
     materials/{safe_slug}/primary.jpg
     materials/{safe_slug}/uses/space.jpg
     materials/{safe_slug}/uses/product.jpg
     ```
   - `safe_slug`は材料名から自動生成されるパス安全な文字列（例: "アルミニウム" → "アルミニウム"）

2. **Streamlit Cloud の Secrets に IMAGE_BASE_URL を設定**
   - Streamlit Cloud の "Manage app" → "Secrets" を開く
   - 以下を追加：
     ```
     IMAGE_BASE_URL=https://your-image-host.com
     ```
   - 末尾のスラッシュは不要（自動で処理されます）

3. **画像差し替え時は IMAGE_VERSION を更新（デプロイ不要で反映）**
   - Streamlit Cloud の "Secrets" で `IMAGE_VERSION` を更新：
     ```
     IMAGE_VERSION=v2.0.0
     ```
   - アプリを再起動（"Manage app" → "Reboot"）すると、画像URLに `?v=v2.0.0` が付与され、キャッシュが無効化されます
   - デプロイ不要で画像の差し替えが反映されます

### ローカルのみで回す場合

`IMAGE_BASE_URL` を未設定にすると、`static/images/materials/` 内のローカルファイルを使用します。

### 必要なファイル

プロジェクトルートに以下のファイルが必要です：

- `app.py` - Streamlitアプリのメインファイル
- `requirements.txt` - 依存パッケージ
- `database.py` - データベースモデル
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

# 画像の外部参照（オプション）
IMAGE_BASE_URL=https://your-image-host.com
IMAGE_VERSION=v1.0.0

# デバッグモード（DEBUG=1のときのみDebug欄を表示）
DEBUG=0
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
