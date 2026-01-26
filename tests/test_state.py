"""
セッション状態管理モジュールのテスト
"""
import unittest
from unittest.mock import MagicMock, patch
import sys

class TestState(unittest.TestCase):
    """core.stateのテスト"""
    
    def test_page_constants_exist(self):
        """ページ名定数が存在することを確認"""
        from core.state import (
            PAGE_HOME, PAGE_MATERIALS_LIST, PAGE_REGISTRATION,
            PAGE_DASHBOARD, PAGE_SEARCH, PAGE_MATERIAL_CARDS,
            PAGE_PERIODIC_TABLE, PAGE_SUBMISSION_STATUS,
            PAGE_APPROVAL_QUEUE, PAGE_BULK_IMPORT
        )
        self.assertEqual(PAGE_HOME, "ホーム")
        self.assertEqual(PAGE_MATERIALS_LIST, "材料一覧")
        self.assertEqual(PAGE_REGISTRATION, "材料登録")
        self.assertEqual(PAGE_APPROVAL_QUEUE, "承認待ち一覧")
    
    def test_key_constants_exist(self):
        """session_stateキー定数が存在することを確認"""
        from core.state import (
            KEY_PAGE, KEY_EDIT_MATERIAL_ID,
            KEY_INCLUDE_UNPUBLISHED, KEY_INCLUDE_DELETED
        )
        self.assertEqual(KEY_PAGE, "page")
        self.assertEqual(KEY_EDIT_MATERIAL_ID, "edit_material_id")
    
    @patch('streamlit.session_state', {})
    def test_ensure_state_defaults_initializes_keys(self):
        """ensure_state_defaults()がキーを初期化することを確認"""
        # モックのsession_stateを作成
        mock_session_state = {}
        
        with patch('streamlit.session_state', mock_session_state):
            from core.state import ensure_state_defaults, KEY_PAGE, DEFAULT_PAGE
            ensure_state_defaults()
            # pageキーが設定されていることを確認
            self.assertIn(KEY_PAGE, mock_session_state)
            self.assertEqual(mock_session_state[KEY_PAGE], DEFAULT_PAGE)


if __name__ == '__main__':
    unittest.main()
