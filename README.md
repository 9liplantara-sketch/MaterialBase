# マテリアルデータベース プロトタイプ

素材カード形式でマテリアル情報を管理するデータベースシステムのプロトタイプです。

## 機能

- マテリアル情報の登録・管理
- 物性データの登録
- 画像のアップロード
- 素材カードの自動生成（HTML形式）
- RESTful API
- Web UI

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. データベース設定

**ローカル開発（SQLite）:**
```bash
# 環境変数なしで起動 → SQLiteが自動使用
streamlit run app.py
```

**本番（Postgres必須）:**
Streamlit Secretsに以下を設定：

```toml
# .streamlit/secrets.toml（Cloud Secrets管理画面）
[connections.materialbase_db]
url = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

詳細は [`POSTGRES_MIGRATION.md`](POSTGRES_MIGRATION.md) を参照してください。

**重要**: Streamlit CloudではSQLiteは使用できません（リブートでデータが消えるため）。

### 2-1. Cloudflare R2 ストレージ設定（画像アップロード用）

**本番（R2必須）:**
Streamlit Secretsに以下を設定：

```toml
# Cloudflare R2 の認証情報
R2_ACCOUNT_ID = "your-account-id"
R2_ACCESS_KEY_ID = "your-access-key-id"
R2_SECRET_ACCESS_KEY = "your-secret-access-key"
R2_BUCKET = "your-bucket-name"
R2_PUBLIC_BASE_URL = "https://your-bucket.r2.dev"

# R2 アップロードを有効化（デフォルト: True）
ENABLE_R2_UPLOAD = "1"
```

**注意:**
- `R2_PUBLIC_BASE_URL` は R2 バケットの公開URL（例: `https://your-bucket.r2.dev`）
- seed中（`INIT_SAMPLE_DATA=1`, `SEED_SKIP_IMAGES=1`）では画像アップロードは自動的に無効化されます
- `ENABLE_R2_UPLOAD=0` に設定すると、画像アップロードが無効化されます（seed時は推奨）

### 3. Alembicマイグレーション（Postgres使用時）

```bash
# Alembic初期化（初回のみ）
alembic init alembic

# alembic/env.pyを設定（POSTGRES_MIGRATION.md参照）

# 初回マイグレーション作成
alembic revision --autogenerate -m "init schema"

# マイグレーション適用
alembic upgrade head
```

詳細は [`POSTGRES_MIGRATION.md`](POSTGRES_MIGRATION.md) を参照してください。

### 4. アプリケーションの起動

```bash
streamlit run app.py
```

または（FastAPIの場合）

```bash
python main.py
```

または

```bash
uvicorn main:app --reload
```

### 5. アクセス

- Web UI: http://localhost:8000
- API ドキュメント: http://localhost:8000/api/docs
- 材料一覧: http://localhost:8000/materials

## 使用方法

### API経由で材料を登録

```bash
curl -X POST "http://localhost:8000/api/materials" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ステンレス鋼 SUS304",
    "category": "金属",
    "description": "オーステナイト系ステンレス鋼",
    "properties": [
      {
        "property_name": "密度",
        "value": 7.93,
        "unit": "g/cm³"
      },
      {
        "property_name": "引張強度",
        "value": 520,
        "unit": "MPa"
      }
    ]
  }'
```

## 重複整理（安全運用）

同名（`name_official`）の重複材料を安全に整理するためのスクリプトが用意されています。
**デフォルトは dry-run** で、破壊的操作は行いません。

### 1) 棚卸し（dry-run）
```bash
python3 scripts/dedupe_materials.py --dry-run
```

出力: `reports/duplicates_report_YYYYMMDD.csv`

### 2) 1件だけ適用（安全な最小単位）
```bash
python3 scripts/dedupe_materials.py --apply --only-name "コンクリート"
```

### 3) 少数だけ適用（テスト用途）
```bash
python3 scripts/dedupe_materials.py --apply --limit 3
```

**注意事項**
- DROP/TRUNCATE など破壊的操作は行いません
- 重複側は `is_deleted=1` にして論理削除します
- 関連テーブルは canonical に付け替え、重複はスキップします

### 素材カードの表示

材料登録後、以下のURLで素材カードを表示できます：
- http://localhost:8000/api/materials/{material_id}/card

## プロジェクト構造

```
.
├── main.py              # FastAPIアプリケーション
├── app.py               # Streamlitアプリケーション
├── database.py          # データベースモデル
├── models.py            # Pydanticモデル
├── card_generator.py    # 素材カード生成
├── requirements.txt     # 依存パッケージ
├── OUTLINE.md          # プロジェクトアウトライン
├── README.md           # このファイル
├── materials.db        # SQLiteデータベース（自動生成）
├── uploads/            # アップロードされた画像（自動生成）
└── static/
    ├── generated/      # 生成物（起動時に自動生成、Git管理外）
    │   ├── elements/   # 元素画像
    │   └── process_examples/  # 加工例画像
    └── images/         # 静的画像ファイル
```

## 生成物の管理方針

本プロジェクトでは、以下の生成物（画像など）を起動時に自動生成します：

- **元素画像** (`static/generated/elements/`): 周期表で使用する元素カード画像
- **加工例画像** (`static/generated/process_examples/`): 加工方法の説明画像

これらの生成物は：
- **Git管理外** (`.gitignore`に`static/generated/`を追加)
- **起動時に自動生成** (`app.py`の`main()`関数で`ensure_all_assets()`を呼び出し)
- **不足分のみ生成** (既存ファイルはスキップ、0バイトファイルや壊れたファイルは再生成)

Streamlit Cloudでは再起動時に一時ファイルが消える可能性があるため、起動時に必ず再生成できる設計になっています。

### 診断モード

サイドバーの「🔍 Asset診断モード」をONにすると、生成物の存在状況を確認できます：
- 総数 / 存在数 / 生成数 / 欠損数
- 欠損ファイル一覧
- 代表的な画像のプレビュー

## データベーススキーマ

- **materials**: 材料情報
- **properties**: 物性データ
- **images**: 画像情報（`file_path` + `url` カラムでS3対応）
- **metadata**: メタデータ
- **use_examples**: 用途例（`image_path` + `image_url` カラムでS3対応）
- **process_example_images**: 加工例画像（`image_path` + `image_url` カラムでS3対応）

### S3画像URL対応

データベーススキーマにS3画像URL対応を追加しました：

- **`Image.url`**: S3 URL（優先）、`file_path`は後方互換のため保持
- **`Material.texture_image_url`**: テクスチャ画像URL（優先）、`texture_image_path`は後方互換のため保持
- **`UseExample.image_url`**: 用途写真URL（優先）、`image_path`は後方互換のため保持
- **`ProcessExampleImage.image_url`**: 加工例画像URL（優先）、`image_path`は後方互換のため保持

**画像参照の優先順位**: URLがある場合はURL優先、URLがない場合は従来のローカルパス表示

詳細は `DB_MIGRATION_S3_URL.md` を参照してください。

### S3ストレージ設定

画像ファイルをS3にアップロードする機能を実装しました。

**環境変数設定**:
- `S3_BUCKET`: S3バケット名（必須）
- `AWS_ACCESS_KEY_ID`: AWSアクセスキー（必須）
- `AWS_SECRET_ACCESS_KEY`: AWSシークレットキー（必須）
- `AWS_REGION`: AWSリージョン（デフォルト: ap-northeast-1）
- `S3_ENDPOINT_URL`: MinIO等の互換S3エンドポイント（オプション）
- `S3_PUBLIC_BASE_URL`: CloudFront等のCDN URL（オプション）

**使用方法**:
```python
from utils.s3_storage import upload_file_to_s3

public_url = upload_file_to_s3(
    local_path="static/material_textures/1_aluminum.png",
    s3_key="material_textures/1_aluminum.png"
)
```

**Streamlit Cloudでの設定**: `.streamlit/secrets.toml`またはSecrets管理画面で環境変数を設定してください。

詳細は `S3_SETUP.md` を参照してください。

### Streamlit Cloudデプロイ

Streamlit Cloudへのデプロイ手順と検証チェックリストは `STREAMLIT_CLOUD_DEPLOY.md` を参照してください。

**主要な検証項目**:
- Build SHA表示の確認
- URL画像表示の確認（ローカルパスに依存しない）
- プレースホルダー表示の確認
- migrateスクリプトの動作確認

### 既存画像のS3移行

既存のローカル画像をS3に移行するバッチスクリプトを用意しました：

```bash
# ドライラン（アップロードしないで対象数だけ表示）
python scripts/migrate_images_to_s3.py --dry-run

# テスト実行（10件のみ）
python scripts/migrate_images_to_s3.py --limit 10

# 本番実行（全件移行）
python scripts/migrate_images_to_s3.py
```

**移行対象**:
- `Image`テーブル: 材料の汎用画像
- `Material.texture_image_path`: テクスチャ画像
- `UseExample.image_path`: 用途写真
- `ProcessExampleImage.image_path`: 加工例画像

**S3キー設計**:
- `materials/{material_id}/primary/{filename}` - 汎用画像
- `materials/{material_id}/textures/{filename}` - テクスチャ画像
- `materials/{material_id}/use_cases/{filename}` - 用途写真
- `materials/{material_id}/process_examples/{filename}` - 加工例画像

## 画像生成機能

### 概要

材料データベースの各材料について、以下の画像を自動生成できます：

- **テクスチャ画像** (1024x1024): 材料の表面テクスチャ
- **用途写真** (1280x720): 実際の使用例（内装/プロダクト等）
- **加工例画像** (1280x720): 加工プロセスの写真

### 画像生成の実行

#### 1. 環境変数の設定

使用する画像生成APIに応じて環境変数を設定：

```bash
# OpenAI DALL-E 3を使用する場合
export IMAGE_API_PROVIDER=openai
export OPENAI_API_KEY=your_api_key_here

# Stability AIを使用する場合
export IMAGE_API_PROVIDER=stability
export STABILITY_API_KEY=your_api_key_here
```

#### 2. 必要なライブラリのインストール

```bash
# OpenAI DALL-E 3の場合
pip install openai

# Stability AIの場合
pip install stability-sdk
```

#### 3. 画像生成スクリプトの実行

```bash
# テストモード（最初の3材料のみ）
python scripts/generate_images.py --test

# 特定の材料のみ生成
python scripts/generate_images.py --material-ids 1 2 3

# 全材料を生成（既存画像はスキップ）
python scripts/generate_images.py

# 既存画像も再生成
python scripts/generate_images.py --no-skip-existing
```

#### 4. 生成された画像の保存先

- テクスチャ画像: `static/material_textures/{material_id}_{slug}.png`
- 用途写真: `static/use_cases/{material_id}_{slug}.png`
- 加工例画像: `static/process_examples/{material_id}_{slug}.png`

これらのディレクトリは`.gitignore`で除外されているため、Git管理外です。

### 画像生成の仕様

- **形式**: PNG（RGB固定、透明は白背景に合成）
- **テクスチャ**: 1024x1024
- **用途/加工例**: 1280x720
- **命名規則**: `{material_id}_{slug}.png`
- **レート制限**: API呼び出し間隔2秒（環境変数`RATE_LIMIT_DELAY`で変更可能）
- **リトライ**: 最大3回（環境変数`MAX_RETRIES`で変更可能）

### プロンプトテンプレート

カテゴリ別に最適化されたプロンプトが自動生成されます：

- **木材**: 木目テクスチャ、自然光
- **金属**: 反射面、工業照明
- **樹脂**: 滑らかな表面、スタジオ照明
- **セラミック/ガラス**: 光沢/マット仕上げ

詳細は`scripts/prompt_templates.py`を参照してください。

### 運用手順

#### 初回セットアップ

1. 環境変数を設定（`.env`ファイルまたはシェルで設定）
2. 必要なライブラリをインストール
3. テストモードで動作確認

```bash
# テストモード（3材料のみ）
python scripts/generate_images.py --test
```

#### 本番実行

```bash
# 全材料の画像を生成（既存画像はスキップ）
python scripts/generate_images.py
```

#### トラブルシューティング

- **APIキーエラー**: 環境変数が正しく設定されているか確認
- **レート制限エラー**: `RATE_LIMIT_DELAY`を増やす（例: 5秒）
- **画像が生成されない**: APIプロバイダーの利用制限を確認
- **パスエラー**: `utils/paths.py`の`project_root()`が正しく動作しているか確認

### データベーススキーマ拡張

以下のフィールド/テーブルが追加されました：

- `materials.texture_image_path`: テクスチャ画像のパス
- `process_example_images`テーブル: 材料別の加工例画像
- `use_examples.image_path`: 用途写真のパス（既存、活用）

スキーマ拡張は`init_db()`実行時に自動的に適用されます（既存データベースにも安全にALTER）。

## 今後の拡張予定

1. PDF形式での素材カード出力
2. LLM統合（自然言語検索、材料推奨）
3. ベクトルデータベースによる類似材料検索
4. 高度な可視化機能
5. データインポート/エクスポート機能

## ライセンス

このプロジェクトはプロトタイプです。

