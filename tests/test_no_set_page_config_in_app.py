"""
回帰防止テスト: app.py に st.set_page_config の直接呼び出しが含まれないことを検証
"""
import unittest
import os
from pathlib import Path


class TestNoSetPageConfigInApp(unittest.TestCase):
    """app.py に st.set_page_config の直接呼び出しが含まれないことを検証"""

    def test_app_py_does_not_contain_st_set_page_config(self):
        """app.py に st.set_page_config( という文字列が含まれないことを確認"""
        # プロジェクトルートを取得
        project_root = Path(__file__).parent.parent
        app_py_path = project_root / "app.py"
        
        # app.py が存在することを確認
        self.assertTrue(app_py_path.exists(), "app.py が見つかりません")
        
        # app.py の内容を読み込む
        with open(app_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # st.set_page_config( という文字列が含まれていないことを確認
        # コメント内の記述は除外するため、実際の呼び出しパターンをチェック
        # st.set_page_config( というパターンがコード内に存在しないことを確認
        lines = content.split("\n")
        for i, line in enumerate(lines, start=1):
            # コメント行はスキップ
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            
            # st.set_page_config( という呼び出しが含まれていないことを確認
            self.assertNotIn(
                "st.set_page_config(",
                line,
                f"app.py の {i} 行目に st.set_page_config( の直接呼び出しが検出されました。"
                "utils/ui_shell.setup_page_config() を使用してください。"
            )


if __name__ == "__main__":
    unittest.main()
