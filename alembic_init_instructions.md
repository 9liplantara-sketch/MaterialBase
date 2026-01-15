# Alembic初期化手順

## 1. Alembicをインストール

```bash
pip install alembic psycopg2-binary
```

## 2. Alembicを初期化

```bash
alembic init alembic
```

これで以下のディレクトリ・ファイルが作成されます:
- `alembic/` - マイグレーションスクリプト用ディレクトリ
- `alembic.ini` - Alembic設定ファイル

## 3. alembic/env.pyを設定

`alembic/env.py`を編集して、database.pyのBaseを参照できるようにします。

```python
from database import Base
from utils.settings import get_database_url

# target_metadataを設定
target_metadata = Base.metadata

# run_migrations_offline()関数内で:
url = get_database_url()

# run_migrations_online()関数内で:
url = get_database_url()
```

## 4. 初回マイグレーションを作成

```bash
alembic revision --autogenerate -m "init schema"
```

これで`alembic/versions/`にマイグレーションファイルが作成されます。

## 5. マイグレーションを適用

```bash
alembic upgrade head
```

## 注意事項

- `alembic revision --autogenerate`は既存のテーブル構造から差分を検出しますが、完全に正確とは限りません
- 生成されたマイグレーションファイルは必ずレビューしてください（UNIQUE制約、NULLABLE、DEFAULT値など）
- 本番環境では`MIGRATE_ON_START=1`を設定するか、デプロイ前に手動で`alembic upgrade head`を実行してください
