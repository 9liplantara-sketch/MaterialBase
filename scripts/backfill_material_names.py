#!/usr/bin/env python3
"""
材料名のバックフィルスクリプト
DBの name_official を修正し、safe_slug も正しく固定する

実行方法:
    python scripts/backfill_material_names.py

このスクリプトは「実行した時だけ」DBを更新し、アプリ起動時に勝手に走らない
"""
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import SessionLocal, Material, init_db
from utils.image_display import safe_slug_from_material
import json
import re


def fix_stainless_steel_names(db):
    """
    ステンレス鋼の名前を修正（SUS30 → SUS304）
    
    Args:
        db: データベースセッション
    
    Returns:
        (fixed_count, errors) のタプル
    """
    fixed_count = 0
    errors = []
    
    try:
        # "ステンレス鋼 SUS30" を含む材料を検索
        materials = db.query(Material).filter(
            Material.name_official.like('%ステンレス鋼%')
        ).all()
        
        print(f"ステンレス鋼関連の材料を {len(materials)} 件検出しました")
        
        for material in materials:
            old_name = material.name_official
            print(f"\n材料 ID: {material.id}")
            print(f"  現在の name_official: {old_name}")
            
            # SUS30 を SUS304 に修正
            if "SUS30" in old_name and "SUS304" not in old_name:
                new_name = old_name.replace("SUS30", "SUS304")
                
                # name_official を更新
                material.name_official = new_name
                print(f"  → name_official を '{new_name}' に更新")
                
                # name_aliases に旧値を追加（存在する場合）
                aliases = []
                try:
                    if material.name_aliases:
                        aliases = json.loads(material.name_aliases)
                except (json.JSONDecodeError, TypeError):
                    # name_aliases が JSON でない場合は文字列として扱う
                    if material.name_aliases:
                        aliases = [alias.strip() for alias in str(material.name_aliases).split(",") if alias.strip()]
                
                # 旧値が aliases にない場合は追加
                if old_name not in aliases:
                    aliases.insert(0, old_name)  # 先頭に追加
                    material.name_aliases = json.dumps(aliases, ensure_ascii=False)
                    print(f"  → name_aliases に旧値 '{old_name}' を追加")
                
                fixed_count += 1
            
            # safe_slug を確認（デバッグ用）
            safe_slug = safe_slug_from_material(material)
            print(f"  → safe_slug: {safe_slug}")
            
            # 画像パスの存在確認
            base_dir = project_root / "static" / "images" / "materials"
            legacy_dir = base_dir / safe_slug
            jp_dir = base_dir / material.name_official.replace(" ", "_").replace("　", "_")
            old_jp_dir = None
            if "ステンレス鋼" in material.name_official:
                old_jp_dir = base_dir / "ステンレス鋼"
            
            print(f"  → 画像パス確認:")
            print(f"     - safe_slug: {legacy_dir} (exists: {legacy_dir.exists()})")
            if old_jp_dir and old_jp_dir != legacy_dir:
                print(f"     - 日本語フォルダ: {old_jp_dir} (exists: {old_jp_dir.exists()})")
        
        if fixed_count > 0:
            db.commit()
            print(f"\n✓ {fixed_count} 件の材料名を修正しました")
        else:
            print("\n✓ 修正が必要な材料は見つかりませんでした")
    
    except Exception as e:
        db.rollback()
        errors.append(f"エラー: {e}")
        import traceback
        errors.append(traceback.format_exc())
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    return fixed_count, errors


def fix_all_material_slugs(db):
    """
    すべての材料の safe_slug を確認・報告（実際には修正しない）
    将来的に safe_slug カラムを追加する場合の準備
    
    Args:
        db: データベースセッション
    
    Returns:
        report の辞書
    """
    materials = db.query(Material).all()
    report = {
        "total": len(materials),
        "slug_mismatches": [],
        "missing_images": []
    }
    
    base_dir = project_root / "static" / "images" / "materials"
    
    print(f"\n{'='*60}")
    print("Safe Slug 確認レポート")
    print(f"{'='*60}")
    
    for material in materials:
        safe_slug = safe_slug_from_material(material)
        expected_path = base_dir / safe_slug / "primary.jpg"
        
        # 日本語フォルダ名でのフォールバック確認
        jp_name = material.name_official
        jp_path = base_dir / jp_name / "primary.jpg"
        
        exists_safe = expected_path.exists()
        exists_jp = jp_path.exists()
        
        print(f"\n材料: {material.name_official} (ID: {material.id})")
        print(f"  safe_slug: {safe_slug}")
        print(f"  safe_slug パス: {expected_path} (exists: {exists_safe})")
        print(f"  日本語フォルダ パス: {jp_path} (exists: {exists_jp})")
        
        if not exists_safe and not exists_jp:
            report["missing_images"].append({
                "id": material.id,
                "name": material.name_official,
                "safe_slug": safe_slug,
                "expected_path": str(expected_path),
                "jp_path": str(jp_path)
            })
            print(f"  ⚠️  画像が見つかりません")
    
    return report


def main():
    """メイン処理"""
    print("="*60)
    print("材料名バックフィルスクリプト")
    print("="*60)
    
    # データベース初期化
    init_db()
    
    db = SessionLocal()
    
    try:
        # ステンレス鋼の名前を修正
        print("\n[1] ステンレス鋼の名前修正")
        print("-"*60)
        fixed_count, errors = fix_stainless_steel_names(db)
        
        if errors:
            print("\n❌ エラーが発生しました:")
            for error in errors:
                print(f"  {error}")
            sys.exit(1)
        
        # すべての材料の safe_slug を確認
        print("\n[2] Safe Slug 確認")
        print("-"*60)
        report = fix_all_material_slugs(db)
        
        print(f"\n{'='*60}")
        print("結果サマリー")
        print(f"{'='*60}")
        print(f"修正件数: {fixed_count}")
        print(f"総材料数: {report['total']}")
        print(f"画像が見つからない材料: {len(report['missing_images'])}")
        
        if report['missing_images']:
            print("\n⚠️  画像が見つからない材料:")
            for item in report['missing_images']:
                print(f"  - {item['name']} (ID: {item['id']})")
                print(f"    safe_slug: {item['safe_slug']}")
                print(f"    expected: {item['expected_path']}")
        
        print("\n✓ バックフィル完了")
    
    except Exception as e:
        db.rollback()
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

