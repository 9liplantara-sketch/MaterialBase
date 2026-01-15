# スキーマドリフト安全モード - 漏れ確認結果

## 確認日時
2026-01-15

## 確認対象
`Material.images` relationship を eager load または直接アクセスしている箇所

## 確認結果

### ✅ 安全モード対応済み

1. **`app.py:get_all_materials()`** (行1031-1053)
   - スキーマドリフト検知を実装
   - `images_kind_exists` が `False` の場合、`noload(Material.images)` を使用
   - ✅ 安全モードで動作

2. **`app.py:get_material_by_id()`** (行1122-1146)
   - スキーマドリフト検知を実装
   - `images_kind_exists` が `False` の場合、`noload(Material.images)` を使用
   - ✅ 安全モードで動作

3. **`app.py:fetch_materials_page_cached()`** (行948)
   - 一覧表示用のため、常に `noload(Material.images)` を使用
   - ✅ 安全モードで動作（常時）

### ⚠️ 直接アクセス（安全モード対応済み）

4. **`app.py:show_material_cards()`** (行3891-3897)
   - `material.images` に直接アクセス
   - 安全モードでは `noload` されているため、`material.images` は空のリスト
   - `hasattr` と `len` チェックで安全に処理
   - ✅ 安全モードで動作（空リストでエラーにならない）

5. **`app.py:show_material_detail_tabs()`** (行2650)
   - `get_material_image_ref()` を使用（DBからではなくファイルシステムから取得）
   - ✅ 安全モードでも動作（DBアクセス不要）

### 📝 その他のアクセス

6. **`main.py`** (FastAPI エンドポイント)
   - Streamlit アプリとは別のエンドポイント
   - 本件の対象外

## Material.images relationship の設定

**`database.py:194`**
```python
images = relationship("Image", back_populates="material", cascade="all, delete-orphan")
```

- `lazy` パラメータが指定されていないため、デフォルトの `lazy="select"` を使用
- 安全モードで `noload(Material.images)` を指定すれば、確実にオーバーライドされる
- ✅ 安全モードで確実に動作

## 結論

**すべての `Material.images` へのアクセスが安全モードに対応済み**

- Eager load 箇所: `get_all_materials()`, `get_material_by_id()` で安全モード対応
- 直接アクセス箇所: `show_material_cards()` で安全に処理（空リストでエラーにならない）
- ファイルシステムアクセス: `get_material_image_ref()` は DB アクセス不要

## 推奨事項

1. **新規コード追加時**: `Material.images` にアクセスする場合は、必ず安全モードを考慮する
2. **テスト**: スキーマ不整合時（`images.kind` が存在しない状態）でもアプリがクラッシュしないことを確認
3. **ログ**: 安全モード発動時は `[SCHEMA] missing column images.kind` ログが出力されることを確認
