"""
SQLiteのmaterial_submissionsテーブルを検証するスクリプト

使用方法:
    # デフォルト（./materials.db）
    python scripts/check_sqlite_submissions.py
    
    # 環境変数でDB pathを指定
    export DATABASE_PATH="./materials.db"
    python scripts/check_sqlite_submissions.py
"""
import os
import sys
import sqlite3
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_table_exists(db_path: str) -> bool:
    """テーブルが存在するかチェック"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='material_submissions'
    """)
    result = cursor.fetchone()
    
    conn.close()
    return result is not None


def get_table_info(db_path: str) -> list:
    """テーブルのカラム情報を取得"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(material_submissions)")
    columns = cursor.fetchall()
    
    conn.close()
    return columns


def get_indexes(db_path: str) -> list:
    """テーブルのインデックス情報を取得"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, sql FROM sqlite_master 
        WHERE type='index' AND tbl_name='material_submissions'
    """)
    indexes = cursor.fetchall()
    
    conn.close()
    return indexes


def test_insert_select(db_path: str, dry_run: bool = True) -> bool:
    """INSERT→SELECTで動作確認（dry_run=Trueの場合は実際にはINSERTしない）"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # テストデータ
        test_uuid = "00000000-0000-0000-0000-000000000000"
        test_payload = '{"name_official": "テスト材料", "category_main": "テストカテゴリ"}'
        
        if dry_run:
            print("  [DRY-RUN] INSERT文を実行せずに検証のみ行います")
            # INSERT文を構築して検証
            cursor.execute("""
                SELECT COUNT(*) FROM material_submissions 
                WHERE uuid = ?
            """, (test_uuid,))
            count_before = cursor.fetchone()[0]
            print(f"  [DRY-RUN] テストUUIDでの既存レコード数: {count_before}")
            print("  [DRY-RUN] INSERT文は実行されませんでした")
            result = True
        else:
            # 実際にINSERT
            cursor.execute("""
                INSERT INTO material_submissions 
                (uuid, status, payload_json, name_official, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (test_uuid, 'pending', test_payload, 'テスト材料'))
            
            # SELECTで確認
            cursor.execute("""
                SELECT id, uuid, status, name_official FROM material_submissions 
                WHERE uuid = ?
            """, (test_uuid,))
            row = cursor.fetchone()
            
            if row:
                print(f"  ✅ INSERT成功: id={row[0]}, uuid={row[1]}, status={row[2]}, name_official={row[3]}")
                
                # クリーンアップ（テストデータを削除）
                cursor.execute("DELETE FROM material_submissions WHERE uuid = ?", (test_uuid,))
                conn.commit()
                print("  ✅ テストデータを削除しました")
                result = True
            else:
                print("  ❌ INSERTは成功したが、SELECTで取得できませんでした")
                result = False
            
            conn.commit()
        
    except Exception as e:
        print(f"  ❌ INSERT→SELECTテストでエラー: {e}")
        conn.rollback()
        result = False
    finally:
        conn.close()
    
    return result


def main():
    """メイン処理"""
    print("=" * 80)
    print("SQLite material_submissions テーブル検証スクリプト")
    print("=" * 80)
    
    # DB pathを取得
    db_path = os.getenv("DATABASE_PATH", "./materials.db")
    db_path = Path(db_path).resolve()
    
    if not db_path.exists():
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return 1
    
    print(f"Database path: {db_path}")
    print()
    
    # テーブル存在確認
    print("=" * 80)
    print("1. テーブル存在確認")
    print("=" * 80)
    
    if check_table_exists(str(db_path)):
        print("✅ material_submissions テーブルが存在します")
    else:
        print("❌ material_submissions テーブルが存在しません")
        print("   → Alembic migrationを実行してください: python3 -m alembic upgrade head")
        return 1
    
    print()
    
    # カラム情報を取得
    print("=" * 80)
    print("2. カラム情報（PRAGMA table_info）")
    print("=" * 80)
    
    columns = get_table_info(str(db_path))
    if columns:
        print(f"  カラム数: {len(columns)}")
        print()
        print("  {:<20} {:<10} {:<10} {:<10} {:<10}".format(
            "カラム名", "型", "NOT NULL", "デフォルト", "PK"
        ))
        print("  " + "-" * 70)
        for col in columns:
            cid, name, col_type, not_null, default, pk = col
            not_null_str = "YES" if not_null else "NO"
            default_str = str(default) if default else "NULL"
            pk_str = "YES" if pk else "NO"
            print("  {:<20} {:<10} {:<10} {:<10} {:<10}".format(
                name, col_type, not_null_str, default_str, pk_str
            ))
    else:
        print("  ❌ カラム情報を取得できませんでした")
        return 1
    
    print()
    
    # インデックス情報を取得
    print("=" * 80)
    print("3. インデックス情報")
    print("=" * 80)
    
    indexes = get_indexes(str(db_path))
    if indexes:
        print(f"  インデックス数: {len(indexes)}")
        print()
        for idx_name, idx_sql in indexes:
            print(f"  {idx_name}:")
            if idx_sql:
                print(f"    {idx_sql}")
            else:
                print(f"    (自動生成インデックス)")
    else:
        print("  ⚠️  インデックスが見つかりませんでした")
    
    print()
    
    # INSERT→SELECTテスト（dry-run）
    print("=" * 80)
    print("4. INSERT→SELECT動作確認（DRY-RUN）")
    print("=" * 80)
    
    if test_insert_select(str(db_path), dry_run=True):
        print("  ✅ DRY-RUN検証完了")
    else:
        print("  ❌ DRY-RUN検証でエラーが発生しました")
        return 1
    
    print()
    
    # 実際のデータ件数
    print("=" * 80)
    print("5. 既存データ件数")
    print("=" * 80)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM material_submissions")
        total_count = cursor.fetchone()[0]
        print(f"  総件数: {total_count}")
        
        if total_count > 0:
            cursor.execute("SELECT COUNT(*) FROM material_submissions WHERE status = 'pending'")
            pending_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM material_submissions WHERE status = 'approved'")
            approved_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM material_submissions WHERE status = 'rejected'")
            rejected_count = cursor.fetchone()[0]
            
            print(f"  - pending: {pending_count}")
            print(f"  - approved: {approved_count}")
            print(f"  - rejected: {rejected_count}")
            
            # 最新5件を表示
            cursor.execute("""
                SELECT id, uuid, status, name_official, created_at 
                FROM material_submissions 
                ORDER BY id DESC 
                LIMIT 5
            """)
            rows = cursor.fetchall()
            if rows:
                print()
                print("  最新5件:")
                print("  {:<5} {:<40} {:<10} {:<30} {:<20}".format(
                    "ID", "UUID", "Status", "Name Official", "Created At"
                ))
                print("  " + "-" * 110)
                for row in rows:
                    print("  {:<5} {:<40} {:<10} {:<30} {:<20}".format(
                        str(row[0])[:5], str(row[1])[:40], str(row[2])[:10], 
                        str(row[3] or 'N/A')[:30], str(row[4] or 'N/A')[:20]
                    ))
    except Exception as e:
        print(f"  ❌ データ件数の取得でエラー: {e}")
        return 1
    finally:
        conn.close()
    
    print()
    print("=" * 80)
    print("検証完了")
    print("=" * 80)
    print()
    print("💡 実際にINSERT→SELECTテストを実行する場合は、dry_run=Falseに変更してください")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
