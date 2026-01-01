# クイックスタートガイド

## 1. 環境セットアップ

```bash
# プロジェクトディレクトリに移動
cd "/Users/ta_rabo/Desktop/マテリアルの体系化と未来"

# 仮想環境の作成（推奨）
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# または
# venv\Scripts\activate  # Windows

# 依存パッケージのインストール
pip install -r requirements.txt
```

## 2. データベースの初期化

```bash
# サンプルデータの追加（オプション）
python init_sample_data.py
```

## 3. アプリケーションの起動

```bash
# 方法1: uvicornを使用（推奨）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 方法2: Pythonスクリプトから直接起動
python main.py
```

## 4. アクセス

ブラウザで以下のURLにアクセス：

- **ホームページ**: http://localhost:8000
- **材料一覧**: http://localhost:8000/materials
- **API ドキュメント**: http://localhost:8000/api/docs
- **インタラクティブAPI**: http://localhost:8000/api/redoc

## 5. 基本的な使い方

### 5.1 材料の登録（API経由）

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

### 5.2 素材カードの表示

材料を登録した後、以下のURLで素材カードを表示できます：

```
http://localhost:8000/api/materials/{material_id}/card
```

例：材料IDが1の場合
```
http://localhost:8000/api/materials/1/card
```

### 5.3 画像のアップロード

```bash
curl -X POST "http://localhost:8000/api/materials/1/images" \
  -F "file=@/path/to/image.jpg" \
  -F "image_type=sample" \
  -F "description=材料サンプル写真"
```

## 6. サンプルデータ

`init_sample_data.py`を実行すると、以下のサンプル材料が登録されます：

1. **ステンレス鋼 SUS304** - 金属
2. **アルミニウム合金 A5052** - 金属
3. **ポリエチレン (PE)** - プラスチック
4. **アルミナセラミック** - セラミック

## 7. トラブルシューティング

### ポートが既に使用されている場合

```bash
# 別のポートを指定
uvicorn main:app --reload --port 8001
```

### データベースエラー

データベースファイル（`materials.db`）を削除して再初期化：

```bash
rm materials.db
python init_sample_data.py
```

### 画像が表示されない

- `uploads/`ディレクトリが存在することを確認
- 画像ファイルのパスが正しいことを確認
- ファイルの読み取り権限を確認

## 8. 次のステップ

1. **カスタマイズ**: `card_generator.py`で素材カードのデザインを変更
2. **機能追加**: `main.py`に新しいAPIエンドポイントを追加
3. **LLM統合**: `llm_integration.py`を実装してAI機能を追加
4. **データ拡張**: より多くの材料データを追加

## 9. 参考資料

- [FastAPI ドキュメント](https://fastapi.tiangolo.com/)
- [SQLAlchemy ドキュメント](https://docs.sqlalchemy.org/)
- [プロジェクトアウトライン](OUTLINE.md)

