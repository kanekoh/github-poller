#!/usr/bin/env python3
"""
サンプルアプリケーション - GitHub Poller テスト用

このファイルを GitHub リポジトリにプッシュして、
GitHub Poller が変更を検出してパイプラインを起動することをテストできます。
"""

def main():
    """メイン関数"""
    print("=" * 60)
    print("  GitHub Poller Sample Application")
    print("=" * 60)
    print()
    print("✅ アプリケーションが正常に実行されました！")
    print()
    print("このファイルを変更して Git にプッシュすると、")
    print("GitHub Poller が変更を検出してパイプラインを起動します。")
    print()
    print("Version: 1.0.0")
    print("=" * 60)


if __name__ == "__main__":
    main()

