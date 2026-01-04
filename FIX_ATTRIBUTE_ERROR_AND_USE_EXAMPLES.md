# AttributeError解消と用途例画像表示の改善 - 修正サマリー

## 修正日: 2026年1月4日

## 問題
1. `material_detail_tabs.py`の`show_history_story_tab()`で`material.ng_uses_other`等の属性にアクセスしてAttributeErrorが発生
2. 用途例の出典表示が分かりにくい

## 実装した修正

### A. バグ修正：ng_uses_other等のAttributeError解消

#### 修正内容
- `show_history_story_tab()`で全ての属性を`getattr()`で安全にアクセスするように変更
- 修正した属性:
  - `development_motive_other` → `getattr(material, 'development_motive_other', None)`
  - `development_background_short` → `getattr(material, 'development_background_short', None)`
  - `development_story` → `getattr(material, 'development_story', None)`
  - `tactile_other` → `getattr(material, 'tactile_other', None)`
  - `visual_other` → `getattr(material, 'visual_other', None)`
  - `sound_smell` → `getattr(material, 'sound_smell', None)`
  - `aging_characteristics` → `getattr(material, 'aging_characteristics', None)`
  - `processing_knowhow` → `getattr(material, 'processing_knowhow', None)`
- `ng_uses_other`は既に`getattr()`で安全化済み（変更なし）

#### 効果
- 履歴/ストーリータブでAttributeErrorが発生しなくなる
- データベースにカラムが存在しない場合でもエラーで落ちない

### B. 代表用途の写真表示機能（既存実装の確認と改善）

#### 現状確認
- `UseExample`テーブルは既に存在し、以下のカラムを持つ:
  - `image_path`: 画像パス（相対パス）
  - `source_name`: 出典名（例: "Generated", "PhotoAC"）
  - `source_url`: 出典URL
  - `license_note`: ライセンス表記
- `utils/use_example_display.py`: 用途例画像表示モジュール（既存）
- `utils/use_example_image_generator.py`: 用途例画像生成モジュール（既存）
- `material_detail_tabs.py`: 用途例表示機能（既存実装済み）

#### 改善内容
1. **出典表示の改善**
   - 出典情報（source_name, source_url, license_note）を統合して1行で表示
   - より読みやすく、権利情報が明確に表示される

2. **ディレクトリの作成**
   - `static/uses/`: 用途画像保存用（git管理）
   - `uploads/uses/`: 用途画像保存用（生成・増殖用）

#### 既存機能の確認
- `show_procurement_uses_tab()`内で「代表的な使用例」セクションが既に実装済み
- 用途例はdomainごとにグループ化して表示
- 画像は`display_use_example_image()`で表示（健康状態チェック付き）
- 画像がない場合はプレースホルダー表示（黒画像は出さない）

## 変更ファイル

### 修正ファイル
1. **`material_detail_tabs.py`**
   - `show_history_story_tab()`: 全ての属性を`getattr()`で安全にアクセス
   - `show_procurement_uses_tab()`: 出典表示を改善

### 新規作成ファイル
1. **`static/uses/`** - 用途画像保存用ディレクトリ
2. **`uploads/uses/`** - 用途画像保存用ディレクトリ

### 既存ファイル（確認のみ）
1. **`utils/use_example_display.py`** - 用途例画像表示モジュール（既存）
2. **`utils/use_example_image_generator.py`** - 用途例画像生成モジュール（既存）
3. **`database.py`** - `UseExample`テーブル定義（既存、変更なし）

## 動作確認項目

- [x] 真鍮（黄銅）の詳細を開く → ストーリータブで落ちない
- [x] アルミの詳細を開く → 用途例（鍋/建築材）が画像付きで表示される
- [x] use_examples未登録の材料でも落ちない
- [x] 出典情報が正しく表示される

## 技術的詳細

### 安全な属性アクセスパターン
```python
# 修正前（危険）
if material.development_motive_other:
    st.markdown(f"**その他動機**: {material.development_motive_other}")

# 修正後（安全）
development_motive_other = getattr(material, 'development_motive_other', None)
if development_motive_other:
    st.markdown(f"**その他動機**: {development_motive_other}")
```

### 出典表示の改善
```python
# 修正前（複数行）
if source_name:
    if source_url:
        st.markdown(f"<small>[{source_name}]({source_url})</small>", ...)
    else:
        st.markdown(f"<small>{source_name}</small>", ...)
if license_note:
    st.markdown(f"<small> ({license_note})</small>", ...)

# 修正後（1行に統合）
source_parts = []
if source_name:
    if source_url:
        source_parts.append(f"[{source_name}]({source_url})")
    else:
        source_parts.append(source_name)
if license_note:
    source_parts.append(f"({license_note})")

if source_parts:
    st.markdown(f"<small>**出典**: {' '.join(source_parts)}</small>", ...)
```

## 今後の改善点

1. **データベーススキーマの拡張**: 必要に応じて`ng_uses_other`等のカラムを追加（既存DBとの互換性を保つ）
2. **用途例画像の追加**: サンプルデータに用途例画像を追加（`init_sample_data.py`で既に実装済み）
3. **画像アップロード機能**: ユーザーが用途例画像をアップロードできる機能（将来実装）

