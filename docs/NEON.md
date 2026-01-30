# Neon無料枠運用ルール

本プロジェクトはNeon無料枠（Scale-to-zero前提）で運用するため、以下のルールを遵守します。

## DBアクセスの基本方針

### 初期表示ではDBを叩かない
- **運用ルール**: 初期表示ではDBを叩かない（Neon節約 / Scale-to-zero前提）
- **DBアクセスは「ユーザー操作（ボタン/確定）」または「管理者限定」に寄せる**
- 件数表示や統計情報はボタンクリック時のみ取得する設計
- スキーマチェックも管理者モード時のみ自動実行、それ以外はボタンで実行
- 例外: DEBUG/診断モードのみ（必要な場合）

### 重い処理の自動実行ガード
- 「🔌 DBを起こす」ボタン後、直後の1回だけは重いDB処理を自動実行しない（直近3秒はガード）
- ボタン押下の明示操作は許可（ガードは自動実行のみ）
- 連打ガード: ボタン系トリガーに対して2秒以内の連打は無視

## 環境変数による診断機能

### DEBUG_ENV=1
- DBアクセスログを出力（`services/materials_service.py`）
- DBUnavailableError 発生時に traceback を logger に出力
- import エラー時に詳細情報（sys.path, cwd, traceback）を表示

### GUARD_DB_CALLS=1
- 呼び出し元情報をログに出力（初期表示DB禁止のガード）
- `services/materials_service.py` の各 public 関数で、呼び出し元ファイル名/関数名を logger に出力
- レビュー前に「初期表示DB禁止」を破る変更を検出可能

**使用方法**:
```bash
# 診断モードで起動
DEBUG_ENV=1 GUARD_DB_CALLS=1 streamlit run app.py
```

## DBUnavailableError の挙動

### 自動リトライ
- 最大2回の軽量リトライを試行
- リトライ間隔: 2秒
- リトライ成功時は `st.rerun()` で続行

### 統一UX
- リトライ失敗時は統一メッセージ + `st.stop()`
- 「🔄 再試行」ボタンで手動リトライ可能
- ログに context と例外メッセージを記録（DEBUG_ENV=1 のときは traceback も）

### 最後の砦
- `run_app_entrypoint()` の最上位で `DBUnavailableError` を捕捉
- 既存の個別捕捉（9箇所）で捕捉できなかった場合の統一UX
- 必ず `st.stop()` で停止（落ちない設計の維持）

## キャッシュ戦略

### st.cache_data TTL
- 件数/統計: 300秒（5分）TTL
- 一覧: 120秒（2分）TTL
- スキーマチェック: 60秒TTL

### キャッシュクリア
- `st.cache_data.clear()` の全消しは禁止（Neon節約のため）

## 運用時の注意事項

### ログ確認
- Streamlit Cloudのログで `[DB_UNAVAILABLE]` を検索して原因を特定
- `[GUARD_DB_CALL]` で初期表示時のDBアクセスを検出
- `DEBUG_ENV=1` で詳細な traceback を確認

### DB起床
- 「🔌 DBを起こす」ボタンで手動起床
- 起床直後（3秒以内）は重い処理の自動実行をスキップ
- ボタン押下の明示操作は許可

### パフォーマンス
- 重いクエリガード: 一覧取得の上限（MAX_LIST_LIMIT=200件）
- 無限リトライ禁止（CU節約のため）
- 連打ガード: ボタン系トリガーに対して2秒以内の連打は無視
