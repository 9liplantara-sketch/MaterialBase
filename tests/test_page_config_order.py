"""
app.py の先頭部分で setup_page_config() が適切な位置に配置されていることを検証
"""
import unittest
from pathlib import Path


class TestPageConfigOrder(unittest.TestCase):
    """app.py の先頭部分で setup_page_config() の配置順序を検証"""

    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        self.project_root = Path(__file__).parent.parent
        self.app_py_path = self.project_root / "app.py"
        self.assertTrue(
            self.app_py_path.exists(),
            "app.py が見つかりません"
        )

    def _read_app_py_lines(self, max_lines=80):
        """app.py の先頭N行を読み込む"""
        with open(self.app_py_path, "r", encoding="utf-8") as f:
            return [line.rstrip() for line in f.readlines()[:max_lines]]

    def _read_app_py_content(self):
        """app.py の全内容を読み込む"""
        with open(self.app_py_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_setup_page_config_is_placed_early_after_streamlit_import(self):
        """
        app.py の先頭80行で、setup_page_config() が適切な位置に配置されていることを確認
        """
        lines = self._read_app_py_lines(80)

        # import streamlit as st の行番号を探す（1-indexed）
        streamlit_import_line = None
        for i, line in enumerate(lines, start=1):
            if line.strip() == "import streamlit as st":
                streamlit_import_line = i
                break

        # import streamlit as st が存在することを確認
        self.assertIsNotNone(
            streamlit_import_line,
            "app.py の先頭80行に 'import streamlit as st' が見つかりません"
        )

        # setup_page_config の import と呼び出しの行番号を探す
        setup_import_line = None
        setup_call_line = None

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if "from utils.ui_shell import setup_page_config" in stripped:
                setup_import_line = i
            if stripped == "setup_page_config()":
                setup_call_line = i

        # from utils.ui_shell import setup_page_config が存在することを確認
        self.assertIsNotNone(
            setup_import_line,
            "app.py の先頭80行に 'from utils.ui_shell import setup_page_config' "
            "が見つかりません"
        )

        # setup_page_config() が存在することを確認
        self.assertIsNotNone(
            setup_call_line,
            "app.py の先頭80行に 'setup_page_config()' が見つかりません"
        )

        # from utils.ui_shell import setup_page_config が
        # import streamlit as st の後にあることを確認
        self.assertGreater(
            setup_import_line,
            streamlit_import_line,
            f"'from utils.ui_shell import setup_page_config' (行{setup_import_line}) "
            f"は 'import streamlit as st' (行{streamlit_import_line}) "
            f"の後に配置される必要があります。"
        )

        # import streamlit as st の後の1〜15行以内に
        # setup_page_config の import があることを確認
        max_allowed_line = streamlit_import_line + 15
        self.assertLessEqual(
            setup_import_line,
            max_allowed_line,
            f"'from utils.ui_shell import setup_page_config' は "
            f"'import streamlit as st' (行{streamlit_import_line}) の15行以内に "
            f"配置される必要があります。現在は行{setup_import_line}にあります。"
        )

        # setup_page_config() の呼び出しが import の後にあることを確認
        self.assertGreater(
            setup_call_line,
            setup_import_line,
            f"'setup_page_config()' (行{setup_call_line}) は "
            f"'from utils.ui_shell import setup_page_config' "
            f"(行{setup_import_line}) の後に配置される必要があります。"
        )

        # import streamlit as st の後の1〜15行以内に
        # setup_page_config() の呼び出しがあることを確認
        self.assertLessEqual(
            setup_call_line,
            max_allowed_line,
            f"'setup_page_config()' は 'import streamlit as st' "
            f"(行{streamlit_import_line}) の15行以内に配置される必要があります。"
            f"現在は行{setup_call_line}にあります。"
        )

    def test_setup_page_config_exists_in_first_80_lines(self):
        """
        A. app.py の先頭80行以内に setup_page_config() 呼び出しが存在する
        """
        lines = self._read_app_py_lines(80)

        # setup_page_config() の呼び出しを探す
        found = False
        for line in lines:
            if line.strip() == "setup_page_config()":
                found = True
                break

        self.assertTrue(
            found,
            "app.py の先頭80行以内に 'setup_page_config()' が見つかりません"
        )

    def test_setup_page_config_after_streamlit_import(self):
        """
        B. app.py の import streamlit as st より後に setup_page_config() がある
        """
        lines = self._read_app_py_lines(80)

        # import streamlit as st の行番号を探す
        streamlit_import_line = None
        for i, line in enumerate(lines, start=1):
            if line.strip() == "import streamlit as st":
                streamlit_import_line = i
                break

        self.assertIsNotNone(
            streamlit_import_line,
            "app.py の先頭80行に 'import streamlit as st' が見つかりません"
        )

        # setup_page_config() の行番号を探す
        setup_call_line = None
        for i, line in enumerate(lines, start=1):
            if line.strip() == "setup_page_config()":
                setup_call_line = i
                break

        self.assertIsNotNone(
            setup_call_line,
            "app.py の先頭80行に 'setup_page_config()' が見つかりません"
        )

        # setup_page_config() が import streamlit as st の後にあることを確認
        self.assertGreater(
            setup_call_line,
            streamlit_import_line,
            f"'setup_page_config()' (行{setup_call_line}) は "
            f"'import streamlit as st' (行{streamlit_import_line}) "
            f"の後に配置される必要があります。"
        )

    def test_no_top_level_st_calls_before_setup_page_config(self):
        """
        C. setup_page_config() より前にトップレベルで st. 呼び出しが存在しない
        例: st.secrets は「関数定義内ならOK」「トップレベル実行ならNG」
        """
        lines = self._read_app_py_lines(80)

        # setup_page_config() の行番号を探す
        setup_call_line = None
        for i, line in enumerate(lines, start=1):
            if line.strip() == "setup_page_config()":
                setup_call_line = i
                break

        self.assertIsNotNone(
            setup_call_line,
            "app.py の先頭80行に 'setup_page_config()' が見つかりません"
        )

        # setup_page_config() より前の行で、トップレベルの st. 呼び出しを探す
        # トップレベル = インデントが0（行頭から始まる）
        # ただし、setup_page_config() 自体は許可する
        # コメントや文字列リテラル内は簡易的に除外（行の先頭が # や " や ' で始まる場合はスキップ）
        for i, line in enumerate(lines[:setup_call_line], start=1):
            stripped = line.strip()

            # 空行、コメント、文字列リテラルはスキップ
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith('"') or stripped.startswith("'"):
                continue

            # トップレベルかどうか（行頭からのインデントが0）
            if not line.startswith((" ", "\t")):
                # トップレベルの行で st. を含む場合
                if "st." in stripped:
                    # setup_page_config() の呼び出しは許可
                    if "setup_page_config()" in stripped:
                        continue
                    # import 文は許可
                    if stripped.startswith("import ") or stripped.startswith("from "):
                        continue
                    # それ以外の st. 呼び出しはNG
                    self.fail(
                        f"行{i}にトップレベルの st. 呼び出しが見つかりました: "
                        f"{stripped}\n"
                        f"setup_page_config() (行{setup_call_line}) より前に "
                        f"トップレベルで st. を呼び出すことはできません。"
                    )

    def test_no_direct_st_set_page_config_in_app(self):
        """
        D. app.py に "st.set_page_config(" という文字列が含まれない
        """
        content = self._read_app_py_content()

        # st.set_page_config( が含まれていないことを確認
        self.assertNotIn(
            "st.set_page_config(",
            content,
            "app.py に 'st.set_page_config(' が含まれています。"
            "setup_page_config() 関数を使用してください。"
        )


if __name__ == "__main__":
    unittest.main()
