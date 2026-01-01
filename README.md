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
├── database.py          # データベースモデル
├── models.py            # Pydanticモデル
├── card_generator.py    # 素材カード生成
├── requirements.txt     # 依存パッケージ
├── OUTLINE.md          # プロジェクトアウトライン
├── README.md           # このファイル
├── materials.db        # SQLiteデータベース（自動生成）
└── uploads/            # アップロードされた画像（自動生成）
```

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

