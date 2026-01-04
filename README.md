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

### 2. アプリケーションの起動

```bash
python main.py
```

または

```bash
uvicorn main:app --reload
```

### 3. アクセス

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
- **images**: 画像情報
- **metadata**: メタデータ

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

