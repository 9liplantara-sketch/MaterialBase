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


# ===== Phase 2: DBセッション統一API =====
# Streamlit側で database.get_db() generator を二度と使わない構造にする

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    読み取り専用セッションを取得（context manager）
    
    Usage:
        with get_session() as db:
            result = db.execute(...)
            # commit/rollbackは自動で行われない（読み取り専用）
    
    Note:
        - commit/rollbackは呼び出し側の責務
        - 読み取り専用のクエリに使用
        - 例外時も自動rollbackしない（明示的に制御するため）
    """
    session_maker = get_sessionmaker()
    session = session_maker()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    書き込み用セッションを取得（context manager、自動commit/rollback）
    
    Usage:
        with session_scope() as db:
            db.add(...)
            # 例外時は自動rollback、正常終了時は自動commit
    
    Note:
        - 正常終了時は自動commit
        - 例外時は自動rollback
        - 明示的なcommit/rollbackは不要
    """
    session_maker = get_sessionmaker()
    session = session_maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def normalize_submission_key(submission_key):
    """
    submission_key を正規化して、id (int) か uuid (str) かを判定する。
    
    Args:
        submission_key: int, str, または None
    
    Returns:
        tuple: (kind: str|None, value: int|str|None)
            - kind=="id" の場合: value は必ず int（保証）
            - kind=="uuid" の場合: value は str (UUID)
            - submission_key が None/空文字の場合: (None, None)
    
    Note:
        - kind=="id" を返すのは「入力が int」または「strで isdigit() のみ」の場合のみ
        - それ以外（uuid文字列含む）は必ず kind=="uuid" を返す
        - 返却kindとvalueの整合性を保証する（kind=="id" なら value は必ず int）
    """
    import uuid
    import logging
    import os
    
    logger = logging.getLogger(__name__)
    
    if submission_key is None:
        return (None, None)
    
    # int の場合はそのまま id として扱う
    if isinstance(submission_key, int):
        if os.getenv("DEBUG", "0") == "1":
            logger.info(f"[normalize_submission_key] input=int({submission_key}), returning kind='id', value=int")
        return ("id", submission_key)
    
    # str の場合
    if isinstance(submission_key, str):
        stripped = submission_key.strip()
        if not stripped:
            return (None, None)
        
        # 全て数字なら id として扱う（厳密に isdigit() のみ）
        if stripped.isdigit():
            normalized_int = int(stripped)
            if os.getenv("DEBUG", "0") == "1":
                logger.info(f"[normalize_submission_key] input=str('{stripped}'), isdigit=True, returning kind='id', value=int({normalized_int})")
            return ("id", normalized_int)
        
        # UUID形式かどうかを判定（UUID形式なら uuid、それ以外も uuid として扱う）
        try:
            # UUID形式として有効かチェック（形式チェックのみ、実際の存在確認はしない）
            uuid.UUID(stripped)
            if os.getenv("DEBUG", "0") == "1":
                logger.info(f"[normalize_submission_key] input=str('{stripped}'), valid UUID, returning kind='uuid', value=str")
            return ("uuid", stripped)
        except (ValueError, AttributeError):
            # UUID形式でない場合も uuid として扱う（検索時に失敗する可能性があるが、型エラーは防げる）
            if os.getenv("DEBUG", "0") == "1":
                logger.info(f"[normalize_submission_key] input=str('{stripped}'), not UUID format, returning kind='uuid', value=str")
            return ("uuid", stripped)
    
    # その他の型は str に変換して uuid として扱う
    if os.getenv("DEBUG", "0") == "1":
        logger.info(f"[normalize_submission_key] input=other({type(submission_key)}), converting to str, returning kind='uuid', value=str")
    return ("uuid", str(submission_key))


def load_payload_json(payload_json):
    """
    MaterialSubmission.payload_json を安全に dict に復元する。
    
    Args:
        payload_json: dict, str(JSON文字列), None, またはその他の型
    
    Returns:
        dict: 復元された辞書。復元できない場合は空の辞書 {} を返す。
    
    Note:
        - None → {}
        - dict → そのまま返す
        - str → json.loads を試す。成功して dict なら返す。失敗 or dict以外は {}
        - その他型 → {}
    """
    import json
    
    if payload_json is None:
        return {}
    
    if isinstance(payload_json, dict):
        return payload_json
    
    if isinstance(payload_json, str):
        try:
            parsed = json.loads(payload_json)
            if isinstance(parsed, dict):
                return parsed
            else:
                # JSON文字列だが dict でない場合（list など）
                return {}
        except (json.JSONDecodeError, TypeError, ValueError):
            # JSONパース失敗
            return {}
    
    # その他の型
    return {}
