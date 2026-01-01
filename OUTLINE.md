# マテリアルデータベース構築プロジェクト アウトライン

## 1. プロジェクト概要

### 1.1 目的
- 素材カード形式でマテリアル情報を視覚的に管理・表示するデータベースシステムの構築
- 将来的に物理的な材料サンプル、写真データ、材料物性を統合したLLM（Large Language Model）システムへの拡張

### 1.2 目標
- マテリアル情報の体系的な管理
- 視覚的な素材カードの自動生成
- 検索・フィルタリング機能
- 将来的なAI/LLM統合の基盤構築

## 2. システムアーキテクチャ

### 2.1 全体構成
```
┌─────────────────┐
│  フロントエンド  │ (React/HTML + CSS)
│  (素材カードUI)  │
└────────┬────────┘
         │
┌────────▼────────┐
│   Web API      │ (FastAPI)
│  (REST API)     │
└────────┬────────┘
         │
┌────────▼────────┐
│   データベース  │ (SQLite/PostgreSQL)
│  (マテリアル情報)│
└────────┬────────┘
         │
┌────────▼────────┐
│  画像ストレージ  │ (ローカル/クラウド)
│  (写真データ)    │
└─────────────────┘
```

### 2.2 将来のLLM統合
```
┌─────────────────┐
│   LLM Layer     │ (GPT/Claude等)
│  (材料分析・推論)│
└────────┬────────┘
         │
┌────────▼────────┐
│  Vector DB      │ (材料データの埋め込み)
│  (Embeddings)   │
└─────────────────┘
```

## 3. データモデル設計

### 3.1 マテリアルエンティティ
- **Material (材料)**
  - id: 一意ID
  - name: 材料名
  - category: カテゴリ（金属、プラスチック、セラミック等）
  - description: 説明
  - created_at, updated_at: タイムスタンプ

### 3.2 物性データ
- **Property (物性)**
  - id: 一意ID
  - material_id: 材料ID（外部キー）
  - property_name: 物性名（密度、引張強度、融点等）
  - value: 値
  - unit: 単位
  - measurement_condition: 測定条件

### 3.3 画像データ
- **Image (画像)**
  - id: 一意ID
  - material_id: 材料ID（外部キー）
  - file_path: ファイルパス
  - image_type: 画像タイプ（サンプル写真、顕微鏡画像等）
  - description: 説明

### 3.4 メタデータ
- **Metadata (メタデータ)**
  - id: 一意ID
  - material_id: 材料ID（外部キー）
  - key: キー
  - value: 値（JSON形式で柔軟に対応）

## 4. 機能要件

### 4.1 Phase 1: 基本機能（プロトタイプ）
1. **マテリアル登録**
   - 材料情報の入力
   - 物性データの登録
   - 画像のアップロード

2. **素材カード生成**
   - 材料情報を視覚的に表示
   - 物性データの可視化
   - 画像の表示

3. **検索・フィルタリング**
   - 材料名での検索
   - カテゴリでのフィルタリング
   - 物性値での範囲検索

4. **データ管理**
   - CRUD操作（作成、読み取り、更新、削除）
   - データのエクスポート/インポート

### 4.2 Phase 2: 拡張機能（将来）
1. **AI/LLM統合**
   - 材料の自然言語検索
   - 材料の推奨・提案
   - 物性データの予測
   - 材料の類似性分析

2. **高度な可視化**
   - 物性データのグラフ表示
   - 材料の比較機能
   - 3D可視化

3. **コラボレーション機能**
   - 複数ユーザー対応
   - コメント・アノテーション
   - バージョン管理

## 5. 技術スタック

### 5.1 バックエンド
- **言語**: Python 3.10+
- **フレームワーク**: FastAPI
- **データベース**: SQLite (プロトタイプ) → PostgreSQL (本番)
- **ORM**: SQLAlchemy
- **画像処理**: Pillow, OpenCV

### 5.2 フロントエンド
- **言語**: HTML, CSS, JavaScript
- **フレームワーク**: React (将来拡張) または Vanilla JS
- **UIライブラリ**: Tailwind CSS / Material-UI

### 5.3 LLM統合（将来）
- **LLM API**: OpenAI GPT, Anthropic Claude
- **ベクトルDB**: Chroma, Pinecone, Weaviate
- **埋め込みモデル**: OpenAI embeddings, Sentence Transformers

## 6. データベーススキーマ

```sql
-- 材料テーブル
CREATE TABLE materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 物性テーブル
CREATE TABLE properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    property_name VARCHAR(100) NOT NULL,
    value FLOAT,
    unit VARCHAR(50),
    measurement_condition TEXT,
    FOREIGN KEY (material_id) REFERENCES materials(id)
);

-- 画像テーブル
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    image_type VARCHAR(50),
    description TEXT,
    FOREIGN KEY (material_id) REFERENCES materials(id)
);

-- メタデータテーブル
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    key VARCHAR(100) NOT NULL,
    value TEXT,
    FOREIGN KEY (material_id) REFERENCES materials(id)
);
```

## 7. API設計

### 7.1 エンドポイント
- `GET /api/materials` - 材料一覧取得
- `GET /api/materials/{id}` - 材料詳細取得
- `POST /api/materials` - 材料作成
- `PUT /api/materials/{id}` - 材料更新
- `DELETE /api/materials/{id}` - 材料削除
- `GET /api/materials/{id}/card` - 素材カード生成
- `POST /api/materials/{id}/images` - 画像アップロード
- `GET /api/materials/search` - 材料検索

## 8. 素材カードデザイン

### 8.1 カード要素
- 材料名（大きく表示）
- カテゴリバッジ
- 代表画像
- 主要物性データ（表形式）
- 説明文
- QRコード（詳細ページへのリンク）

### 8.2 レイアウト
- カードサイズ: A4縦/横、またはカスタムサイズ
- レスポンシブデザイン対応
- PDF/PNG出力対応

## 9. 実装フェーズ

### Phase 1: プロトタイプ（1-2週間）
- [x] アウトライン作成
- [ ] データベーススキーマ実装
- [ ] バックエンドAPI実装
- [ ] 基本的なフロントエンド実装
- [ ] 素材カード生成機能

### Phase 2: 機能拡張（2-4週間）
- [ ] 高度な検索機能
- [ ] データインポート/エクスポート
- [ ] 画像処理機能の強化
- [ ] UI/UXの改善

### Phase 3: LLM統合（4-8週間）
- [ ] ベクトルデータベースの構築
- [ ] LLM API統合
- [ ] 自然言語検索機能
- [ ] 材料推奨機能

## 10. 将来の拡張アイデア

1. **材料サンプル管理**
   - 物理サンプルの在庫管理
   - サンプル貸出管理
   - サンプル状態の追跡

2. **実験データ連携**
   - 測定機器との連携
   - 実験データの自動取り込み
   - データ品質管理

3. **材料設計支援**
   - 材料選定支援
   - 物性予測モデル
   - 材料組成の最適化

4. **コラボレーション**
   - チーム間でのデータ共有
   - レビュー・承認ワークフロー
   - ナレッジベース構築

