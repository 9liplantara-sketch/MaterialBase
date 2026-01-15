"""add images kind column

Revision ID: 39259bb6188b
Revises: 1c69967a4374
Create Date: 2026-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39259bb6188b'
down_revision: Union[str, Sequence[str], None] = '1c69967a4374'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    images テーブルに kind 列を追加し、既存データを backfill する（Phase1: 最小限）
    
    方針:
    - kind 列を nullable で追加（Phase1: 段階的移行）
    - 既存行の kind を backfill:
      - image_type 列が存在する場合はそれを使用（後方互換）
      - image_type 列が存在しない場合は 'primary' を設定
    - 冪等性: "ADD COLUMN IF NOT EXISTS" を使用して、既に存在する場合はスキップ
    - 将来の一意制約（material_id, kind）を入れやすいように設計
    """
    from sqlalchemy import text, inspect
    
    # 接続を取得して列の存在確認
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # images テーブルの既存カラムを確認
    existing_columns = [col['name'] for col in inspector.get_columns('images')]
    
    # kind 列が存在しない場合のみ追加（冪等性）
    if 'kind' not in existing_columns:
        # Postgres の "ADD COLUMN IF NOT EXISTS" を使用（冪等性）
        if conn.dialect.name == 'postgresql':
            conn.execute(text("ALTER TABLE images ADD COLUMN IF NOT EXISTS kind VARCHAR(50)"))
        else:
            # SQLite など、IF NOT EXISTS をサポートしない場合は通常の add_column
            op.add_column('images', sa.Column('kind', sa.String(length=50), nullable=True))
        
        # image_type 列の存在確認
        has_image_type = 'image_type' in existing_columns
        
        # 既存データの backfill（image_type 列の有無を確認してから実行）
        if has_image_type:
            # image_type 列が存在する場合: image_type を使用、無ければ 'primary'
            conn.execute(text("""
                UPDATE images
                SET kind = CASE
                    WHEN image_type IS NOT NULL AND image_type != '' THEN image_type
                    ELSE 'primary'
                END
                WHERE kind IS NULL
            """))
        else:
            # image_type 列が存在しない場合: 全て 'primary' を設定
            conn.execute(text("""
                UPDATE images
                SET kind = 'primary'
                WHERE kind IS NULL
            """))
        
        conn.commit()
    else:
        # kind 列が既に存在する場合は backfill のみ実行（冪等性）
        has_image_type = 'image_type' in existing_columns
        
        if has_image_type:
            # image_type 列が存在する場合: 未設定の行のみ backfill
            conn.execute(text("""
                UPDATE images
                SET kind = CASE
                    WHEN image_type IS NOT NULL AND image_type != '' THEN image_type
                    ELSE 'primary'
                END
                WHERE kind IS NULL
            """))
        else:
            # image_type 列が存在しない場合: 未設定の行のみ 'primary' を設定
            conn.execute(text("""
                UPDATE images
                SET kind = 'primary'
                WHERE kind IS NULL
            """))
        
        conn.commit()
    
    # 既存データを backfill した後、NOT NULL 制約を追加（既存行は全て埋まっている）
    # ただし、Phase1では nullable のままにして、段階的に移行
    # 将来的に NOT NULL 制約を追加する場合は、以下のコメントを参考にする:
    # op.alter_column('images', 'kind', nullable=False, server_default='primary')
    
    # 一意制約（material_id, kind）を追加
    # 注意: Phase1では既存データに重複がある可能性があるため、まずはコメントアウト
    # 将来的に一意制約を追加する場合は、重複を解消してから実行:
    # op.create_unique_constraint('uq_image_material_kind', 'images', ['material_id', 'kind'])


def downgrade() -> None:
    """
    images テーブルから kind 列を削除（rollback用）
    
    注意: 一意制約を追加していた場合は、先に削除する必要がある
    """
    from sqlalchemy import inspect, text
    
    # 接続を取得して列の存在確認
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # images テーブルの既存カラムを確認
    existing_columns = [col['name'] for col in inspector.get_columns('images')]
    
    # 一意制約を削除（存在する場合）
    if 'kind' in existing_columns:
        try:
            op.drop_constraint('uq_image_material_kind', 'images', type_='unique')
        except Exception:
            pass  # 存在しない場合はスキップ
        
        # kind 列を削除（存在する場合のみ）
        op.drop_column('images', 'kind')
