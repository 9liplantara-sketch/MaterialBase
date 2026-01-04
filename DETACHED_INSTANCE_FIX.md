# DetachedInstanceError修正とサンプルデータ自動投入

## 修正内容

### 1. DetachedInstanceErrorの修正

#### 問題
- データベースセッションを閉じた後に`m.properties`にアクセスしようとしてエラーが発生
- `total_properties = sum(len(m.properties) for m in materials)`でエラー

#### 解決策A: Eager Load（先読み）
- `get_all_materials()`と`get_material_by_id()`で`selectinload`を使用してリレーションを先読み
- セッションを閉じた後でも`properties`にアクセス可能

```python
from sqlalchemy.orm import selectinload
from sqlalchemy import select

def get_all_materials():
    db = get_db()
    try:
        stmt = (
            select(Material)
            .options(
                selectinload(Material.properties),
                selectinload(Material.images),
                selectinload(Material.metadata_items),
            )
        )
        materials = db.execute(stmt).scalars().all()
        return materials
    finally:
        db.close()
```

#### 解決策B: SQLで直接カウント（より堅牢）
- `total_properties`の計算をSQLで直接実行
- 大量データでも高速で、セッション外アクセスを完全に回避

```python
from sqlalchemy import select, func

db = get_db()
try:
    total_properties = db.execute(select(func.count(Property.id))).scalar() or 0
finally:
    db.close()
```

### 2. サンプルデータの自動投入

#### 問題
- Streamlit Cloudでは`init_sample_data.py`が自動実行されない
- データベースが空の状態で起動する

#### 解決策
- `ensure_sample_data()`関数を追加
- アプリ起動時に材料数が0件の場合、自動的にサンプルデータを投入

```python
def ensure_sample_data():
    """サンプルデータが存在しない場合、自動投入"""
    db = get_db()
    try:
        count = db.execute(select(func.count(Material.id))).scalar() or 0
        if count == 0:
            from init_sample_data import init_sample_data
            init_sample_data()
            st.info("📦 サンプルデータを自動投入しました。ページをリロードしてください。")
    except Exception as e:
        st.error(f"サンプルデータの投入中にエラーが発生しました: {e}")
    finally:
        db.close()
```

## 修正したファイル

- `app.py`:
  - `get_all_materials()`: Eager Loadを追加
  - `get_material_by_id()`: Eager Loadを追加
  - `total_properties`の計算をSQLで直接実行（2箇所）
  - `ensure_sample_data()`関数を追加
  - `main()`の最初で`ensure_sample_data()`を呼び出し

## 動作確認

1. アプリ起動時に自動的にサンプルデータが投入される
2. `DetachedInstanceError`が発生しない
3. サイドバーの統計情報が正常に表示される
4. ダッシュボードの統計情報が正常に表示される

## デプロイ手順

```bash
git add app.py
git commit -m "Fix DetachedInstanceError and auto-seed sample data"
git push origin main
```

その後、Streamlit Cloudで：
1. Manage app → Reboot
2. アプリを開いてサンプルデータが表示されることを確認


