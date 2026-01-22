"""
Phase 1: ページルーティング
app.pyの巨大if/elif分岐を辞書マップに置き換える
"""
from typing import Callable, Optional


# ページ名からページ関数へのマッピング
# 初期状態では app.py 内の関数を参照する（後で pages/ に移動）
_PAGE_ROUTES: dict[str, Optional[Callable]] = {}


def register_page(page_name: str, page_func: Callable) -> None:
    """
    ページ名とページ関数を登録
    
    Args:
        page_name: ページ名（例: "ホーム", "材料一覧"）
        page_func: ページ関数（呼び出し可能オブジェクト）
    """
    _PAGE_ROUTES[page_name] = page_func


def route(page_name: str) -> Optional[Callable]:
    """
    ページ名からページ関数を取得
    
    Args:
        page_name: ページ名（例: "ホーム", "材料一覧"）
    
    Returns:
        ページ関数、見つからない場合はNone
    """
    return _PAGE_ROUTES.get(page_name)


def get_all_page_names() -> list[str]:
    """
    登録されているすべてのページ名を取得
    
    Returns:
        ページ名のリスト
    """
    return list(_PAGE_ROUTES.keys())
