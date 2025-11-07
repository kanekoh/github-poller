# テストスイート

GitHub Poller のテストコードです。

## テストの実行

### 基本的な実行

```bash
# すべてのテストを実行
pytest

# uv を使う場合（依存関係を自動管理）
uv run pytest

# 詳細な出力
pytest -v

# 特定のテストファイルを実行
pytest tests/test_poller.py

# 特定のテストケースを実行
pytest tests/test_poller.py::TestGitHubPoller::test_expand_placeholders
```

### uv を使った高速実行

`uv` を使うと、依存関係のインストールとテスト実行が高速化されます。

```bash
# 1回のコマンドで依存関係インストール＋テスト実行
uv run --with pytest --with pytest-cov pytest

# カバレッジ付き
uv run pytest --cov=src --cov-report=term-missing

# 仮想環境を作成してから実行（推奨）
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements-dev.txt
pytest
```

### カバレッジ付き実行

```bash
# カバレッジを測定
pytest --cov=src --cov-report=term-missing

# HTML レポートを生成
pytest --cov=src --cov-report=html

# レポートを表示（macOS/Linux）
open htmlcov/index.html
```

### マーカーを使った実行

```bash
# ユニットテストのみ実行
pytest -m unit

# 統合テストのみ実行
pytest -m integration

# 遅いテストを除外
pytest -m "not slow"
```

## セットアップ

### 開発環境の準備

#### 方法1: uv を使用（推奨・高速）

```bash
# uv のインストール（まだの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係をインストール
uv pip install -r requirements-dev.txt

# または、仮想環境も uv で管理
uv venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

#### 方法2: 標準の pip を使用

```bash
# 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 開発用依存関係をインストール
pip install -r requirements-dev.txt
```

## テストの構成

### テストファイル

- `test_poller.py`: メインのテストスイート
  - `TestGitHubPoller`: GitHubPoller クラスのユニットテスト
  - `TestPipelineRunNaming`: PipelineRun 命名規則のテスト

### テストカバレッジ

主要な機能をカバー：

- ✅ プレースホルダー展開
- ✅ GitHub API からの SHA 取得
- ✅ PipelineRun の作成
- ✅ ConfigMap の読み書き
- ✅ ポーリングロジック
- ✅ エラーハンドリング

## テストケース詳細

### プレースホルダーテスト

```python
test_expand_placeholders()               # 基本的なプレースホルダー展開
test_expand_placeholders_with_default_branch()  # デフォルト値の処理
```

### GitHub API テスト

```python
test_get_latest_commit_sha_success()     # 正常な SHA 取得
test_get_latest_commit_sha_with_git_extension()  # .git 拡張子の処理
test_get_latest_commit_sha_github_error()  # エラーハンドリング
```

### Tekton 統合テスト

```python
test_trigger_tekton_pipeline_basic()     # 基本的な PipelineRun 作成
test_trigger_tekton_pipeline_with_workspace()  # ワークスペース指定
test_trigger_tekton_pipeline_with_serviceaccount()  # ServiceAccount 指定
test_trigger_tekton_pipeline_with_timeout()  # タイムアウト指定
test_trigger_tekton_pipeline_no_pipeline_name()  # エラーケース
test_trigger_tekton_pipeline_api_error()  # API エラー
```

### ポーリングロジックテスト

```python
test_poll_repositories_no_change()       # 変更なし
test_poll_repositories_with_change()     # 変更あり、パイプライン起動
test_poll_repositories_first_check()     # 初回チェック
test_poll_repositories_github_error()    # GitHub エラー時
```

## CI/CD での実行

### GitHub Actions の例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## トラブルシューティング

### モジュールが見つからない

```bash
# PYTHONPATH を設定
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
pytest
```

### ImportError が発生する

```bash
# 依存関係を再インストール
pip install -r requirements-dev.txt --force-reinstall
```

### テストが失敗する

```bash
# 詳細なトレースバックを表示
pytest -vv --tb=long

# 最初の失敗で停止
pytest -x

# pdb デバッガーを起動
pytest --pdb
```

## コードスタイル

### フォーマッター

```bash
# Black でフォーマット
black src/ tests/

# フォーマットチェックのみ
black --check src/ tests/
```

### Linter

```bash
# flake8 でチェック
flake8 src/ tests/

# pylint でチェック
pylint src/
```

### 型チェック

```bash
# mypy で型チェック
mypy src/
```

## ベストプラクティス

1. **各テストは独立させる**: 他のテストに依存しない
2. **モックを適切に使う**: 外部依存（API、データベース）はモック化
3. **テスト名は分かりやすく**: 何をテストしているか明確に
4. **エッジケースもテスト**: 正常系だけでなく異常系も
5. **カバレッジを維持**: 80%以上を目標に

## 参考リンク

- [pytest ドキュメント](https://docs.pytest.org/)
- [unittest.mock ドキュメント](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-cov](https://pytest-cov.readthedocs.io/)

