"""
回帰防止テスト: features/ 配下の .py ファイルに app モジュールの import が含まれないことを検証
"""
import unittest
import os
from pathlib import Path


class TestNoImportAppFromFeatures(unittest.TestCase):
    """features/ 配下の .py ファイルに app モジュールの import が含まれないことを検証"""

    def test_features_py_files_do_not_import_app(self):
        """features/ 配下のすべての .py ファイルに import app または from app import が含まれないことを確認"""
        # プロジェクトルートを取得
        project_root = Path(__file__).parent.parent
        features_dir = project_root / "features"
        
        # features/ ディレクトリが存在することを確認
        self.assertTrue(features_dir.exists(), "features/ ディレクトリが見つかりません")
        self.assertTrue(features_dir.is_dir(), "features/ はディレクトリではありません")
        
        # features/ 配下のすべての .py ファイルを取得
        py_files = list(features_dir.glob("*.py"))
        self.assertGreater(len(py_files), 0, "features/ 配下に .py ファイルが見つかりません")
        
        # 禁止パターン
        forbidden_patterns = [
            "import app",
            "from app import",
        ]
        
        # 各ファイルをチェック
        for py_file in py_files:
            with self.subTest(file=py_file.name):
                # ファイルの内容を読み込む
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 各行をチェック（コメント内も含めて厳しくチェック）
                lines = content.split("\n")
                for i, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    
                    # import app のチェック（行の先頭または空白の後に "import app" が来る）
                    # 例: "import app" または "    import app" または "# import app"
                    if "import app" in line:
                        # "import app" の前が空白または行の先頭であることを確認
                        import_app_index = line.find("import app")
                        if import_app_index >= 0:
                            before_import = line[:import_app_index].strip()
                            # 前が空（行の先頭）または空白のみ、またはコメント記号のみの場合
                            if not before_import or before_import == "#" or before_import.startswith("#"):
                                self.fail(
                                    f"{py_file.name} の {i} 行目に 'import app' が検出されました。\n"
                                    f"行の内容: {line}\n"
                                    f"features/ 配下のファイルから app モジュールを import することは禁止されています。"
                                )
                    
                    # from app import のチェック（行の先頭または空白の後に "from app import" が来る）
                    # 例: "from app import" または "    from app import" または "# from app import"
                    if "from app import" in line:
                        # "from app import" の前が空白または行の先頭であることを確認
                        from_app_index = line.find("from app import")
                        if from_app_index >= 0:
                            before_from = line[:from_app_index].strip()
                            # 前が空（行の先頭）または空白のみ、またはコメント記号のみの場合
                            if not before_from or before_from == "#" or before_from.startswith("#"):
                                self.fail(
                                    f"{py_file.name} の {i} 行目に 'from app import' が検出されました。\n"
                                    f"行の内容: {line}\n"
                                    f"features/ 配下のファイルから app モジュールを import することは禁止されています。"
                                )


if __name__ == "__main__":
    unittest.main()
