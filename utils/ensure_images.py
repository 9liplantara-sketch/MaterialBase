"""
起動時の画像自動修復モジュール
"""
from pathlib import Path
from typing import List
from database import Material, Image as ImageModel
from utils.image_health import check_image_health, normalize_image_path
from utils.db import session_scope
from image_generator import ensure_material_image
from sqlalchemy.orm import selectinload


def ensure_images(project_root: Path = None):
    """
    起動時にすべての材料画像をチェックし、問題があれば自動修復
    
    Args:
        project_root: プロジェクトルートのパス
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)
    
    try:
        with session_scope() as db:
            # すべての材料を取得（画像リレーションも読み込む）
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            
            materials = db.execute(
                select(Material)
                .options(selectinload(Material.images))
            ).scalars().all()
            
            if not materials:
                return
            
            print("=" * 60)
            print("画像の自動修復を開始します...")
            print("=" * 60)
            
            fixed_count = 0
            regenerated_count = 0
            
            for material in materials:
                material_name = material.name_official or material.name
                category = material.category_main or material.category or "その他"
                
                # 画像が登録されているか確認
                if not material.images:
                    # 画像がない場合は生成
                    print(f"📦 {material_name} (ID: {material.id}): 画像なし → 生成中...")
                    image_path = ensure_material_image(material_name, category, material.id, db)
                    if image_path:
                        regenerated_count += 1
                        print(f"  ✅ 画像を生成しました: {image_path}")
                    else:
                        print(f"  ❌ 画像生成に失敗しました")
                    continue
                
                # 各画像の健康状態をチェック
                for img in material.images:
                    health = check_image_health(img.file_path, project_root)
                    
                    if health["status"] == "ok":
                        # 正常な画像はパスを正規化するだけ（既存DBの絶対パスを相対パスに変換）
                        normalized = normalize_image_path(img.file_path, project_root)
                        if normalized != img.file_path:
                            img.file_path = normalized
                            fixed_count += 1
                            print(f"📦 {material_name} (ID: {material.id}): パスを正規化しました")
                        continue
                    
                    # 問題がある画像は再生成
                    print(f"📦 {material_name} (ID: {material.id}): {health['status']} → 再生成中...")
                    print(f"  理由: {health['reason']}")
                    
                    # 既存の画像レコードを削除
                    db.delete(img)
                    
                    # 再生成
                    image_path = ensure_material_image(material_name, category, material.id, db)
                    if image_path:
                        regenerated_count += 1
                        print(f"  ✅ 画像を再生成しました: {image_path}")
                    else:
                        print(f"  ❌ 画像再生成に失敗しました")
            
            # session_scope が自動で commit（例外時は自動 rollback）
            print("=" * 60)
            print(f"✅ 画像の自動修復が完了しました")
            print(f"   - パス正規化: {fixed_count}件")
            print(f"   - 再生成: {regenerated_count}件")
            print("=" * 60)
        
    except Exception as e:
        print(f"❌ 画像の自動修復中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        # session_scope が自動で rollback するため、明示的な rollback は不要



