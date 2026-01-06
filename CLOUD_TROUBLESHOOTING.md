# Streamlit Cloud トラブルシューティングガイド

## 概要

Streamlit Cloudで「Applications are not updated when new commits are...」という警告が出続き、GitHubへpushした変更がCloudに反映されない場合の対処法です。

## デプロイ診断情報の確認

### Version/Build表示の見方

アプリのサイドバー下部に以下の情報が表示されます：

```
Version: a1b2c3d
Build: 2026-01-06T12:34:56+00:00
```

**確認方法:**
1. Streamlit Cloudでアプリを開く
2. サイドバーを確認
3. `Version`と`Build`が表示されていることを確認

**判定方法:**
- `Version`が最新のコミットSHAと一致しているか確認
  ```bash
  git rev-parse --short HEAD
  ```
- 一致していない場合、Cloudが古いコミットを拾っている可能性があります

## 問題の切り分け

### 1. GitHub連携の確認

**確認項目:**
- Source control account（GitHub連携）が有効か
- 権限が失効していないか（private repo含む）
- リポジトリへのアクセス権限があるか

**確認方法:**
1. Streamlit Cloudのアプリ管理画面にアクセス
2. 「Settings」→「Source control」を確認
3. GitHubアカウントが正しく接続されているか確認

**対処法:**
- 接続が切れている場合は、再認証が必要
- 権限が失効している場合は、GitHubで権限を再付与

### 2. リポジトリ名・オーナー変更の確認

**確認項目:**
- リポジトリ名が変更されていないか
- リポジトリのオーナーが変更されていないか

**問題:**
- リポジトリ名やオーナーが変更されると、Streamlit Cloudの連携が切れる場合がある
- この場合、再デプロイが必要

**対処法:**
1. Streamlit Cloudのアプリ管理画面で「Settings」を開く
2. 「Source control」でリポジトリを再選択
3. または、アプリを削除して再デプロイ

### 3. Workspaceの確認

**確認項目:**
- Workspaceがrepoオーナーと一致しているか

**問題:**
- Workspaceとリポジトリオーナーが異なる場合、更新が止まる場合がある

**対処法:**
- 正しいWorkspaceにアプリがデプロイされているか確認
- 必要に応じて、正しいWorkspaceに再デプロイ

### 4. "View latest updates"の確認

**確認方法:**
1. Streamlit Cloudのアプリ管理画面で「View latest updates」をクリック
2. 最新のビルドを確認
3. 最新ビルドを適用

**対処法:**
- 「View latest updates」から最新ビルドを手動で適用
- これで一時的に最新状態に戻る場合がある

## 復旧手順（段階的）

### ステップ1: 基本確認

1. **GitHubにpushされているか確認**
   ```bash
   git log -1 --oneline
   git push origin main
   ```

2. **Streamlit Cloudのログを確認**
   - アプリ管理画面で「Logs」を確認
   - エラーが出ていないか確認

3. **Version/Build表示を確認**
   - サイドバーで`Version`と`Build`を確認
   - 最新のコミットSHAと一致しているか確認

### ステップ2: GitHub連携の再認証

1. Streamlit Cloudのアプリ管理画面にアクセス
2. 「Settings」→「Source control」を開く
3. 「Disconnect」をクリック（必要に応じて）
4. 「Connect GitHub」をクリックして再認証

### ステップ3: リポジトリの再選択

1. Streamlit Cloudのアプリ管理画面で「Settings」を開く
2. 「Source control」でリポジトリを再選択
3. ブランチを確認（`main`または`master`）
4. 「Save」をクリック

### ステップ4: アプリの再起動

1. Streamlit Cloudのアプリ管理画面で「Manage app」をクリック
2. 「Reboot」をクリック
3. 再起動後、Version/Build表示を確認

### ステップ5: 最終手段（アプリ削除→再デプロイ）

**注意:** この手順は最後の手段です。アプリの設定（Secrets等）が失われる可能性があります。

1. **Secretsのバックアップ**
   - Streamlit Cloudの「Settings」→「Secrets」を開く
   - Secretsの内容をコピーして保存

2. **アプリの削除**
   - Streamlit Cloudのアプリ管理画面で「Settings」を開く
   - 「Delete app」をクリック
   - 確認して削除

3. **再デプロイ**
   - Streamlit Cloudで「New app」をクリック
   - リポジトリを選択
   - ブランチを選択（`main`または`master`）
   - Secretsを再設定
   - 「Deploy」をクリック

## 予防策

### 1. 定期的な確認

- 定期的にVersion/Build表示を確認
- 最新のコミットSHAと一致しているか確認

### 2. コミットメッセージの明確化

- コミットメッセージに変更内容を明記
- これにより、どのコミットが反映されているか確認しやすい

### 3. 自動デプロイの確認

- Streamlit Cloudの設定で自動デプロイが有効になっているか確認
- 「Settings」→「Source control」で確認

## よくある質問

### Q: Version/Build表示が"unknown"になっている

**A:** Gitリポジトリが正しく接続されていない可能性があります。
- ローカル環境で`git rev-parse --short HEAD`が動作するか確認
- Streamlit Cloudのログでエラーが出ていないか確認

### Q: Versionは正しいが、変更が反映されない

**A:** キャッシュの問題の可能性があります。
- Streamlit Cloudで「Reboot」を実行
- ブラウザのキャッシュをクリア
- 画像の場合は、画像キャッシュバスター（`?v=<mtime>`）が効いているか確認

### Q: "View latest updates"をクリックしても反映されない

**A:** より深刻な問題の可能性があります。
- GitHub連携を再認証
- リポジトリを再選択
- 最終手段としてアプリを再デプロイ

## 関連ドキュメント

- [STREAMLIT_CLOUD_DEPLOY.md](./STREAMLIT_CLOUD_DEPLOY.md) - デプロイ手順
- [DEBUG_IMAGE.md](./DEBUG_IMAGE.md) - 画像デバッグガイド
- [IMAGE_SYNC.md](./IMAGE_SYNC.md) - 画像同期ガイド

## サポート

問題が解決しない場合は、以下を確認してください：

1. Streamlit Cloudのログを確認
2. GitHubのリポジトリ設定を確認
3. Streamlit Community Forumで質問

