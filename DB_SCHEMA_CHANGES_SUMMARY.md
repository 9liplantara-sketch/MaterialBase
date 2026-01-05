# DBスキーマ変更サマリー: S3画像URL対応

## 変更内容

### 1. Imageテーブル
- ✅ `url` (String(1000), nullable) - **新規追加**: S3 URL
- ✅ `file_path` (String(500), nullable) - **変更**: nullableに変更（既存データは保持）

### 2. Materialテーブル
- ✅ `texture_image_url` (String(1000), nullable) - **新規追加**: テクスチャ画像URL
- ✅ `texture_image_path` (String(500), nullable) - **既存**: 後方互換のため保持

### 3. UseExampleテーブル
- ✅ `image_url` (String(1000), nullable) - **新規追加**: 画像URL
- ✅ `image_path` (String(500), nullable) - **既存**: 後方互換のため保持

### 4. ProcessExampleImageテーブル
- ✅ `image_url` (String(1000), nullable) - **新規追加**: 画像URL
- ✅ `image_path` (String(500), nullable) - **変更**: nullableに変更（既存データは保持）

## マイグレーション実行方法

### 自動マイグレーション（推奨）

```python
from database import init_db

# データベース初期化（既存テーブルは保持、カラムのみ追加）
init_db()
```

`init_db()`を実行すると、既存のデータベースに対して以下のALTER TABLEが自動実行されます：

- `ALTER TABLE images ADD COLUMN url VARCHAR(1000);`
- `ALTER TABLE materials ADD COLUMN texture_image_url VARCHAR(1000);`
- `ALTER TABLE use_examples ADD COLUMN image_url VARCHAR(1000);`
- `ALTER TABLE process_example_images ADD COLUMN image_url VARCHAR(1000);`

### 手動マイグレーション

既存のデータベースがある場合、以下のSQLを実行：

```sql
-- Imageテーブルにurlカラムを追加
ALTER TABLE images ADD COLUMN url VARCHAR(1000);

-- Materialテーブルにtexture_image_urlカラムを追加
ALTER TABLE materials ADD COLUMN texture_image_url VARCHAR(1000);

-- UseExampleテーブルにimage_urlカラムを追加
ALTER TABLE use_examples ADD COLUMN image_url VARCHAR(1000);

-- ProcessExampleImageテーブルにimage_urlカラムを追加
ALTER TABLE process_example_images ADD COLUMN image_url VARCHAR(1000);
```

## 画像参照の優先順位

**「URLがある場合はURL優先、URLがない場合は従来のローカルパス表示」**

### 実装例（次のステップで実装）

```python
def get_image_url(file_path: Optional[str] = None, url: Optional[str] = None) -> Optional[str]:
    """
    画像URLを取得（S3優先、フォールバックでローカルパス）
    
    Args:
        file_path: ローカルパス（後方互換）
        url: S3 URL（優先）
    
    Returns:
        画像URL（S3 URL または ローカルパス）
    """
    # 1. S3 URLが存在する場合はそれを返す
    if url:
        return url
    
    # 2. ローカルパスの場合、相対パスをそのまま返す
    if file_path:
        return file_path
    
    return None
```

## 後方互換性

- ✅ **既存の`file_path`/`image_path`カラムは保持**: 既存データはそのまま動作
- ✅ **新規データからS3 URLを使用**: 移行期間中は両方のカラムに値を保存可能
- ✅ **段階的移行**: 既存データは後で移行スクリプトで一括移行

## Materialの主画像参照

Materialの主画像は既に`Image`テーブルを通して参照しているため、`Image.url`を追加すれば対応完了：

```python
# 既存のコード（app.py, main.py）
primary_image = material.images[0] if material.images else None
primary_image_path = primary_image.file_path if primary_image else None

# 変更後（utils/image_url.pyを使用）
from utils.image_url import get_image_url
primary_image_url = get_image_url(
    file_path=primary_image.file_path,
    url=primary_image.url
) if primary_image else None
```

## 注意事項

1. **SQLiteの制限**: SQLiteでは`ALTER COLUMN`が直接できないため、`file_path`の`nullable`変更は新しいテーブル作成＋移行が必要。ただし、既存データに影響を与えないため、カラム追加のみで対応。

2. **既存データの保護**: 既存の`file_path`/`image_path`データは削除せず、そのまま保持します。

3. **主画像参照**: Materialの主画像は`Image`テーブルを通して参照するため、`Image.url`を追加すれば対応完了。

## 次のステップ

1. ✅ **スキーマ変更完了** - このファイル
2. ⏳ **`utils/image_url.py`を作成** - 統一URL解決関数
3. ⏳ **既存の画像表示関数を`get_image_url()`経由に変更**
4. ⏳ **S3アップロード機能の実装**

