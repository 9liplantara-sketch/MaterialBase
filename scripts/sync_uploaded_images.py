"""
uploads/ と uploads/uses/ にある画像を static/images/materials/ に同期するスクリプト

命名規則（これが正）:
- uploads/{材料名}.{任意拡張子}           → primary（材料のメイン画像）
- uploads/uses/{材料名}1.{任意拡張子}     → space（生活/空間の使用例）
- uploads/uses/{材料名}2.{任意拡張子}     → product（プロダクトの使用例）

拡張子は jpg/jpeg/png/webp を許容。優先順位: jpg > jpeg > png > webp

出力先（JPG固定）:
- static/images/materials/{safe_slug}/primary.jpg
- static/images/materials/{safe_slug}/uses/space.jpg
- static/images/materials/{safe_slug}/uses/product.jpg

注意:
- 入力が.jpg/.jpegの場合: shutil.copy2()でそのままコピー（mtimeも維持、再エンコードしない）
- 入力が.png/.webpの場合: Pillowで開いてJPGに変換（透過は白背景合成）
"""
import os
import re
import hashlib
import shutil
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


def copy_image_to_jpg(source_path: Path, dest_path: Path) -> Tuple[bool, bool]:
    """
    画像をJPGに変換またはコピーして保存
    
    - 入力が.jpg/.jpegの場合: shutil.copy2()でそのままコピー（mtimeも維持、再エンコードしない）
    - 入力が.png/.webpの場合: Pillowで開いてJPGに変換（透過は白背景合成）
    
    Args:
        source_path: 元画像のパス（任意の拡張子）
        dest_path: 保存先のパス（.jpg固定）
    
    Returns:
        (成功した場合True, 変換が必要だった場合True)
    """
    try:
        source_ext = source_path.suffix.lower()
        
        # .jpg/.jpegの場合はそのままコピー（再エンコードしない）
        if source_ext in ['.jpg', '.jpeg']:
            ensure_dir(dest_path.parent)
            shutil.copy2(source_path, dest_path)  # mtimeも維持
            return True, False  # 変換不要
        
        # .png/.webpの場合はJPGに変換
        # 画像を開く
        img = Image.open(source_path)
        needs_conversion = True
        
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
        
        # JPGとして保存（拡張子は常に.jpg、quality=90, optimize=True）
        ensure_dir(dest_path.parent)
        img.save(dest_path, 'JPEG', quality=90, optimize=True)
        return True, needs_conversion
    except Exception as e:
        print(f"  ❌ エラー: {source_path} -> {dest_path}: {e}")
        return False, False


def copy_image_preserving_ext(source_path: Path, dest_path: Path) -> bool:
    """
    互換性のためのラッパー関数（JPG固定出力）
    
    注意: 名前は"preserving_ext"だが、実際はJPG固定で保存します。
    
    Args:
        source_path: 元画像のパス（任意の拡張子）
        dest_path: 保存先のパス（.jpg固定）
    
    Returns:
        成功した場合True
    """
    success, _ = copy_image_to_jpg(source_path, dest_path)
    return success


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
        
        # クリーンアップ関数（旧ファイル削除）
        def cleanup_old_files(base_path: Path, filename_base: str) -> List[str]:
            """同一スロットの旧ファイル（jpeg/png/webp）を削除"""
            old_exts = ['.jpeg', '.png', '.webp']
            deleted = []
            for old_ext in old_exts:
                old_path = base_path / f'{filename_base}{old_ext}'
                if old_path.exists() and old_path != base_path / f'{filename_base}.jpg':
                    try:
                        old_path.unlink()
                        deleted.append(old_ext[1:])  # .png -> png
                    except Exception as e:
                        print(f"    ⚠️  旧ファイル削除失敗: {old_path.name} ({e})")
            return deleted
        
        # メイン画像（primary）- JPG固定
        primary_dest = material_base_dir / 'primary.jpg'
        if files['primary']:
            source_path, ext = files['primary'][0]
            
            # クリーンアップを先に実行（スキップ判定より前）
            if not dry_run:
                deleted = cleanup_old_files(material_base_dir, 'primary')
                if deleted:
                    print(f"  🗑️  旧ファイル削除: {', '.join(deleted)}")
            
            # べき等性チェック（JPGファイルと比較）
            if primary_dest.exists() and files_are_identical(source_path, primary_dest):
                print(f"  ⏭️  primary: {source_path.name} -> primary.jpg (同一ファイル、スキップ)")
                synced_results[material_name]['primary'] = str(primary_dest.relative_to(project_root))
            else:
                if dry_run:
                    print(f"  🔍 ドライラン: {source_path.name} -> primary.jpg")
                    synced_results[material_name]['primary'] = str(primary_dest.relative_to(project_root))
                else:
                    success, converted = copy_image_to_jpg(source_path, primary_dest)
                    if success:
                        if converted:
                            conv_msg = f" ({ext} -> jpg変換)"
                        else:
                            conv_msg = " (jpgそのままコピー、mtime維持)"
                        print(f"  ✅ primary: {source_path.name} -> primary.jpg{conv_msg}")
                        synced_results[material_name]['primary'] = str(primary_dest.relative_to(project_root))
                    else:
                        print(f"  ❌ primary: コピー失敗")
        else:
            print(f"  ⏭️  primary: ファイルなし")
            missing.append('primary')
        
        # 使用例1（space）- JPG固定
        uses_dir = material_base_dir / 'uses'
        space_dest = uses_dir / 'space.jpg'
        if files['space']:
            source_path, ext = files['space'][0]
            
            # クリーンアップを先に実行
            if not dry_run:
                deleted = cleanup_old_files(uses_dir, 'space')
                if deleted:
                    print(f"  🗑️  旧ファイル削除: {', '.join(deleted)}")
            
            # べき等性チェック（JPGファイルと比較）
            if space_dest.exists() and files_are_identical(source_path, space_dest):
                print(f"  ⏭️  space: {source_path.name} -> space.jpg (同一ファイル、スキップ)")
                synced_results[material_name]['space'] = str(space_dest.relative_to(project_root))
            else:
                if dry_run:
                    print(f"  🔍 ドライラン: {source_path.name} -> space.jpg")
                    synced_results[material_name]['space'] = str(space_dest.relative_to(project_root))
                else:
                    success, converted = copy_image_to_jpg(source_path, space_dest)
                    if success:
                        if converted:
                            conv_msg = f" ({ext} -> jpg変換)"
                        else:
                            conv_msg = " (jpgそのままコピー、mtime維持)"
                        print(f"  ✅ space: {source_path.name} -> space.jpg{conv_msg}")
                        synced_results[material_name]['space'] = str(space_dest.relative_to(project_root))
                    else:
                        print(f"  ❌ space: コピー失敗")
        else:
            print(f"  ⏭️  space: ファイルなし")
            missing.append('space')
        
        # 使用例2（product）- JPG固定
        product_dest = uses_dir / 'product.jpg'
        if files['product']:
            source_path, ext = files['product'][0]
            
            # クリーンアップを先に実行
            if not dry_run:
                deleted = cleanup_old_files(uses_dir, 'product')
                if deleted:
                    print(f"  🗑️  旧ファイル削除: {', '.join(deleted)}")
            
            # べき等性チェック（JPGファイルと比較）
            if product_dest.exists() and files_are_identical(source_path, product_dest):
                print(f"  ⏭️  product: {source_path.name} -> product.jpg (同一ファイル、スキップ)")
                synced_results[material_name]['product'] = str(product_dest.relative_to(project_root))
            else:
                if dry_run:
                    print(f"  🔍 ドライラン: {source_path.name} -> product.jpg")
                    synced_results[material_name]['product'] = str(product_dest.relative_to(project_root))
                else:
                    success, converted = copy_image_to_jpg(source_path, product_dest)
                    if success:
                        if converted:
                            conv_msg = f" ({ext} -> jpg変換)"
                        else:
                            conv_msg = " (jpgそのままコピー、mtime維持)"
                        print(f"  ✅ product: {source_path.name} -> product.jpg{conv_msg}")
                        synced_results[material_name]['product'] = str(product_dest.relative_to(project_root))
                    else:
                        print(f"  ❌ product: コピー失敗")
        else:
            print(f"  ⏭️  product: ファイルなし")
            missing.append('product')
        
        if missing:
            missing_summary[material_name] = missing
    
    return synced_results, missing_summary


def load_db_materials() -> Optional[Dict[str, int]]:
    """
    DBから材料名マッピングを取得（DBスキーマ不整合に耐性あり）
    
    Returns:
        {正規化名: material_id} または None（DB接続失敗時）
    """
    try:
        from database import SessionLocal, Material
    except ImportError as e:
        print(f"⚠️  DBモジュールインポートエラー（--no-db相当で続行）: {e}")
        return None
    except Exception as e:
        print(f"⚠️  DBモジュール読み込みエラー（--no-db相当で続行）: {e}")
        return None
    
    try:
        db = SessionLocal()
    except Exception as e:
        print(f"⚠️  DB接続エラー（--no-db相当で続行）: {e}")
        return None
    
    try:
        materials = db.query(Material).all()
        result = {}
        for m in materials:
            try:
                # name_official を優先、なければ name
                name = getattr(m, 'name_official', None) or getattr(m, 'name', None)
                if name:
                    normalized = normalize_material_name(name)
                    material_id = getattr(m, 'id', None)
                    if material_id:
                        result[normalized] = material_id
                        # 元の名前も追加（完全一致用）
                        if name != normalized:
                            result[name] = material_id
            except Exception as e:
                # 個別の材料でエラーが出ても続行
                print(f"    ⚠️  材料データ取得エラー（スキップ）: {e}")
                continue
        return result
    except Exception as e:
        print(f"⚠️  DBクエリエラー（--no-db相当で続行）: {e}")
        return None
    finally:
        try:
            db.close()
        except Exception:
            pass


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
    
    # DBから材料名を取得（DBスキーマ不整合に耐性あり）
    db_materials = None
    if not args.no_db:
        db_materials = load_db_materials()
        if db_materials is None:
            print("⚠️  DB接続失敗またはスキーマ不整合のため、--no-db相当で続行します")
            print()
        else:
            print(f"📊 DB材料数: {len(db_materials)} 件")
            print()
    else:
        print("📊 DB突合をスキップ（--no-db）")
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
