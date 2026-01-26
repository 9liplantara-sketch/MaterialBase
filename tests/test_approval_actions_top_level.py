"""
回帰防止テスト: features/approval_actions.py に4つの関数がトップレベル関数として存在することを確認

正規表現ではなくASTを使用して、関数がトップレベル（カラム0）で定義されていることを検証する。
これにより、インデントエラーや正規表現の誤検出を防ぐ。
"""
import unittest
import os
import ast


class TestApprovalActionsTopLevel(unittest.TestCase):
    """approval_actions.py に4つの関数がトップレベル関数として存在することを確認"""
    
    REQUIRED_FUNCTIONS = [
        "approve_submission",
        "reject_submission",
        "reopen_submission",
        "calculate_submission_diff",
    ]
    
    def setUp(self):
        """テストファイルのパスを設定"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.approval_actions_py_path = os.path.join(project_root, "features", "approval_actions.py")
    
    def test_approval_actions_functions_exist_at_top_level(self):
        """approval_actions.py に4つの関数がトップレベル関数として存在することを確認"""
        if not os.path.exists(self.approval_actions_py_path):
            self.fail(f"features/approval_actions.py not found at {self.approval_actions_py_path}")
        
        with open(self.approval_actions_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        try:
            tree = ast.parse(content, filename=self.approval_actions_py_path)
        except SyntaxError as e:
            self.fail(f"Failed to parse features/approval_actions.py: {e}")
        
        # トップレベル関数を収集（col_offset == 0 の関数定義）
        top_level_functions = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 関数定義の行番号とカラムオフセットを取得
                lineno = node.lineno
                col_offset = node.col_offset
                
                # トップレベル関数（col_offset == 0）のみを記録
                if col_offset == 0:
                    top_level_functions[node.name] = {
                        "lineno": lineno,
                        "col_offset": col_offset,
                    }
        
        # 必要な関数がすべて存在するか確認
        missing_functions = []
        for func_name in self.REQUIRED_FUNCTIONS:
            if func_name not in top_level_functions:
                missing_functions.append(func_name)
        
        if missing_functions:
            self.fail(
                f"Missing top-level functions in features/approval_actions.py: {missing_functions}\n"
                f"Found top-level functions: {list(top_level_functions.keys())}"
            )
        
        # 各関数がトップレベルであることを確認（念のため）
        for func_name in self.REQUIRED_FUNCTIONS:
            func_info = top_level_functions[func_name]
            self.assertEqual(
                func_info["col_offset"],
                0,
                f"Function {func_name} is not at top level (col_offset={func_info['col_offset']}, line={func_info['lineno']})"
            )


if __name__ == "__main__":
    unittest.main()
