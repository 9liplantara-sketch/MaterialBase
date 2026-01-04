# 1/4アップデート内容 - 技術的処理の骨子

## STEP 3: 元素データの実装（権利安全）

### 処理概要
118元素すべてのデータをJSON形式で実装し、周期表ページで表示できるようにする。

### 実装した処理

#### 1. 元素データJSONファイルの生成
- **処理**: `generate_elements_json.py`スクリプトを作成
- **内容**: 118元素すべての基本データをPython辞書として定義
- **データ構造**: 
  ```python
  {
    "atomic_number": int,
    "symbol": str,
    "name_ja": str,
    "name_en": str,
    "group": str,  # 分類（非金属、金属など）
    "period": int,
    "state": str,  # 気体、液体、固体
    "notes": str,
    "sources": [{"name": "Wikidata", "license": "CC0", "url": "..."}]
  }
  ```
- **出力**: `data/elements.json`（UTF-8、JSON形式）

#### 2. 周期表UIの実データ対応
- **処理**: `periodic_table_ui.py`を更新
- **変更点**:
  - ダミーデータ（`DUMMY_ELEMENTS`）を削除
  - `load_elements_data()`関数を追加（`@st.cache_data`でキャッシュ）
  - JSONファイルから元素データを読み込む処理を実装
  - `get_element_by_atomic_number()`, `get_element_by_symbol()`, `get_element_by_name()`を実データ対応に変更

#### 3. 出典情報の表示
- **処理**: `render_element_detail_panel()`を更新
- **内容**: 各元素の出典情報（Wikidata CC0）を表示

### 技術的ポイント
- **権利安全性**: すべてのデータの出典をWikidata (CC0)に統一
- **キャッシュ**: Streamlitの`@st.cache_data`でパフォーマンス最適化
- **エラーハンドリング**: JSON読み込みエラー時のフォールバック処理

---

## STEP 4: 元素カード画像の生成（自前）

### 処理概要
118元素すべてに自前生成画像を用意し、抽象的・図形的な表現で元素を視覚化する。

### 実装した処理

#### 1. 元素画像生成関数の実装
- **処理**: `image_generator.py`に元素画像生成機能を追加
- **関数**: `generate_element_image(symbol, atomic_number, group, size, output_dir)`
- **生成ロジック**:
  1. 元素分類に応じた背景色を取得（`get_element_group_color()`）
  2. PILで400x400のRGB画像を作成
  3. 抽象的装飾を追加:
     - 円形のグラデーション（中心から外側へ）
     - 幾何学的な対角線
  4. 元素記号を中心に配置（フォントサイズ: 画像サイズの1/4）
  5. 原子番号を左上に小さく表示（フォントサイズ: 元素記号の1/3）
  6. WebP形式で保存（品質90）

#### 2. 元素分類別の色マッピング
- **処理**: `get_element_group_color(group)`関数を実装
- **色定義**:
  - 非金属: (144, 238, 144) - ライトグリーン
  - 金属: (255, 182, 193) - ライトピンク
  - 半金属: (221, 160, 221) - プラム
  - ハロゲン: (255, 215, 0) - ゴールド
  - 貴ガス: (135, 206, 235) - スカイブルー
  - その他: 分類ごとに色を定義

#### 3. 自動生成機能
- **処理**: `ensure_element_image()`関数を実装
- **ロジック**:
  1. 既存画像の存在チェック（`element_{atomic_number}_{symbol}.webp`）
  2. 存在しない場合、`generate_element_image()`を呼び出し
  3. 生成された画像のパスを返す

#### 4. 一括生成機能
- **処理**: `generate_all_element_images()`関数を実装
- **ロジック**:
  1. `data/elements.json`から118元素すべてを読み込み
  2. 各元素に対して`ensure_element_image()`を実行
  3. 成功/失敗をログ出力

#### 5. 周期表UIでの画像表示
- **処理**: `periodic_table_ui.py`を更新
- **追加機能**:
  - `get_element_image_path()`: 元素画像のパスを取得（存在しない場合は生成）
  - `render_element_detail_panel()`: 元素詳細パネルに画像を表示

### 技術的ポイント
- **PIL/Pillow**: 画像生成に使用
- **フォント**: システムフォント（Helvetica/Arial）を試行、フォールバックでデフォルトフォント
- **色の整数変換**: PILの`draw.ellipse()`などで使用する色は整数タプルに変換
- **パス処理**: 相対パスと絶対パスの両方に対応

---

## STEP 5: 材料カードを「3タブ構造」にする

### 処理概要
材料詳細表示を3つのタブに分割し、情報を整理して表示する。

### 実装した処理

#### 1. 3タブ構造モジュールの作成
- **処理**: `material_detail_tabs.py`を新規作成
- **関数構成**:
  - `show_material_detail_tabs(material)`: メイン関数、Streamlitの`st.tabs()`を使用
  - `show_properties_tab(material)`: タブ1 - 材料物性
  - `show_procurement_uses_tab(material)`: タブ2 - 入手先・用途
  - `show_history_story_tab(material)`: タブ3 - 歴史・物語

#### 2. JSONフィールドのパース処理
- **処理**: `parse_json_field(field_value)`関数を実装
- **ロジック**:
  1. `json.loads()`でJSON文字列をパース
  2. リストの場合はそのまま返す
  3. 文字列の場合はリストに変換
  4. パースエラー時は空リストを返す

#### 3. タブ1: 材料物性の表示処理
- **処理**: `show_properties_tab()`
- **表示内容**:
  1. 基本特性を3カラムで表示（色、透明性、硬さ、重さ感、比重、耐水性、耐熱性、耐候性）
  2. 物性データをPandas DataFrameで表示
  3. 物性データをカード形式でも表示（3カラムグリッド）
  4. 加工・実装条件を2カラムで表示

#### 4. タブ2: 入手先・用途の表示処理
- **処理**: `show_procurement_uses_tab()`
- **表示内容**:
  1. 入手先情報（供給元、調達性、コスト帯）
  2. 参照URL（`ReferenceURL`テーブルから取得、リレーションが無い場合は直接クエリ）
  3. 主な用途カテゴリをバッジ形式で表示（4カラムグリッド）
  4. 用途例（`UseExample`テーブルから取得）
  5. 用途イメージ画像（材料の画像を3カラムグリッドで表示）

#### 5. タブ3: 歴史・物語の表示処理
- **処理**: `show_history_story_tab()`
- **表示内容**:
  1. 開発背景・ストーリー（開発動機、開発背景、開発ストーリー）
  2. デザイン視点での特徴（触感、視覚、音・匂い、加工性）
  3. 関連材料
  4. NG用途

#### 6. 材料一覧ページの更新
- **処理**: `app.py`の`show_materials_list()`を更新
- **変更点**:
  1. 詳細表示モードを追加（`selected_material_id`で制御）
  2. 「詳細を見る」ボタンで詳細表示に遷移
  3. 「一覧に戻る」ボタンで一覧表示に戻る
  4. 詳細表示時は`show_material_detail_tabs()`を呼び出し

#### 7. 素材カードページの更新
- **処理**: `app.py`の`show_material_cards()`を更新
- **変更点**:
  1. 材料選択後に`show_material_detail_tabs()`を呼び出し
  2. 3タブ構造で詳細表示
  3. 印刷用カードは従来通り表示

### 技術的ポイント
- **エラーハンドリング**: すべてのフィールドで存在チェック（`hasattr()`, `getattr()`）
- **データベースリレーション**: リレーションが読み込まれていない場合の直接クエリ対応
- **フィールド名のバリエーション**: `prototype_difficulty` / `prototyping_difficulty`の両方に対応
- **後方互換性**: 旧フィールド（`name`, `category`）と新フィールド（`name_official`, `category_main`）の両方に対応

---

## STEP 6: 材料 × 元素のマッピング（最小実装）

### 処理概要
材料に主要元素リストを持たせ、周期表ページで材料を選択すると含まれる元素をハイライト表示する。

### 実装した処理

#### 1. データベーススキーマの拡張
- **処理**: `database.py`の`Material`クラスにフィールドを追加
- **追加フィールド**: `main_elements = Column(Text)`
- **データ形式**: JSON文字列（原子番号の配列、例: `[1, 6, 8]`）

#### 2. 材料登録フォームの拡張
- **処理**: `material_form_detailed.py`の`show_layer1_form()`を更新
- **追加内容**:
  1. 「主要元素リスト」セクションを追加（レイヤー①の最後）
  2. テキスト入力欄で原子番号をカンマ区切りで入力
  3. 入力値のバリデーション:
     - カンマ区切りで分割
     - 整数に変換
     - 1-118の範囲に制限
  4. JSON文字列に変換して`form_data['main_elements']`に保存
- **保存処理**: `save_material_data()`で`main_elements`フィールドに保存

#### 3. 周期表UIの材料選択機能
- **処理**: `periodic_table_ui.py`の`show_periodic_table()`を更新
- **追加内容**:
  1. 材料選択ドロップダウンを追加（ページ上部）
  2. `get_all_materials()`で材料一覧を取得
  3. 選択された材料の`main_elements`をJSONパース
  4. 原子番号のセット（`highlighted_elements`）を作成
  5. セッションステート（`selected_material_id_for_elements`）で管理

#### 4. 周期表のハイライト表示処理
- **処理**: 周期表レンダリング関数を更新
- **変更点**:
  1. `render_periodic_table()`: `highlighted_elements`パラメータを追加
  2. `render_period_row()`: `highlighted_elements`パラメータを追加
  3. `render_f_block()`: `highlighted_elements`パラメータを追加
  4. `render_element_cell()`: `is_highlighted`パラメータを追加
- **ハイライトスタイル**:
  - 青い枠: `2px solid #667eea`
  - 影: `box-shadow: 0 0 8px 2px rgba(102, 126, 234, 0.6)`
  - 選択状態（金色）とハイライト状態（青い枠）の優先順位を実装

#### 5. 選択材料情報の表示
- **処理**: 周期表ページの右側パネルを更新
- **表示内容**:
  1. 選択中の材料名
  2. 含まれる主要元素数
  3. 元素リスト（元素記号と日本語名）

### 技術的ポイント
- **JSONパース**: `json.loads()`で文字列を配列に変換、エラーハンドリングを実装
- **セット操作**: `highlighted_elements`を`set`型で管理（高速な`in`演算）
- **状態管理**: Streamlitのセッションステートで選択状態を管理
- **視覚的フィードバック**: CSSでハイライト表示（枠線と影）
- **優先順位**: 選択状態（金色）> ハイライト状態（青い枠）

---

## 共通の技術的処理

### 1. エラーハンドリング
- **パターン**: `try-except`ブロックでエラーを捕捉
- **フォールバック**: エラー時はデフォルト値や空データを返す
- **ユーザー通知**: `st.warning()`, `st.error()`, `st.info()`で通知

### 2. データの永続化
- **JSON形式**: 複雑なデータ構造をJSON文字列で保存（SQLiteのText型）
- **パース処理**: 読み込み時に`json.loads()`で復元
- **バリデーション**: 入力値の型チェックと範囲チェック

### 3. UIコンポーネント
- **Streamlitタブ**: `st.tabs()`でタブ構造を実装
- **カラムレイアウト**: `st.columns()`でグリッドレイアウト
- **カスタムCSS**: `st.markdown()`の`unsafe_allow_html=True`でスタイル適用

### 4. パフォーマンス最適化
- **キャッシュ**: `@st.cache_data`でデータ読み込みをキャッシュ
- **遅延読み込み**: 必要な時だけデータを読み込む
- **セット操作**: `set`型で高速な要素検索

---

## ファイル変更サマリー

### 新規作成ファイル
1. `data/elements.json` - 118元素データ
2. `generate_elements_json.py` - JSON生成スクリプト
3. `material_detail_tabs.py` - 3タブ構造モジュール
4. `static/images/elements/` - 118画像ファイル

### 更新ファイル
1. `database.py` - `main_elements`フィールド追加
2. `periodic_table_ui.py` - 実データ対応、材料選択機能、ハイライト表示
3. `image_generator.py` - 元素画像生成機能追加
4. `material_form_detailed.py` - 主要元素リスト入力欄追加
5. `app.py` - 材料一覧ページ、素材カードページの更新

