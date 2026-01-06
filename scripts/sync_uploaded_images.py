"""
uploads/ と uploads/uses/ にある画像を static/images/materials/ に同期するスクリプト

命名規則（これが正）:
- uploads/{材料名}.{任意拡張子}           → primary（材料のメイン画像）
- uploads/uses/{材料名}1.{任意拡張子}     → space（生活/空間の使用例）
- uploads/uses/{材料名}2.{任意拡張子}     → product（プロダクトの使用例）

拡張子は jpg/jpeg/png/webp を許容。優先順位: jpg > jpeg > png > webp

出力先:
- static/images/materials/{safe_slug}/primary.{ext}
- static/images/materials/{safe_slug}/uses/space.{ext}
- static/images/materials/{safe_slug}/uses/product.{ext}
"""
import os
import re
import hashlib
from pathlib import Path
from PIL import Image
from typing import Optional, Dict, Tuple, List
import sys
from datetime import datetime

# プロジェクトルートを取得
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.paths import resolve_path, ensure_dir


def safe_slug(name: str) -> str:
    """
    素材名をパス安全なスラッグに変換
    
    Args:
        name: 素材名（例: "栗材", "ポリプロピレン"）
    
    Returns:
        パス安全なスラッグ（例: "栗材", "ポリプロピレン"）
    """
    # 前後空白除去
    slug = name.strip()
    # 禁止文字を "_" へ置換
    forbidden_chars = r'[/\\:*?"<>|]'
    slug = re.sub(forbidden_chars, '_', slug)
    return slug


def normalize_material_name(name: str) -> str:
    """
    材料名を正規化（DB突合用）
    
    Args:
        name: 材料名
    
    Returns:
        正規化された材料名（空白除去、全角/半角統一など）
    """
    # 前後空白除去
    normalized = name.strip()
    # 全角スペースを半角に
    normalized = normalized.replace('　', ' ')
    # 連続スペースを1つに
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def get_file_hash(file_path: Path) -> str:
    """
    ファイルのハッシュ値を取得（べき等性チェック用）
    
    Args:
        file_path: ファイルパス
    
    Returns:
        SHA256ハッシュ値（16進数文字列）
    """
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


def files_are_identical(source_path: Path, dest_path: Path) -> bool:
    """
    2つのファイルが同一かチェック（ハッシュ比較）
    
    Args:
        source_path: ソースファイルパス
        dest_path: 出力先ファイルパス
    
    Returns:
        同一の場合True
    """
    if not dest_path.exists():
        return False
    
    try:
        source_hash = get_file_hash(source_path)
        dest_hash = get_file_hash(dest_path)
        return source_hash == dest_hash
    except Exception:
        return False


def copy_image_preserving_ext(source_path: Path, dest_path: Path) -> bool:
    """
    画像を拡張子を保持してコピー（透過対策で白背景合成）
    
    Args:
        source_path: 元画像のパス
        dest_path: 保存先のパス（拡張子を含む）
    
    Returns:
        成功した場合True
    """
    try:
        # 画像を開く
        img = Image.open(source_path)
        
        # RGBモードに変換（透過対策で白背景合成）
        if img.mode in ('RGBA', 'LA', 'P'):
            # 透過画像の場合は白背景に合成
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                rgb_img.paste(img, mask=img.split()[3])
            elif img.mode == 'LA':
                rgb_img.paste(img.convert('RGB'), mask=img.split()[1])
            else:
                # Pモード（パレット）の場合
                if 'transparency' in img.info:
                    rgb_img.paste(img.convert('RGBA'), mask=img.convert('RGBA').split()[3])
                else:
                    rgb_img = img.convert('RGB')
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 拡張子を保持して保存
        ensure_dir(dest_path.parent)
        ext = dest_path.suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            img.save(dest_path, 'JPEG', quality=95)
        elif ext == '.png':
            img.save(dest_path, 'PNG', optimize=True)
        elif ext == '.webp':
            img.save(dest_path, 'WEBP', quality=95)
        else:
            # 不明な拡張子はPNGにフォールバック
            img.save(dest_path.with_suffix('.png'), 'PNG', optimize=True)
        return True
    except Exception as e:
        print(f"  ❌ エラー: {source_path} -> {dest_path}: {e}")
        return False


def find_material_files(
    uploads_dir: Path,
    db_materials: Optional[Dict[str, int]] = None
) -> Dict[str, Dict[str, List[Tuple[Path, str]]]]:
    """
    uploads/ ディレクトリを走査して素材名ごとにファイルを収集
    
    Args:
        uploads_dir: uploads/ ディレクトリのパス
        db_materials: DBの材料名マッピング {正規化名: material_id}
    
    Returns:
        {材料名: {'primary': [(Path, ext), ...], 'space': [...], 'product': [...]}}
        拡張子優先順位: jpg > jpeg > png > webp
    """
    materials: Dict[str, Dict[str, List[Tuple[Path, str]]]] = {}
    
    # 拡張子優先順位
    ext_priority = {'.jpg': 0, '.jpeg': 1, '.png': 2, '.webp': 3}
    allowed_exts = set(ext_priority.keys())
    
    # uploads/ 直下のメイン画像を収集
    if uploads_dir.exists():
        for file_path in uploads_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                ext = file_path.suffix.lower()
                if ext in allowed_exts:
                    # 拡張子を除いたファイル名を素材名として使用
                    material_name = file_path.stem
                    
                    # DB突合（完全一致 or 正規化一致）
                    matched_name = None
                    if db_materials:
                        normalized = normalize_material_name(material_name)
                        # 完全一致を優先
                        if material_name in db_materials:
                            matched_name = material_name
                        elif normalized in db_materials:
                            matched_name = normalized
                        else:
                            # 部分一致も試す（大文字小文字無視）
                            for db_name in db_materials.keys():
                                if normalize_material_name(db_name).lower() == normalized.lower():
                                    matched_name = db_name
                                    break
                    else:
                        matched_name = material_name
                    
                    if matched_name:
                        if matched_name not in materials:
                            materials[matched_name] = {'primary': [], 'space': [], 'product': []}
                        materials[matched_name]['primary'].append((file_path, ext))
    
    # uploads/uses/ の使用例画像を収集
    uses_dir = uploads_dir / 'uses'
    if uses_dir.exists():
        for file_path in uses_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                ext = file_path.suffix.lower()
                if ext in allowed_exts:
                    # {素材名}1.* または {素材名}2.* のパターンを抽出
                    match = re.match(r'^(.+?)([12])\..+$', file_path.name)
                    if match:
                        material_name = match.group(1)
                        use_number = match.group(2)
                        
                        # DB突合
                        matched_name = None
                        if db_materials:
                            normalized = normalize_material_name(material_name)
                            if material_name in db_materials:
                                matched_name = material_name
                            elif normalized in db_materials:
                                matched_name = normalized
                            else:
                                for db_name in db_materials.keys():
                                    if normalize_material_name(db_name).lower() == normalized.lower():
                                        matched_name = db_name
                                        break
                        else:
                            matched_name = material_name
                        
                        if matched_name:
                            if matched_name not in materials:
                                materials[matched_name] = {'primary': [], 'space': [], 'product': []}
                            if use_number == '1':
                                materials[matched_name]['space'].append((file_path, ext))
                            elif use_number == '2':
                                materials[matched_name]['product'].append((file_path, ext))
    
    # 各材料ごとに、優先順位の高い拡張子を選択（最新の1枚を採用）
    for material_name in materials:
        for image_type in ['primary', 'space', 'product']:
            files = materials[material_name][image_type]
            if files:
                # 拡張子優先順位でソート（優先順位が同じ場合はmtimeでソート、新しい順）
                files.sort(key=lambda x: (ext_priority.get(x[1], 999), -x[0].stat().st_mtime))
                # 最新の1枚を採用
                materials[material_name][image_type] = [files[0]]
            else:
                materials[material_name][image_type] = []
    
    return materials


def sync_images(
    uploads_dir: Path,
    materials_dir: Path,
    db_materials: Optional[Dict[str, int]] = None,
    dry_run: bool = False
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, List[str]]]:
    """
    画像を同期
    
    Args:
        uploads_dir: uploads/ ディレクトリのパス
        materials_dir: static/images/materials/ ディレクトリのパス
        db_materials: DBの材料名マッピング {正規化名: material_id}
        dry_run: ドライランモード（実際にはコピーしない）
    
    Returns:
        (同期結果 {材料名: {type: 出力先パス}}, 不足一覧 {材料名: [不足タイプ]})
    """
    materials = find_material_files(uploads_dir, db_materials)
    
    synced_results: Dict[str, Dict[str, str]] = {}
    missing_summary: Dict[str, List[str]] = {}
    
    print(f"\n📦 {len(materials)} 件の素材を発見しました\n")
    print("=" * 80)
    
    for material_name, files in sorted(materials.items()):
        slug = safe_slug(material_name)
        material_base_dir = materials_dir / slug
        
        print(f"\n📁 {material_name} (slug: {slug})")
        print("-" * 80)
        
        synced_results[material_name] = {}
        missing = []
        
        # メイン画像（primary）
        if files['primary']:
            source_path, ext = files['primary'][0]
            dest_path = material_base_dir / f'primary{ext}'
            
            # べき等性チェック
            if files_are_identical(source_path, dest_path):
                print(f"  ⏭️  primary: {source_path.name} -> {dest_path.name} (同一ファイル、スキップ)")
                synced_results[material_name]['primary'] = str(dest_path.relative_to(project_root))
            else:
                if dry_run:
                    print(f"  🔍 ドライラン: {source_path.name} -> {dest_path.name}")
                    synced_results[material_name]['primary'] = str(dest_path.relative_to(project_root))
                else:
                    if copy_image_preserving_ext(source_path, dest_path):
                        print(f"  ✅ primary: {source_path.name} -> {dest_path.name} (拡張子: {ext})")
                        synced_results[material_name]['primary'] = str(dest_path.relative_to(project_root))
                    else:
                        print(f"  ❌ primary: コピー失敗")
        else:
            print(f"  ⏭️  primary: ファイルなし")
            missing.append('primary')
        
        # 使用例1（space）
        uses_dir = material_base_dir / 'uses'
        if files['space']:
            source_path, ext = files['space'][0]
            dest_path = uses_dir / f'space{ext}'
            
            # べき等性チェック
            if files_are_identical(source_path, dest_path):
                print(f"  ⏭️  space: {source_path.name} -> {dest_path.name} (同一ファイル、スキップ)")
                synced_results[material_name]['space'] = str(dest_path.relative_to(project_root))
            else:
                if dry_run:
                    print(f"  🔍 ドライラン: {source_path.name} -> {dest_path.name}")
                    synced_results[material_name]['space'] = str(dest_path.relative_to(project_root))
                else:
                    if copy_image_preserving_ext(source_path, dest_path):
                        print(f"  ✅ space: {source_path.name} -> {dest_path.name} (拡張子: {ext})")
                        synced_results[material_name]['space'] = str(dest_path.relative_to(project_root))
                    else:
                        print(f"  ❌ space: コピー失敗")
        else:
            print(f"  ⏭️  space: ファイルなし")
            missing.append('space')
        
        # 使用例2（product）
        if files['product']:
            source_path, ext = files['product'][0]
            dest_path = uses_dir / f'product{ext}'
            
            # べき等性チェック
            if files_are_identical(source_path, dest_path):
                print(f"  ⏭️  product: {source_path.name} -> {dest_path.name} (同一ファイル、スキップ)")
                synced_results[material_name]['product'] = str(dest_path.relative_to(project_root))
            else:
                if dry_run:
                    print(f"  🔍 ドライラン: {source_path.name} -> {dest_path.name}")
                    synced_results[material_name]['product'] = str(dest_path.relative_to(project_root))
                else:
                    if copy_image_preserving_ext(source_path, dest_path):
                        print(f"  ✅ product: {source_path.name} -> {dest_path.name} (拡張子: {ext})")
                        synced_results[material_name]['product'] = str(dest_path.relative_to(project_root))
                    else:
                        print(f"  ❌ product: コピー失敗")
        else:
            print(f"  ⏭️  product: ファイルなし")
            missing.append('product')
        
        if missing:
            missing_summary[material_name] = missing
    
    return synced_results, missing_summary


def load_db_materials() -> Dict[str, int]:
    """
    DBから材料名マッピングを取得
    
    Returns:
        {正規化名: material_id}
    """
    try:
        from database import SessionLocal, Material
        db = SessionLocal()
        try:
            materials = db.query(Material).all()
            result = {}
            for m in materials:
                # name_official を優先、なければ name
                name = m.name_official or m.name
                if name:
                    normalized = normalize_material_name(name)
                    result[normalized] = m.id
                    # 元の名前も追加（完全一致用）
                    if name != normalized:
                        result[name] = m.id
            return result
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  DB接続エラー（続行）: {e}")
        return {}


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='uploads/ の画像を static/images/materials/ に同期')
    parser.add_argument('--dry-run', action='store_true', help='ドライランモード（実際にはコピーしない）')
    parser.add_argument('--no-db', action='store_true', help='DB突合をスキップ')
    args = parser.parse_args()
    
    uploads_dir = resolve_path('uploads')
    materials_dir = resolve_path('static/images/materials')
    
    print("=" * 80)
    print("画像同期スクリプト")
    print("=" * 80)
    print(f"📂 ソース: {uploads_dir}")
    print(f"📂 保存先: {materials_dir}")
    if args.dry_run:
        print("🔍 ドライランモード")
    print()
    
    # DBから材料名を取得
    db_materials = None if args.no_db else load_db_materials()
    if db_materials:
        print(f"📊 DB材料数: {len(db_materials)} 件")
        print()
    
    # 画像同期
    synced_results, missing_summary = sync_images(
        uploads_dir, materials_dir, db_materials, dry_run=args.dry_run
    )
    
    # サマリー表示
    print("\n" + "=" * 80)
    print("📊 同期結果サマリー")
    print("=" * 80)
    
    total_primary = sum(1 for r in synced_results.values() if 'primary' in r)
    total_space = sum(1 for r in synced_results.values() if 'space' in r)
    total_product = sum(1 for r in synced_results.values() if 'product' in r)
    
    print(f"✅ primary: {total_primary} 件")
    print(f"✅ space: {total_space} 件")
    print(f"✅ product: {total_product} 件")
    print()
    
    # 不足一覧
    if missing_summary:
        print("=" * 80)
        print("⚠️  不足している画像")
        print("=" * 80)
        for material_name, missing_types in sorted(missing_summary.items()):
            print(f"📁 {material_name}: {', '.join(missing_types)}")
    else:
        print("✅ すべての材料に必要な画像が揃っています")
    
    print("\n" + "=" * 80)
    print("✨ 完了")
    print("=" * 80)


if __name__ == '__main__':
    main()
