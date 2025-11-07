# GitHub Poller - Makefile

.PHONY: help install install-uv test test-cov lint format clean docker-build

# デフォルトターゲット
help:
	@echo "GitHub Poller - 利用可能なコマンド:"
	@echo ""
	@echo "  make install       - pip で依存関係をインストール"
	@echo "  make install-uv    - uv で依存関係をインストール（高速）"
	@echo "  make test          - テストを実行"
	@echo "  make test-cov      - カバレッジ付きでテストを実行"
	@echo "  make lint          - コード品質チェック"
	@echo "  make format        - コードフォーマット"
	@echo "  make clean         - 一時ファイルを削除"
	@echo "  make docker-build  - Docker イメージをビルド"
	@echo ""

# 依存関係のインストール（pip）
install:
	pip install -r requirements-dev.txt

# 依存関係のインストール（uv）
install-uv:
	uv pip install -r requirements-dev.txt

# テストを実行
test:
	pytest -v

# カバレッジ付きでテストを実行
test-cov:
	pytest --cov=src --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "HTML レポート: htmlcov/index.html"

# Linter を実行
lint:
	flake8 src/ tests/
	pylint src/

# コードフォーマット
format:
	black src/ tests/

# 型チェック
typecheck:
	mypy src/

# 一時ファイルを削除
clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Docker イメージをビルド
docker-build:
	docker build -t github-poller:latest .

# Docker イメージをビルド（タグ指定）
docker-build-tag:
	@read -p "Enter image tag (e.g., your-registry/github-poller:v1.0.0): " tag; \
	docker build -t $$tag .

# すべてのチェックを実行（CI/CD用）
ci: test-cov lint typecheck
	@echo ""
	@echo "すべてのチェックが完了しました！"

