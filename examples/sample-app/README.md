# サンプルアプリケーション

GitHub Poller をテストするための最小限のアプリケーションです。

## 使い方

### 1. GitHub リポジトリを作成

```bash
# 新しいリポジトリを作成（GitHub で）
# 例: https://github.com/your-username/poller-test
```

### 2. このディレクトリをプッシュ

```bash
# ローカルで Git リポジトリを初期化
cd examples/sample-app
git init
git add .
git commit -m "Initial commit"

# GitHub リポジトリにプッシュ
git remote add origin https://github.com/your-username/poller-test.git
git branch -M main
git push -u origin main
```

### 3. ConfigMap を設定

```yaml
repositories:
  - name: "poller-test"
    url: "https://github.com/your-username/poller-test"
    branch: "main"
    pipeline: "demo-pipeline"
    params:
      - name: "repo-url"
        value: "${repo.url}"
      - name: "branch"
        value: "${repo.branch}"
    lastCheckedSHA: ""
```

### 4. 変更をテスト

```bash
# hello.py を編集
echo 'print("Updated!")' >> hello.py

# コミット＆プッシュ
git add hello.py
git commit -m "Update hello.py"
git push

# GitHub Poller が次回実行時に変更を検出し、
# demo-pipeline が自動的に起動されます
```

## 動作確認

```bash
# PipelineRun が作成されたか確認
kubectl get pipelinerun -l github-poller/repository=poller-test

# ログを確認
kubectl logs -l tekton.dev/pipeline=demo-pipeline -f
```

