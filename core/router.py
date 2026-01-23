"""
ルーティングモジュール
pages配下のrender関数を遅延importして辞書で返す
"""
from typing import Dict, Callable, Optional
import importlib
import logging

logger = logging.getLogger(__name__)

# ページ名とモジュールパスのマッピング
PAGE_ROUTES: Dict[str, str] = {
    "材料登録": "pages.registration_page",
    "承認待ち一覧": "pages.approval_page",
    # 他のページは必要に応じて追加
}

# キャッシュ: 一度importしたモジュールを保持
_imported_modules: Dict[str, Optional[object]] = {}


def get_routes() -> Dict[str, Callable]:
    """
    pages配下のrender関数を遅延importして辞書で返す
    
    Returns:
        ページ名をキー、render関数を値とする辞書
    """
    routes = {}
    
    for page_name, module_path in PAGE_ROUTES.items():
        try:
            # キャッシュをチェック
            if module_path in _imported_modules:
                module = _imported_modules[module_path]
                if module is None:
                    continue
            else:
                # 遅延import
                module = importlib.import_module(module_path)
                _imported_modules[module_path] = module
            
            # render関数を取得
            if hasattr(module, "render"):
                routes[page_name] = module.render
            else:
                logger.warning(f"Module {module_path} does not have 'render' function")
                _imported_modules[module_path] = None
        except ImportError as e:
            logger.error(f"Failed to import {module_path}: {e}")
            _imported_modules[module_path] = None
        except Exception as e:
            logger.error(f"Error loading route {page_name} from {module_path}: {e}")
            _imported_modules[module_path] = None
    
    return routes
