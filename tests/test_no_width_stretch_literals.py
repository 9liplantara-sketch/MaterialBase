"""
回帰防止テスト: width='stretch' や width="stretch" が app.py と material_form_detailed.py に含まれないことを確認

Streamlit Cloudで width='stretch' は非推奨でエラーになるため、
すべて正しいAPI（use_container_width=True など）に置換済みであることを検証する。
"""
import unittest
import os


class TestNoWidthStretchLiterals(unittest.TestCase):
    """width='stretch' や width="stretch" が含まれないことを確認"""
    
    def setUp(self):
        """テストファイルのパスを設定"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.app_py_path = os.path.join(project_root, "app.py")
        self.material_form_detailed_py_path = os.path.join(project_root, "material_form_detailed.py")
    
    def test_app_py_does_not_contain_width_stretch_single_quote(self):
        """app.py に width='stretch' が含まれないことを確認"""
        with open(self.app_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if "width='stretch'" in line:
                self.fail(
                    f"app.py line {i} contains width='stretch':\n"
                    f"{line.strip()}\n"
                    f"Please use the correct Streamlit API (e.g., use_container_width=True) instead."
                )
    
    def test_app_py_does_not_contain_width_stretch_double_quote(self):
        """app.py に width=\"stretch\" が含まれないことを確認"""
        with open(self.app_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if 'width="stretch"' in line:
                self.fail(
                    f"app.py line {i} contains width=\"stretch\":\n"
                    f"{line.strip()}\n"
                    f"Please use the correct Streamlit API (e.g., use_container_width=True) instead."
                )
    
    def test_material_form_detailed_py_does_not_contain_width_stretch_single_quote(self):
        """material_form_detailed.py に width='stretch' が含まれないことを確認"""
        if not os.path.exists(self.material_form_detailed_py_path):
            self.skipTest("material_form_detailed.py not found")
        
        with open(self.material_form_detailed_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if "width='stretch'" in line:
                self.fail(
                    f"material_form_detailed.py line {i} contains width='stretch':\n"
                    f"{line.strip()}\n"
                    f"Please use the correct Streamlit API (e.g., use_container_width=True) instead."
                )
    
    def test_material_form_detailed_py_does_not_contain_width_stretch_double_quote(self):
        """material_form_detailed.py に width=\"stretch\" が含まれないことを確認"""
        if not os.path.exists(self.material_form_detailed_py_path):
            self.skipTest("material_form_detailed.py not found")
        
        with open(self.material_form_detailed_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if 'width="stretch"' in line:
                self.fail(
                    f"material_form_detailed.py line {i} contains width=\"stretch\":\n"
                    f"{line.strip()}\n"
                    f"Please use the correct Streamlit API (e.g., use_container_width=True) instead."
                )


if __name__ == "__main__":
    unittest.main()
