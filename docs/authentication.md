# GitHub 認証方法

GitHub Poller は2つの認証方法をサポートしています。

## 認証方法の選択

### デフォルト: GitHub Apps（推奨）

環境変数 `GITHUB_AUTH_TYPE` を設定しない、または `app` に設定すると GitHub Apps 認証を使用します。

### Personal Access Token

環境変数 `GITHUB_AUTH_TYPE` を `pat` に設定すると Personal Access Token 認証を使用します。

## 比較表

| 項目 | GitHub Apps | Personal Access Token |
|------|-------------|----------------------|
| **セットアップ** | やや複雑 | シンプル ⭐ |
| **セキュリティ** | 高い ⭐⭐⭐ | 中程度 |
| **権限スコープ** | リポジトリ単位で細かく設定 ⭐⭐⭐ | 全リポジトリ |
| **トークン有効期限** | 1時間（自動更新） ⭐⭐⭐ | 無期限（手動更新） |
| **レート制限** | 15,000 req/h ⭐⭐⭐ | 5,000 req/h |
| **組織管理** | 容易 ⭐⭐⭐ | 個人に依存 |
| **監査ログ** | 詳細 ⭐⭐⭐ | 限定的 |

## GitHub Apps の設定方法

### 1. GitHub App の作成

1. GitHub 組織の **Settings** → **Developer settings** → **GitHub Apps** にアクセス
2. **New GitHub App** をクリック
3. 基本情報を入力：
   - **GitHub App name**: `github-poller` など
   - **Homepage URL**: プロジェクトの URL
   - **Webhook**: 無効化（Active のチェックを外す）

4. **Repository permissions** を設定：
   ```
   Contents: Read-only      # コミット情報の取得
   Metadata: Read-only      # リポジトリ情報の取得（自動付与）
   ```

5. **Create GitHub App** をクリック

### 2. Private Key の生成

App の設定画面で：
1. **Generate a private key** をクリック
2. `.pem` ファイルがダウンロードされる
3. このファイルを安全に保管

### 3. App ID の記録

App 設定画面の上部に表示される **App ID** を記録します（例: 123456）

### 4. App のインストール

1. App 設定画面で **Install App** をクリック
2. 対象の組織を選択
3. インストール先のリポジトリを選択：
   - **All repositories**（すべてのリポジトリ）
   - **Only select repositories**（特定のリポジトリのみ）推奨 ⭐

4. インストール完了後、URL から **Installation ID** を取得：
   ```
   https://github.com/organizations/YOUR_ORG/settings/installations/12345678
                                                                    ^^^^^^^^
                                                                Installation ID
   ```

### 5. Secret の作成

```bash
# 使用する namespace を設定
export NAMESPACE="github-poller"

# Secret を作成
kubectl create secret generic github-poller-secret \
  --from-literal=app-id=123456 \
  --from-literal=installation-id=987654 \
  --from-file=private-key=/path/to/your-app.private-key.pem \
  -n $NAMESPACE
```

### 6. CronJob の環境変数を設定

```yaml
env:
  - name: GITHUB_AUTH_TYPE
    value: "app"  # GitHub Apps を使用
```

## Personal Access Token の設定方法

### 1. Token の作成

1. GitHub の **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** にアクセス
2. **Generate new token (classic)** をクリック
3. 必要なスコープを選択：
   - **public_repo**: パブリックリポジトリのみ
   - **repo**: プライベートリポジトリも含む
4. トークンを生成してコピー

### 2. Secret の作成

```bash
# 使用する namespace を設定
export NAMESPACE="github-poller"

# Secret を作成
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=ghp_xxxxxxxxxxxxxxxxxxxx \
  -n $NAMESPACE
```

### 3. CronJob の環境変数を設定

```yaml
env:
  - name: GITHUB_AUTH_TYPE
    value: "pat"  # Personal Access Token を使用
```

## フォールバック機能

`GITHUB_AUTH_TYPE=app` の場合、GitHub Apps 認証が失敗すると自動的に PAT にフォールバックします。

```
GitHub Apps 認証試行
  ↓ 失敗
PAT 認証にフォールバック
  ↓ 成功
ポーリング開始
```

この機能により、GitHub Apps への移行中でも安全に運用できます。

## 推奨される使い分け

### GitHub Apps を推奨する場合

✅ エンタープライズ環境  
✅ 複数の組織で使用  
✅ セキュリティコンプライアンス要件がある  
✅ 長期運用を想定  
✅ 高頻度ポーリング（レート制限対策）

### PAT を推奨する場合

✅ 個人プロジェクト  
✅ 小規模チーム（< 10人）  
✅ 迅速なセットアップが必要  
✅ 監視リポジトリが少ない（< 10個）  
✅ 5分間隔のポーリング

## トラブルシューティング

### GitHub Apps 認証エラー

```
ERROR: GitHub App authentication failed: ...
INFO: Falling back to Personal Access Token
```

**原因:**
- App ID、Installation ID、Private Key のいずれかが間違っている
- App が組織にインストールされていない
- Private Key の形式が不正

**対処:**
1. Secret の内容を確認
2. App がインストールされているか GitHub で確認
3. Private Key が正しい PEM 形式か確認

### PAT 認証エラー

```
ERROR: GitHub token not found. Set GITHUB_TOKEN env var or provide /secrets/github-token
```

**原因:**
- Secret に `github-token` キーが存在しない
- Secret が正しくマウントされていない

**対処:**
1. 使用する namespace を設定：`export NAMESPACE="github-poller"`
2. Secret の作成を確認：`kubectl get secret github-poller-secret -n $NAMESPACE`
3. Secret の内容を確認：`kubectl get secret github-poller-secret -n $NAMESPACE -o yaml`

## セキュリティ上の注意

### GitHub Apps

- ✅ Private Key は絶対に Git にコミットしない
- ✅ 本番環境では Vault や External Secrets Operator を使用
- ✅ 最小権限の原則（必要なリポジトリのみにアクセス）
- ✅ 定期的に使用状況を監査

### PAT

- ✅ Token は絶対に Git にコミットしない
- ✅ 最小限のスコープのみ付与
- ✅ 定期的にローテーション
- ✅ 使用者が退職する場合は即座に無効化

