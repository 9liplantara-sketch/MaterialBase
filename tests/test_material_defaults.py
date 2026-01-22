"""
材料（Material）のNOT NULL列に対するデフォルト値補完のテスト

Phase 4: NOT NULL補完を単一の仕様に集約
"""
import unittest
from utils.material_defaults import (
    apply_material_defaults,
    REQUIRED_FIELDS,
    DEFAULT_VALUES,
    get_csv_required_fields
)


class TestMaterialDefaults(unittest.TestCase):
    """材料デフォルト値補完のテストクラス"""

    def test_apply_material_defaults_fills_missing_fields(self):
        """必須キーが欠けていても apply_material_defaults が埋める"""
        data = {
            'name_official': 'テスト材料',
            'category_main': 'プラスチック',
            # 他の必須フィールドは欠けている
        }
        
        result = apply_material_defaults(data)
        
        # 必須フィールドが補完されている
        self.assertEqual(result['origin_type'], '不明')
        self.assertEqual(result['origin_detail'], '不明')
        self.assertEqual(result['transparency'], '不明')
        self.assertEqual(result['hardness_qualitative'], '不明')
        self.assertEqual(result['weight_qualitative'], '不明')
        self.assertEqual(result['water_resistance'], '不明')
        self.assertEqual(result['weather_resistance'], '不明')
        self.assertEqual(result['procurement_status'], '不明')
        self.assertEqual(result['cost_level'], '不明')
        self.assertEqual(result['equipment_level'], '家庭/工房レベル')
        self.assertEqual(result['prototyping_difficulty'], '中')
        self.assertEqual(result['visibility'], '非公開（管理者のみ）')
        self.assertEqual(result['is_published'], 0)
        self.assertEqual(result['is_deleted'], 0)
        
        # 元のデータは変更されていない
        self.assertEqual(data['name_official'], 'テスト材料')
        self.assertNotIn('origin_type', data)

    def test_apply_material_defaults_preserves_existing_values(self):
        """既存の値は上書きしない"""
        data = {
            'name_official': 'テスト材料',
            'category_main': 'プラスチック',
            'transparency': '透明',
            'origin_type': '石油由来',
        }
        
        result = apply_material_defaults(data)
        
        # 既存の値は保持される
        self.assertEqual(result['transparency'], '透明')
        self.assertEqual(result['origin_type'], '石油由来')
        
        # 欠けているフィールドは補完される
        self.assertEqual(result['origin_detail'], '不明')
        self.assertEqual(result['hardness_qualitative'], '不明')

    def test_apply_material_defaults_normalizes_strings(self):
        """空文字や空白が正規化される"""
        data = {
            'name_official': '  テスト材料  ',
            'category_main': 'プラスチック',
            'transparency': '  透明  ',
            'origin_type': '',  # 空文字
            'origin_detail': '   ',  # 空白のみ
        }
        
        result = apply_material_defaults(data)
        
        # 文字列がstripされる
        self.assertEqual(result['name_official'], 'テスト材料')
        self.assertEqual(result['transparency'], '透明')
        
        # 空文字や空白のみの文字列は補完される
        self.assertEqual(result['origin_type'], '不明')
        self.assertEqual(result['origin_detail'], '不明')

    def test_apply_material_defaults_sets_is_published_from_visibility(self):
        """is_publishedはvisibilityから決定される"""
        # 公開の場合
        data1 = {
            'name_official': 'テスト材料',
            'category_main': 'プラスチック',
            'visibility': '公開',
        }
        result1 = apply_material_defaults(data1)
        self.assertEqual(result1['is_published'], 1)
        
        # 非公開の場合
        data2 = {
            'name_official': 'テスト材料',
            'category_main': 'プラスチック',
            'visibility': '非公開（管理者のみ）',
        }
        result2 = apply_material_defaults(data2)
        self.assertEqual(result2['is_published'], 0)
        
        # デフォルト（visibilityが無い場合）
        data3 = {
            'name_official': 'テスト材料',
            'category_main': 'プラスチック',
        }
        result3 = apply_material_defaults(data3)
        self.assertEqual(result3['is_published'], 0)  # 安全側に倒す

    def test_required_fields_has_all_not_null_columns(self):
        """REQUIRED_FIELDSにすべてのNOT NULL列が含まれている"""
        # database.pyから抽出したNOT NULL列（heat_resistance_rangeはnullable=Trueなので除外）
        expected_not_null_fields = {
            'name_official',
            'category_main',
            'origin_type',
            'origin_detail',
            'transparency',
            'hardness_qualitative',
            'weight_qualitative',
            'water_resistance',
            'weather_resistance',
            'equipment_level',
            'prototyping_difficulty',
            'procurement_status',
            'cost_level',
            'visibility',
            'is_published',
            'is_deleted',
        }
        
        self.assertEqual(REQUIRED_FIELDS, expected_not_null_fields)

    def test_default_values_has_all_required_fields(self):
        """DEFAULT_VALUESにすべての補完対象フィールドが含まれている"""
        # name_official と category_main は補完しない（バリデーションで弾く）
        skip_fields = {'name_official', 'category_main'}
        
        missing_fields = []
        for field in REQUIRED_FIELDS:
            if field not in skip_fields:
                if field not in DEFAULT_VALUES:
                    missing_fields.append(field)
        
        self.assertEqual(len(missing_fields), 0, 
            f"REQUIRED_FIELDSに以下のフィールドがあるが、DEFAULT_VALUESにデフォルト値が定義されていません: {missing_fields}")

    def test_get_csv_required_fields(self):
        """CSV必須項目の一覧を返す"""
        csv_required = get_csv_required_fields()
        
        # CSVで必須とすべき項目（補完しない項目）
        self.assertIn('name_official', csv_required)
        self.assertIn('category_main', csv_required)
        
        # CSV必須はDB必須のサブセット
        self.assertTrue(csv_required.issubset(REQUIRED_FIELDS))


if __name__ == '__main__':
    unittest.main()
