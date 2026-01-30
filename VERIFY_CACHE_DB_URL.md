# db_url キャッシュキー検証手順

## 目的
`@st.cache_data` 関数のキャッシュキーに `db_url` が含まれ、DB切替時にキャッシュが混ざらないことを確認する。

## 検証手順

### 1. 関数定義の確認（db_url 引数があるか）

```bash
# 対象関数が db_url 引数を持つことを確認
grep -n "def get_material_image_url_cached\|def get_all_materials" app.py | grep "db_url"
```

**期待結果**:
```
406:def get_material_image_url_cached(db_url: str, material_id: int, updated_at_str: str = None) -> Optional[str]:
1242:def get_all_materials(db_url: str, include_unpublished: bool = False, include_deleted: bool = False):
```

### 2. 呼び出し側の確認（db_url を渡しているか）

```bash
# 呼び出し側が db_url を渡していることを確認
grep -n "get_material_image_url_cached(\|get_all_materials(" app.py | grep -v "^[0-9]*:def " | grep -v "db_url"
```

**期待結果**: 
- `get_material_image_url_cached(` の呼び出しはすべて `db_url` を含む
- `get_all_materials(` の呼び出しはすべて `db_url` を含む
- 出力が空（すべて `db_url` を含んでいる）であること

```bash
# より詳細な確認（呼び出し箇所を表示）
grep -n "get_material_image_url_cached(\|get_all_materials(" app.py | grep -v "^[0-9]*:def "
```

**期待結果例**:
```
487:    return get_material_image_url_cached(db_url, material_id, updated_at_str)
1847:                            materials = get_all_materials(db_url)
2577:            materials = get_all_materials(db_url)
2584:                retry_fn=lambda: get_all_materials(db_url)
3888:        materials = get_all_materials(db_url, include_unpublished=include_unpublished)
3892:            retry_fn=lambda: get_all_materials(db_url, include_unpublished=include_unpublished),
```

### 3. 動作確認（db_url 切り替えテスト）

#### 3-1. SQLite → PostgreSQL 切り替えテスト

**手順**:

1. **SQLite で起動（キャッシュを生成）**:
   ```bash
   # DATABASE_URL を未設定にして SQLite フォールバックを使用
   unset DATABASE_URL
   streamlit run app.py
   ```
   - アプリ起動後、材料一覧や画像を表示してキャッシュを生成
   - ブラウザで材料一覧を表示（`get_all_materials` のキャッシュ生成）
   - 画像を表示（`get_material_image_url_cached` のキャッシュ生成）

2. **PostgreSQL に切り替え（キャッシュが分離されることを確認）**:
   ```bash
   # PostgreSQL URL を設定して起動
   export DATABASE_URL="postgresql://user:pass@host:5432/dbname?sslmode=require"
   streamlit run app.py
   ```
   - アプリ起動後、同じ材料一覧や画像を表示
   - **期待動作**: SQLite のキャッシュが使われず、PostgreSQL から新しくデータを取得する
   - キャッシュが分離されているため、SQLite のデータが表示されない（または PostgreSQL のデータが表示される）

3. **SQLite に戻す（再度キャッシュが分離されることを確認）**:
   ```bash
   unset DATABASE_URL
   streamlit run app.py
   ```
   - **期待動作**: PostgreSQL のキャッシュが使われず、SQLite から新しくデータを取得する

#### 3-2. PostgreSQL URL 切り替えテスト（2つの異なるDB）

**手順**:

1. **PostgreSQL DB-A で起動**:
   ```bash
   export DATABASE_URL="postgresql://user:pass@host-a:5432/dbname?sslmode=require"
   streamlit run app.py
   ```
   - 材料一覧や画像を表示してキャッシュを生成

2. **PostgreSQL DB-B に切り替え**:
   ```bash
   export DATABASE_URL="postgresql://user:pass@host-b:5432/dbname?sslmode=require"
   streamlit run app.py
   ```
   - **期待動作**: DB-A のキャッシュが使われず、DB-B から新しくデータを取得する

#### 3-3. 簡易確認方法（キャッシュクリアなしで切り替え）

**注意**: Streamlit のキャッシュはプロセス内で保持されるため、同じプロセスで `DATABASE_URL` を変更してもキャッシュは分離されません。**プロセスを再起動**する必要があります。

**確認ポイント**:
- `db_url` が異なる場合、`@st.cache_data` のキャッシュキーが異なるため、自動的に別キャッシュとして扱われる
- プロセス再起動後、異なる `db_url` では古いキャッシュが当たらない

### 4. 検証コマンド一覧

```bash
# 1. 関数定義確認
echo "=== 関数定義確認 ==="
grep -n "^def get_material_image_url_cached\|^def get_all_materials" app.py

# 2. 呼び出し側確認（db_url を含まない呼び出しがないか）
echo "=== 呼び出し側確認（db_url なしの呼び出しを検出、内部実装を除外） ==="
grep -n "get_material_image_url_cached(\|get_all_materials(" app.py | grep -v "^[0-9]*:def " | grep -v "_get_all_materials" | grep -v "db_url" || echo "OK: すべての呼び出しに db_url が含まれています"

# 3. すべての呼び出し箇所を表示（内部実装を除外）
echo "=== すべての呼び出し箇所（外部呼び出しのみ） ==="
grep -n "get_material_image_url_cached(\|get_all_materials(" app.py | grep -v "^[0-9]*:def " | grep -v "_get_all_materials"

# 4. 現在の DATABASE_URL 確認
echo "=== 現在の DATABASE_URL ==="
echo "DATABASE_URL=${DATABASE_URL:-未設定（SQLiteフォールバック）}"
```

### 5. 期待される動作

- ✅ `db_url` が異なる場合、キャッシュキーが異なるため、別キャッシュとして扱われる
- ✅ SQLite (`sqlite:///./materials.db`) と PostgreSQL (`postgresql://...`) でキャッシュが分離される
- ✅ 異なる PostgreSQL URL でもキャッシュが分離される
- ✅ プロセス再起動後、異なる `db_url` では古いキャッシュが当たらない

### 6. トラブルシューティング

**Q: キャッシュが分離されない**
- A: Streamlit のキャッシュはプロセス内で保持されます。`DATABASE_URL` を変更したら**必ずプロセスを再起動**してください。

**Q: キャッシュが残っているように見える**
- A: Streamlit のキャッシュは `st.cache_data.clear()` でクリアできますが、この検証では `db_url` の違いで自動的に分離されることを確認するため、キャッシュクリアは不要です。

**Q: どのようにキャッシュが分離されたことを確認できるか**
- A: 異なる `db_url` で起動し、データが異なる（または存在しない）ことを確認します。同じデータが表示される場合は、キャッシュが混ざっている可能性があります。
