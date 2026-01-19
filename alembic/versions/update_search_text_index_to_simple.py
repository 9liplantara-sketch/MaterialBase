"""update search_text index to use 'simple' instead of 'japanese'

Revision ID: update_search_index_simple
Revises: add_pgvector_embeddings
Create Date: 2026-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'update_search_index_simple'
down_revision: Union[str, Sequence[str], None] = 'add_pgvector_embeddings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    search_textのGINインデックスを'simple'に変更
    
    方針:
    - 既存の'japanese'インデックスを削除
    - 'simple'インデックスを作成
    """
    from sqlalchemy import inspect
    
    # 接続を取得
    conn = op.get_bind()
    
    # Postgresの場合のみ
    if conn.dialect.name == 'postgresql':
        # 既存の'japanese'インデックスを削除
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_materials_search_text_gin"))
        except Exception:
            pass  # 存在しない場合はスキップ
        
        # 'simple'インデックスを作成
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_materials_search_text_gin 
            ON materials USING gin(to_tsvector('simple', COALESCE(search_text, '')))
        """))
        
        conn.commit()


def downgrade() -> None:
    """
    search_textのGINインデックスを'japanese'に戻す（rollback用）
    """
    from sqlalchemy import inspect
    
    # 接続を取得
    conn = op.get_bind()
    
    # Postgresの場合のみ
    if conn.dialect.name == 'postgresql':
        # 既存の'simple'インデックスを削除
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_materials_search_text_gin"))
        except Exception:
            pass
        
        # 'japanese'インデックスを作成
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_materials_search_text_gin 
            ON materials USING gin(to_tsvector('japanese', COALESCE(search_text, '')))
        """))
        
        conn.commit()
