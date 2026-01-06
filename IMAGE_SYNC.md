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

### 同名で複数の拡張子がある場合

優先順位の高い拡張子が採用されます：
1. `.jpg`
2. `.jpeg`
3. `.png`
4. `.webp`

最新のファイル（mtime）が優先されます。

### DB突合が失敗する場合

`--no-db` オプションを使用すると、DB突合をスキップしてファイル名をそのまま使用します。

## アプリでの表示

同期された画像は、アプリの以下の場所で自動的に表示されます：

- **メイン画像**: 材料詳細ページの上部
- **使用例画像**: 「入手先・用途」タブの「代表的な使用例」セクション

画像は自動的に探索され、存在する場合は表示されます。
