"""
DBヘルスチェックサービス層
DB接続のping（SELECT 1）を提供
"""
import logging
from utils.db import get_session, DBUnavailableError
from sqlalchemy import text

logger = logging.getLogger(__name__)


def ping_db() -> bool:
    """
    DB接続をping（SELECT 1を1回だけ実行）
    
    Returns:
        True: 接続成功
        False: 接続失敗（通常は例外が投げられる）
    
    Raises:
        DBUnavailableError: DB接続エラー時
    
    Note:
        - サービス層はUIを知らない（streamlit import禁止）
        - 失敗したらDBUnavailableErrorを投げる（UIは知らない）
    """
    try:
        with get_session() as db:
            # SELECT 1を1回だけ実行
            result = db.execute(text("SELECT 1"))
            result.scalar()  # 結果を取得（1が返る）
            return True
    except Exception as e:
        # 接続エラーをDBUnavailableErrorにラップ
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'connect', 'network', 'timeout', 'refused', 'closed']):
            raise DBUnavailableError(f"データベース接続エラー: {e}") from e
        raise
