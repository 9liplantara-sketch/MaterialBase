"""add search_text column for full-text search

Revision ID: add_search_text
Revises: 39259bb6188b
Create Date: 2026-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'add_search_text'
down_revision: Union[str, Sequence[str], None] = '39259bb6188b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    materials テーブルに search_text 列を追加し、全文検索インデックスを作成
    
    方針:
    - search_text 列を Text 型で追加（nullable=True、後でバックフィル）
    - Postgres の全文検索用 GIN インデックスを作成
    - 既存データは後でバックフィルスクリプトで更新
    """
    from sqlalchemy import inspect
    
    # 接続を取得して列の存在確認
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # materials テーブルの既存カラムを確認
    existing_columns = [col['name'] for col in inspector.get_columns('materials')]
    
    # search_text 列が存在しない場合のみ追加（冪等性）
    if 'search_text' not in existing_columns:
        # Postgres の "ADD COLUMN IF NOT EXISTS" を使用（冪等性）
        if conn.dialect.name == 'postgresql':
            conn.execute(text("ALTER TABLE materials ADD COLUMN IF NOT EXISTS search_text TEXT"))
        else:
            # SQLite など、IF NOT EXISTS をサポートしない場合は通常の add_column
            op.add_column('materials', sa.Column('search_text', sa.Text(), nullable=True))
        
        # Postgres の場合、全文検索用の GIN インデックスを作成
        if conn.dialect.name == 'postgresql':
            # to_tsvector を使った GIN インデックスを作成
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_materials_search_text_gin 
                ON materials USING gin(to_tsvector('japanese', COALESCE(search_text, '')))
            """))
        
        conn.commit()


def downgrade() -> None:
    """
    materials テーブルから search_text 列とインデックスを削除（rollback用）
    """
    from sqlalchemy import inspect
    
    # 接続を取得して列の存在確認
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # materials テーブルの既存カラムを確認
    existing_columns = [col['name'] for col in inspector.get_columns('materials')]
    
    # search_text 列が存在する場合のみ削除
    if 'search_text' in existing_columns:
        # Postgres の場合、インデックスを先に削除
        if conn.dialect.name == 'postgresql':
            try:
                conn.execute(text("DROP INDEX IF EXISTS idx_materials_search_text_gin"))
            except Exception:
                pass  # 存在しない場合はスキップ
        
        # search_text 列を削除
        op.drop_column('materials', 'search_text')
