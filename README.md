# GitHub Poller for Kubernetes

Kubernetes CronJob として動作する GitHub リポジトリ監視システムです。定期的に GitHub リポジトリの変更をポーリングし、変更が検出された場合に Tekton パイプラインを自動起動します。

## 概要

このシステムは、Webhook が利用できない環境（インターネットから隔離されたクラスタなど）において、GitHub リポジトリの変更を検知し、CI/CD パイプラインを自動実行するために設計されています。

### 参考文献

このプロジェクトのアイディアは、Red Hat の以下のブログ記事をベースに実装されています：

📖 [Polling triggers in OpenShift Pipeline](https://www.redhat.com/ja/blog/polling-triggers-in-openshift-pipeline) - Red Hat Blog

ブログ記事では CronJob と EventListener を組み合わせたアプローチが紹介されていますが、本実装では以下の改良を加えています：

- **Kubernetes API 直接利用**: EventListener を経由せず、Kubernetes Python Client で PipelineRun を直接作成
- **プレースホルダー機能**: ConfigMap の冗長性を削減する変数展開機能
- **包括的なテストスイート**: 76% のコードカバレッジを持つユニットテスト
- **Red Hat UBI ベース**: エンタープライズグレードのコンテナイメージ

### 主な特徴

- **軽量**: Git クローンを行わず、GitHub API でメタ情報のみを取得
- **柔軟な設定**: ConfigMap で複数のリポジトリを管理
- **ステートフル**: 前回チェックしたコミット SHA を ConfigMap に保存
- **Tekton 統合**: Kubernetes API で PipelineRun リソースを直接作成
- **Kubernetes ネイティブ**: CronJob として定期実行、外部 CLI 不要

## アーキテクチャ

```
┌─────────────────┐
│  GitHub.com     │
│  (Public/Cloud) │
└────────┬────────┘
         │ API (HTTPS)
         │
┌────────▼──────────────────────────────────────┐
│ Kubernetes Cluster                             │
│                                                │
│  ┌──────────────┐      ┌──────────────────┐  │
│  │  CronJob     │      │  ConfigMap       │  │
│  │  (5分ごと)   │◄────►│  - リポジトリ設定│  │
│  │              │      │  - 最終SHA       │  │
│  └──────┬───────┘      └──────────────────┘  │
│         │                                      │
│         │ 変更検出時                           │
│         ▼                                      │
│  ┌──────────────┐      ┌──────────────────┐  │
│  │ K8s API      │─────►│ PipelineRun      │  │
│  │ (Create)     │      │ (Tekton)         │  │
│  └──────────────┘      └──────────────────┘  │
│                                                │
│  ┌──────────────┐                             │
│  │  Secret      │                             │
│  │  (GitHub     │                             │
│  │   Token)     │                             │
│  └──────────────┘                             │
└────────────────────────────────────────────────┘
```

## ディレクトリ構成

```
github-poller/
├── src/
│   └── poller.py              # メインのポーリングスクリプト
├── tests/                     # テストコード
│   ├── __init__.py
│   ├── test_poller.py         # ユニットテスト
│   └── README.md              # テスト実行方法
├── k8s/
│   ├── serviceaccount.yaml    # ServiceAccount 定義
│   ├── role.yaml              # RBAC Role（ConfigMap 読み書き、PipelineRun 作成）
│   ├── rolebinding.yaml       # RoleBinding
│   ├── secret.yaml            # GitHub トークン用 Secret（サンプル）
│   ├── configmap.yaml         # リポジトリ設定（サンプル）
│   └── cronjob.yaml           # CronJob 定義
├── examples/                  # サンプル・テスト用リソース
│   ├── README.md              # サンプルの使い方
│   ├── sample-app/            # テスト用アプリケーション
│   ├── tekton/                # デモ用 Tekton リソース
│   └── kubernetes/            # サンプル ConfigMap/Secret
├── Dockerfile                 # コンテナイメージビルド用
├── requirements.txt           # Python 依存関係
├── requirements-dev.txt       # 開発・テスト用依存関係
├── pytest.ini                 # pytest 設定
├── .coveragerc                # カバレッジ設定
├── Makefile                   # タスクランナー
└── README.md                  # このファイル
```

## 🚀 クイックスタート（サンプルで試す）

すぐに動作を確認したい場合は、`examples/` ディレクトリに含まれるサンプルを使用してください。

### 必要なもの

- Kubernetes クラスタが稼働中
- `kubectl` コマンドが使用可能
- GitHub Personal Access Token

### 5分で試す手順

```bash
# 1. Tekton Pipelines のインストール（未インストールの場合）
kubectl apply -f https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml

# 2. サンプルの Tekton リソースをデプロイ
kubectl apply -f examples/tekton/

# 3. GitHub トークンで Secret を作成
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=YOUR_GITHUB_TOKEN_HERE \
  --namespace=default

# 4. サンプル ConfigMap を編集
# YOUR-USERNAME/YOUR-REPO を実際の GitHub リポジトリに変更
vi examples/kubernetes/configmap-sample.yaml

# 5. ConfigMap を適用
kubectl apply -f examples/kubernetes/configmap-sample.yaml

# 6. GitHub Poller の本体をデプロイ（イメージビルドが必要）
# ※ このステップは「セットアップ手順」を参照してください

# 7. 手動でテスト実行
kubectl create job --from=cronjob/github-poller github-poller-test

# 8. ログを確認
kubectl logs -f job/github-poller-test

# 9. パイプラインが起動されたか確認
kubectl get pipelinerun

# 10. パイプラインのログを確認
kubectl logs -l tekton.dev/pipeline=demo-pipeline -f
```

### サンプルの内容

#### 📦 examples/sample-app/
GitHub にプッシュしてテストできる最小限のサンプルアプリケーション。

#### 🔧 examples/tekton/
- **task-echo.yaml**: ログ出力用のシンプルなタスク
- **pipeline-demo.yaml**: 5ステップのデモパイプライン
  1. 🚀 開始通知
  2. 📥 情報取得シミュレーション
  3. 🔨 ビルドシミュレーション
  4. 🧪 テストシミュレーション
  5. ✅ 完了通知

各ステップで**分かりやすいログ**を出力するため、パイプラインが起動されたことが一目で分かります：

```
==================================================================
  Tekton Pipeline Triggered by GitHub Poller
==================================================================

📋 Pipeline Parameters:
  • Message:     🚀 Pipeline Started - Change detected!
  • Repository:  https://github.com/your-org/your-repo
  • Branch:      main

🕐 Execution Time:
  • Date: 2025-11-07
  • Time: 14:30:45 UTC

⚙️  Simulating work...
  Step 1/5 - Processing...
  ✅ Work completed successfully!
```

#### ⚙️ examples/kubernetes/
- **configmap-sample.yaml**: サンプル ConfigMap（すぐに使える）
- **test-secret.yaml**: Secret のテンプレート

### 動作確認の流れ

1. サンプルアプリを自分の GitHub リポジトリにプッシュ
2. ConfigMap でそのリポジトリを監視対象に設定
3. ファイルを変更してプッシュ
4. CronJob が変更を検出（最大5分待機）
5. **デモパイプラインが自動起動** 🎉
6. ログで実行を確認

詳細は [examples/README.md](examples/README.md) を参照してください。

---

## セットアップ手順（本番環境）

### 前提条件

- Kubernetes クラスタ（v1.21 以降推奨）
- Tekton Pipelines がインストール済み
- Docker または Podman（イメージビルド用）
- コンテナレジストリへのアクセス
- GitHub Personal Access Token

### 1. GitHub Personal Access Token の作成

1. GitHub の Settings → Developer settings → Personal access tokens → Tokens (classic) にアクセス
2. "Generate new token (classic)" をクリック
3. 必要なスコープを選択：
   - **public_repo**: パブリックリポジトリのみの場合
   - **repo**: プライベートリポジトリも含む場合
4. トークンを生成してコピー

### 2. コンテナイメージのビルドとプッシュ

```bash
# イメージをビルド（Red Hat UBI9 + Python 3.12 ベース）
docker build -t your-registry/github-poller:latest .

# レジストリにプッシュ
docker push your-registry/github-poller:latest
```

**注意**: Red Hat UBI イメージを使用しています。認証なしで利用可能ですが、Red Hat カタログからイメージを取得します。

### 3. Secret の作成

**推奨: コマンドラインから直接作成**（Git にトークンを保存しない）

```bash
# 環境変数に GitHub トークンを設定
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Secret を作成
kubectl create secret generic github-poller-secret \
  --from-literal=github-token=$GITHUB_TOKEN \
  --namespace=default

# 確認
kubectl get secret github-poller-secret -n default
```

**または、テンプレートから作成**（開発環境のみ）

```bash
# k8s/secret.yaml を編集してトークンを設定
cp k8s/secret.yaml k8s/secret-local.yaml
vi k8s/secret-local.yaml  # YOUR_GITHUB_TOKEN_HERE を実際のトークンに置き換え

# Secret を作成
kubectl apply -f k8s/secret-local.yaml

# 使用後は削除（重要！）
rm k8s/secret-local.yaml
```

⚠️ **重要**: Secret ファイルを Git にコミットしないでください。`.gitignore` で保護されています。

### 4. ConfigMap の設定

`k8s/configmap.yaml` を編集して、監視対象のリポジトリを設定します：

```yaml
data:
  config.yaml: |
    repositories:
      - name: "my-app"
        url: "https://github.com/your-org/my-app"
        branch: "main"
        pipeline: "build-pipeline"
        params:
          - name: "repo-url"
            value: "https://github.com/your-org/my-app"
          - name: "branch"
            value: "main"
        lastCheckedSHA: ""
```

ConfigMap を作成：

```bash
kubectl apply -f k8s/configmap.yaml
```

### 5. RBAC の設定

```bash
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/role.yaml
kubectl apply -f k8s/rolebinding.yaml
```

### 6. CronJob のデプロイ

`k8s/cronjob.yaml` を編集してイメージ名を更新：

```yaml
image: your-registry/github-poller:latest
```

CronJob を作成：

```bash
kubectl apply -f k8s/cronjob.yaml
```

## ConfigMap 設定詳細

### 基本設定

```yaml
repositories:
  - name: "リポジトリの識別名"
    url: "https://github.com/owner/repo"
    branch: "監視対象ブランチ（デフォルト: main）"
    pipeline: "起動する Tekton Pipeline 名"
    params:  # Tekton パイプラインに渡すパラメータ
      - name: "パラメータ名"
        value: "パラメータ値"
    lastCheckedSHA: ""  # 自動更新されます（空のままで OK）
```

### プレースホルダー

パラメータ値でプレースホルダーを使用して、リポジトリ設定の値を自動的に展開できます：

- `${repo.url}`: リポジトリの URL
- `${repo.branch}`: ブランチ名
- `${repo.name}`: リポジトリ名

**例**:
```yaml
- name: "my-app"
  url: "https://github.com/your-org/my-app"
  branch: "main"
  pipeline: "build-pipeline"
  params:
    - name: "repo-url"
      value: "${repo.url}"      # "https://github.com/your-org/my-app" に展開
    - name: "branch"
      value: "${repo.branch}"   # "main" に展開
    - name: "app-name"
      value: "${repo.name}"     # "my-app" に展開
```

これにより、ConfigMap の冗長性を削減し、設定の保守性が向上します。

### 高度な設定

#### ワークスペースの指定

```yaml
- name: "api-service"
  url: "https://github.com/your-org/api-service"
  branch: "develop"
  pipeline: "api-build-pipeline"
  workspaces:
    - name: "source"
      claimName: "pipeline-workspace-pvc"
  params:
    - name: "repo-url"
      value: "${repo.url}"
  lastCheckedSHA: ""
```

#### ServiceAccount の指定

```yaml
- name: "secure-app"
  url: "https://github.com/your-org/secure-app"
  branch: "main"
  pipeline: "secure-build-pipeline"
  serviceAccount: "tekton-pipeline-sa"
  params:
    - name: "repo-url"
      value: "${repo.url}"
  lastCheckedSHA: ""
```

#### タイムアウトの指定

```yaml
- name: "long-running-app"
  url: "https://github.com/your-org/long-running-app"
  branch: "main"
  pipeline: "long-build-pipeline"
  timeout: "2h"  # 2時間でタイムアウト（デフォルト: 1h）
  params:
    - name: "repo-url"
      value: "${repo.url}"
  lastCheckedSHA: ""
```

## 動作確認

### CronJob の状態確認

```bash
# CronJob の確認
kubectl get cronjob github-poller

# 最近のジョブ実行履歴
kubectl get jobs -l app=github-poller

# Pod のログ確認
kubectl logs -l app=github-poller --tail=100
```

### 手動実行（テスト用）

```bash
# CronJob から手動でジョブを作成
kubectl create job --from=cronjob/github-poller github-poller-manual

# ログを確認
kubectl logs -l job-name=github-poller-manual -f
```

### ConfigMap の確認

```bash
# 現在の設定を確認
kubectl get configmap github-poller-config -o yaml

# SHA が更新されているか確認
kubectl get configmap github-poller-config -o jsonpath='{.data.config\.yaml}' | grep lastCheckedSHA
```

## トラブルシューティング

### ログの確認

```bash
# 最新の Pod のログを確認
kubectl logs -l app=github-poller --tail=100 -f

# 特定の Job のログを確認
kubectl logs job/github-poller-28381234 -f
```

### よくある問題

#### 1. GitHub API 認証エラー

**エラー**: `GitHub API error: 401 Bad credentials`

**解決策**:
- Secret に正しい GitHub トークンが設定されているか確認
- トークンに適切なスコープ（repo または public_repo）が付与されているか確認

```bash
# Secret の確認
kubectl get secret github-poller-secret -o jsonpath='{.data.github-token}' | base64 -d
```

#### 2. ConfigMap の更新権限エラー

**エラー**: `Failed to update ConfigMap: Forbidden`

**解決策**:
- ServiceAccount に適切な権限があるか確認
- Role と RoleBinding が正しく設定されているか確認

```bash
# Role の確認
kubectl get role github-poller -o yaml

# RoleBinding の確認
kubectl get rolebinding github-poller -o yaml
```

#### 3. Pipeline の起動に失敗

**エラー**: `Failed to trigger pipeline`

**解決策**:
- 指定した Pipeline 名が正しいか確認
- ServiceAccount に PipelineRun 作成権限があるか確認
- Tekton が正しくインストールされているか確認

```bash
# Pipeline の確認
kubectl get pipeline

# 権限の確認
kubectl auth can-i create pipelineruns --as=system:serviceaccount:default:github-poller

# Tekton のインストール確認
kubectl get crd | grep tekton
```

#### 4. PipelineRun の作成エラー

**エラー**: `Failed to create PipelineRun: the server could not find the requested resource`

**解決策**:
- Tekton Pipelines がインストールされているか確認

```bash
# Tekton のインストール
kubectl apply -f https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml

# インストール確認
kubectl get pods -n tekton-pipelines
```

## カスタマイズ

### ポーリング間隔の変更

`k8s/cronjob.yaml` の `schedule` フィールドを変更：

```yaml
spec:
  # 毎10分: "*/10 * * * *"
  # 毎時: "0 * * * *"
  # 毎日9時: "0 9 * * *"
  schedule: "*/5 * * * *"
```

### タイムアウトの変更

```yaml
spec:
  jobTemplate:
    spec:
      # 600秒（10分）からカスタマイズ
      activeDeadlineSeconds: 600
```

### リソース制限の調整

```yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "200m"
```

## セキュリティ考慮事項

1. **GitHub トークン**: 最小限の権限（public_repo）を推奨
2. **Secret 管理**: 可能であれば External Secrets Operator や Vault を使用
3. **ネットワークポリシー**: 必要な通信のみを許可
4. **非 root ユーザー**: コンテナは UID 1001 で実行（Red Hat UBI 標準）
5. **イメージスキャン**: 定期的に脆弱性スキャンを実施
6. **UBI ベースイメージ**: Red Hat が提供するセキュアで検証済みのベースイメージを使用

## ライセンス

このプロジェクトは自由に使用・改変できます。

## 開発者向け情報

### テストの実行

このプロジェクトには包括的なテストスイートが含まれています。

#### 方法1: uv を使用（推奨・高速）

[uv](https://github.com/astral-sh/uv) は高速な Python パッケージマネージャーです。

```bash
# uv のインストール（まだの場合）
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# または Homebrew
brew install uv

# 依存関係をインストールしてテストを実行
uv pip install -r requirements-dev.txt

# テストを実行
uv run pytest

# カバレッジ付きで実行
uv run pytest --cov=src --cov-report=term-missing --cov-report=html

# HTML カバレッジレポートを表示
open htmlcov/index.html
```

#### 方法2: 標準の pip を使用

```bash
# 仮想環境を作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 開発用依存関係をインストール
pip install -r requirements-dev.txt

# すべてのテストを実行
pytest

# カバレッジ付きで実行
pytest --cov=src --cov-report=term-missing --cov-report=html

# HTML カバレッジレポートを表示
open htmlcov/index.html
```

#### 方法3: uv で仮想環境も管理

```bash
# uv で仮想環境を作成
uv venv

# 仮想環境を有効化
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係をインストール
uv pip install -r requirements-dev.txt

# テストを実行
pytest
```

#### 方法4: Makefile を使用（最も簡単）

```bash
# 利用可能なコマンドを表示
make help

# uv で依存関係をインストール
make install-uv

# テストを実行
make test

# カバレッジ付きでテストを実行
make test-cov
```

テストの詳細は [tests/README.md](tests/README.md) を参照してください。

### ローカルでのテスト

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
export GITHUB_TOKEN="your_token_here"
export NAMESPACE="default"
export CONFIGMAP_NAME="github-poller-config"

# kubeconfig が設定されていることを確認
kubectl config current-context

# スクリプトの実行
python src/poller.py
```

### コードの構造

- `GitHubPoller` クラス: メインのロジック
  - `get_configmap()`: ConfigMap から設定を取得
  - `update_configmap()`: ConfigMap を更新
  - `get_latest_commit_sha()`: GitHub API でコミット SHA を取得
  - `_expand_placeholders()`: プレースホルダーを展開
  - `trigger_tekton_pipeline()`: Kubernetes API で PipelineRun を作成
  - `poll_repositories()`: 全リポジトリをポーリング

### 拡張のアイデア

1. **Slack/Teams 通知**: 変更検出時やエラー時に通知
2. **メトリクス**: Prometheus メトリクスのエクスポート
3. **WebUI**: 監視状態を可視化するダッシュボード
4. **複数ブランチ**: 1つのリポジトリの複数ブランチを監視
5. **タグ監視**: ブランチだけでなくタグのリリースも監視

## サポート

問題が発生した場合は、以下を確認してください：

1. Pod のログ
2. ConfigMap の設定
3. Secret の内容
4. RBAC の権限
5. Tekton Pipeline の定義

### 初めて使う場合

まずは **[examples/](examples/)** ディレクトリのサンプルを試すことをお勧めします：

```bash
# サンプルのクイックスタート
cd examples/
cat README.md  # 詳細な手順を確認
```

---

## 参考資料

### オリジナルのアイディア

- [Polling triggers in OpenShift Pipeline](https://www.redhat.com/ja/blog/polling-triggers-in-openshift-pipeline) - Red Hat Blog  
  Daein Park 氏による OpenShift Pipeline でのポーリングトリガーの実装方法

### 関連ドキュメント

- [Tekton Pipelines Documentation](https://tekton.dev/docs/)
- [Kubernetes Python Client](https://github.com/kubernetes-client/python)
- [PyGithub Documentation](https://pygithub.readthedocs.io/)

---

**Note**: このシステムは GitHub API のレート制限（認証済みリクエスト: 5000回/時間）に注意してください。多数のリポジトリを短い間隔で監視する場合は、レート制限に達する可能性があります。

