"""
画像状態デバッグスクリプト（Python 3.8+互換）

uploads/ と static/images/materials/ の画像状態を確認する
"""
import sys
import os
import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import argparse

# Pythonバージョン表示
print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
print(f"Python executable: {sys.executable}")
print()

# プロジェクトルートを取得
project_root = Path(__file__).parent.parent


def safe_slug(name: str) -> str:
    """素材名をパス安全なスラッグに変換"""
    slug = name.strip()
    forbidden_chars = r'[/\\:*?"<>|]'
    slug = re.sub(forbidden_chars, '_', slug)
    return slug


def get_file_md5(file_path: Path) -> Optional[str]:
    """ファイルのMD5ハッシュを取得"""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        return None


def format_mtime(mtime: float) -> str:
    """mtimeをYYYY-MM-DD HH:MM:SS形式に変換"""
    try:
        dt = datetime.fromtimestamp(mtime)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return "N/A"


def format_size(size: int) -> str:
    """ファイルサイズを人間可読形式に変換"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def find_image_files(
    base_dir: Path,
    slug: str,
    image_type: str,
    ext_priority: List[str]
) -> Tuple[Optional[Path], str]:
    """
    画像ファイルを探索（新仕様優先、旧仕様フォールバック）
    
    Args:
        base_dir: ベースディレクトリ（static/images/materials または uploads）
        slug: 材料スラッグ
        image_type: 'primary', 'space', 'product'
        ext_priority: 拡張子優先順位リスト
    
    Returns:
        (見つかったファイルのPath, 'new' or 'old' or 'none')
    """
    material_dir = base_dir / slug
    
    if image_type == 'primary':
        # 新仕様: {base_dir}/{slug}/primary.{ext}
        for ext in ext_priority:
            path = material_dir / f'primary{ext}'
            if path.exists():
                return path, 'new'
        
        # 旧仕様フォールバック: {base_dir}/{slug}/primary/primary.{ext}
        primary_dir = material_dir / 'primary'
        if primary_dir.exists():
            for ext in ext_priority:
                path = primary_dir / f'primary{ext}'
                if path.exists():
                    return path, 'old'
    
    elif image_type in ['space', 'product']:
        # 新仕様: {base_dir}/{slug}/uses/{image_type}.{ext}
        uses_dir = material_dir / 'uses'
        if uses_dir.exists():
            for ext in ext_priority:
                path = uses_dir / f'{image_type}{ext}'
                if path.exists():
                    return path, 'new'
    
    return None, 'none'


def find_upload_files(
    uploads_dir: Path,
    material_name: str,
    image_type: str
) -> Optional[Path]:
    """
    uploads/ から画像ファイルを探索
    
    Args:
        uploads_dir: uploads/ ディレクトリ
        material_name: 材料名（ファイル名に使用）
        image_type: 'primary', 'space', 'product'
    
    Returns:
        見つかったファイルのPath、なければNone
    """
    ext_priority = ['.jpg', '.jpeg', '.png', '.webp']
    
    if image_type == 'primary':
        # uploads/{material_name}.{ext}
        for ext in ext_priority:
            path = uploads_dir / f'{material_name}{ext}'
            if path.exists():
                return path
    
    elif image_type == 'space':
        # uploads/uses/{material_name}1.{ext}
        uses_dir = uploads_dir / 'uses'
        if uses_dir.exists():
            for ext in ext_priority:
                path = uses_dir / f'{material_name}1{ext}'
                if path.exists():
                    return path
    
    elif image_type == 'product':
        # uploads/uses/{material_name}2.{ext}
        uses_dir = uploads_dir / 'uses'
        if uses_dir.exists():
            for ext in ext_priority:
                path = uses_dir / f'{material_name}2{ext}'
                if path.exists():
                    return path
    
    return None


def print_file_info(
    label: str,
    file_path: Optional[Path],
    project_root: Path,
    show_absolute: bool = False
):
    """ファイル情報を表示"""
    print(f"  {label}:")
    if file_path and file_path.exists():
        try:
            stat = file_path.stat()
            rel_path = file_path.relative_to(project_root)
            abs_path = file_path.resolve()
            
            print(f"    パス: {abs_path if show_absolute else rel_path}")
            print(f"    存在: ✅")
            print(f"    サイズ: {format_size(stat.st_size)}")
            print(f"    mtime: {format_mtime(stat.st_mtime)}")
            
            md5 = get_file_md5(file_path)
            if md5:
                print(f"    md5: {md5}")
            else:
                print(f"    md5: ❌ 取得失敗")
        except Exception as e:
            print(f"    ❌ エラー: {e}")
    else:
        print(f"    存在: ❌ ファイルなし")


def compare_files(
    upload_path: Optional[Path],
    static_path: Optional[Path]
) -> str:
    """2つのファイルを比較してSAME/DIFFを返す"""
    if not upload_path or not upload_path.exists():
        return "UPLOAD_MISSING"
    if not static_path or not static_path.exists():
        return "STATIC_MISSING"
    
    upload_md5 = get_file_md5(upload_path)
    static_md5 = get_file_md5(static_path)
    
    if upload_md5 and static_md5:
        if upload_md5 == static_md5:
            return "SAME"
        else:
            return "DIFF"
    else:
        return "COMPARE_ERROR"


def list_directory(dir_path: Path, project_root: Path):
    """ディレクトリの内容を一覧表示"""
    print(f"\n📂 ディレクトリ一覧: {dir_path.relative_to(project_root)}")
    print("=" * 80)
    
    if not dir_path.exists():
        print("❌ ディレクトリが存在しません")
        return
    
    if not dir_path.is_dir():
        print("❌ ディレクトリではありません")
        return
    
    files = []
    dirs = []
    
    try:
        for item in sorted(dir_path.iterdir()):
            if item.is_file():
                try:
                    stat = item.stat()
                    files.append((item, stat))
                except Exception:
                    files.append((item, None))
            elif item.is_dir():
                dirs.append(item)
    except Exception as e:
        print(f"❌ ディレクトリ読み込みエラー: {e}")
        return
    
    if dirs:
        print("\n📁 サブディレクトリ:")
        for d in dirs:
            print(f"  {d.name}/")
    
    if files:
        print("\n📄 ファイル:")
        for file_path, stat in files:
            rel_path = file_path.relative_to(project_root)
            if stat:
                print(f"  {rel_path}")
                print(f"    サイズ: {format_size(stat.st_size)}")
                print(f"    mtime: {format_mtime(stat.st_mtime)}")
            else:
                print(f"  {rel_path} (stat取得失敗)")
    else:
        print("\n📄 ファイル: なし")
    
    if not dirs and not files:
        print("\n📄 空のディレクトリ")


def main():
    parser = argparse.ArgumentParser(
        description='画像状態をデバッグ（Python 3.8+互換）'
    )
    parser.add_argument(
        '--material',
        type=str,
        help='材料名（uploads側のファイル名に使用、例: "アルミニウム"）'
    )
    parser.add_argument(
        '--slug',
        type=str,
        help='スラッグ（static側のディレクトリ名、省略時はmaterialを使用）'
    )
    parser.add_argument(
        '--base',
        type=str,
        default='static/images/materials',
        help='static側のベースディレクトリ（デフォルト: static/images/materials）'
    )
    parser.add_argument(
        '--uploads',
        type=str,
        default='uploads',
        help='uploads側のディレクトリ（デフォルト: uploads）'
    )
    parser.add_argument(
        '--compare-uploads',
        action='store_true',
        help='uploads側とstatic側を比較'
    )
    parser.add_argument(
        '--list-dir',
        type=str,
        help='指定ディレクトリの内容を一覧表示'
    )
    parser.add_argument(
        '--absolute',
        action='store_true',
        help='絶対パスで表示'
    )
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    base_dir = project_root / args.base
    uploads_dir = project_root / args.uploads
    ext_priority = ['.jpg', '.jpeg', '.png', '.webp']
    
    # ディレクトリ一覧表示モード
    if args.list_dir:
        list_dir_path = project_root / args.list_dir
        list_directory(list_dir_path, project_root)
        return
    
    # 材料名が指定されていない場合はエラー
    if not args.material:
        parser.error("--material は必須です（例: --material 'アルミニウム'）")
    
    material_name = args.material
    slug = args.slug if args.slug else safe_slug(material_name)
    
    print("=" * 80)
    print("画像状態デバッグ")
    print("=" * 80)
    print(f"材料名: {material_name}")
    print(f"スラッグ: {slug}")
    print(f"ベースディレクトリ: {base_dir.relative_to(project_root)}")
    print(f"uploadsディレクトリ: {uploads_dir.relative_to(project_root)}")
    print()
    
    # static側の画像を探索
    print("=" * 80)
    print("📦 static側の画像")
    print("=" * 80)
    
    static_images = {}
    for image_type in ['primary', 'space', 'product']:
        file_path, spec_type = find_image_files(base_dir, slug, image_type, ext_priority)
        static_images[image_type] = file_path
        
        label = f"{image_type.upper()}"
        if spec_type == 'old':
            label += " (旧仕様)"
        elif spec_type == 'new':
            label += " (新仕様)"
        
        print_file_info(label, file_path, project_root, args.absolute)
        print()
    
    # uploads側との比較
    if args.compare_uploads:
        print("=" * 80)
        print("📤 uploads側の画像")
        print("=" * 80)
        
        upload_images = {}
        for image_type in ['primary', 'space', 'product']:
            file_path = find_upload_files(uploads_dir, material_name, image_type)
            upload_images[image_type] = file_path
            print_file_info(f"{image_type.upper()}", file_path, project_root, args.absolute)
            print()
        
        print("=" * 80)
        print("🔍 比較結果")
        print("=" * 80)
        
        for image_type in ['primary', 'space', 'product']:
            upload_path = upload_images.get(image_type)
            static_path = static_images.get(image_type)
            
            result = compare_files(upload_path, static_path)
            
            print(f"  {image_type.upper()}: {result}")
            if result == "SAME":
                print(f"    ✅ uploads側とstatic側が同一（同期済み）")
            elif result == "DIFF":
                print(f"    ⚠️  uploads側とstatic側が異なる（同期が必要）")
                if upload_path and static_path:
                    upload_md5 = get_file_md5(upload_path)
                    static_md5 = get_file_md5(static_path)
                    print(f"      uploads md5: {upload_md5}")
                    print(f"      static md5:  {static_md5}")
            elif result == "UPLOAD_MISSING":
                print(f"    ⚠️  uploads側にファイルなし")
            elif result == "STATIC_MISSING":
                print(f"    ⚠️  static側にファイルなし（同期が必要）")
            elif result == "COMPARE_ERROR":
                print(f"    ❌ 比較エラー")
            print()
    
    # サマリー
    print("=" * 80)
    print("📊 サマリー")
    print("=" * 80)
    
    existing = [t for t, p in static_images.items() if p and p.exists()]
    missing = [t for t, p in static_images.items() if not p or not p.exists()]
    
    print(f"✅ 存在: {', '.join(existing) if existing else 'なし'}")
    print(f"❌ 欠損: {', '.join(missing) if missing else 'なし'}")
    print()
    
    if args.compare_uploads:
        print("💡 ヒント:")
        print("  - SAME: 同期済み（問題なし）")
        print("  - DIFF: 同期が必要（scripts/sync_uploaded_images.py を実行）")
        print("  - STATIC_MISSING: 同期が必要")
        print()


if __name__ == '__main__':
    main()
