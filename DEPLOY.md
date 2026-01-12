# オンラインデプロイガイド

このプロトタイプをオンラインで動かすためのデプロイ方法を説明します。

## データベース設定（必須）

### Streamlit Cloud Secrets設定

Streamlit Community Cloudではローカルファイル（SQLite）が永続化されないため、**外部Postgresデータベースが必須**です。

#### Secrets設定方法

1. Streamlit Cloudのダッシュボードで「Settings」→「Secrets」を開く
2. 以下のいずれかの形式で設定:

**推奨形式（connections方式）:**
```toml
[connections.materialbase_db]
url = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

**簡易形式:**
```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

#### データベースプロバイダーの例

**Neon (推奨):**
- Neonは無料プランでPostgresを提供
- 接続URL例: `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`
- 注意: `sslmode=require`が必須（NeonはSSL必須）

**Supabase:**
- 接続URL例: `postgresql://postgres:pass@db.xxx.supabase.co:5432/postgres`
- SSL設定: `sslmode=require`を推奨

**その他のPostgresプロバイダー:**
- ElephantSQL、Railway、Renderなど
- 接続URLは各プロバイダーのドキュメントを参照

#### 重要な注意事項

- **Cloud環境ではSQLiteフォールバックは禁止**: `DATABASE_URL`が設定されていない場合はエラーになります
- **ローカル開発**: `DATABASE_URL`が未設定の場合、`sqlite:///./materials.db`が使用されます（開発用）

## データベースマイグレーション（Alembic）

### 初回セットアップ

1. **Alembicを初期化（初回のみ）:**
   ```bash
   alembic init alembic
   ```

2. **alembic/env.pyを編集:**
   ```python
   from database import Base
   from utils.settings import get_database_url
   
   target_metadata = Base.metadata
   
   # run_migrations_offline()とrun_migrations_online()内で:
   url = get_database_url()
   ```

3. **初回マイグレーションを作成:**
   ```bash
   alembic revision --autogenerate -m "init schema"
   ```
   **重要**: 生成されたマイグレーションファイル（`alembic/versions/xxx_init_schema.py`）をレビューしてください

4. **マイグレーションを適用:**
   ```bash
   alembic upgrade head
   ```

### スキーマ変更時

1. **モデルを変更**（`database.py`のMaterial、ReferenceURLなど）

2. **マイグレーションを生成:**
   ```bash
   alembic revision --autogenerate -m "add_new_column"
   ```

3. **生成されたマイグレーションをレビュー**（`alembic/versions/`内のファイル）

4. **マイグレーションを適用:**
   ```bash
   alembic upgrade head
   ```

### 自動マイグレーション（オプション）

Streamlit Cloudで起動時に自動マイグレーションを実行する場合:

**Secretsに追加:**
```toml
MIGRATE_ON_START = "1"
```

**注意**: 自動マイグレーションは便利ですが、通常はデプロイ前に手動で`alembic upgrade head`を実行することを推奨します（安全性のため）

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

### 画像の外部参照で差し替える手順（推奨運用）

画像を外部ホストで管理し、差し替え運用を行う場合：

#### 1. 画像ホストに画像をアップロード

画像ホスト（例: AWS S3, Cloudflare R2, GitHub Pages等）に以下の構造でアップロード：

```
materials/{safe_slug}/primary.jpg
materials/{safe_slug}/uses/space.jpg
materials/{safe_slug}/uses/product.jpg
```

- `safe_slug`は材料名から自動生成されるパス安全な文字列（例: "アルミニウム" → "アルミニウム"）
- 画像は必ずJPG形式（`.jpg`）で保存してください

#### 2. Streamlit Cloud の Secrets に IMAGE_BASE_URL を設定

- Streamlit Cloud の "Manage app" → "Secrets" を開く
- 以下を追加：
  ```
  IMAGE_BASE_URL=https://your-image-host.com
  ```
- 末尾のスラッシュは不要（自動で処理されます）

#### 3. 画像差し替え時は IMAGE_VERSION を更新（デプロイ不要で反映）

- Streamlit Cloud の "Secrets" で `IMAGE_VERSION` を更新：
  ```
  IMAGE_VERSION=v2.0.0
  ```
- アプリを再起動（"Manage app" → "Reboot"）すると、画像URLに `?v=v2.0.0` が付与され、キャッシュが無効化されます
- **デプロイ不要で画像の差し替えが反映されます**

#### 画像解決の優先順位

アプリは以下の順序で画像を解決します：

1. **DBの明示URL**（最優先）
   - `Material.texture_image_url`（primary画像）
   - `UseExample.image_url`（space/product画像）
   - http(s) URLの場合のみ採用

2. **IMAGE_BASE_URL 規約URL**
   - `{IMAGE_BASE_URL}/materials/{safe_slug}/primary.jpg`
   - `{IMAGE_BASE_URL}/materials/{safe_slug}/uses/space.jpg`
   - `{IMAGE_BASE_URL}/materials/{safe_slug}/uses/product.jpg`
   - URLには必ず `?v={IMAGE_VERSION or APP_VERSION or "dev"}` が付与されます

3. **ローカルファイル fallback**
   - `static/images/materials/{safe_slug}/primary.jpg`
   - `static/images/materials/{safe_slug}/uses/space.jpg`
   - `static/images/materials/{safe_slug}/uses/product.jpg`

4. **旧互換 fallback**（最後の手段）
   - 日本語フォルダ名など、旧仕様のフォルダを探索
   - safe_slug配下が無い場合のみ試行

### ローカルのみで回す場合

`IMAGE_BASE_URL` を未設定にすると、`static/images/materials/` 内のローカルファイルを使用します。

### 画像アセットの検証

ローカルで画像アセットの検証を行う場合：

```bash
# 通常モード（公開材料のみ、primary画像が必須）
python scripts/verify_assets.py

# 非公開材料も含めて検証
VERIFY_INCLUDE_UNPUBLISHED=1 python scripts/verify_assets.py

# デバッグ出力あり
DEBUG=1 python scripts/verify_assets.py
```

**検証内容:**
- `primary`画像は必須（解決できない場合はFAIL）
- `space/product`画像は任意（存在すればチェック、無くてもOK）
- 実際の解決ロジック（`get_material_image_ref`）基準で検査
- `safe_slug` / `legacy_jp` どちらで解決されてもOK

**GitHub Actions:**
- main push/PR時に自動検証が実行されます
- `primary`画像が見つからない材料がある場合のみFAIL
- `space/product`未登録はCIを落としません

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
