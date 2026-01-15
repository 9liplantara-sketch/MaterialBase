# Postgres移行ガイド

Streamlit Community CloudでSQLiteが消える問題を解決するため、Postgresへの移行を行います。

## 概要

- **問題**: Streamlit Cloudはローカルファイル永続性を保証しない（SQLiteが消える）
- **解決**: 外部Postgres DBを使用（リブートしてもデータが保持される）
- **品質**: Alembicによるマイグレーション管理（スキーマ変更の追跡可能）

## セットアップ

### 1. Postgres DBの準備

Neon、Supabase、AWS RDSなど、任意のPostgresサービスを使用できます。

**例（Neon）:**
1. https://neon.tech でアカウント作成
2. プロジェクト作成
3. 接続文字列をコピー（例: `postgresql://user:password@host/dbname?sslmode=require`）

### 2. Streamlit Secretsの設定

Streamlit Cloudの Secrets管理画面（`.streamlit/secrets.toml`）に以下を追加：

```toml
# 推奨: connections.materialbase_db.url
[connections.materialbase_db]
url = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"

# または簡易: DATABASE_URL
# DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

**重要:**
- Neonの場合、URL末尾に `?sslmode=require` が必要です
- パスワードは必ずシークレットとして管理（Gitにコミットしない）

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

`requirements.txt`には以下が含まれます：
- `psycopg2-binary>=2.9.9` - Postgres接続
- `alembic>=1.12.1` - マイグレーション管理

### 4. Alembicの初期化（初回のみ）

```bash
# Alembicを初期化
alembic init alembic
```

これで `alembic/` ディレクトリと `alembic.ini` が作成されます。

### 5. alembic/env.pyの設定

`alembic/env.py`を編集して、以下を設定：

```python
# alembic/env.py
from database import Base
from utils.settings import get_database_url

# target_metadataを設定
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    # ... 以下既存コード

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_database_url()
    connectable = create_engine(url, pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()
```

### 6. 初回マイグレーションの作成

```bash
# 既存モデルからマイグレーションファイルを生成
alembic revision --autogenerate -m "init schema"
```

**注意**: 生成されたマイグレーションファイル（`alembic/versions/xxxx_init_schema.py`）を必ずレビューしてください：
- UNIQUE制約が正しく含まれているか
- nullable/default値が正しいか
- 外部キー制約が正しいか

### 7. マイグレーションの適用

```bash
# マイグレーションを適用
alembic upgrade head
```

これでPostgresにテーブルが作成されます。

## 運用

### 初回データ投入（サンプルデータ）

Streamlit Cloudで初回起動時にサンプルデータを投入する場合：

**推奨設定（Streamlit Secrets）:**
```toml
# サンプルデータの投入を有効化（初回のみ）
INIT_SAMPLE_DATA = "1"

# 画像生成をスキップ（材料データのみ投入、高速化・エラー回避）
SEED_SKIP_IMAGES = "1"
```

**重要:**
- `INIT_SAMPLE_DATA=1` は**一度だけ使用**してください。確認後は必ず `0` に戻すか削除してください。
- `SEED_SKIP_IMAGES=1` を推奨します（画像生成でエラーが発生する可能性があるため）。画像は後で手動で追加できます。
- データ投入後、Cloudログで `[SEED] start` と `[SEED] done` を確認してください。

**トラブルシューティング:**
- `materials` が 0件のまま → `SEED_SKIP_IMAGES=1` を設定して画像処理をスキップしてください
- `psycopg.errors.NotNullViolation: null value in column "material_id"` → `SEED_SKIP_IMAGES=1` で解決します

### スキーマ変更の手順

1. **モデル変更**: `database.py`でモデルを修正
2. **マイグレーション生成**:
   ```bash
   alembic revision --autogenerate -m "add_column_description"
   ```
3. **レビュー**: 生成されたマイグレーションファイルを確認
4. **適用**:
   ```bash
   alembic upgrade head
   ```

### アプリ起動時の自動マイグレーション

**重要**: デフォルトでは自動マイグレーションは**OFF**です（安全のため）。

**Cloud環境での推奨設定:**
```toml
# Streamlit Secrets
MIGRATE_ON_START = "0"  # デフォルトOFF（推奨）
```

**理由:**
- Cloud環境では `alembic/env.py` が `DATABASE_URL` を要求します
- `DATABASE_URL` が未設定の場合、起動時にエラーでクラッシュします
- マイグレーションは「デプロイ前に手動で実行」することを推奨します

**自動マイグレーションを有効にする場合（非推奨）:**

```bash
# 環境変数で有効化
export MIGRATE_ON_START=1
streamlit run app.py
```

または、Streamlit Secretsに追加：

```toml
MIGRATE_ON_START = "1"
```

**注意**: `MIGRATE_ON_START=1` を設定する場合は、必ず `DATABASE_URL` が正しく設定されていることを確認してください。

### 既存データの移行（SQLite → Postgres）

ローカルのSQLite DBをPostgresに移行する場合：

```bash
# 1. DATABASE_URLをPostgresに設定
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"

# 2. 移行スクリプトを実行
python scripts/migrate_sqlite_to_postgres.py
```

**注意**: 既存データが消える可能性があるため、必ずバックアップを取ってから実行してください。

## トラブルシューティング

### CloudでSQLiteエラーが出る

**エラー**: `RuntimeError: DATABASE_URL is required on Streamlit Cloud`

**解決**: Streamlit Secretsに `DATABASE_URL` または `connections.materialbase_db.url` を設定してください。

### マイグレーションが失敗する

**エラー**: `alembic.util.exc.CommandError: Can't locate revision identified by 'xxxx'`

**解決**: 
1. マイグレーションファイルが正しく生成されているか確認
2. `alembic current` で現在の状態を確認
3. `alembic history` で履歴を確認

### 接続エラー

**エラー**: `psycopg2.OperationalError: could not connect to server`

**解決**:
1. `sslmode=require` がURLに含まれているか確認（Neon/Supabaseの場合）
2. ファイアウォール設定を確認
3. 接続文字列のユーザー名/パスワード/ホスト名が正しいか確認

## CloudでSQLiteを禁止した理由

Streamlit Community Cloudは**ローカルファイル永続性を保証しません**。リブートのたびにSQLiteファイルが消えるため、データが失われます。この問題を根本解決するため、Cloud環境ではPostgres（外部DB）の使用を必須としました。

**ローカル開発**: SQLiteの使用は可能（開発環境のみ）

**本番（Cloud）**: Postgres必須（データ永続化のため）
