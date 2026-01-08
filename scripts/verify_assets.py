#!/usr/bin/env python3
"""
画像アセットの検証スクリプト
実際の解決ロジック（get_material_image_ref）基準で検査

実行方法:
    python scripts/verify_assets.py

環境変数:
    VERIFY_INCLUDE_UNPUBLISHED=1: 非公開材料も検査（デフォルトは公開のみ）
    DEBUG=0: デバッグ出力を抑制
    INIT_SAMPLE_DATA=0: サンプルデータの自動投入を抑制（CI用）
"""
import sys
import os
from pathlib import Path

# プロジェクトルートを取得
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 最初にinit_db()を呼ぶ（SQLiteの自動マイグレーションを実行）
from database import init_db, SessionLocal, Material
from utils.image_display import get_material_image_ref, safe_slug_from_material

# データベース初期化（マイグレーション実行）
init_db()


def is_git_lfs_pointer(file_path: Path) -> bool:
    """
    Git LFS pointerファイルかどうかを判定
    
    Args:
        file_path: ファイルパス
    
    Returns:
        True の場合、Git LFS pointer
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return False
        
        # ファイルサイズが小さい場合のみチェック（LFS pointerは通常小さい）
        if file_path.stat().st_size > 1024:  # 1KB以上は通常の画像ファイル
            return False
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
            # Git LFS pointerの特徴: "version https://git-lfs.github.com/spec/v1" で始まる
            if first_line.strip().startswith("version https://git-lfs.github.com/spec/v1"):
                return True
        
        return False
    except Exception:
        return False


def verify_assets(project_root: Path) -> tuple[bool, list[str]]:
    """
    画像アセットの検証（実際の解決ロジック基準）
    
    Args:
        project_root: プロジェクトルートのパス
    
    Returns:
        (success: bool, errors: list[str])
    """
    errors = []
    warnings = []
    missing_primary = []
    
    db = SessionLocal()
    
    try:
        # 環境変数で非公開材料も検査するか判定
        include_unpublished = os.getenv("VERIFY_INCLUDE_UNPUBLISHED", "0") == "1"
        
        # DBから materials を取得
        query = db.query(Material)
        if not include_unpublished:
            # デフォルトでは公開のみ（is_published=1）
            if hasattr(Material, 'is_published'):
                query = query.filter(Material.is_published == 1)
        
        materials = query.all()
        print(f"📦 検査対象材料数: {len(materials)} (include_unpublished={include_unpublished})")
        
        if len(materials) == 0:
            print("⚠️  材料が0件です")
            return True, []  # 空DBはエラーとしない
        
        for material in materials:
            material_name = getattr(material, 'name_official', None) or getattr(material, 'name', None) or "N/A"
            safe_slug = safe_slug_from_material(material)
            
            # primary画像の検査（必須）
            # project_rootを明示的に指定（Path.cwd()ではなく、引数で受け取ったパスを使用）
            primary_src, primary_debug = get_material_image_ref(material, "primary", project_root=project_root)
            chosen_branch = primary_debug.get("chosen_branch", "none")
            final_src_type = primary_debug.get("final_src_type")
            
            if chosen_branch == "none" or primary_src is None:
                # primaryは必須なのでFAIL
                error_msg = f"❌ {material_name} ({safe_slug}) primary: 画像が解決できません"
                missing_primary.append({
                    "name": material_name,
                    "safe_slug": safe_slug,
                    "debug": primary_debug
                })
                errors.append(error_msg)
                print(error_msg)
                print(f"   chosen_branch: {chosen_branch}")
                print(f"   candidate_paths: {primary_debug.get('candidate_paths', [])}")
                print(f"   failed_paths: {primary_debug.get('failed_paths', [])}")
                print(f"   candidate_urls: {primary_debug.get('candidate_urls', [])}")
            elif isinstance(primary_src, Path):
                # Pathの場合: exists & is_file & size>0 を必須
                if not primary_src.exists():
                    error_msg = f"❌ {material_name} ({safe_slug}) primary: パスが存在しません ({primary_src})"
                    missing_primary.append({
                        "name": material_name,
                        "safe_slug": safe_slug,
                        "debug": primary_debug
                    })
                    errors.append(error_msg)
                    print(error_msg)
                elif not primary_src.is_file():
                    error_msg = f"❌ {material_name} ({safe_slug}) primary: パスがファイルではありません ({primary_src})"
                    missing_primary.append({
                        "name": material_name,
                        "safe_slug": safe_slug,
                        "debug": primary_debug
                    })
                    errors.append(error_msg)
                    print(error_msg)
                elif primary_src.stat().st_size == 0:
                    error_msg = f"❌ {material_name} ({safe_slug}) primary: ファイルサイズが0です ({primary_src})"
                    missing_primary.append({
                        "name": material_name,
                        "safe_slug": safe_slug,
                        "debug": primary_debug
                    })
                    errors.append(error_msg)
                    print(error_msg)
                elif is_git_lfs_pointer(primary_src):
                    error_msg = f"❌ {material_name} ({safe_slug}) primary: Git LFS pointerファイルです ({primary_src})"
                    missing_primary.append({
                        "name": material_name,
                        "safe_slug": safe_slug,
                        "debug": primary_debug
                    })
                    errors.append(error_msg)
                    print(error_msg)
                else:
                    # OK
                    branch_icon = {
                        "db_url": "🌐",
                        "base_url": "🔗",
                        "local": "📁",
                        "legacy_jp": "📂",
                    }.get(chosen_branch, "❓")
                    print(f"✅ {material_name} ({safe_slug}) primary: {branch_icon} {chosen_branch} ({final_src_type})")
            elif isinstance(primary_src, str):
                # URLの場合: http(s) ならOK（HEADリクエストはしない）
                if primary_src.startswith(('http://', 'https://')):
                    branch_icon = {
                        "db_url": "🌐",
                        "base_url": "🔗",
                    }.get(chosen_branch, "❓")
                    print(f"✅ {material_name} ({safe_slug}) primary: {branch_icon} {chosen_branch} (URL: {primary_src[:50]}...)")
                else:
                    # data: URL などは想定外
                    error_msg = f"❌ {material_name} ({safe_slug}) primary: 想定外のURL形式です ({primary_src[:50]}...)"
                    missing_primary.append({
                        "name": material_name,
                        "safe_slug": safe_slug,
                        "debug": primary_debug
                    })
                    errors.append(error_msg)
                    print(error_msg)
            else:
                # 想定外の型
                error_msg = f"❌ {material_name} ({safe_slug}) primary: 想定外の型です ({type(primary_src)})"
                missing_primary.append({
                    "name": material_name,
                    "safe_slug": safe_slug,
                    "debug": primary_debug
                })
                errors.append(error_msg)
                print(error_msg)
            
            # space/product画像の検査（存在すればチェック、必須ではない）
            for kind in ["space", "product"]:
                use_src, use_debug = get_material_image_ref(material, kind, project_root=project_root)
                use_chosen_branch = use_debug.get("chosen_branch", "none")
                use_final_src_type = use_debug.get("final_src_type")
                
                if use_chosen_branch == "none" or use_src is None:
                    # 存在しない場合はWARNING（エラーにはしない）
                    warning_msg = f"⚠️  {material_name} ({safe_slug}) {kind}: 画像が見つかりません（任意）"
                    warnings.append(warning_msg)
                    if os.getenv("DEBUG", "0") == "1":
                        print(warning_msg)
                elif isinstance(use_src, Path):
                    # Pathの場合: exists & is_file & size>0 をチェック
                    if not use_src.exists() or not use_src.is_file() or use_src.stat().st_size == 0:
                        warning_msg = f"⚠️  {material_name} ({safe_slug}) {kind}: ファイルが無効です ({use_src})"
                        warnings.append(warning_msg)
                        if os.getenv("DEBUG", "0") == "1":
                            print(warning_msg)
                    elif is_git_lfs_pointer(use_src):
                        warning_msg = f"⚠️  {material_name} ({safe_slug}) {kind}: Git LFS pointerファイルです ({use_src})"
                        warnings.append(warning_msg)
                        if os.getenv("DEBUG", "0") == "1":
                            print(warning_msg)
                    else:
                        # OK
                        branch_icon = {
                            "db_url": "🌐",
                            "base_url": "🔗",
                            "local": "📁",
                            "legacy_jp": "📂",
                        }.get(use_chosen_branch, "❓")
                        if os.getenv("DEBUG", "0") == "1":
                            print(f"✅ {material_name} ({safe_slug}) {kind}: {branch_icon} {use_chosen_branch} ({use_final_src_type})")
                elif isinstance(use_src, str):
                    # URLの場合: http(s) ならOK
                    if use_src.startswith(('http://', 'https://')):
                        branch_icon = {
                            "db_url": "🌐",
                            "base_url": "🔗",
                        }.get(use_chosen_branch, "❓")
                        if os.getenv("DEBUG", "0") == "1":
                            print(f"✅ {material_name} ({safe_slug}) {kind}: {branch_icon} {use_chosen_branch} (URL)")
                    else:
                        warning_msg = f"⚠️  {material_name} ({safe_slug}) {kind}: 想定外のURL形式です"
                        warnings.append(warning_msg)
                        if os.getenv("DEBUG", "0") == "1":
                            print(warning_msg)
        
        # 結果サマリー
        print("\n" + "=" * 80)
        print("検証結果サマリー")
        print("=" * 80)
        print(f"✅ 検査対象: {len(materials)} 件")
        print(f"❌ primary画像が見つからない: {len(missing_primary)} 件")
        print(f"⚠️  space/product画像の警告: {len(warnings)} 件")
        
        if missing_primary:
            print("\n❌ primary画像が見つからない材料:")
            for item in missing_primary:
                print(f"  - {item['name']} (safe_slug: {item['safe_slug']})")
                if os.getenv("DEBUG", "0") == "1":
                    print(f"    debug: {item['debug']}")
            return False, errors
        else:
            print("\n✅ すべてのprimary画像が解決できました")
            if warnings and os.getenv("DEBUG", "0") == "1":
                print("\n⚠️  警告（space/product画像）:")
                for warning in warnings[:10]:  # 最初の10件のみ
                    print(f"  {warning}")
            return True, errors
    
    except Exception as e:
        error_msg = f"❌ 検証中にエラーが発生: {e}"
        errors.append(error_msg)
        print(error_msg)
        import traceback
        traceback.print_exc()
        return False, errors
    
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="画像アセットの検証（実際の解決ロジック基準）")
    parser.add_argument("--project-root", type=str, default=None, help="プロジェクトルートのパス")
    
    args = parser.parse_args()
    
    # プロジェクトルートの決定（スクリプトの親ディレクトリをデフォルトにする）
    if args.project_root:
        project_root_path = Path(args.project_root).resolve()
    else:
        # スクリプトの親ディレクトリ（プロジェクトルート）を使用
        project_root_path = Path(__file__).parent.parent.resolve()
    
    # 作業ディレクトリをプロジェクトルートに変更（相対パス解決のため）
    original_cwd = Path.cwd()
    try:
        import os
        os.chdir(project_root_path)
        
        success, errors = verify_assets(project_root_path)
    finally:
        os.chdir(original_cwd)
    
    if not success:
        print("\n" + "=" * 80)
        print("検証失敗:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    else:
        sys.exit(0)
