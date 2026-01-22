"""
Phase 7: Unicode正規化とZIP地雷対策のテスト
"""
import unittest
from utils.normalize import (
    normalize_text,
    normalize_filename,
    extract_number_suffix,
    generate_image_basename_candidates,
    should_exclude_zip_entry,
    is_image_extension,
)


class TestNormalize(unittest.TestCase):
    """normalize_text のテスト"""
    
    def test_normalize_text_none(self):
        """Noneは空文字列を返す"""
        self.assertEqual(normalize_text(None), "")
    
    def test_normalize_text_strip(self):
        """前後の空白を除去"""
        self.assertEqual(normalize_text("  test  "), "test")
    
    def test_normalize_text_nfkc_fullwidth(self):
        """NFKCで全角半角が統一される"""
        self.assertEqual(normalize_text("ＡＢＣ"), "ABC")
        self.assertEqual(normalize_text("１２３"), "123")
    
    def test_normalize_text_nfkc_voiced_mark(self):
        """NFKCで濁点合成（ポ → ポ）"""
        # ポ（ホ + ゚）はNFKCでポに正規化される
        self.assertEqual(normalize_text("ポリエチレン"), "ポリエチレン")
        # 既に合成されているポもそのまま
        self.assertEqual(normalize_text("ポリエチレン"), "ポリエチレン")
    
    def test_normalize_text_space_normalization(self):
        """全角スペースを半角に、連続スペースを1つに"""
        self.assertEqual(normalize_text("材料　名"), "材料 名")
        self.assertEqual(normalize_text("材料  名"), "材料 名")
        self.assertEqual(normalize_text("材料　　名"), "材料 名")
    
    def test_normalize_filename(self):
        """ファイル名から拡張子を除いて正規化"""
        self.assertEqual(normalize_filename("ポリエチレン.jpg"), "ポリエチレン")
        self.assertEqual(normalize_filename("材料名1.png"), "材料名1")
        self.assertEqual(normalize_filename("材料名2.webp"), "材料名2")
        self.assertEqual(normalize_filename("  test  .jpg"), "test")
    
    def test_extract_number_suffix(self):
        """末尾の連番（1または2）を抽出"""
        self.assertEqual(extract_number_suffix("材料名1"), 1)
        self.assertEqual(extract_number_suffix("材料名2"), 2)
        self.assertIsNone(extract_number_suffix("材料名"))
        self.assertIsNone(extract_number_suffix("材料名3"))
        self.assertIsNone(extract_number_suffix(""))
    
    def test_generate_image_basename_candidates(self):
        """画像ファイルのベース名候補を生成"""
        candidates = generate_image_basename_candidates("ポリエチレン")
        self.assertEqual(candidates, ["ポリエチレン", "ポリエチレン1", "ポリエチレン2"])
        
        candidates = generate_image_basename_candidates(" 材料名 ")
        self.assertEqual(candidates, ["材料名", "材料名1", "材料名2"])
    
    def test_should_exclude_zip_entry_macosx(self):
        """__MACOSX を含むパスを除外"""
        self.assertTrue(should_exclude_zip_entry("__MACOSX/file.jpg"))
        self.assertTrue(should_exclude_zip_entry("folder/__MACOSX/file.jpg"))
        self.assertTrue(should_exclude_zip_entry("folder/__MACOSX/"))
        self.assertFalse(should_exclude_zip_entry("file.jpg"))
    
    def test_should_exclude_zip_entry_resource_fork(self):
        """._ で始まるファイルを除外"""
        self.assertTrue(should_exclude_zip_entry("._file.jpg"))
        self.assertTrue(should_exclude_zip_entry("folder/._file.jpg"))
        self.assertFalse(should_exclude_zip_entry("file.jpg"))
    
    def test_should_exclude_zip_entry_ds_store(self):
        """.DS_Store を除外"""
        self.assertTrue(should_exclude_zip_entry(".DS_Store"))
        self.assertTrue(should_exclude_zip_entry("folder/.DS_Store"))
        self.assertFalse(should_exclude_zip_entry("file.jpg"))
    
    def test_should_exclude_zip_entry_zero_bytes(self):
        """0バイトファイルを除外"""
        self.assertTrue(should_exclude_zip_entry("file.jpg", size=0))
        self.assertFalse(should_exclude_zip_entry("file.jpg", size=100))
    
    def test_is_image_extension(self):
        """画像拡張子を判定"""
        self.assertTrue(is_image_extension("file.jpg"))
        self.assertTrue(is_image_extension("file.JPG"))
        self.assertTrue(is_image_extension("file.jpeg"))
        self.assertTrue(is_image_extension("file.png"))
        self.assertTrue(is_image_extension("file.webp"))
        self.assertFalse(is_image_extension("file.txt"))
        self.assertFalse(is_image_extension("file.pdf"))
        self.assertFalse(is_image_extension(""))


if __name__ == '__main__':
    unittest.main()
