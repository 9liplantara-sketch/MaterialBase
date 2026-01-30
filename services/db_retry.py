"""
DB接続リトライ機能（軽量、最大2回）
Neon起床ループを防ぐため、無限リトライは禁止
"""
import time
import logging
from typing import TypeVar, Callable, Optional
from utils.db import DBUnavailableError

logger = logging.getLogger(__name__)

T = TypeVar('T')


def db_retry(
    func: Callable[[], T],
    max_retries: int = 2,
    retry_delay: float = 2.0,
    operation_name: str = "DB操作"
) -> T:
    """
    DB操作を最大2回までリトライ（軽量）
    
    Args:
        func: 実行するDB操作関数
        max_retries: 最大リトライ回数（デフォルト2回）
        retry_delay: リトライ間隔（秒、デフォルト2秒）
        operation_name: 操作名（ログ用）
    
    Returns:
        funcの戻り値
    
    Raises:
        DBUnavailableError: 最大リトライ回数に達した場合
    """
    last_error = None
    
    for attempt in range(max_retries + 1):  # 初回 + リトライ回数
        try:
            return func()
        except DBUnavailableError as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"[DB_RETRY] {operation_name} 失敗 (試行 {attempt + 1}/{max_retries + 1}), {retry_delay}秒後に再試行...")
                time.sleep(retry_delay)
            else:
                logger.error(f"[DB_RETRY] {operation_name} 最大リトライ回数に達しました ({max_retries + 1}回)")
                raise
    
    # ここには到達しないはずだが、念のため
    if last_error:
        raise last_error
    raise RuntimeError(f"{operation_name} が予期せず失敗しました")
