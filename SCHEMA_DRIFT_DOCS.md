# スキーマドリフト検知と安全モード

## 概要

Material Map は、データベーススキーマの不整合を検知し、アプリケーションがクラッシュしないように「安全モード」で動作する機能を実装しています。

## 動作原理

### スキーマドリフト検知

- **軽量チェック**: `information_schema.columns` (Postgres) または `PRAGMA table_info` (SQLite) を使用
- **キャッシュ**: `st.cache_data(ttl=60)` で結果をキャッシュし、Streamlit再実行時の重複チェックを避ける（60秒TTL）
- **pg_catalog大量アクセスを回避**: `pg_catalog` への大量の問い合わせは行わない

### 安全モード

スキーマ不整合が検知された場合：
- 画像ロード（`images` 関連の eager load）を無効化
- 一覧表示は動作するが、画像は「画像が利用できません（DB migrate必要）」と表示
- アプリケーションはクラッシュしない

## 現在の検知対象

- `images.kind` 列の存在確認

## 使用方法

### マイグレーションの実行

スキーマ不整合を解消するには：

1. Streamlit Secrets に `MIGRATE_ON_START=1` を設定
   - **注意**: `DATABASE_URL` 環境変数の設定は不要です
   - `connections.materialbase_db.url` または `DATABASE_URL` を Streamlit Secrets に設定してください
2. アプリケーションを再起動
3. Alembic マイグレーションが自動実行され、不足している列が追加される

### スキーマ検証の実行

明示的にスキーマ検証を行いたい場合：

1. Streamlit Secrets に `VERIFY_SCHEMA_ON_START=1` を設定
2. アプリケーションを再起動
3. スキーマ検査が実行される（通常運用時はスキップされる）

## 期待されるログ

### 通常運用時（MIGRATE_ON_START=0, VERIFY_SCHEMA_ON_START=0）

```
[DB INIT] skip schema verification (postgres cloud, normal operation)
[DB INIT] connection check: OK
```

### スキーマ不整合検知時

```
[SCHEMA] missing column images.kind - run migration with MIGRATE_ON_START=1
```

### マイグレーション実行時（MIGRATE_ON_START=1）

```
[DB INIT] Alembic migration applied (MIGRATE_ON_START=1)
```

## 手動確認手順

### Cloud上での確認

#### Phase1: マイグレーション実行（MIGRATE_ON_START=1）

1. **Secrets設定**:
   ```
   MIGRATE_ON_START=1
   VERIFY_SCHEMA_ON_START=0
   DEBUG=1  # オプション（デバッグ情報表示）
   ```

2. **Reboot**:
   - Streamlit Cloud でアプリケーションを再起動

3. **ログ確認**:
   - Cloud ログで以下が表示されることを確認:
     ```
     [DB INIT] Alembic migration start (MIGRATE_ON_START=1)
     [DB INIT] Database URL: postgresql://user:***@host
     [DB INIT] sqlalchemy.url set in alembic config
     [DB INIT] DATABASE_URL set in environment
     [DB INIT] Alembic migration end: SUCCESS
     ```
   - `RuntimeError: DATABASE_URL is not set` が表示されないことを確認
   - `[DB INIT] Alembic migration end: FAILED` が表示されないことを確認

4. **動作確認**:
   - 警告メッセージが消えることを確認
   - 正常に画像が表示されることを確認
   - `pg_catalog` への大量の問い合わせが発生しないことを確認

#### Phase2: 通常運用に戻す（MIGRATE_ON_START=0）

1. **Secrets設定**:
   ```
   MIGRATE_ON_START=0
   VERIFY_SCHEMA_ON_START=0
   DEBUG=0  # または設定しない
   ```

2. **Reboot**:
   - Streamlit Cloud でアプリケーションを再起動

3. **ログ確認**:
   - Cloud ログで以下が表示されることを確認:
     ```
     [DB INIT] skip schema verification (postgres cloud, normal operation)
     [DB INIT] connection check: OK
     ```

4. **動作確認**:
   - 正常に画像が表示されることを確認（マイグレーションが反映されている）
   - スキーマドリフト検知が動作していることを確認（キャッシュは60秒TTL）

#### スキーマ検証時（VERIFY_SCHEMA_ON_START=1）

1. **Secrets設定**:
   ```
   MIGRATE_ON_START=0
   VERIFY_SCHEMA_ON_START=1
   DEBUG=1  # オプション
   ```

2. **Reboot**:
   - Streamlit Cloud でアプリケーションを再起動

3. **ログ確認**:
   - Cloud ログでスキーマ検証が実行されることを確認
   - `pg_catalog` への大量の問い合わせが発生しないことを確認（`information_schema.columns` を使用）

## 設計方針

### Phase1（現在）

- `images.kind` 列を nullable で追加
- 既存データを backfill（`image_type` から `kind` へ移行、無ければ `'primary'`）
- 一意制約は将来追加（Phase2）

### Phase2（将来）

- `images.kind` 列に NOT NULL 制約を追加
- 一意制約（`material_id`, `kind`）を追加

## トラブルシューティング

### マイグレーションが実行されない

- `MIGRATE_ON_START=1` が正しく設定されているか確認
- Alembic の revision が正しく作成されているか確認
- Cloud ログでエラーメッセージを確認
- `RuntimeError: DATABASE_URL is not set` が表示される場合:
  - Streamlit Secrets に `connections.materialbase_db.url` または `DATABASE_URL` が設定されているか確認
  - `DATABASE_URL` 環境変数の設定は不要です（Streamlit Secrets のみで動作します）
  - `database.py` が `alembic_cfg.set_main_option("sqlalchemy.url", db_url)` を正しく設定しているか確認
- `[DB INIT] Alembic migration end: FAILED` が表示される場合:
  - ログの詳細なエラーメッセージを確認
  - データベース接続が正しく設定されているか確認

### スキーマ不整合が検知されない

- `VERIFY_SCHEMA_ON_START=1` を設定してスキーマ検証を実行
- `DEBUG=1` を設定して詳細ログを確認

### 安全モードが動作しない

- `get_all_materials()` で `images_kind_exists` が正しく検知されているか確認
- スキーマチェック関数が正しく動作しているか確認
