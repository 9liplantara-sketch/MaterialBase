"""
データベース接続のキャッシュ管理
Streamlit の st.cache_resource を使用して engine/sessionmaker をプロセス内で一度だけ作成
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Streamlit のインポートを安全に行う
try:
    import streamlit as st
except Exception:
    st = None

# utils.settings を安全に import
try:
    from utils.settings import get_database_url, get_db_dialect, is_cloud
except Exception:
    # フォールバック
    def get_database_url():
        return os.getenv("DATABASE_URL", "sqlite:///./materials.db")
    
    def get_db_dialect(url: str):
        if url.startswith(("postgresql://", "postgres://")):
            return "postgresql"
        elif url.startswith("sqlite:///"):
            return "sqlite"
        else:
            return "postgresql"
    
    def is_cloud():
        return False


def _create_engine_impl(db_url: str):
    """
    engine を作成（内部実装、キャッシュされない）
    
    Args:
        db_url: データベースURL
    
    Returns:
        SQLAlchemy Engine
    """
    dialect = get_db_dialect(db_url)
    DEBUG_MODE = os.getenv("DEBUG", "0") == "1"
    
    if dialect == "postgresql":
        # Postgres設定
        engine = create_engine(
            db_url,
            pool_pre_ping=True,  # 接続の死活監視
            future=True,  # SQLAlchemy 2.0互換
            echo=DEBUG_MODE,  # DEBUG時のみSQLログ
        )
    elif dialect == "sqlite":
        # SQLite設定（ローカル開発用）
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=DEBUG_MODE,  # DEBUG時のみSQLログ
        )
    else:
        raise ValueError(f"Unsupported database dialect: {dialect}")
    
    return engine


def _create_sessionmaker_impl(engine):
    """
    sessionmaker を作成（内部実装、キャッシュされない）
    
    Args:
        engine: SQLAlchemy Engine
    
    Returns:
        SQLAlchemy sessionmaker
    """
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False
    )


# Streamlit が利用可能な場合のみ cache_resource を使用
if st is not None:
    @st.cache_resource
    def get_engine(db_url: str = None):
        """
        SQLAlchemy Engine を取得（プロセス内で一度だけ作成、キャッシュされる）
        
        Args:
            db_url: データベースURL（Noneの場合は自動取得）
        
        Returns:
            SQLAlchemy Engine
        """
        if db_url is None:
            db_url = get_database_url()
        return _create_engine_impl(db_url)
    
    @st.cache_resource
    def get_sessionmaker(db_url: str = None):
        """
        SQLAlchemy sessionmaker を取得（プロセス内で一度だけ作成、キャッシュされる）
        
        Args:
            db_url: データベースURL（Noneの場合は自動取得）
        
        Returns:
            SQLAlchemy sessionmaker
        """
        if db_url is None:
            db_url = get_database_url()
        engine = get_engine(db_url)
        return _create_sessionmaker_impl(engine)
else:
    # Streamlit が利用できない場合（テスト環境など）はキャッシュなし
    _engine_cache = {}
    _sessionmaker_cache = {}
    
    def get_engine(db_url: str = None):
        if db_url is None:
            db_url = get_database_url()
        if db_url not in _engine_cache:
            _engine_cache[db_url] = _create_engine_impl(db_url)
        return _engine_cache[db_url]
    
    def get_sessionmaker(db_url: str = None):
        if db_url is None:
            db_url = get_database_url()
        if db_url not in _sessionmaker_cache:
            engine = get_engine(db_url)
            _sessionmaker_cache[db_url] = _create_sessionmaker_impl(engine)
        return _sessionmaker_cache[db_url]
