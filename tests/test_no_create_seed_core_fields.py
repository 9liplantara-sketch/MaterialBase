"""
回帰防止テスト: createモードでCORE_FIELDSがsession_stateにseedされないことを確認

createモードでは、主要6項目（CORE_FIELDS）をsession_stateにseedしない設計になっている。
ユーザーが触った時だけtouchedが立つ設計を維持するため、誤ってseed処理が追加されないことを検証する。
"""
import unittest
import os
import re


class TestNoCreateSeedCoreFields(unittest.TestCase):
    """createモードでCORE_FIELDSがsession_stateにseedされないことを確認"""
    
    # CORE_FIELDSの定義（material_form_detailed.pyと一致）
    CORE_FIELDS = [
        'name_official',
        'category_main',
        'origin_type',
        'transparency',
        'visibility',
        'is_published',
    ]
    
    def setUp(self):
        """テストファイルのパスを設定"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.material_form_detailed_py_path = os.path.join(project_root, "material_form_detailed.py")
    
    def _is_in_string_or_comment(self, line: str, pos: int) -> bool:
        """
        指定位置が文字列リテラルまたはコメント内かどうかを判定
        
        Args:
            line: 行の内容
            pos: チェックする位置
        
        Returns:
            bool: 文字列リテラルまたはコメント内ならTrue
        """
        # コメントの位置を取得
        comment_pos = line.find('#')
        if comment_pos != -1 and pos > comment_pos:
            return True
        
        # 文字列リテラル内かどうかを簡易チェック（シングルクォートとダブルクォート）
        before = line[:pos]
        # シングルクォートのペアを数える（エスケープは考慮しない簡易版）
        single_quotes = before.count("'") - before.count("\\'")
        double_quotes = before.count('"') - before.count('\\"')
        
        # 奇数個なら文字列リテラル内
        return (single_quotes % 2 == 1) or (double_quotes % 2 == 1)
    
    def _check_dangerous_pattern(self, lines: list, line_idx: int, context_lines: int = 10) -> bool:
        """
        指定行が危険なパターンかどうかをチェック
        
        Args:
            lines: 全行のリスト
            line_idx: チェックする行のインデックス
            context_lines: 前後何行をコンテキストとして見るか
        
        Returns:
            bool: 危険なパターンならTrue
        """
        line = lines[line_idx]
        
        # st.session_state[...] = のパターンを検出
        session_state_pattern = r'st\.session_state\[.*?\]\s*='
        if not re.search(session_state_pattern, line):
            return False
        
        # CORE_FIELDSのいずれかが含まれているかチェック
        has_core_field = any(field in line for field in self.CORE_FIELDS)
        if not has_core_field:
            return False
        
        # 文字列リテラルやコメント内の場合は除外
        match = re.search(session_state_pattern, line)
        if match and self._is_in_string_or_comment(line, match.start()):
            return False
        
        # 前後context_lines行をチェックして、scope == "create" があるか確認
        start_idx = max(0, line_idx - context_lines)
        end_idx = min(len(lines), line_idx + context_lines + 1)
        context = '\n'.join(lines[start_idx:end_idx])
        
        # scope == "create" または scope == 'create' のパターンを検出
        create_scope_patterns = [
            r'scope\s*==\s*["\']create["\']',
            r'scope\s*=\s*["\']create["\']',  # 代入もチェック
            r'if\s+scope\s*==\s*["\']create["\']',  # if文
            r'elif\s+scope\s*==\s*["\']create["\']',  # elif文
        ]
        
        has_create_scope = any(re.search(pattern, context) for pattern in create_scope_patterns)
        
        # createモードのコンテキストがある場合、かつCORE_FIELDSへの代入がある場合は危険
        if has_create_scope:
            # ただし、明示的に「createモードでは設定しない」というコメントがある場合は除外
            if 'createモードでは' in context and ('設定しない' in context or 'seed禁止' in context):
                return False
            
            # ただし、if existing_material: のブロック内で、createモードのチェックがない場合は除外
            # （editモードの処理として正しい）
            if 'if existing_material:' in context and not any(
                'create' in line.lower() and ('if' in line or 'elif' in line)
                for line in lines[start_idx:line_idx]
            ):
                return False
            
            return True
        
        return False
    
    def test_no_create_seed_core_fields(self):
        """material_form_detailed.py で createモードでCORE_FIELDSがseedされないことを確認"""
        if not os.path.exists(self.material_form_detailed_py_path):
            self.skipTest("material_form_detailed.py not found")
        
        with open(self.material_form_detailed_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split("\n")
        
        # 危険なパターンを検出
        dangerous_lines = []
        for i, line in enumerate(lines):
            if self._check_dangerous_pattern(lines, i):
                dangerous_lines.append((i + 1, line.strip()))
        
        if dangerous_lines:
            error_msg = "material_form_detailed.py で createモードでCORE_FIELDSがsession_stateにseedされている可能性があります:\n\n"
            for line_num, line_content in dangerous_lines:
                error_msg += f"  Line {line_num}: {line_content}\n"
            error_msg += "\ncreateモードでは、CORE_FIELDSをsession_stateにseedしないでください。\n"
            error_msg += "ユーザーが触った時だけtouchedが立つ設計を維持してください。\n"
            error_msg += "editモードでのseedは問題ありませんが、createモードのコンテキスト内では禁止です。"
            self.fail(error_msg)
    
    def test_seed_widget_function_has_create_check(self):
        """seed_widget関数内でcreateモードのチェックがあることを確認"""
        if not os.path.exists(self.material_form_detailed_py_path):
            self.skipTest("material_form_detailed.py not found")
        
        with open(self.material_form_detailed_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # seed_widget関数の定義を探す
        if 'def seed_widget' not in content:
            self.skipTest("seed_widget function not found")
        
        # seed_widget関数内でcreateモードのチェックがあるか確認
        # パターン: scope == "create" と CORE_FIELDS のチェック
        seed_widget_pattern = r'def seed_widget.*?(?=\n    def|\nclass|\Z)'
        match = re.search(seed_widget_pattern, content, re.DOTALL)
        
        if match:
            seed_widget_body = match.group(0)
            # createモードのチェックがあるか確認
            has_create_check = (
                'scope == "create"' in seed_widget_body or
                "scope == 'create'" in seed_widget_body or
                'scope == "create"' in seed_widget_body.replace(' ', '')
            )
            
            # CORE_FIELDSのチェックがあるか確認
            has_core_fields_check = any(field in seed_widget_body for field in self.CORE_FIELDS)
            
            if has_create_check and has_core_fields_check:
                # チェックがある場合はOK
                return
            
            # チェックがない場合は警告（ただし、実装によっては別の方法で保護されている可能性がある）
            # このテストは警告のみで、失敗にはしない
            if not has_create_check:
                self.fail(
                    "seed_widget関数内でcreateモードのチェックが見つかりません。\n"
                    "createモードでCORE_FIELDSがseedされないように保護されているか確認してください。"
                )


if __name__ == "__main__":
    unittest.main()
