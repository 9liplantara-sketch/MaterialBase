# Streamlit Cloud デプロイ手順と検証チェックリスト

## 概要

このドキュメントでは、Streamlit Cloudにデプロイする際のS3画像対応の設定手順と検証方法を説明します。

---

## 1. Streamlit Cloud Secrets設定

### 手順

1. Streamlit Cloudのアプリ管理画面にアクセス
2. 「Settings」→「Secrets」を開く
3. 以下の形式でSecretsを追加（`toml`形式）：

```toml
# S3設定（必須）
S3_BUCKET = "your-bucket-name"
AWS_ACCESS_KEY_ID = "your_access_key_id"
AWS_SECRET_ACCESS_KEY = "your_secret_access_key"
AWS_REGION = "ap-northeast-1"

# S3設定（オプション）
S3_ENDPOINT_URL = ""  # MinIO等の互換S3（通常は空）
S3_PUBLIC_BASE_URL = "https://d1234567890.cloudfront.net"  # CloudFront等のCDN URL（オプション）
```

### 注意事項

- **認証情報は絶対にGitにコミットしない**
- Secretsは自動的に環境変数として読み込まれる
- 変更後はアプリを再起動する必要がある場合がある

---

## 2. S3バケットポリシー設定（Public運用）

### 公開prefixのみ許可するバケットポリシー例

以下のポリシーは、`materials/`プレフィックスのみ公開読み取りを許可します：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-bucket-name/materials/*"
    }
  ]
}
```

### 設定手順

1. AWSコンソールでS3バケットを開く
2. 「Permissions」タブを選択
3. 「Bucket policy」セクションで「Edit」をクリック
4. 上記のポリシーを貼り付け（`your-bucket-name`を実際のバケット名に置換）
5. 「Save changes」をクリック

### 注意事項

- **最小権限の原則**: 必要最小限のプレフィックスのみ公開
- **機密情報の保護**: `materials/`以外のプレフィックスは公開しない
- **CORS設定**: 必要に応じてCORS設定も追加

### CORS設定例

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["https://your-app.streamlit.app"],
    "ExposeHeaders": [],
    "MaxAgeSeconds": 3000
  }
]
```

---

## 3. CloudFront設定（CDN使用時）

### 設定手順

1. AWS CloudFrontでディストリビューションを作成
2. OriginとしてS3バケットを指定
3. 「Restrict Bucket Access」を有効化（推奨）
4. 「Origin Access Identity (OAI)」を作成
5. ディストリビューションのURLを取得（例: `https://d1234567890.cloudfront.net`）

### Streamlit Cloud Secrets設定

```toml
S3_PUBLIC_BASE_URL = "https://d1234567890.cloudfront.net"
```

この設定により、`upload_file_to_s3()`が返すURLはCloudFront URLになります。

### メリット

- **高速配信**: CDN経由で高速に画像を配信
- **コスト削減**: S3への直接アクセスを削減
- **セキュリティ**: OAIを使用してS3バケットへの直接アクセスを制限

---

## 4. 検証チェックリスト

### ✅ チェック1: Build SHA表示

**確認方法**:
1. Streamlit Cloudでアプリを開く
2. サイドバーを確認
3. `build: {sha}` が表示されていることを確認

**期待結果**:
```
build: a1b2c3d
time: 2026-01-05T12:34:56
```

**問題がある場合**:
- Gitリポジトリが正しく接続されているか確認
- `app.py`の`get_git_sha()`関数が正しく動作しているか確認

---

### ✅ チェック2: URL画像が表示される（ローカルパスに依存しない）

**確認方法**:
1. アプリで材料詳細ページを開く
2. 画像が表示されることを確認
3. ブラウザの開発者ツールで画像のURLを確認
4. URLがS3 URL（またはCloudFront URL）であることを確認

**期待結果**:
- 画像が正常に表示される
- 画像URLが `https://...s3...amazonaws.com/...` または `https://...cloudfront.net/...` 形式

**問題がある場合**:
- S3 Secretsが正しく設定されているか確認
- `utils/image_display.py`の`get_display_image_source()`が正しく動作しているか確認
- ブラウザのコンソールでエラーを確認

---

### ✅ チェック3: 画像が0件でもプレースホルダが表示される

**確認方法**:
1. 画像が登録されていない材料を開く
2. プレースホルダー（「画像なし」）が表示されることを確認
3. 真っ白な画面にならないことを確認

**期待結果**:
- グレーの背景（`#f0f0f0`）に「画像なし」テキストが表示される
- 真っ白な画面にならない

**問題がある場合**:
- `utils/image_display.py`の`display_image_unified()`が正しく動作しているか確認
- プレースホルダーの生成ロジックを確認

---

### ✅ チェック4: Assets Mode診断が表示される

**確認方法**:
1. サイドバーを確認
2. 「Assets Mode」が表示されていることを確認
3. URL画像数が正しく表示されていることを確認

**期待結果**:
```
Assets Mode: 🟢 url
URL画像: 10/10 (100%)
```

または

```
Assets Mode: 🟡 mixed
URL画像: 5/10 (50%)
```

**問題がある場合**:
- `app.py`の`get_assets_mode_stats()`が正しく動作しているか確認
- データベース接続が正常か確認

---

### ✅ チェック5: migrateスクリプトのdry-runが動く

**確認方法**:
1. Streamlit Cloudのターミナル（またはローカル環境）で実行：
```bash
python scripts/migrate_images_to_s3.py --dry-run
```

**期待結果**:
```
============================================================
S3設定確認
============================================================
  s3_bucket: True
  aws_access_key_id: True
  ...

============================================================
Imageテーブル: 5件の画像を処理します
============================================================
[1/5] 🔍 ドライラン: uploads/1_material.webp -> materials/1/primary/1_material.webp
...

============================================================
移行結果サマリー
============================================================
総対象数: 20件
🔍 ドライラン対象: 20件
⚠️  スキップ: 0件
❌ 失敗: 0件
```

**問題がある場合**:
- S3 Secretsが正しく設定されているか確認
- `utils/s3_storage.py`の`check_s3_config()`を確認
- データベース接続が正常か確認

---

### ✅ チェック6: --limit 5 で移行→UI反映を確認

**確認方法**:
1. 移行スクリプトを実行：
```bash
python scripts/migrate_images_to_s3.py --limit 5
```

2. 移行が成功することを確認：
```
[1/5] ✅ 移行成功: uploads/1_material.webp -> https://...
```

3. アプリをリロード
4. 移行した材料の画像がS3 URLで表示されることを確認
5. ブラウザの開発者ツールで画像URLを確認

**期待結果**:
- 移行が成功する
- アプリで画像が正常に表示される
- 画像URLがS3 URL（またはCloudFront URL）である

**問題がある場合**:
- S3アップロードが成功しているか確認（AWSコンソールで確認）
- データベースの`url`カラムが更新されているか確認
- アプリのキャッシュをクリアしてリロード

---

## 5. Streamlit Cloud更新停止時の対処法

### 問題: "Applications are not updated when new commits are..." 警告が出続く

**症状:**
- GitHubへpushした変更がCloudに反映されない
- 「View latest updates / Last updated X hours ago」が表示され続ける

**原因:**
- GitHub連携（Source control account）が無効または権限失効
- リポジトリ名・オーナー変更
- Workspaceとrepoオーナーの不一致

**対処法（段階的）:**

1. **Version/Build表示を確認**
   - サイドバーで`Version`と`Build`を確認
   - 最新のコミットSHAと一致しているか確認
   ```bash
   git rev-parse --short HEAD
   ```

2. **GitHub連携の再認証**
   - Streamlit Cloudの「Settings」→「Source control」を開く
   - 「Disconnect」→「Connect GitHub」で再認証

3. **リポジトリの再選択**
   - 「Settings」→「Source control」でリポジトリを再選択
   - ブランチを確認（`main`または`master`）

4. **アプリの再起動**
   - 「Manage app」→「Reboot」を実行

5. **最終手段: アプリ削除→再デプロイ**
   - Secretsをバックアップ
   - アプリを削除
   - 再デプロイ（Secretsを再設定）

詳細は [CLOUD_TROUBLESHOOTING.md](./CLOUD_TROUBLESHOOTING.md) を参照してください。

---

## 6. トラブルシューティング

### エラー: "S3_BUCKET環境変数が設定されていません"

**原因**: Streamlit Cloud Secretsが正しく設定されていない

**解決方法**:
1. Streamlit Cloudの「Settings」→「Secrets」を確認
2. `S3_BUCKET`が正しく設定されているか確認
3. アプリを再起動

---

### エラー: "バケットへのアクセス権限がありません"

**原因**: IAMユーザーの権限が不足している

**解決方法**:
1. IAMポリシーを確認
2. 以下の権限があることを確認：
   - `s3:PutObject`
   - `s3:PutObjectAcl`
   - `s3:GetObject`
   - `s3:HeadBucket`

---

### 画像が表示されない（URLは正しい）

**原因**: バケットポリシーまたはCORS設定の問題

**解決方法**:
1. S3バケットポリシーを確認
2. CORS設定を確認
3. CloudFrontを使用している場合は、CloudFrontの設定を確認

---

### Assets Modeが表示されない

**原因**: データベース接続エラーまたは統計取得エラー

**解決方法**:
1. アプリのログを確認
2. データベース接続が正常か確認
3. `get_assets_mode_stats()`のエラーハンドリングを確認（エラー時は表示しない）

---

## 6. デプロイ後の確認事項

### 必須確認

- [ ] Build SHAが表示される
- [ ] Assets Mode診断が表示される
- [ ] URL画像が正常に表示される
- [ ] プレースホルダーが正常に表示される
- [ ] migrateスクリプトのdry-runが動作する

### 推奨確認

- [ ] 実際に画像を移行してUI反映を確認
- [ ] CloudFrontを使用している場合は、CDN経由で画像が配信されることを確認
- [ ] バケットポリシーが正しく設定されていることを確認
- [ ] CORS設定が正しいことを確認

---

## 7. 参考リンク

- [Streamlit Cloud Secrets管理](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management)
- [AWS S3バケットポリシー](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html)
- [AWS CloudFront設定](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html)

---

## 8. サポート

問題が解決しない場合は、以下を確認してください：

1. Streamlit Cloudのログを確認
2. AWS CloudWatchのログを確認
3. ブラウザの開発者ツールでエラーを確認
4. `utils/s3_storage.py`の`test_s3_connection()`を実行して接続を確認


