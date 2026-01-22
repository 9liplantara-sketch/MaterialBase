# Phase 1: app.py巨大問題の根治 - 分割計画

## 現状
- app.py: 5770行
- 主要ページ関数が1ファイルに集約されている
- 部分編集でインデントエラーが発生しやすい

## 分割方針

### 分割後の構造
```
app.py                    # ルーティングと共通初期化のみ（~500行目標）
pages/
  __init__.py
  home.py                 # show_home() と関連関数
  materials_list.py       # show_materials_list() と関連関数
  dashboard.py            # show_dashboard() と関連関数
  search.py               # show_search(), _render_material_search_card()
  admin/
    __init__.py
    approval.py           # show_approval_queue(), approve_submission(), _apply_not_null_defaults_for_approval()
    bulk_import.py         # show_bulk_import()
  submission.py           # show_submission_status()
  material_cards.py       # show_material_cards()
utils/
  (既存)
```

### 分割手順（段階的）

#### Step 1: pages/ディレクトリ作成と__init__.py
- `mkdir -p pages/admin`
- `touch pages/__init__.py pages/admin/__init__.py`

#### Step 2: 共通ユーティリティの確認
- app.pyの先頭にある共通関数（get_build_sha, is_debug, safe_url等）を確認
- これらは`utils/common.py`に移動するか、app.pyに残すか判断

#### Step 3: 各ページ関数を順次移動
1. `show_home()` → `pages/home.py`
2. `show_materials_list()` → `pages/materials_list.py`
3. `show_dashboard()` → `pages/dashboard.py`
4. `show_search()` → `pages/search.py`
5. `show_approval_queue()` → `pages/admin/approval.py`
6. `approve_submission()` → `pages/admin/approval.py`
7. `show_bulk_import()` → `pages/admin/bulk_import.py`
8. `show_submission_status()` → `pages/submission.py`
9. `show_material_cards()` → `pages/material_cards.py`

#### Step 4: app.pyのルーティング部分を更新
- `main()`内のページルーティングを更新
- 各ページ関数を`from pages.xxx import show_xxx`でインポート

#### Step 5: 依存関係の整理
- 各ページファイルが必要なimportを追加
- 循環参照を避ける

### 注意事項
- 各ステップで`bash scripts/compile_check.sh`を実行
- 動作を変えずに移動（リファクタリングは後で）
- 見出しコメント境界でブロック置換

### 成功条件
- app.pyが500行以下になる
- 各ページファイルが独立している
- Streamlit Cloudで同じUIが出る（見た目同等）
