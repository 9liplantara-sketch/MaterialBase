"""
既存材料のembeddingをバックフィルするスクリプト

使用方法:
    python scripts/backfill_embeddings.py
"""
import os
import sys
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import SessionLocal, Material, init_db
from utils.search import update_material_embedding


def backfill_embeddings():
    """既存材料のembeddingをバックフィル"""
    init_db()
    db = SessionLocal()
    
    try:
        # 全材料を取得
        materials = db.query(Material).filter(Material.is_deleted == 0).all()
        
        total = len(materials)
        updated = 0
        skipped = 0
        errors = 0
        
        print(f"[INFO] Found {total} materials")
        print("-" * 80)
        
        for material in materials:
            try:
                if update_material_embedding(db, material):
                    updated += 1
                    if updated % 10 == 0:
                        print(f"[INFO] Updated {updated}/{total} materials...")
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                print(f"[ERROR] Failed to update material {material.id} ({material.name_official}): {e}")
        
        print("-" * 80)
        print(f"[INFO] Completed:")
        print(f"  Total materials: {total}")
        print(f"  Updated: {updated}")
        print(f"  Skipped (no change): {skipped}")
        print(f"  Errors: {errors}")
        
    finally:
        db.close()


if __name__ == "__main__":
    backfill_embeddings()
