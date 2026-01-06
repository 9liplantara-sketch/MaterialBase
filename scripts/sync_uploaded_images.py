"""
uploads/ と uploads/uses/ にある画像を static/images/materials/ に同期するスクリプト

命名規則:
- uploads/{素材名}.*            -> static/images/materials/{safe_slug}/primary/primary.png
- uploads/uses/{素材名}1.*      -> static/images/materials/{safe_slug}/uses/space.png
- uploads/uses/{素材名}2.*      -> static/images/materials/{safe_slug}/uses/product.png

画像はPNGに正規化（透過対策で白背景合成）
"""
import os
import re
from pathlib import Path
from PIL import Image
from typing import Optional, Dict, Tuple
import sys

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
    # スラッシュ、バックスラッシュ、コロン、アスタリスク、疑問符、引用符、不等号、パイプ
    forbidden_chars = r'[/\\:*?"<>|]'
    slug = re.sub(forbidden_chars, '_', slug)
    return slug


def normalize_to_png(source_path: Path, dest_path: Path) -> bool:
    """
    画像をPNGに正規化して保存（透過対策で白背景合成）
    
    Args:
        source_path: 元画像のパス
        dest_path: 保存先のPNGパス
    
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
        
        # PNGとして保存
        ensure_dir(dest_path.parent)
        img.save(dest_path, 'PNG', optimize=True)
        return True
    except Exception as e:
        print(f"  ❌ エラー: {source_path} -> {dest_path}: {e}")
        return False


def find_material_files(uploads_dir: Path) -> Dict[str, Dict[str, Optional[Path]]]:
    """
    uploads/ ディレクトリを走査して素材名ごとにファイルを収集
    
    Args:
        uploads_dir: uploads/ ディレクトリのパス
    
    Returns:
        {素材名: {'primary': Path or None, 'use1': Path or None, 'use2': Path or None}}
    """
    materials: Dict[str, Dict[str, Optional[Path]]] = {}
    
    # uploads/ 直下のメイン画像を収集
    if uploads_dir.exists():
        for file_path in uploads_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                # 拡張子を除いたファイル名を素材名として使用
                material_name = file_path.stem
                if material_name not in materials:
                    materials[material_name] = {'primary': None, 'use1': None, 'use2': None}
                materials[material_name]['primary'] = file_path
    
    # uploads/uses/ の使用例画像を収集
    uses_dir = uploads_dir / 'uses'
    if uses_dir.exists():
        for file_path in uses_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                # {素材名}1.* または {素材名}2.* のパターンを抽出
                match = re.match(r'^(.+?)([12])\..+$', file_path.name)
                if match:
                    material_name = match.group(1)
                    use_number = match.group(2)
                    if material_name not in materials:
                        materials[material_name] = {'primary': None, 'use1': None, 'use2': None}
                    if use_number == '1':
                        materials[material_name]['use1'] = file_path
                    elif use_number == '2':
                        materials[material_name]['use2'] = file_path
    
    return materials


def sync_images(
    uploads_dir: Path,
    materials_dir: Path,
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """
    画像を同期
    
    Args:
        uploads_dir: uploads/ ディレクトリのパス
        materials_dir: static/images/materials/ ディレクトリのパス
        dry_run: ドライランモード（実際にはコピーしない）
    
    Returns:
        (同期したファイル数, スキップしたファイル数, エラー数)
    """
    materials = find_material_files(uploads_dir)
    
    synced_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"\n📦 {len(materials)} 件の素材を発見しました\n")
    
    for material_name, files in sorted(materials.items()):
        slug = safe_slug(material_name)
        material_base_dir = materials_dir / slug
        
        print(f"📁 {material_name} (slug: {slug})")
        
        # メイン画像（primary）
        if files['primary']:
            dest_path = material_base_dir / 'primary' / 'primary.png'
            if dry_run:
                print(f"  🔍 ドライラン: {files['primary']} -> {dest_path}")
                synced_count += 1
            else:
                if normalize_to_png(files['primary'], dest_path):
                    print(f"  ✅ primary: {files['primary'].name} -> primary.png")
                    synced_count += 1
                else:
                    error_count += 1
        else:
            print(f"  ⏭️  primary: ファイルなし")
            skipped_count += 1
        
        # 使用例1（space）
        if files['use1']:
            dest_path = material_base_dir / 'uses' / 'space.png'
            if dry_run:
                print(f"  🔍 ドライラン: {files['use1']} -> {dest_path}")
                synced_count += 1
            else:
                if normalize_to_png(files['use1'], dest_path):
                    print(f"  ✅ space: {files['use1'].name} -> space.png")
                    synced_count += 1
                else:
                    error_count += 1
        else:
            print(f"  ⏭️  space: ファイルなし")
            skipped_count += 1
        
        # 使用例2（product）
        if files['use2']:
            dest_path = material_base_dir / 'uses' / 'product.png'
            if dry_run:
                print(f"  🔍 ドライラン: {files['use2']} -> {dest_path}")
                synced_count += 1
            else:
                if normalize_to_png(files['use2'], dest_path):
                    print(f"  ✅ product: {files['use2'].name} -> product.png")
                    synced_count += 1
                else:
                    error_count += 1
        else:
            print(f"  ⏭️  product: ファイルなし")
            skipped_count += 1
        
        print()
    
    return synced_count, skipped_count, error_count


def sync_use_examples_to_db(
    materials_dir: Path,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    使用例画像をDBに登録（オプション機能）
    
    Args:
        materials_dir: static/images/materials/ ディレクトリのパス
        dry_run: ドライランモード
    
    Returns:
        (登録した件数, スキップした件数)
    """
    try:
        from database import SessionLocal, Material, UseExample
    except ImportError:
        print("⚠️  DB登録機能はスキップされました（databaseモジュールが見つかりません）")
        return 0, 0
    
    db = SessionLocal()
    registered_count = 0
    skipped_count = 0
    
    try:
        # materials/ ディレクトリを走査
        for material_dir in materials_dir.iterdir():
            if not material_dir.is_dir():
                continue
            
            # 素材名を取得（ディレクトリ名から）
            material_name = material_dir.name
            
            # DBから材料を検索
            material = db.query(Material).filter(
                (Material.name_official == material_name) |
                (Material.name == material_name)
            ).first()
            
            if not material:
                continue
            
            uses_dir = material_dir / 'uses'
            if not uses_dir.exists():
                continue
            
            # space.png がある場合
            space_path = uses_dir / 'space.png'
            if space_path.exists():
                # 既存のUseExampleをチェック（idempotent）
                existing = db.query(UseExample).filter(
                    UseExample.material_id == material.id,
                    UseExample.example_name == "空間の使用例"
                ).first()
                
                if not existing:
                    if not dry_run:
                        use_example = UseExample(
                            material_id=material.id,
                            example_name="空間の使用例",
                            domain="空間",
                            description="空間での使用例",
                            image_path=str(space_path.relative_to(project_root))
                        )
                        db.add(use_example)
                        db.commit()
                        registered_count += 1
                        print(f"  ✅ DB登録: {material_name} - 空間の使用例")
                    else:
                        print(f"  🔍 ドライラン: {material_name} - 空間の使用例を登録")
                        registered_count += 1
                else:
                    skipped_count += 1
            
            # product.png がある場合
            product_path = uses_dir / 'product.png'
            if product_path.exists():
                # 既存のUseExampleをチェック（idempotent）
                existing = db.query(UseExample).filter(
                    UseExample.material_id == material.id,
                    UseExample.example_name == "プロダクトの使用例"
                ).first()
                
                if not existing:
                    if not dry_run:
                        use_example = UseExample(
                            material_id=material.id,
                            example_name="プロダクトの使用例",
                            domain="プロダクト",
                            description="プロダクトでの使用例",
                            image_path=str(product_path.relative_to(project_root))
                        )
                        db.add(use_example)
                        db.commit()
                        registered_count += 1
                        print(f"  ✅ DB登録: {material_name} - プロダクトの使用例")
                    else:
                        print(f"  🔍 ドライラン: {material_name} - プロダクトの使用例を登録")
                        registered_count += 1
                else:
                    skipped_count += 1
    
    finally:
        db.close()
    
    return registered_count, skipped_count


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='uploads/ の画像を static/images/materials/ に同期')
    parser.add_argument('--dry-run', action='store_true', help='ドライランモード（実際にはコピーしない）')
    parser.add_argument('--no-db', action='store_true', help='DB登録をスキップ')
    args = parser.parse_args()
    
    uploads_dir = resolve_path('uploads')
    materials_dir = resolve_path('static/images/materials')
    
    print("=" * 60)
    print("画像同期スクリプト")
    print("=" * 60)
    print(f"📂 ソース: {uploads_dir}")
    print(f"📂 保存先: {materials_dir}")
    if args.dry_run:
        print("🔍 ドライランモード")
    print()
    
    # 画像同期
    synced, skipped, errors = sync_images(uploads_dir, materials_dir, dry_run=args.dry_run)
    
    print("=" * 60)
    print("📊 同期結果")
    print("=" * 60)
    print(f"✅ 同期: {synced} 件")
    print(f"⏭️  スキップ: {skipped} 件")
    print(f"❌ エラー: {errors} 件")
    print()
    
    # DB登録（オプション）
    if not args.no_db:
        print("=" * 60)
        print("📝 DB登録（使用例）")
        print("=" * 60)
        registered, db_skipped = sync_use_examples_to_db(materials_dir, dry_run=args.dry_run)
        print(f"✅ 登録: {registered} 件")
        print(f"⏭️  スキップ: {db_skipped} 件")
        print()
    
    print("=" * 60)
    print("✨ 完了")
    print("=" * 60)


if __name__ == '__main__':
    main()

