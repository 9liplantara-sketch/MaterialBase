"""add_material_submissions_table

Revision ID: 0e6fb273f251
Revises: allow_null_heat_resistance_range
Create Date: 2026-01-27 16:27:59.106861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '0e6fb273f251'
down_revision: Union[str, Sequence[str], None] = 'allow_null_heat_resistance_range'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(conn, table_name: str) -> bool:
    """テーブルが存在するかチェック（SQLite/PostgreSQL両対応）"""
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(conn, table_name: str, column_name: str) -> bool:
    """カラムが存在するかチェック（SQLite/PostgreSQL両対応）"""
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """
    material_submissionsテーブルを作成（存在しない場合のみ）
    
    既存のinit_schema.pyに含まれているが、適用されていないDBに対して
    安全にテーブルを作成する。
    """
    conn = op.get_bind()
    
    # テーブルが存在しない場合のみ作成
    if not table_exists(conn, 'material_submissions'):
        op.create_table('material_submissions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('uuid', sa.String(length=36), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('name_official', sa.String(length=255), nullable=True),
            sa.Column('payload_json', sa.Text(), nullable=False),
            sa.Column('editor_note', sa.Text(), nullable=True),
            sa.Column('reject_reason', sa.Text(), nullable=True),
            sa.Column('submitted_by', sa.String(length=255), nullable=True),
            sa.Column('approved_material_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['approved_material_id'], ['materials.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # インデックスを作成
        op.create_index(op.f('ix_material_submissions_id'), 'material_submissions', ['id'], unique=False)
        op.create_index(op.f('ix_material_submissions_uuid'), 'material_submissions', ['uuid'], unique=True)
        op.create_index('ix_material_submissions_status', 'material_submissions', ['status'], unique=False)
        op.create_index('ix_material_submissions_created_at', 'material_submissions', ['created_at'], unique=False)
        op.create_index('ix_material_submissions_name_official', 'material_submissions', ['name_official'], unique=False)
        op.create_index('ix_material_submissions_approved_material_id', 'material_submissions', ['approved_material_id'], unique=False)
    else:
        # テーブルが存在する場合、name_officialカラムが存在しない場合は追加
        if not column_exists(conn, 'material_submissions', 'name_official'):
            op.add_column('material_submissions', sa.Column('name_official', sa.String(length=255), nullable=True))
            # name_officialにインデックスを追加
            op.create_index('ix_material_submissions_name_official', 'material_submissions', ['name_official'], unique=False)
        
        # その他のインデックスが存在しない場合は追加（既存テーブルへの後付け）
        inspector = inspect(conn)
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('material_submissions')]
        
        if 'ix_material_submissions_status' not in existing_indexes:
            op.create_index('ix_material_submissions_status', 'material_submissions', ['status'], unique=False)
        if 'ix_material_submissions_created_at' not in existing_indexes:
            op.create_index('ix_material_submissions_created_at', 'material_submissions', ['created_at'], unique=False)
        if 'ix_material_submissions_approved_material_id' not in existing_indexes:
            op.create_index('ix_material_submissions_approved_material_id', 'material_submissions', ['approved_material_id'], unique=False)


def downgrade() -> None:
    """
    material_submissionsテーブルを削除（downgrade時のみ）
    
    注意: 既存データがある場合は削除されるため、downgradeは慎重に行うこと
    """
    conn = op.get_bind()
    
    if table_exists(conn, 'material_submissions'):
        # インデックスを削除
        inspector = inspect(conn)
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('material_submissions')]
        
        for index_name in existing_indexes:
            if index_name.startswith('ix_material_submissions_'):
                try:
                    op.drop_index(index_name, table_name='material_submissions')
                except Exception:
                    pass  # インデックスが存在しない場合は無視
        
        # テーブルを削除
        op.drop_table('material_submissions')
