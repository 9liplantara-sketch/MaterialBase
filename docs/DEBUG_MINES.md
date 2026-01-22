# Material Map / MaterialBase 既知の地雷と対策

このドキュメントは、Material Map / MaterialBase で発生したクラッシュや不具合の「地雷」を記録し、再発防止策をまとめたものです。

最終更新: 2026-01-21

---

## 地雷カテゴリ一覧

### 1. DBセッション関連（generator地雷）

**症状**: `AttributeError: 'generator' object has no attribute 'execute'`

**原因**: 
- `database.py`の`get_db()`が`yield db`を使うgenerator関数
- UI層で`from database import get_db`して直接使うとgeneratorが返る
- generatorに対して`.execute()`を呼び出してエラー

**発生箇所**:
- `_render_material_search_card()`内の`prop_count`取得（app.py:3939）
- その他、`from database import get_db`を使っている箇所

**対策**:
- ✅ `SessionLocal()`を直接使用（プロジェクト標準の方法）
- ✅ `utils/db.py`に統一窓口を作る（Phase 2で実装完了）
- ✅ `from database import get_db`を全ファイルから排除（Phase 2で実装完了）
- ✅ `get_session()`（読み取り専用）と`session_scope()`（書き込み、自動commit/rollback）を提供

**再発防止**:
- `git grep "from database import get_db"`で検索して禁止
- DBセッション取得は`SessionLocal()`または`utils/db.py`の関数のみ使用

---

### 2. インデントエラー（app.py巨大問題）

**症状**: `IndentationError: expected an indented block`（特に3068行目付近）

**原因**:
- app.pyが5770行と巨大
- Cursorの部分編集でインデントが崩れる
- `if`文の直後にインデントなしの行が来る

**発生箇所**:
- `if space_url or product_url:`の直後（app.py:3067-3068）
- その他、部分編集でインデントが崩れた箇所

**対策**:
- ✅ 該当箇所のインデント修正（一時対応）
- 🔄 Phase 1でapp.pyをページ単位で分割予定

**再発防止**:
- app.pyを小さく分割（Phase 1）
- 見出しコメント境界でブロック置換
- 行番号ピンポイント編集を禁止

---

### 3. NOT NULL違反（NotNullViolation）

**症状**: `NotNullViolation: null value in column "procurement_status" violates not-null constraint`

**原因**:
- CSV/フォームでNOT NULL列が未入力
- 承認時にデフォルト値補完が`flush()`より後に実行される
- 補完ロジックが複数箇所に分散

**発生箇所**:
- `approve_submission()`のTx1（app.py:4336）
- `create_or_update_material()`のbulk import（utils/bulk_import.py）

**対策**:
- ✅ `_apply_not_null_defaults_for_approval()`を`flush()`より前に実行
- ✅ `_apply_not_null_defaults()`をbulk importで実行
- ✅ Phase 4完了: `utils/material_defaults.py`に単一の仕様として集約
- ✅ `apply_material_defaults()`関数で承認と一括登録の双方が同じ補完ロジックを通る
- ✅ `REQUIRED_FIELDS`と`DEFAULT_VALUES`でNOT NULL列とデフォルト値を一元管理

**再発防止**:
- ✅ 補完の真実は `utils/material_defaults.py` の `apply_material_defaults()` のみ（Phase 4完了）
- ✅ 承認（`_tx1_upsert_material_core()`）と一括登録（`create_or_update_material()`）で同じ`apply_material_defaults()`を使用
- ✅ **補完の流れ**: dict補完 → Material設定（Materialオブジェクトに値を入れた後に補完するのは禁止）
- ✅ 新しいNOT NULL列が増えたら `REQUIRED_FIELDS` と `DEFAULT_VALUES` を更新（`docs/PHASE4_NOT_NULL.md`も更新）
- ✅ CSV必須項目チェックも`get_csv_required_fields()`から生成可能
- ✅ 旧関数（`_apply_not_null_defaults_for_approval`, `_apply_not_null_defaults`）は削除済み

---

### 4. トランザクション汚染（Tx汚染）

**症状**: 
- `ForeignKeyViolation: approved_material_id = 252 を更新しようとしているが、materials に id=252 が存在しない`
- `Material XXX does not exist after creation`

**原因**:
- Tx1内でproperties/embedding更新が失敗し、Tx全体が汚染される
- Postgresは1回エラーでTxが失敗状態になり、最終commitが成立しない
- commit前に存在確認をしている

**発生箇所**:
- `approve_submission()`のTx1（app.py:4336）

**対策**:
- ✅ properties upsertをTx1から分離（TxProps）
- ✅ embedding upsertをTx1から分離（TxEmb）
- ✅ images upsertをTx1から分離（Tx2）
- ✅ submission status更新をTx1から分離（TxSub）
- ✅ Tx1を`_tx1_upsert_material_core()`関数化（副作用排除）
- ✅ Tx1失敗時は即return（Tx2/TxProps/TxEmb/TxSubへ進まない）
- ✅ Tx1成功後にmaterial存在確認を実行
- ✅ TxSubは必須Tx（失敗時は承認全体を失敗扱い）
- ✅ Tx2/TxProps/TxEmbは任意Tx（失敗しても承認は継続）
- ✅ すべて統一API（`get_session()`/`session_scope()`）を使用

**再発防止**:
- Tx1はmaterials作成/更新とNOT NULL補完のみ
- properties/embedding/imagesは別トランザクション
- Tx1失敗時は即return（Tx2以降へ行かない）

---

### 5. DBに無いカラム参照（UndefinedColumn）

**症状**: `SQLAlchemy`が存在しないカラムを参照してエラー

**原因**:
- `use_environment`カラムをモデル/UIに追加したが、DBにマイグレーション未実行
- コメントアウトで対応したが、参照が残っている

**発生箇所**:
- `use_environment`関連（一時的にコメントアウト済み）

**対策**:
- ✅ 該当箇所をコメントアウト（一時対応）
- 🔄 Phase 5で完全対応予定

**再発防止**:
- コメントアウト禁止：参照ゼロまで削除 or Alembicで追加して完全対応
- DBスキーマとコード参照を一致させる

---

### 6. 日本語URL未エンコード

**症状**: 日本語ファイル名の画像が表示されない

**原因**:
- `public_url`生成時に日本語ファイル名が未エンコード
- `safe_url()`が適用されていない

**発生箇所**:
- 画像表示全般

**対策**:
- ✅ `safe_url()`を適用（一部対応済み）
- 🔄 Phase 6で完全対応予定

**再発防止**:
- 画像URL生成時に必ず`safe_url()`を適用
- `utils/image_display.py`に集約

---

### 7. Unicode正規化（NFKC未適用）

**症状**: CSV材料名とZIP画像ファイル名が一致しない

**原因**:
- 材料名とファイル名のUnicode正規化が不一致
- NFKC正規化が適用されていない

**発生箇所**:
- 一括登録の画像照合（utils/bulk_import.py）

**対策**:
- ✅ `fix_zip_filename()`でcp437→utf-8変換
- 🔄 Phase 7でNFKC正規化を追加予定

**再発防止**:
- 材料名とファイル名の双方をNFKC正規化してから比較
- `utils/normalize.py`に集約

---

### 8. 検索結果カード描画失敗

**症状**: 検索結果が9件あるのにカードが0件表示される

**原因**:
- `prop_count`取得で例外が発生し、カード全体が描画失敗
- 例外ハンドリングが不十分

**発生箇所**:
- `_render_material_search_card()`（app.py:3925）

**対策**:
- ✅ `prop_count`取得をtry/exceptで囲み、失敗してもカード描画継続
- 🔄 Phase 8で完全対応予定

**再発防止**:
- 補助情報（prop_count等）の取得失敗は警告のみ
- カード描画は必ず継続
- N+1クエリを事前集計で回避

---

## 対策の優先順位

1. **最優先**: Phase 1（app.py分割）→ インデントエラー再発防止
2. **高優先**: Phase 2（DBセッション統一）→ generator地雷撲滅
3. **高優先**: Phase 3（Tx分離固定）→ トランザクション汚染防止
4. **中優先**: Phase 4（NOT NULL補完集約）→ NotNullViolation防止
5. **中優先**: Phase 5（カラム参照整合）→ UndefinedColumn防止
6. **低優先**: Phase 6-8（画像・一括登録・検索の堅牢化）

---

## 再発防止の仕組み

### ゲート（必須）
- `bash scripts/compile_check.sh`が通ること
- 各フェーズで必ず実行

### テスト（推奨）
- pytestで重要関数の単体テスト
- `apply_defaults()`、`filename_normalize()`、`safe_url()`等

### ドキュメント（必須）
- この`DEBUG_MINES.md`を更新
- `SMOKE_TEST.md`で手動確認手順を記録

---

## 関連ドキュメント

- `docs/SMOKE_TEST.md`: 手動確認チェックリスト
- `docs/RUNBOOK.md`: 運用マニュアル（backfill scripts等）
