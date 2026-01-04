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

## 今後の拡張予定

1. PDF形式での素材カード出力
2. LLM統合（自然言語検索、材料推奨）
3. ベクトルデータベースによる類似材料検索
4. 高度な可視化機能
5. データインポート/エクスポート機能

## ライセンス

このプロジェクトはプロトタイプです。

