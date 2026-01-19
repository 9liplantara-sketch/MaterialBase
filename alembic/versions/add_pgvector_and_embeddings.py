"""add pgvector extension and material_embeddings table

Revision ID: add_pgvector_embeddings
Revises: add_search_text
Create Date: 2026-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'add_pgvector_embeddings'
down_revision: Union[str, Sequence[str], None] = 'add_search_text'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    pgvector拡張を有効化し、material_embeddingsテーブルを作成
    
    方針:
    - pgvector拡張を有効化（CREATE EXTENSION IF NOT EXISTS vector）
    - material_embeddingsテーブルを作成
    - material_idをPK/FKとして設定
    - embedding vector(1536) を追加（OpenAIのtext-embedding-3-smallの次元数）
    - content_hashで差分更新を可能にする
    """
    from sqlalchemy import inspect
    
    # 接続を取得
    conn = op.get_bind()
    
    # Postgresの場合のみpgvector拡張を有効化
    if conn.dialect.name == 'postgresql':
        # pgvector拡張を有効化（既に存在する場合はスキップ）
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # material_embeddingsテーブルが存在しない場合のみ作成
        inspector = inspect(conn)
        existing_tables = inspector.get_table_names()
        
        if 'material_embeddings' not in existing_tables:
            # material_embeddingsテーブルを作成（生のSQLでvector型を使用）
            conn.execute(text("""
                CREATE TABLE material_embeddings (
                    material_id INTEGER PRIMARY KEY,
                    content_hash VARCHAR(64) NOT NULL,
                    embedding vector(1536),
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE
                )
            """))
            
            # インデックスを作成（コサイン類似度検索用）
            # データが少ないうちはivfflatインデックスは作成しない（後で必要に応じて作成）
            # 必要に応じて以下のコメントを解除して作成:
            # conn.execute(text("""
            #     CREATE INDEX IF NOT EXISTS idx_material_embeddings_embedding_cosine 
            #     ON material_embeddings 
            #     USING ivfflat (embedding vector_cosine_ops)
            #     WITH (lists = 100)
            # """))
            
            conn.commit()
    else:
        # SQLiteなど、Postgres以外の場合はARRAY型で作成（ベクトル検索は使えない）
        inspector = inspect(conn)
        existing_tables = inspector.get_table_names()
        
        if 'material_embeddings' not in existing_tables:
            op.create_table(
                'material_embeddings',
                sa.Column('material_id', sa.Integer(), nullable=False),
                sa.Column('content_hash', sa.String(64), nullable=False),
                sa.Column('embedding', sa.Text(), nullable=True),  # JSON文字列として保存
                sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
                sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='CASCADE'),
                sa.PrimaryKeyConstraint('material_id')
            )


def downgrade() -> None:
    """
    material_embeddingsテーブルとpgvector拡張を削除（rollback用）
    """
    from sqlalchemy import inspect
    
    # 接続を取得
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # material_embeddingsテーブルが存在する場合のみ削除
    existing_tables = inspector.get_table_names()
    
    if 'material_embeddings' in existing_tables:
        # インデックスを削除
        if conn.dialect.name == 'postgresql':
            try:
                conn.execute(text("DROP INDEX IF EXISTS idx_material_embeddings_embedding_cosine"))
            except Exception:
                pass
        
        # テーブルを削除
        op.drop_table('material_embeddings')
        
        # pgvector拡張は削除しない（他の用途で使われている可能性があるため）
