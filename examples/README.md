# GitHub Poller サンプル

このディレクトリには、GitHub Poller をすぐに試せるサンプルが含まれています。

## 含まれるファイル

```
examples/
├── README.md                    # このファイル
├── sample-app/                  # サンプルアプリケーション
│   └── hello.py                # シンプルな Python アプリ
├── tekton/                      # Tekton リソース
│   ├── task-echo.yaml          # Echo タスク（ログ出力用）
│   └── pipeline-demo.yaml      # デモパイプライン
└── kubernetes/                  # Kubernetes リソース
    ├── configmap-sample.yaml   # サンプル設定
    └── test-secret.yaml        # テスト用 Secret
```

## クイックスタート

### 前提条件

1. Kubernetes クラスタが稼働中
2. Tekton Pipelines がインストール済み
3. GitHub Poller がデプロイ済み

### 手順

#### 1. Tekton リソースをデプロイ

```bash
# サンプルの Task と Pipeline を作成
kubectl apply -f examples/tekton/
```

#### 2. ConfigMap を更新

サンプルの ConfigMap を編集して、実際の GitHub リポジトリ情報を設定：

```bash
# ConfigMap を編集
vi examples/kubernetes/configmap-sample.yaml

# 適用
kubectl apply -f examples/kubernetes/configmap-sample.yaml
```

#### 3. Secret を設定

```bash
# GitHub トークンを設定
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=YOUR_GITHUB_TOKEN_HERE \
  --namespace=default

# または、テンプレートから作成（開発環境のみ）
cp examples/kubernetes/secret.yaml.template examples/kubernetes/secret-local.yaml
vi examples/kubernetes/secret-local.yaml  # トークンを設定
kubectl apply -f examples/kubernetes/secret-local.yaml
rm examples/kubernetes/secret-local.yaml  # 使用後は削除

# 💡 詳細は examples/kubernetes/README.md を参照
```

#### 5. CronJob を手動実行してテスト

```bash
# 手動でジョブを作成
kubectl create job --from=cronjob/github-poller github-poller-test -n github-poller

# ログを確認
kubectl logs -f job/github-poller-test -n github-poller

# PipelineRun が作成されたか確認
kubectl get pipelinerun -n github-poller

# PipelineRun のログを確認
kubectl logs -l tekton.dev/pipeline=demo-pipeline -n github-poller -f
```

#### 6. 結果の確認

```bash
# ConfigMap が更新されているか確認
kubectl get configmap github-poller-config -n github-poller -o yaml

# PipelineRun の詳細を確認
kubectl describe pipelinerun <pipelinerun-name> -n github-poller
```

## サンプルアプリについて

`sample-app/hello.py` は、GitHub にプッシュして試すための最小限のアプリケーションです。

### 使い方

1. 自分の GitHub リポジトリを作成
2. `sample-app/` の内容をプッシュ
3. `configmap-sample.yaml` でそのリポジトリを指定
4. CronJob が変更を検出すると、自動的にパイプラインが起動されます

## トラブルシューティング

### パイプラインが起動しない

```bash
# Poller のログを確認
kubectl logs -l app=github-poller --tail=100

# ConfigMap の設定を確認
kubectl get configmap github-poller-config -o yaml
```

### パイプラインが失敗する

```bash
# PipelineRun の状態を確認
kubectl get pipelinerun

# 詳細なログを確認
kubectl describe pipelinerun <pipelinerun-name>
```

### 権限エラー

```bash
# ServiceAccount の権限を確認
kubectl auth can-i create pipelineruns --as=system:serviceaccount:github-poller:github-poller
```

## カスタマイズ

### 独自のパイプラインを作成

1. `examples/tekton/` を参考に独自の Pipeline を作成
2. `configmap-sample.yaml` で新しい Pipeline 名を指定
3. 必要なパラメータを追加

### 複数リポジトリの監視

`configmap-sample.yaml` に複数のリポジトリエントリを追加するだけです：

```yaml
repositories:
  - name: "repo1"
    url: "https://github.com/your-org/repo1"
    branch: "main"
    pipeline: "demo-pipeline"
    # ...
  - name: "repo2"
    url: "https://github.com/your-org/repo2"
    branch: "develop"
    pipeline: "another-pipeline"
    # ...
```

