"""
既存材料のsearch_textをバックフィルするスクリプト

使用方法:
    python scripts/backfill_search_text.py
"""
import os
import sys
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import SessionLocal, Material, init_db
from utils.search import generate_search_text, update_material_search_text


def backfill_search_text():
    """既存材料のsearch_textをバックフィル"""
    init_db()
    db = SessionLocal()
    
    try:
        # 全材料を取得
        materials = db.query(Material).filter(Material.is_deleted == 0).all()
        
        total = len(materials)
        updated = 0
        errors = 0
        
        print(f"[INFO] Found {total} materials")
        print("-" * 80)
        
        for material in materials:
            try:
                search_text = generate_search_text(material)
                material.search_text = search_text
                updated += 1
                
                if updated % 10 == 0:
                    db.commit()
                    print(f"[INFO] Updated {updated}/{total} materials...")
            except Exception as e:
                errors += 1
                print(f"[ERROR] Failed to update material {material.id} ({material.name_official}): {e}")
        
        # 最終コミット
        db.commit()
        
        print("-" * 80)
        print(f"[INFO] Completed:")
        print(f"  Total materials: {total}")
        print(f"  Updated: {updated}")
        print(f"  Errors: {errors}")
        
    finally:
        db.close()


if __name__ == "__main__":
    backfill_search_text()
