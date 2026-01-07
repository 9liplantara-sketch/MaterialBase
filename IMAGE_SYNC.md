# 画像同期ガイド

## 概要

`uploads/` と `uploads/uses/` にある画像を `static/images/materials/` に同期するためのガイドです。

## 命名規則（これが正）

画像ファイルは以下の命名規則に従って配置してください：

### メイン画像（primary）

```
uploads/{材料名}.{拡張子}
```

**例:**
- `uploads/アルミニウム.jpg`
- `uploads/カリン材.png`
- `uploads/ポリプロピレン.webp`

### 使用例画像（space / product）

```
uploads/uses/{材料名}1.{拡張子}  → space（生活/空間の使用例）
uploads/uses/{材料名}2.{拡張子}  → product（プロダクトの使用例）
```

**例:**
- `uploads/uses/アルミニウム1.jpg` → space
- `uploads/uses/アルミニウム2.jpg` → product
- `uploads/uses/カリン材1.png` → space
- `uploads/uses/カリン材2.png` → product

### 拡張子

以下の拡張子をサポートしています：
- `.jpg` （優先度: 最高）
- `.jpeg`
- `.png`
- `.webp` （優先度: 最低）

**注意:** 同名で複数の拡張子がある場合、優先順位の高いものが採用されます。

## 同期スクリプトの実行

### 基本的な使い方

```bash
python scripts/sync_uploaded_images.py
```

### オプション

- `--dry-run`: ドライランモード（実際にはコピーしない、確認のみ）
- `--no-db`: DB突合をスキップ（材料名の突合を行わない）

**例:**
```bash
# ドライランで確認
python scripts/sync_uploaded_images.py --dry-run

# DB突合なしで実行
python scripts/sync_uploaded_images.py --no-db
```

## 出力先

同期された画像は以下の場所に保存されます：

```
static/images/materials/{safe_slug}/primary.{ext}
static/images/materials/{safe_slug}/uses/space.{ext}
static/images/materials/{safe_slug}/uses/product.{ext}
```

**例:**
- `static/images/materials/アルミニウム/primary.jpg`
- `static/images/materials/アルミニウム/uses/space.jpg`
- `static/images/materials/アルミニウム/uses/product.jpg`

`safe_slug` は材料名からパス安全な文字列に変換されたものです（禁止文字は `_` に置換されます）。

## 材料名の突合

スクリプトは自動的にDBの `Material.name` または `Material.name_official` と突合します。

- **完全一致**: ファイル名とDBの材料名が完全に一致する場合
- **正規化一致**: 空白や全角/半角の違いを無視して一致する場合
- **部分一致**: 大文字小文字を無視して一致する場合

DBに存在しない材料名のファイルはスキップされます（`--no-db` オプション使用時は除く）。

## べき等性

スクリプトはべき等性を保証します：

- 既に同一ファイルが出力先に存在する場合、スキップされます（ハッシュ比較）
- 同じファイルを何度実行しても、結果は同じです

## ログ出力

スクリプトは以下の情報を出力します：

### 材料ごとの詳細

各材料について以下を表示：
- 検出した入力パス
- 出力先パス
- 採用した拡張子
- スキップ理由（同一ファイル、ファイルなしなど）

### サマリー

最後に以下を表示：
- 同期した画像数（primary/space/product別）
- 不足している画像の一覧

## トラブルシューティング

### 画像が反映されない

1. **材料名の確認**: DBの `Material.name` または `Material.name_official` とファイル名が一致しているか確認
2. **拡張子の確認**: `.jpg`, `.jpeg`, `.png`, `.webp` のいずれかであることを確認
3. **ドライランで確認**: `--dry-run` オプションで実際に何が検出されるか確認
4. **Git追跡の確認**: `static/images/materials/` がGitで追跡されているか確認（`git ls-files`）
5. **Gitにプッシュ**: 同期後、`git add`, `git commit`, `git push` でCloudに反映

### 同名で複数の拡張子がある場合

優先順位の高い拡張子が採用されます：
1. `.jpg`
2. `.jpeg`
3. `.png`
4. `.webp`

最新のファイル（mtime）が優先されます。

### DB突合が失敗する場合

`--no-db` オプションを使用すると、DB突合をスキップしてファイル名をそのまま使用します。

### Streamlit Cloudで表示されない場合

**重要**: `uploads/` は `.gitignore` で除外されているため、Cloudには届きません。

1. **同期の確認**: `scripts/debug_image_state.py --compare-uploads` で差分を確認
2. **Git追跡の確認**: `git ls-files static/images/materials/` で追跡状態を確認
3. **Gitにプッシュ**: `git add static/images/materials/ && git commit && git push`
4. **Cloud再起動**: Streamlit Cloudで「Manage app → Reboot」を実行（キャッシュクリア）

詳細は [DEBUG_IMAGE.md](./DEBUG_IMAGE.md) を参照してください。

## アプリでの表示

同期された画像は、アプリの以下の場所で自動的に表示されます：

- **メイン画像**: 材料詳細ページの上部
- **使用例画像**: 「入手先・用途」タブの「代表的な使用例」セクション

画像は自動的に探索され、存在する場合は表示されます。

## ローカル検証手順

画像同期が正しく動作していることを確認するための手順です。

### 1. 画像同期の実行

```bash
# DB突合をスキップして実行（推奨）
python scripts/sync_uploaded_images.py --no-db
```

### 2. Git状態の確認

```bash
# static/images/materials/ の更新を確認
git status

# 更新されたファイルを確認
git status static/images/materials/
```

**期待される結果:**
- `static/images/materials/**/*.jpg` が更新されている（または新規追加されている）
- 削除されたファイルが大量に出ていない

### 3. Gitにコミット・プッシュ

```bash
# 更新された画像ファイルをステージング
git add static/images/materials

# コミット
git commit -m "chore: sync material images"

# プッシュ
git push
```

### 4. Cloud Debugでの確認

Streamlit Cloudにデプロイ後、アプリのサイドバーにある「🔧 Debug (temporary)」を展開して以下を確認：

1. **materials.db 情報**
   - path: 絶対パス
   - mtime: 更新日時
   - size: ファイルサイズ
   - materials件数: DB内の材料数

2. **画像ファイル情報（アルミニウム）**
   - **primary**: `static/images/materials/アルミニウム/primary.jpg` の mtime/size
   - **space**: `static/images/materials/アルミニウム/uses/space.jpg` の mtime/size
   - **product**: `static/images/materials/アルミニウム/uses/product.jpg` の mtime/size

**期待される結果:**
- 画像ファイルの mtime が更新されている（同期実行後の日時になっている）
- 画像ファイルの size が正しい（0バイトでない）

### 5. 画像表示の確認

アプリ上で以下を確認：

1. **ホームページ**: 「最近登録された材料」で画像が表示される
2. **材料一覧ページ**: 材料カードで画像が表示される
3. **材料詳細ページ**: 「入手先・用途」タブで使用例画像が表示される

**期待される結果:**
- 更新した画像が正しく表示される
- 古い画像が表示されない（キャッシュがクリアされている）

## 画像処理の詳細

### JPG/JPG入力の場合

- **処理方法**: `shutil.copy2()` でそのままコピー
- **特徴**:
  - 再エンコードしない（バイト列が同一）
  - mtime（更新日時）も維持される
  - md5ハッシュが一致する

### PNG/WEBP入力の場合

- **処理方法**: Pillowで開いてJPGに変換
- **特徴**:
  - 透過画像は白背景に合成される
  - 品質90で保存される
  - md5ハッシュは一致しない（変換されるため）

### 比較スクリプトでの判定

`scripts/debug_image_state.py --compare-uploads` を実行すると：

- **JPG/JPGの場合**: `SAME`（md5一致）または `DIFF`（md5不一致、同期が必要）
- **PNG/WEBPの場合**: `CONVERTED`（変換されるためmd5不一致は正常、参考表示）
