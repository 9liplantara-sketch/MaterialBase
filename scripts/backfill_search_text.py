"""
既存材料のsearch_textをバックフィルするスクリプト（純CLI版）

使用方法:
    export DATABASE_URL="postgresql://user:pass@host:port/dbname"
    python scripts/backfill_search_text.py
    
    # 既にsearch_textが入っているものも上書きする場合
    python scripts/backfill_search_text.py --force
"""
import os
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# psycopg2をインポート（Postgres用）
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("[ERROR] psycopg2 is required. Install with: pip install psycopg2-binary")
    sys.exit(1)

# utils.searchをインポート（streamlit依存なし）
from utils.search import generate_search_text


def parse_database_url_for_display(db_url: str) -> str:
    """
    DATABASE_URLをパースしてログ表示用の文字列を生成（接続には使わない）
    
    Args:
        db_url: DATABASE_URL文字列
    
    Returns:
        ログ表示用文字列（hostはマスク、パスワードは非表示）
    """
    parsed = urlparse(db_url)
    host_display = parsed.hostname if parsed.hostname else "unknown"
    # hostをマスク（最初の数文字だけ表示）
    if len(host_display) > 10:
        host_display = host_display[:6] + "..." + host_display[-4:]
    port = parsed.port or 5432
    database = parsed.path.lstrip('/')
    return f"{host_display}:{port}/{database}"


def prepare_connection_string(db_url: str) -> str:
    """
    DATABASE_URLをpsycopg2用の接続文字列に変換
    
    Args:
        db_url: DATABASE_URL文字列（postgresql+psycopg:// または postgresql://）
    
    Returns:
        psycopg2用の接続文字列（postgresql://）
    """
    # postgresql+psycopg:// を postgresql:// に置換
    if db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return db_url


def get_material_by_id(conn, material_id: int) -> dict:
    """
    材料をIDで取得（辞書形式）
    
    Args:
        conn: psycopg2接続
        material_id: 材料ID
    
    Returns:
        材料データの辞書（Noneの場合は存在しない）
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM materials
            WHERE id = %s AND is_deleted = 0
        """, (material_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def backfill_search_text(force: bool = False):
    """既存材料のsearch_textをバックフィル（純CLI版）"""
    
    # DATABASE_URLを必須チェック
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL environment variable is required")
        print("  Example: export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        sys.exit(1)
    
    # DATABASE_URLをログ表示用にパース（接続には使わない）
    try:
        display_str = parse_database_url_for_display(db_url)
        print(f"[INFO] Connecting to: {display_str}")
    except Exception as e:
        print(f"[WARNING] Failed to parse DATABASE_URL for display: {e}")
        print("[INFO] Proceeding with connection...")
    
    # 接続文字列を準備（postgresql+psycopg:// を postgresql:// に置換）
    conn_str = prepare_connection_string(db_url)
    
    # データベース接続（DATABASE_URLをそのまま使用、正しくパース）
    try:
        # psycopg2.connect()はURL文字列を直接受け取れないので、パースして渡す
        # ただし、urlparse()で正しくパースすればhostは壊れない
        parsed = urlparse(conn_str)
        
        # パース結果を確認（デバッグ用）
        if not parsed.hostname:
            print(f"[ERROR] Failed to parse hostname from DATABASE_URL")
            print(f"[ERROR] Parsed hostname: {parsed.hostname}")
            print(f"[ERROR] Full URL (masked): {display_str}")
            sys.exit(1)
        
        conn = psycopg2.connect(
            host=parsed.hostname,  # 正しくパースされたhostnameを使用
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password
        )
        conn.autocommit = False  # 手動コミット
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        print(f"[ERROR] Connection string (masked): {display_str}")
        sys.exit(1)
    
    try:
        # 起動時にcount(*)を確認（Neonと一致するか確認用）
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM materials WHERE is_deleted = 0")
            total_count = cur.fetchone()[0]
            print(f"[INFO] Total active materials (is_deleted=0): {total_count}")
            if total_count != 11:
                print(f"[WARNING] Expected 11 materials, but found {total_count}")
            print("-" * 80)
        
        # 対象材料を取得
        if force:
            # --forceの場合はsearch_textがNULL/空のものも含めて全件更新
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name_official, name, category_main, category,
                           name_aliases, material_forms, origin_type, origin_detail,
                           color_tags, transparency, hardness_qualitative, weight_qualitative,
                           water_resistance, heat_resistance_range, weather_resistance,
                           processing_methods, processing_other, equipment_level,
                           prototyping_difficulty, use_categories, use_other,
                           safety_tags, safety_other, restrictions, description,
                           development_background_short
                    FROM materials
                    WHERE is_deleted = 0
                    ORDER BY id
                """)
                materials = [dict(row) for row in cur.fetchall()]
        else:
            # 通常はsearch_textがNULL/空のものだけ
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name_official, name, category_main, category,
                           name_aliases, material_forms, origin_type, origin_detail,
                           color_tags, transparency, hardness_qualitative, weight_qualitative,
                           water_resistance, heat_resistance_range, weather_resistance,
                           processing_methods, processing_other, equipment_level,
                           prototyping_difficulty, use_categories, use_other,
                           safety_tags, safety_other, restrictions, description,
                           development_background_short
                    FROM materials
                    WHERE is_deleted = 0
                      AND (search_text IS NULL OR search_text = '')
                    ORDER BY id
                """)
                materials = [dict(row) for row in cur.fetchall()]
        
        total = len(materials)
        updated = 0
        skipped = 0
        errors = 0
        
        print(f"[INFO] Target materials: {total}")
        if force:
            print("[INFO] Force mode: updating all materials (including those with existing search_text)")
        else:
            print("[INFO] Normal mode: updating only materials with NULL/empty search_text")
        print("-" * 80)
        
        # Materialオブジェクトの簡易クラス（generate_search_text用）
        class MaterialProxy:
            def __init__(self, d):
                for key, value in d.items():
                    setattr(self, key, value)
        
        # 各材料を処理
        for idx, mat_dict in enumerate(materials):
            try:
                material = MaterialProxy(mat_dict)
                search_text = generate_search_text(material)
                
                # SQLでUPDATE
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE materials
                        SET search_text = %s
                        WHERE id = %s
                    """, (search_text, material.id))
                
                updated += 1
                
                # 100件ごとにコミット
                if updated % 100 == 0:
                    conn.commit()
                    print(f"[INFO] Updated {updated}/{total} materials...")
            
            except Exception as e:
                errors += 1
                material_name = mat_dict.get('name_official') or mat_dict.get('name') or 'N/A'
                print(f"[ERROR] Failed to update material {mat_dict['id']} ({material_name}): {e}")
                conn.rollback()  # エラー時はロールバック
        
        # 最終コミット
        conn.commit()
        
        print("-" * 80)
        print(f"[INFO] Completed:")
        print(f"  Total active materials: {total_count}")
        print(f"  Target materials: {total}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")
        
        # サンプルとして1件（id=215）のsearch_textを表示
        sample_id = 215
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name_official, LEFT(search_text, 100) as search_text_preview
                FROM materials
                WHERE id = %s
            """, (sample_id,))
            row = cur.fetchone()
            if row:
                print("-" * 80)
                print(f"[INFO] Sample (id={sample_id}):")
                print(f"  Name: {row[1]}")
                print(f"  search_text (first 100 chars): {row[2]}")
            else:
                print(f"[INFO] Sample material (id={sample_id}) not found")
        
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill search_text for materials")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update even if search_text already exists"
    )
    args = parser.parse_args()
    
    backfill_search_text(force=args.force)
