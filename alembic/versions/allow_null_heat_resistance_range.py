"""allow null heat_resistance_range

Revision ID: allow_null_heat_resistance_range
Revises: update_search_index_simple
Create Date: 2026-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'allow_null_heat_resistance_range'
down_revision: Union[str, Sequence[str], None] = 'update_search_index_simple'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    heat_resistance_rangeカラムのNOT NULL制約を解除
    一括登録で最小テンプレートでも投入できるようにする
    """
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        # PostgreSQLの場合、NOT NULL制約を解除
        conn.execute(text("ALTER TABLE materials ALTER COLUMN heat_resistance_range DROP NOT NULL"))
        conn.commit()
    else:
        # SQLiteなどの場合は、カラムを再作成する必要がある（通常はPostgreSQLのみ）
        # ここではPostgreSQLのみを想定
        pass


def downgrade() -> None:
    """
    heat_resistance_rangeカラムのNOT NULL制約を復元
    """
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        # 既存のNULL値をデフォルト値に更新（例: '' または '不明'）
        # 注意: 既存のNULL値がある場合は、downgrade前に処理が必要
        conn.execute(text("UPDATE materials SET heat_resistance_range = '' WHERE heat_resistance_range IS NULL"))
        # NOT NULL制約を追加
        conn.execute(text("ALTER TABLE materials ALTER COLUMN heat_resistance_range SET NOT NULL"))
        conn.commit()
    else:
        # SQLiteなどの場合は、カラムを再作成する必要がある（通常はPostgreSQLのみ）
        pass
