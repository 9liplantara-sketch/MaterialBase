"""
既存のローカル画像（uploads/ と uploads/uses/）を R2 に一括アップロードし、DB を更新するスクリプト

使用方法:
    python scripts/migrate_local_uploads_to_r2.py [--dry-run] [--uploads-dir ./uploads] [--uses-dir ./uploads/uses]

注意:
    - Secrets に R2 の認証情報が設定されている必要があります
    - DATABASE_URL が設定されている必要があります
    - dry-run モードでは実際のアップロードは行いません
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import SessionLocal, Material, Image, init_db
from utils.r2_storage import upload_local_file
from utils.image_repo import upsert_image
import utils.settings as settings


def find_material_by_name(db, material_name: str) -> Optional[Material]:
    """
    材料名から Material を検索（name_official 優先、なければ name でも試す）
    
    Args:
        db: データベースセッション
        material_name: 材料名（ファイル名から抽出）
    
    Returns:
        Material オブジェクト、見つからなければ None
    """
    # name_official で検索
    material = db.query(Material).filter(
        Material.name_official == material_name
    ).first()
    
    if material:
        return material
    
    # name で検索（後方互換）
    material = db.query(Material).filter(
        Material.name == material_name
    ).first()
    
    return material


def parse_material_name_from_filename(filename: str) -> Tuple[Optional[str], Optional[str]]:
    """
    ファイル名から材料名と kind を抽出
    
    例:
        - "コンクリート.jpg" -> ("コンクリート", "primary")
        - "コンクリート.1.jpg" -> ("コンクリート", "space")
        - "コンクリート.2.jpg" -> ("コンクリート", "product")
        - "コンクリート1.jpg" -> ("コンクリート", "space")  # 互換
        - "コンクリート2.jpg" -> ("コンクリート", "product")  # 互換
    
    Args:
        filename: ファイル名
    
    Returns:
        (material_name, kind) のタプル
    """
    # 拡張子を除去
    base_name = Path(filename).stem
    
    # .1 / .2 形式をチェック
    if base_name.endswith(".1"):
        material_name = base_name[:-2]
        return material_name, "space"
    elif base_name.endswith(".2"):
        material_name = base_name[:-2]
        return material_name, "product"
    
    # 1 / 2 形式をチェック（互換）
    if base_name.endswith("1"):
        material_name = base_name[:-1]
        return material_name, "space"
    elif base_name.endswith("2"):
        material_name = base_name[:-1]
        return material_name, "product"
    
    # それ以外は primary
    return base_name, "primary"


def migrate_uploads_to_r2(
    uploads_dir: Path,
    uses_dir: Optional[Path] = None,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    ローカル画像を R2 に一括アップロードし、DB を更新
    
    Args:
        uploads_dir: uploads ディレクトリのパス
        uses_dir: uploads/uses ディレクトリのパス（None の場合は uploads_dir/uses）
        dry_run: True の場合は実際のアップロードは行わない
    
    Returns:
        統計情報の辞書
    """
    stats = {
        "uploaded": 0,
        "skipped": 0,
        "missing_material": 0,
        "errors": 0,
    }
    
    # データベース初期化
    init_db()
    db = SessionLocal()
    
    try:
        # フラグチェック
        # get_flag が無い場合に備えた二重化
        flag_fn = getattr(settings, "get_flag", None)
        if not callable(flag_fn):
            # フォールバック: os.getenv のみで判定
            import os
            def flag_fn(key, default=False):
                value = os.getenv(key)
                if value is None:
                    return default
                value_str = str(value).lower().strip()
                return value_str in ("1", "true", "yes", "y", "on")
        
        if flag_fn("INIT_SAMPLE_DATA", False) or flag_fn("SEED_SKIP_IMAGES", False):
            print("[WARNING] INIT_SAMPLE_DATA or SEED_SKIP_IMAGES is enabled. R2 upload will be skipped.")
            return stats
        
        enable_r2_upload = flag_fn("ENABLE_R2_UPLOAD", True)
        if not enable_r2_upload:
            print("[WARNING] ENABLE_R2_UPLOAD is False. R2 upload will be skipped.")
            return stats
        
        # uses_dir のデフォルト
        if uses_dir is None:
            uses_dir = uploads_dir / "uses"
        
        print(f"[MIGRATE] Starting migration (dry_run={dry_run})")
        print(f"[MIGRATE] uploads_dir: {uploads_dir}")
        print(f"[MIGRATE] uses_dir: {uses_dir}")
        print("=" * 60)
        
        # 1. uploads_dir から primary 画像を列挙
        if uploads_dir.exists():
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
            for file_path in uploads_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    material_name, kind = parse_material_name_from_filename(file_path.name)
                    
                    # uses ディレクトリのファイルはスキップ（後で処理）
                    if kind in ("space", "product"):
                        continue
                    
                    if not material_name:
                        print(f"[SKIP] Cannot parse material name from: {file_path.name}")
                        stats["skipped"] += 1
                        continue
                    
                    # 材料を検索
                    material = find_material_by_name(db, material_name)
                    if not material:
                        print(f"[MISSING] Material not found: {material_name} (file: {file_path.name})")
                        stats["missing_material"] += 1
                        continue
                    
                    # R2 にアップロード
                    try:
                        if dry_run:
                            print(f"[DRY-RUN] Would upload: {file_path.name} -> material_id={material.id}, kind={kind}")
                        else:
                            r2_result = upload_local_file(file_path, material.id, kind)
                            upsert_image(
                                db=db,
                                material_id=material.id,
                                kind=kind,
                                r2_key=r2_result["r2_key"],
                                public_url=r2_result["public_url"],
                                bytes=r2_result["bytes"],
                                mime=r2_result["mime"],
                                sha256=r2_result["sha256"],
                            )
                            db.commit()
                            print(f"[UPLOADED] {file_path.name} -> material_id={material.id}, kind={kind}, url={r2_result['public_url']}")
                        stats["uploaded"] += 1
                    except Exception as e:
                        print(f"[ERROR] Failed to upload {file_path.name}: {e}")
                        stats["errors"] += 1
                        db.rollback()
        
        # 2. uses_dir から space/product 画像を列挙
        if uses_dir.exists():
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
            for file_path in uses_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    material_name, kind = parse_material_name_from_filename(file_path.name)
                    
                    if not material_name:
                        print(f"[SKIP] Cannot parse material name from: {file_path.name}")
                        stats["skipped"] += 1
                        continue
                    
                    # 材料を検索
                    material = find_material_by_name(db, material_name)
                    if not material:
                        print(f"[MISSING] Material not found: {material_name} (file: {file_path.name})")
                        stats["missing_material"] += 1
                        continue
                    
                    # R2 にアップロード
                    try:
                        if dry_run:
                            print(f"[DRY-RUN] Would upload: {file_path.name} -> material_id={material.id}, kind={kind}")
                        else:
                            r2_result = upload_local_file(file_path, material.id, kind)
                            upsert_image(
                                db=db,
                                material_id=material.id,
                                kind=kind,
                                r2_key=r2_result["r2_key"],
                                public_url=r2_result["public_url"],
                                bytes=r2_result["bytes"],
                                mime=r2_result["mime"],
                                sha256=r2_result["sha256"],
                            )
                            db.commit()
                            print(f"[UPLOADED] {file_path.name} -> material_id={material.id}, kind={kind}, url={r2_result['public_url']}")
                        stats["uploaded"] += 1
                    except Exception as e:
                        print(f"[ERROR] Failed to upload {file_path.name}: {e}")
                        stats["errors"] += 1
                        db.rollback()
        
        print("=" * 60)
        print(f"[MIGRATE] Migration completed:")
        print(f"  Uploaded: {stats['uploaded']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Missing material: {stats['missing_material']}")
        print(f"  Errors: {stats['errors']}")
        
    finally:
        db.close()
    
    return stats


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Migrate local uploads to R2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no actual upload)"
    )
    parser.add_argument(
        "--uploads-dir",
        type=str,
        default="./uploads",
        help="Uploads directory path (default: ./uploads)"
    )
    parser.add_argument(
        "--uses-dir",
        type=str,
        default=None,
        help="Uses directory path (default: ./uploads/uses)"
    )
    
    args = parser.parse_args()
    
    uploads_dir = Path(args.uploads_dir).resolve()
    uses_dir = Path(args.uses_dir).resolve() if args.uses_dir else None
    
    if not uploads_dir.exists():
        print(f"[ERROR] Uploads directory does not exist: {uploads_dir}")
        sys.exit(1)
    
    stats = migrate_uploads_to_r2(uploads_dir, uses_dir, dry_run=args.dry_run)
    
    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
