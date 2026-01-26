"""
ルーティングモジュールのテスト
"""
import unittest
from unittest.mock import patch, MagicMock
import sys

class TestRouter(unittest.TestCase):
    """core.routerのテスト"""
    
    def test_get_routes_returns_dict(self):
        """get_routes()が辞書を返すことを確認"""
        from core.router import get_routes
        routes = get_routes()
        self.assertIsInstance(routes, dict)
    
    def test_get_routes_contains_registration_page(self):
        """get_routes()に材料登録ページが含まれることを確認"""
        from core.router import get_routes
        routes = get_routes()
        # ページ名が存在することを確認
        self.assertIn("材料登録", routes)
        # render関数がcallableであることを確認
        self.assertTrue(callable(routes.get("材料登録")))
    
    def test_get_routes_contains_approval_page(self):
        """get_routes()に承認待ち一覧ページが含まれることを確認"""
        from core.router import get_routes
        routes = get_routes()
        # ページ名が存在することを確認
        self.assertIn("承認待ち一覧", routes)
        # render関数がcallableであることを確認
        self.assertTrue(callable(routes.get("承認待ち一覧")))


if __name__ == '__main__':
    unittest.main()
