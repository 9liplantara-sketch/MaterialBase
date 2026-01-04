# GitHubリポジトリへのプッシュ手順

## 現在の状態

✅ Gitリポジトリの初期化完了
✅ ファイルのコミット完了
✅ リモートリポジトリの設定完了
⏳ GitHubへのプッシュ（認証が必要）

## プッシュ方法

### 方法1: パーソナルアクセストークンを使用（推奨）

1. **GitHubでパーソナルアクセストークンを作成**
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - "Generate new token (classic)" をクリック
   - スコープで `repo` にチェック
   - トークンをコピー（一度しか表示されません）

2. **ターミナルでプッシュ**
   ```bash
   cd "/Users/ta_rabo/Desktop/マテリアルの体系化と未来"
   git push -u origin main
   ```
   - Username: `9liplantara-sketch` を入力
   - Password: パーソナルアクセストークンを入力

### 方法2: SSHキーを使用

1. **SSHキーを生成**（まだ持っていない場合）
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

2. **SSHキーをGitHubに追加**
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
   - 出力をコピー
   - GitHub → Settings → SSH and GPG keys → New SSH key

3. **リモートURLをSSHに変更**
   ```bash
   git remote set-url origin git@github.com:9liplantara-sketch/test.git
   ```

4. **プッシュ**
   ```bash
   git push -u origin main
   ```

### 方法3: GitHub CLIを使用

```bash
# GitHub CLIをインストール（未インストールの場合）
brew install gh

# 認証
gh auth login

# プッシュ
git push -u origin main
```

## 確認

プッシュが成功したら、以下のURLでリポジトリを確認できます：

https://github.com/9liplantara-sketch/test

## 次のステップ

プッシュが完了したら、Streamlit Cloudでデプロイできます：

1. https://streamlit.io/cloud にアクセス
2. GitHubアカウントでログイン
3. "New app" をクリック
4. リポジトリ `9liplantara-sketch/test` を選択
5. Main file path: `app.py` を指定
6. "Deploy!" をクリック

## トラブルシューティング

### 認証エラーが続く場合

```bash
# リモートURLを確認
git remote -v

# 必要に応じて再設定
git remote set-url origin https://github.com/9liplantara-sketch/test.git
```

### ブランチ名の確認

```bash
git branch
# mainブランチが存在することを確認
```


