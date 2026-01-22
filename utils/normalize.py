"""
Unicode正規化とテキスト処理ユーティリティ
Phase 7: ZIP地雷対策と画像名照合の安定化
"""
import unicodedata
import re
from pathlib import Path
from typing import List, Optional


def normalize_text(s: Optional[str]) -> str:
    """
    テキストを正規化（NFKC、空白処理）
    
    Args:
        s: 正規化するテキスト（Noneの場合は空文字列を返す）
    
    Returns:
        正規化されたテキスト
    
    例:
        normalize_text("ポリエチレン") -> "ポリエチレン"  # 濁点合成
        normalize_text("ＡＢＣ") -> "ABC"  # 全角半角統一
        normalize_text("  test  ") -> "test"  # 空白除去
    """
    if s is None:
        return ""
    
    # strip
    s = s.strip()
    
    # Unicode正規化（NFKC: 互換文字を正規化、濁点合成など）
    s = unicodedata.normalize('NFKC', s)
    
    # 全角スペースを半角スペースに変換
    s = s.replace("　", " ")
    
    # 連続するスペースを1つに
    while "  " in s:
        s = s.replace("  ", " ")
    
    # 再度strip（正規化後の空白を除去）
    s = s.strip()
    
    return s


def normalize_filename(name: str) -> str:
    """
    ファイル名（拡張子付き）を正規化し、拡張子を除いたベース名を返す
    
    Args:
        name: ファイル名（例: "材料名.jpg", "材料名1.png"）
    
    Returns:
        拡張子を除いた正規化済みベース名（例: "材料名", "材料名1"）
    
    例:
        normalize_filename("ポリエチレン.jpg") -> "ポリエチレン"
        normalize_filename("材料名1.png") -> "材料名1"
    """
    if not name:
        return ""
    
    # パスからファイル名のみを取得
    from pathlib import Path
    basename = Path(name).stem  # 拡張子を除いたベース名
    
    # 正規化
    return normalize_text(basename)


def extract_number_suffix(basename: str) -> Optional[int]:
    """
    ベース名から末尾の連番（1または2）を抽出
    
    Args:
        basename: 正規化済みベース名（例: "材料名1", "材料名2"）
    
    Returns:
        末尾の連番（1または2）、見つからない場合はNone
    
    例:
        extract_number_suffix("材料名1") -> 1
        extract_number_suffix("材料名2") -> 2
        extract_number_suffix("材料名") -> None
    """
    if not basename:
        return None
    
    # 末尾が1桁の数字（1または2）かチェック
    match = re.match(r'^(.+?)([12])$', basename)
    if match:
        return int(match.group(2))
    
    return None


def generate_image_basename_candidates(material_name: str) -> List[str]:
    """
    材料名から画像ファイルのベース名候補を生成
    
    Args:
        material_name: 材料名（CSV側、未正規化）
    
    Returns:
        正規化済みベース名候補のリスト
        - 材料名（primary用）
        - 材料名 + "1"（space用）
        - 材料名 + "2"（product用）
    
    例:
        generate_image_basename_candidates("ポリエチレン")
        -> ["ポリエチレン", "ポリエチレン1", "ポリエチレン2"]
    """
    normalized = normalize_text(material_name)
    
    if not normalized:
        return []
    
    candidates = [
        normalized,           # primary: 材料名.jpg
        f"{normalized}1",    # space: 材料名1.jpg
        f"{normalized}2",    # product: 材料名2.jpg
    ]
    
    return candidates


def should_exclude_zip_entry(name: str, size: Optional[int] = None) -> bool:
    """
    ZIPエントリを除外すべきか判定（macOSメタファイルなど）
    
    Args:
        name: ZIPエントリ名（パス含む）
        size: ファイルサイズ（バイト、Noneの場合はサイズチェックをスキップ）
    
    Returns:
        Trueの場合は除外すべき
    
    除外条件:
        - パスに "__MACOSX" を含む
        - ファイル名が "._" で始まる
        - ".DS_Store"
        - size が明示的に0と指定された場合（size == 0）
    
    Note:
        size が None の場合はサイズチェックをスキップ（テスト用）
        実際の使用では extract_zip_images で zip_entry_info.file_size を渡す
    """
    if not name:
        return True
    
    # __MACOSX ディレクトリ
    if "__MACOSX" in name or "__MACOSX/" in name or "__MACOSX\\" in name:
        return True
    
    # macOSリソースフォーク（._で始まる、またはパス内に/._を含む）
    basename = Path(name).name
    if basename.startswith("._") or "/._" in name or "\\._" in name:
        return True
    
    # .DS_Store（ファイル名が.DS_Store、またはパス内に/.DS_Storeを含む）
    if basename == ".DS_Store" or "/.DS_Store" in name or "\\.DS_Store" in name:
        return True
    
    # 0バイト（sizeが明示的に0と指定された場合のみ）
    if size is not None and size == 0:
        return True
    
    return False


def is_image_extension(name: str) -> bool:
    """
    ファイル名が画像拡張子か判定
    
    Args:
        name: ファイル名
    
    Returns:
        Trueの場合は画像ファイル
    """
    if not name:
        return False
    
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    from pathlib import Path
    ext = Path(name).suffix.lower()
    return ext in allowed_extensions
