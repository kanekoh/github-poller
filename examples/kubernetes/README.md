# Kubernetes リソース - サンプル

GitHub Poller をすぐに試すためのサンプル Kubernetes リソースです。

## ファイル一覧

### 📄 configmap-sample.yaml
監視対象リポジトリの設定サンプル。

**使い方:**
```bash
# 1. YOUR-USERNAME/YOUR-REPO を実際の値に変更
vi configmap-sample.yaml

# 2. 適用
kubectl apply -f configmap-sample.yaml
```

### 🔒 secret.yaml.template
GitHub Personal Access Token を格納する Secret のテンプレート。

**⚠️ 重要: このファイルは Git にコミットしないでください！**

## Secret の作成方法

### 方法1: コマンドラインから直接作成（推奨）

```bash
# GitHub トークンを環境変数に設定
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Secret を作成
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=$GITHUB_TOKEN \
  --namespace=github-poller

# 確認
kubectl get secret github-poller-secret -n github-poller
```

### 方法2: テンプレートから作成（開発環境のみ）

```bash
# 1. テンプレートをコピー
cp secret.yaml.template secret-local.yaml

# 2. YOUR_GITHUB_TOKEN_HERE を実際のトークンに置き換え
vi secret-local.yaml

# 3. Secret を作成
kubectl apply -f secret-local.yaml

# 4. ファイルを削除（重要！）
rm secret-local.yaml
```

### 方法3: 1コマンドで作成（テスト用）

```bash
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=YOUR_TOKEN_HERE \
  --namespace=github-poller
```

## GitHub Token の取得方法

1. GitHub にログイン
2. Settings → Developer settings → Personal access tokens → Tokens (classic)
3. "Generate new token (classic)" をクリック
4. 必要なスコープを選択:
   - **public_repo**: パブリックリポジトリのみの場合
   - **repo**: プライベートリポジトリも監視する場合
5. トークンを生成してコピー

## Secret の形式

Secret には以下のキーが必要です：

| キー | 説明 | 例 |
|------|------|-----|
| `github-token` | GitHub Personal Access Token | `ghp_xxxxxxxxxxxx` |

### Secret の内部構造

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-poller-secret
  namespace: github-poller
type: Opaque
stringData:
  github-token: "ghp_xxxxxxxxxxxxxxxxxxxx"
```

## Secret の確認

```bash
# Secret が存在するか確認
kubectl get secret github-poller-secret -n github-poller

# Secret の詳細を表示（Base64 エンコードされた状態）
kubectl get secret github-poller-secret -n github-poller -o yaml

# Secret の値をデコード（注意: ターミナルに表示されます）
kubectl get secret github-poller-secret -n github-poller -o jsonpath='{.data.github-token}' | base64 -d
```

## Secret の更新

```bash
# 既存の Secret を削除
kubectl delete secret github-poller-secret -n github-poller

# 新しいトークンで再作成
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=NEW_TOKEN_HERE \
  --namespace=github-poller
```

または、直接編集：

```bash
# Secret を Base64 エンコードして編集
kubectl edit secret github-poller-secret -n github-poller
```

## セキュリティのベストプラクティス

### ✅ 推奨

1. **コマンドラインで作成**: ファイルにトークンを保存しない
2. **環境変数を使用**: `$GITHUB_TOKEN` で渡す
3. **最小権限**: 必要最小限のスコープのみ付与
4. **定期的な更新**: トークンを定期的にローテーション
5. **Secret 管理ツール**: 本番環境では以下を検討
   - [External Secrets Operator](https://external-secrets.io/)
   - [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
   - [HashiCorp Vault](https://www.vaultproject.io/)
   - クラウドプロバイダーの Secret Manager

### ❌ 避けるべき

1. **Git にコミット**: 絶対に Secret を Git にコミットしない
2. **プレーンテキスト**: トークンをプレーンテキストファイルに保存しない
3. **過剰な権限**: 不要なスコープを付与しない
4. **共有**: トークンを他人と共有しない

## トラブルシューティング

### Secret が見つからない

```bash
# 正しい namespace を指定しているか確認
kubectl get secret -n github-poller

# Secret を再作成
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=$GITHUB_TOKEN \
  --namespace=github-poller
```

### 認証エラー

```bash
# トークンが正しいか確認（GitHub API でテスト）
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# 正常な場合は、ユーザー情報が返ります
```

### Pod が Secret を読めない

```bash
# Pod の状態を確認
kubectl describe pod <pod-name>

# Secret がマウントされているか確認
kubectl get pod <pod-name> -o yaml | grep -A 10 volumes
```

## 本番環境への移行

開発環境でテストが完了したら、本番環境では以下を検討してください：

1. **External Secrets Operator** を使用
2. **Namespace を分離**: 本番用の専用 namespace を作成
3. **RBAC を強化**: Secret へのアクセスを制限
4. **監査ログ**: Secret アクセスのログを記録
5. **自動ローテーション**: トークンの自動更新

---

**次のステップ**: Secret を作成したら、[examples/README.md](../README.md) に戻ってシステム全体をテストしてください。

