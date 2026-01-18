"""
用途画像（材料名1.jpg/材料名2.jpg）をR2+imagesテーブルへ復元するスクリプト

背景:
ローカル時代、uploadフォルダに
- 「材料名1.jpg」= 空間写真 (kind="space")
- 「材料名2.jpg」= プロダクト写真 (kind="product")
が材料ごとに保存されていた。
DB移行後、この用途画像が表示されず「画像なし」になっている。

使用方法:
    python scripts/backfill_use_images.py --root uploads [--dry-run] [--apply]

注意:
    - Secrets に R2 の認証情報が設定されている必要があります
    - DATABASE_URL が設定されている必要があります
    - dry-run モード（デフォルト）では実際のアップロードは行いません
"""
import os
import sys
import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import hashlib

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import SessionLocal, Material, Image, init_db
from utils.r2_storage import upload_bytes_to_r2, make_public_url
from utils.image_repo import upsert_image
import utils.settings as settings


def normalize_material_name(name: str) -> str:
    """
    材料名を正規化（全角/半角スペース統一、末尾空白除去）
    
    Args:
        name: 材料名
    
    Returns:
        正規化された材料名
    """
    if not name:
        return ""
    # 全角スペースを半角スペースに変換
    name = name.replace("　", " ")
    # 連続するスペースを1つに
    while "  " in name:
        name = name.replace("  ", " ")
    # 末尾の空白を除去
    name = name.strip()
    return name


def find_use_image_files(material_name: str, upload_dir: Path) -> Dict[str, Optional[Path]]:
    """
    材料名から用途画像ファイルを探す
    
    Args:
        material_name: 材料名（正規化済み）
        upload_dir: アップロードディレクトリ
    
    Returns:
        {"space": Path or None, "product": Path or None} の辞書
    """
    result = {"space": None, "product": None}
    
    if not material_name:
        return result
    
    # 拡張子候補
    extensions = [".jpg", ".jpeg", ".png", ".webp"]
    
    # kind="space" のファイルを探す（材料名1.jpg など）
    for ext in extensions:
        candidates = [
            upload_dir / f"{material_name}1{ext}",
            upload_dir / f"{material_name}1.{ext.lstrip('.')}",  # 材料名1.jpg 形式
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                result["space"] = candidate
                break
        if result["space"]:
            break
    
    # kind="product" のファイルを探す（材料名2.jpg など）
    for ext in extensions:
        candidates = [
            upload_dir / f"{material_name}2{ext}",
            upload_dir / f"{material_name}2.{ext.lstrip('.')}",  # 材料名2.jpg 形式
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                result["product"] = candidate
                break
        if result["product"]:
            break
    
    return result


def calculate_sha256(file_path: Path) -> str:
    """
    ファイルのSHA256ハッシュを計算
    
    Args:
        file_path: ファイルパス
    
    Returns:
        SHA256ハッシュ（16進数文字列）
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def get_mime_type(file_path: Path) -> str:
    """
    ファイルパスからMIMEタイプを推定
    
    Args:
        file_path: ファイルパス
    
    Returns:
        MIMEタイプ文字列
    """
    ext = file_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "image/jpeg")


def check_existing_image(db, material_id: int, kind: str, sha256: str, r2_key: str) -> bool:
    """
    既存の画像が存在するかチェック（SHA256またはr2_keyで判定）
    
    Args:
        db: データベースセッション
        material_id: 材料ID
        kind: 画像種別
        sha256: SHA256ハッシュ
        r2_key: R2キー
    
    Returns:
        既存画像が存在する場合 True
    """
    # material_id + kind で既存チェック
    existing = db.query(Image).filter(
        Image.material_id == material_id,
        Image.kind == kind
    ).first()
    
    if existing:
        # 同じSHA256または同じr2_keyならスキップ
        if existing.sha256 == sha256 or existing.r2_key == r2_key:
            return True
    
    # 他の材料で同じSHA256の画像があるかチェック（重複アップロード防止）
    duplicate = db.query(Image).filter(
        Image.sha256 == sha256,
        Image.material_id != material_id
    ).first()
    
    if duplicate:
        return True
    
    return False


def backfill_use_images(
    upload_dir: Path,
    dry_run: bool = True
) -> Dict[str, int]:
    """
    用途画像をR2+imagesテーブルへ復元
    
    Args:
        upload_dir: アップロードディレクトリ
        dry_run: ドライランモード（デフォルト: True）
    
    Returns:
        統計情報の辞書
    """
    stats = {
        "total_materials": 0,
        "found_space": 0,
        "found_product": 0,
        "uploaded_space": 0,
        "uploaded_product": 0,
        "skipped_space": 0,
        "skipped_product": 0,
        "errors": 0,
    }
    
    # データベース初期化
    init_db()
    db = SessionLocal()
    
    try:
        # 全材料を取得
        materials = db.query(Material).filter(
            Material.is_deleted == 0
        ).all()
        
        stats["total_materials"] = len(materials)
        
        # CSVレポート用のデータ
        report_rows = []
        
        print(f"[INFO] Found {stats['total_materials']} materials")
        print(f"[INFO] Upload directory: {upload_dir}")
        print(f"[INFO] Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
        print("-" * 80)
        
        for material in materials:
            material_id = material.id
            name_official = normalize_material_name(material.name_official or "")
            name = normalize_material_name(material.name or "")
            
            # 材料名候補（name_official優先、なければname）
            material_name = name_official if name_official else name
            
            if not material_name:
                report_rows.append({
                    "material_id": material_id,
                    "material_name": "N/A",
                    "kind": "N/A",
                    "file_found": False,
                    "file_path": "",
                    "sha256": "",
                    "file_size": "",
                    "action": "SKIP",
                    "reason": "No material name",
                })
                continue
            
            # 用途画像ファイルを探す
            image_files = find_use_image_files(material_name, upload_dir)
            
            # kind="space" の処理
            if image_files["space"]:
                stats["found_space"] += 1
                file_path = image_files["space"]
                
                try:
                    sha256 = calculate_sha256(file_path)
                    mime = get_mime_type(file_path)
                    file_size = file_path.stat().st_size
                    
                    # R2キーを生成（materials/<id>/space/<filename>）
                    r2_key = f"materials/{material_id}/space/{file_path.name}"
                    
                    if dry_run:
                        # 既存チェック（dry-runでも確認）
                        existing = check_existing_image(db, material_id, "space", sha256, r2_key)
                        action = "SKIP" if existing else "UPLOAD"
                        reason = "Already exists" if existing else "Will upload"
                        
                        report_rows.append({
                            "material_id": material_id,
                            "material_name": material_name,
                            "kind": "space",
                            "file_found": True,
                            "file_path": str(file_path),
                            "sha256": sha256[:16] + "...",
                            "file_size": file_size,
                            "action": action,
                            "reason": reason,
                        })
                        print(f"[DRY-RUN] Material {material_id} ({material_name}): space image found -> {action}")
                    else:
                        # 既存チェック
                        if check_existing_image(db, material_id, "space", sha256, r2_key):
                            stats["skipped_space"] += 1
                            report_rows.append({
                                "material_id": material_id,
                                "material_name": material_name,
                                "kind": "space",
                                "file_found": True,
                                "file_path": str(file_path),
                                "sha256": sha256[:16] + "...",
                                "file_size": file_size,
                                "action": "SKIP",
                                "reason": "Already exists",
                            })
                            print(f"[SKIP] Material {material_id} ({material_name}): space image already exists")
                        else:
                            # R2へアップロード
                            try:
                                # ファイルを読み込む
                                with open(file_path, "rb") as f:
                                    file_data = f.read()
                                
                                # R2へアップロード
                                upload_bytes_to_r2(r2_key, file_data, mime)
                                
                                # 公開URLを生成
                                public_url = make_public_url(r2_key)
                                
                                if public_url:
                                    
                                    # imagesテーブルへupsert
                                    upsert_image(
                                        db=db,
                                        material_id=material_id,
                                        kind="space",
                                        r2_key=r2_key,
                                        public_url=public_url,
                                        mime=mime,
                                        sha256=sha256,
                                        bytes=file_size,
                                    )
                                    db.commit()
                                    
                                    stats["uploaded_space"] += 1
                                    report_rows.append({
                                        "material_id": material_id,
                                        "material_name": material_name,
                                        "kind": "space",
                                        "file_found": True,
                                        "file_path": str(file_path),
                                        "sha256": sha256[:16] + "...",
                                        "file_size": file_size,
                                        "action": "UPLOADED",
                                        "reason": "Success",
                                    })
                                    print(f"[OK] Material {material_id} ({material_name}): space image uploaded -> {public_url}")
                                else:
                                    error_msg = "Failed to generate public URL"
                                    stats["errors"] += 1
                                    report_rows.append({
                                        "material_id": material_id,
                                        "material_name": material_name,
                                        "kind": "space",
                                        "file_found": True,
                                        "file_path": str(file_path),
                                        "sha256": sha256[:16] + "...",
                                        "file_size": file_size,
                                        "action": "ERROR",
                                        "reason": error_msg,
                                    })
                                    print(f"[ERROR] Material {material_id} ({material_name}): space image upload failed -> {error_msg}")
                            except Exception as e:
                                db.rollback()
                                stats["errors"] += 1
                                report_rows.append({
                                    "material_id": material_id,
                                    "material_name": material_name,
                                    "kind": "space",
                                    "file_found": True,
                                    "file_path": str(file_path),
                                    "sha256": sha256[:16] + "...",
                                    "file_size": file_size,
                                    "action": "ERROR",
                                    "reason": str(e),
                                })
                                print(f"[ERROR] Material {material_id} ({material_name}): space image error -> {e}")
                except Exception as e:
                    stats["errors"] += 1
                    report_rows.append({
                        "material_id": material_id,
                        "material_name": material_name,
                        "kind": "space",
                        "file_found": True,
                        "file_path": str(file_path),
                        "sha256": "",
                        "file_size": "",
                        "action": "ERROR",
                        "reason": str(e),
                    })
                    print(f"[ERROR] Material {material_id} ({material_name}): space image processing error -> {e}")
            else:
                report_rows.append({
                    "material_id": material_id,
                    "material_name": material_name,
                    "kind": "space",
                    "file_found": False,
                    "file_path": "",
                    "sha256": "",
                    "file_size": "",
                    "action": "NOT_FOUND",
                    "reason": "File not found",
                })
            
            # kind="product" の処理
            if image_files["product"]:
                stats["found_product"] += 1
                file_path = image_files["product"]
                
                try:
                    sha256 = calculate_sha256(file_path)
                    mime = get_mime_type(file_path)
                    file_size = file_path.stat().st_size
                    
                    # R2キーを生成（materials/<id>/product/<filename>）
                    r2_key = f"materials/{material_id}/product/{file_path.name}"
                    
                    if dry_run:
                        # 既存チェック（dry-runでも確認）
                        existing = check_existing_image(db, material_id, "product", sha256, r2_key)
                        action = "SKIP" if existing else "UPLOAD"
                        reason = "Already exists" if existing else "Will upload"
                        
                        report_rows.append({
                            "material_id": material_id,
                            "material_name": material_name,
                            "kind": "product",
                            "file_found": True,
                            "file_path": str(file_path),
                            "sha256": sha256[:16] + "...",
                            "file_size": file_size,
                            "action": action,
                            "reason": reason,
                        })
                        print(f"[DRY-RUN] Material {material_id} ({material_name}): product image found -> {action}")
                    else:
                        # 既存チェック
                        if check_existing_image(db, material_id, "product", sha256, r2_key):
                            stats["skipped_product"] += 1
                            report_rows.append({
                                "material_id": material_id,
                                "material_name": material_name,
                                "kind": "product",
                                "file_found": True,
                                "file_path": str(file_path),
                                "sha256": sha256[:16] + "...",
                                "file_size": file_size,
                                "action": "SKIP",
                                "reason": "Already exists",
                            })
                            print(f"[SKIP] Material {material_id} ({material_name}): product image already exists")
                        else:
                            # R2へアップロード
                            try:
                                # ファイルを読み込む
                                with open(file_path, "rb") as f:
                                    file_data = f.read()
                                
                                # R2へアップロード
                                upload_bytes_to_r2(r2_key, file_data, mime)
                                
                                # 公開URLを生成
                                public_url = make_public_url(r2_key)
                                
                                if public_url:
                                    # imagesテーブルへupsert
                                    upsert_image(
                                        db=db,
                                        material_id=material_id,
                                        kind="product",
                                        r2_key=r2_key,
                                        public_url=public_url,
                                        mime=mime,
                                        sha256=sha256,
                                        bytes=file_size,
                                    )
                                    db.commit()
                                    
                                    stats["uploaded_product"] += 1
                                    report_rows.append({
                                        "material_id": material_id,
                                        "material_name": material_name,
                                        "kind": "product",
                                        "file_found": True,
                                        "file_path": str(file_path),
                                        "sha256": sha256[:16] + "...",
                                        "file_size": file_size,
                                        "action": "UPLOADED",
                                        "reason": "Success",
                                    })
                                    print(f"[OK] Material {material_id} ({material_name}): product image uploaded -> {public_url}")
                                else:
                                    error_msg = "Failed to generate public URL"
                                    stats["errors"] += 1
                                    report_rows.append({
                                        "material_id": material_id,
                                        "material_name": material_name,
                                        "kind": "product",
                                        "file_found": True,
                                        "file_path": str(file_path),
                                        "sha256": sha256[:16] + "...",
                                        "file_size": file_size,
                                        "action": "ERROR",
                                        "reason": error_msg,
                                    })
                                    print(f"[ERROR] Material {material_id} ({material_name}): product image upload failed -> {error_msg}")
                            except Exception as e:
                                db.rollback()
                                stats["errors"] += 1
                                report_rows.append({
                                    "material_id": material_id,
                                    "material_name": material_name,
                                    "kind": "product",
                                    "file_found": True,
                                    "file_path": str(file_path),
                                    "sha256": sha256[:16] + "...",
                                    "file_size": file_size,
                                    "action": "ERROR",
                                    "reason": str(e),
                                })
                                print(f"[ERROR] Material {material_id} ({material_name}): product image error -> {e}")
                except Exception as e:
                    stats["errors"] += 1
                    report_rows.append({
                        "material_id": material_id,
                        "material_name": material_name,
                        "kind": "product",
                        "file_found": True,
                        "file_path": str(file_path),
                        "sha256": "",
                        "file_size": "",
                        "action": "ERROR",
                        "reason": str(e),
                    })
                    print(f"[ERROR] Material {material_id} ({material_name}): product image processing error -> {e}")
            else:
                report_rows.append({
                    "material_id": material_id,
                    "material_name": material_name,
                    "kind": "product",
                    "file_found": False,
                    "file_path": "",
                    "sha256": "",
                    "file_size": "",
                    "action": "NOT_FOUND",
                    "reason": "File not found",
                })
        
        # CSVレポートを出力
        reports_dir = project_root / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        csv_path = reports_dir / f"use_images_backfill_{timestamp}.csv"
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "material_id",
                "material_name",
                "kind",
                "file_found",
                "file_path",
                "sha256",
                "file_size",
                "action",
                "reason",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if report_rows:
                writer.writerows(report_rows)
        
        print("-" * 80)
        print(f"[INFO] Report saved to: {csv_path}")
        print(f"[INFO] Statistics:")
        print(f"  Total materials: {stats['total_materials']}")
        print(f"  Found space images: {stats['found_space']}")
        print(f"  Found product images: {stats['found_product']}")
        if not dry_run:
            print(f"  Uploaded space images: {stats['uploaded_space']}")
            print(f"  Uploaded product images: {stats['uploaded_product']}")
            print(f"  Skipped space images: {stats['skipped_space']}")
            print(f"  Skipped product images: {stats['skipped_product']}")
        print(f"  Errors: {stats['errors']}")
        
    finally:
        db.close()
    
    return stats


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="用途画像（材料名1.jpg/材料名2.jpg）をR2+imagesテーブルへ復元"
    )
    parser.add_argument(
        "--root",
        type=str,
        default="uploads",
        help="アップロードディレクトリ（デフォルト: uploads）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="ドライランモード（デフォルト: True）"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="実際にアップロードを実行（--dry-run と同時指定不可）"
    )
    
    args = parser.parse_args()
    
    if args.apply:
        dry_run = False
    else:
        dry_run = True
    
    upload_dir = Path(args.root)
    if not upload_dir.exists():
        print(f"[ERROR] Upload directory not found: {upload_dir}")
        sys.exit(1)
    
    if not upload_dir.is_dir():
        print(f"[ERROR] Not a directory: {upload_dir}")
        sys.exit(1)
    
    print(f"[INFO] Starting backfill use images...")
    print(f"[INFO] Upload directory: {upload_dir}")
    print(f"[INFO] Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    
    if dry_run:
        print("[WARNING] DRY-RUN mode: No actual uploads will be performed")
    else:
        print("[WARNING] APPLY mode: Actual uploads will be performed")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("[INFO] Cancelled by user")
            sys.exit(0)
    
    stats = backfill_use_images(upload_dir, dry_run=dry_run)
    
    print("[INFO] Backfill completed")


if __name__ == "__main__":
    main()
