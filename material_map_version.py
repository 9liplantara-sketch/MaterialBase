"""
Material Map バージョン情報モジュール

APP_VERSION: Git commit short SHA（優先）または環境変数 GIT_SHA、無ければ "unknown"
BUILD_TIME_UTC: ビルド時刻（ISO8601形式）
"""
import os
import subprocess
from datetime import datetime, timezone
from typing import Tuple


def get_app_version() -> str:
    """
    APP_VERSIONを取得（git commit short SHA を優先）
    
    Returns:
        Git commit short SHA、または環境変数 GIT_SHA、無ければ "unknown"
    """
    # 1. git rev-parse --short HEAD を試す
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.abspath(__file__))
        ).decode().strip()
        if sha:
            return sha
    except Exception:
        pass
    
    # 2. 環境変数 GIT_SHA を読む
    git_sha = os.environ.get("GIT_SHA")
    if git_sha:
        return git_sha
    
    # 3. どちらも無い場合は "unknown"
    return "unknown"


def get_build_time_utc() -> str:
    """
    BUILD_TIME_UTCを取得（ISO8601形式）
    
    Returns:
        ビルド時刻（ISO8601形式、UTC）
    """
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def get_version_info() -> Tuple[str, str]:
    """
    バージョン情報を取得
    
    Returns:
        (APP_VERSION, BUILD_TIME_UTC) のタプル
    """
    return get_app_version(), get_build_time_utc()


# モジュール読み込み時に取得（起動時ログ用）
APP_VERSION = get_app_version()
BUILD_TIME_UTC = get_build_time_utc()

# 起動時ログ
if __name__ != "__main__":
    print(f"[Material Map] APP_VERSION: {APP_VERSION}, BUILD_TIME_UTC: {BUILD_TIME_UTC}")


if __name__ == "__main__":
    # テスト実行
    version, build_time = get_version_info()
    print(f"APP_VERSION: {version}")
    print(f"BUILD_TIME_UTC: {build_time}")

