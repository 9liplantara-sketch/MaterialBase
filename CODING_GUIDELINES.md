# コーディングガイドライン

## 変更時の注意事項

### 1. ブロック単位での置換
- ❌ 行番号指定での変更は避ける
- ✅ 該当関数/該当UIブロックを検索して「ブロック単位で置換」する
- 例:
  ```python
  # ❌ 悪い例: 行番号指定
  # 1434-1448行目を変更
  
  # ✅ 良い例: 関数/ブロック単位
  # show_layer1_form関数内のcategory_mainのselectboxブロックを変更
  ```

### 2. 構文検証
- 変更後は必ず `ast.parse` または `py_compile` を通す
- 検証コマンド:
  ```bash
  python -c "import ast; ast.parse(open('material_form_detailed.py', 'r', encoding='utf-8').read())"
  ```
  または
  ```bash
  python -m py_compile material_form_detailed.py
  ```

### 3. 既存仕様の維持
以下の仕様を壊さないこと:
- **touched gate**: 主要6項目（CORE_FIELDS）はユーザーが触った場合のみpayloadに含める
- **create seed禁止**: createモードではCORE_FIELDSをsession_stateにseedしない

### 主要な関数ブロック

#### コア関数
- `wkey(field, scope, material_id=None, submission_id=None)`: Widget key生成
- `mark_touched(key)`: touchedフラグを設定
- `extract_payload(scope, material_id=None, submission_id=None)`: payload抽出（touched gate実装）

#### フォーム表示関数
- `show_detailed_material_form(material_id=None)`: メインフォーム
- `show_layer1_form(existing_material=None, suffix="new")`: レイヤー①（必須情報）
- `show_layer2_form(existing_material=None, scope="create", material_id_for_wkey=None)`: レイヤー②（任意情報）

#### データ処理関数
- `material_to_form_data(material)`: Materialオブジェクトをフォームデータに変換
- `save_material(form_data, material_id=None)`: 材料データを保存
- `save_material_submission(form_data, uploaded_files=None, submitted_by=None)`: 投稿を保存

#### seed処理ブロック
- `show_detailed_material_form`内のseed処理（583-622行目付近）
  - `seed_widget`関数内でcreateモードのCORE_FIELDS seedを禁止

### UIブロックの例

#### category_mainのselectboxブロック
```python
# selectbox の index を計算（優先順: session_state > existing_material > デフォルト）
category_main_key = wkey("category_main", scope, material_id=material_id_for_wkey)
# current_value を優先順で取得: 1) session_state 2) edit時のexisting_material 3) None
current_value = st.session_state.get(category_main_key)
if current_value is None and existing_material:
    current_value = getattr(existing_material, 'category_main', None)
# index を計算（optionsに存在すればそのindex、なければ0にフォールバック）
if current_value and current_value in MATERIAL_CATEGORIES:
    category_main_index = MATERIAL_CATEGORIES.index(current_value)
    # editモードでsession_stateに無い場合は設定（createモードでは設定しない）
    if existing_material and category_main_key not in st.session_state:
        st.session_state[category_main_key] = current_value
else:
    # optionsに存在しない、またはcurrent_valueがNoneの場合は0にフォールバック
    category_main_index = 0
form_data['category_main'] = st.selectbox(
    "2-1 材料カテゴリ（大分類）*",
    MATERIAL_CATEGORIES,
    index=category_main_index,
    key=category_main_key,
    on_change=mark_touched,
    args=(category_main_key,),
)
```

### テスト実行
変更後は関連テストを実行:
```bash
python -m unittest tests.test_no_create_seed_core_fields -v
```
