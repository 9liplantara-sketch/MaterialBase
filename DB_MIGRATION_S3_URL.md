# データベースマイグレーション: S3画像URL対応

## 変更内容

### スキーマ変更

以下のカラムを追加しました（既存カラムは保持、後方互換性を維持）：

1. **`Image`テーブル**
   - `url` (String(1000), nullable) - S3 URL（新規追加）
   - `file_path` (String(500), nullable) - ローカルパス（既存、後方互換）

2. **`Material`テーブル**
   - `texture_image_url` (String(1000), nullable) - テクスチャ画像URL（新規追加）
   - `texture_image_path` (String(500), nullable) - テクスチャ画像パス（既存、後方互換）

3. **`UseExample`テーブル**
   - `image_url` (String(1000), nullable) - 画像URL（新規追加）
   - `image_path` (String(500), nullable) - 画像パス（既存、後方互換）

4. **`ProcessExampleImage`テーブル**
   - `image_url` (String(1000), nullable) - 画像URL（新規追加）
   - `image_path` (String(500), nullable) - 画像パス（既存、後方互換）

## マイグレーション手順

### 自動マイグレーション（推奨）

`init_db()`関数が自動的にカラムを追加します：

```python
from database import init_db

# データベース初期化（既存テーブルは保持、カラムのみ追加）
init_db()
```

### 手動マイグレーション（必要に応じて）

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

### 実装例

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

### 使用例

```python
# Imageテーブルの場合
image = db.query(Image).first()
image_url = get_image_url(file_path=image.file_path, url=image.url)

# Materialテーブルの場合
material = db.query(Material).first()
texture_url = get_image_url(
    file_path=material.texture_image_path,
    url=material.texture_image_url
)

# UseExampleテーブルの場合
use_example = db.query(UseExample).first()
use_image_url = get_image_url(
    file_path=use_example.image_path,
    url=use_example.image_url
)

# ProcessExampleImageテーブルの場合
process_image = db.query(ProcessExampleImage).first()
process_image_url = get_image_url(
    file_path=process_image.image_path,
    url=process_image.image_url
)
```

## 後方互換性

- **既存の`file_path`/`image_path`カラムは保持**: 既存データはそのまま動作
- **新規データからS3 URLを使用**: 移行期間中は両方のカラムに値を保存可能
- **段階的移行**: 既存データは後で移行スクリプトで一括移行

## 注意事項

1. **SQLiteの制限**: SQLiteでは`ALTER COLUMN`が直接できないため、`file_path`の`nullable`変更は新しいテーブル作成＋移行が必要。ただし、既存データに影響を与えないため、カラム追加のみで対応。

2. **既存データの保護**: 既存の`file_path`/`image_path`データは削除せず、そのまま保持します。

3. **主画像参照**: Materialの主画像は`Image`テーブルを通して参照するため、`Image.url`を追加すれば対応完了。

## 次のステップ

1. ✅ スキーマ変更完了
2. ⏳ `utils/image_url.py`を作成（統一URL解決関数）
3. ⏳ 既存の画像表示関数を`get_image_url()`経由に変更
4. ⏳ S3アップロード機能の実装

