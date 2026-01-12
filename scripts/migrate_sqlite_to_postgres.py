"""
SQLiteからPostgresへデータを移行するスクリプト
既存のSQLite DBを読み込み、PostgresにINSERTします。
"""
import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from database import Base, Material, Property, ReferenceURL, UseExample, MaterialSubmission
from utils.settings import get_database_url, get_db_dialect
import json


def migrate_table(source_engine, target_engine, table_name, table_class, order_by=None):
    """
    テーブルを移行（FK順序を考慮）
    
    Args:
        source_engine: ソース（SQLite）エンジン
        target_engine: ターゲット（Postgres）エンジン
        table_name: テーブル名
        table_class: SQLAlchemyモデルクラス
        order_by: ソート順（ORDER BY句）
    """
    print(f"\n[移行] {table_name}...")
    
    source_session = sessionmaker(bind=source_engine)()
    target_session = sessionmaker(bind=target_engine)()
    
    try:
        # ソースから全レコードを取得
        query = source_session.query(table_class)
        if order_by:
            query = query.order_by(order_by)
        records = query.all()
        
        if not records:
            print(f"  → レコードなし（スキップ）")
            return 0
        
        print(f"  → {len(records)}件のレコードを取得")
        
        # ターゲットにINSERT（既存チェックあり）
        inserted = 0
        skipped = 0
        
        for record in records:
            try:
                # 既存チェック（主キーで）
                existing = target_session.query(table_class).filter_by(id=record.id).first()
                if existing:
                    skipped += 1
                    continue
                
                # 新しいレコードを作成（属性をコピー）
                new_record = table_class()
                for column in table_class.__table__.columns:
                    if column.name != "id" or record.id is not None:
                        setattr(new_record, column.name, getattr(record, column.name, None))
                
                target_session.add(new_record)
                inserted += 1
                
            except Exception as e:
                print(f"  ⚠ レコードID {getattr(record, 'id', '?')} の移行に失敗: {e}")
                target_session.rollback()
                continue
        
        target_session.commit()
        print(f"  ✓ 移行完了: {inserted}件追加, {skipped}件スキップ")
        return inserted
        
    except Exception as e:
        print(f"  ✗ 移行失敗: {e}")
        target_session.rollback()
        import traceback
        traceback.print_exc()
        return 0
    finally:
        source_session.close()
        target_session.close()


def main():
    """メイン処理"""
    print("=" * 60)
    print("SQLite → Postgres データ移行スクリプト")
    print("=" * 60)
    
    # ソース（SQLite）
    sqlite_path = Path("materials.db")
    if not sqlite_path.exists():
        print(f"\n✗ SQLite DBが見つかりません: {sqlite_path}")
        print("  移行するデータが存在しません。")
        return
    
    sqlite_url = f"sqlite:///./{sqlite_path}"
    print(f"\n[ソース] SQLite: {sqlite_url}")
    
    # ターゲット（Postgres）
    try:
        postgres_url = get_database_url()
        if get_db_dialect(postgres_url) != "postgresql":
            raise ValueError(f"Postgres URLが必要です: {postgres_url}")
    except Exception as e:
        print(f"\n✗ Postgres URLの取得に失敗: {e}")
        print("  DATABASE_URL環境変数またはStreamlit Secretsを設定してください。")
        return
    
    print(f"[ターゲット] Postgres: {get_db_dialect(postgres_url)}")
    
    # 確認
    print("\n移行を実行しますか？ (yes/no): ", end="")
    if input().lower() != "yes":
        print("キャンセルしました。")
        return
    
    # エンジン作成
    sqlite_engine = create_engine(sqlite_url)
    postgres_engine = create_engine(postgres_url, pool_pre_ping=True)
    
    # ターゲットのテーブル作成（Alembic推奨だが、念のため）
    print("\n[準備] ターゲットDBのテーブルを作成...")
    try:
        Base.metadata.create_all(bind=postgres_engine)
        print("  ✓ テーブル作成完了")
    except Exception as e:
        print(f"  ⚠ テーブル作成エラー（既に存在する可能性）: {e}")
    
    # 移行（FK順序に注意）
    total = 0
    
    # 1. materials（FK無し）
    total += migrate_table(sqlite_engine, postgres_engine, "materials", Material, order_by=Material.id)
    
    # 2. properties（material_id FK）
    total += migrate_table(sqlite_engine, postgres_engine, "properties", Property, order_by=Property.id)
    
    # 3. reference_urls（material_id FK）
    total += migrate_table(sqlite_engine, postgres_engine, "reference_urls", ReferenceURL, order_by=ReferenceURL.id)
    
    # 4. use_examples（material_id FK）
    total += migrate_table(sqlite_engine, postgres_engine, "use_examples", UseExample, order_by=UseExample.id)
    
    # 5. material_submissions（FK無し）
    try:
        total += migrate_table(sqlite_engine, postgres_engine, "material_submissions", MaterialSubmission, order_by=MaterialSubmission.id)
    except Exception as e:
        print(f"  ⚠ material_submissions移行スキップ（テーブルが存在しない可能性）: {e}")
    
    print("\n" + "=" * 60)
    print(f"移行完了: 合計 {total}件のレコードを移行しました。")
    print("=" * 60)


if __name__ == "__main__":
    main()
