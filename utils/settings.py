"""
設定管理モジュール
st.secrets / os.environ から設定を読み取る（優先順位付き）
"""
import os
from pathlib import Path
from typing import Optional


def is_cloud() -> bool:
    """
    Streamlit Cloud環境かどうかを判定
    
    Returns:
        Cloud環境ならTrue、ローカル環境ならFalse
    """
    # Streamlit Cloudの環境変数をチェック
    if os.getenv("STREAMLIT_CLOUD") == "1":
        return True
    
    # その他のCloud判定（HOSTNAMEや/mount/srcの存在など）
    if os.getenv("HOSTNAME") and "streamlit" in os.getenv("HOSTNAME", "").lower():
        return True
    
    # /mount/src の存在をチェック（Streamlit Cloudの特徴的なパス）
    if Path("/mount/src").exists():
        return True
    
    return False


def get_database_url() -> str:
    """
    データベースURLを取得（優先順位付き）
    
    優先順位:
    1. st.secrets["connections"]["materialbase_db"]["url"] （推奨）
    2. st.secrets["DATABASE_URL"]（簡易）
    3. os.environ["DATABASE_URL"]（ローカル/CI向け）
    4. （ローカルのみ）sqlite:///materials.db フォールバック
    
    Returns:
        データベースURL文字列
    
    Raises:
        RuntimeError: Cloud環境でDATABASE_URLが設定されていない場合
    """
    # st.secretsから取得を試みる
    try:
        import streamlit as st
        secrets = st.secrets
        
        # 推奨: connections.materialbase_db.url
        try:
            url = secrets.get("connections", {}).get("materialbase_db", {}).get("url")
            if url:
                return str(url)
        except Exception:
            pass
        
        # 簡易: DATABASE_URL
        try:
            url = secrets.get("DATABASE_URL")
            if url:
                return str(url)
        except Exception:
            pass
    except Exception:
        # streamlitがimportできない場合（スクリプト実行時など）は無視
        pass
    
    # os.environから取得
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    
    # ローカル環境のみ: SQLiteフォールバック
    if not is_cloud():
        return "sqlite:///./materials.db"
    
    # Cloud環境でDATABASE_URLが無い場合は例外
    raise RuntimeError(
        "DATABASE_URL is required on Streamlit Cloud. "
        "Please set it in Streamlit Secrets (connections.materialbase_db.url or DATABASE_URL)."
    )


def get_db_dialect(url: str) -> str:
    """
    データベースURLからdialect（postgresql/sqlite）を判定
    
    Args:
        url: データベースURL
    
    Returns:
        'postgresql' または 'sqlite'
    """
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return "postgresql"
    elif url.startswith("sqlite:///"):
        return "sqlite"
    else:
        # デフォルトはpostgresqlとみなす
        return "postgresql"


def mask_db_url(url: str) -> str:
    """
    データベースURLをマスク（パスワードを隠す）
    デバッグ表示用
    
    Args:
        url: データベースURL
    
    Returns:
        パスワードをマスクしたURL
    """
    # postgresql://user:password@host:port/dbname
    if "://" in url and "@" in url:
        parts = url.split("://")
        if len(parts) == 2:
            scheme = parts[0]
            rest = parts[1]
            if "@" in rest:
                auth_part, host_part = rest.split("@", 1)
                if ":" in auth_part:
                    user = auth_part.split(":")[0]
                    masked = f"{scheme}://{user}:***@{host_part}"
                    return masked
    return url
