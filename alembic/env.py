from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from database import Base
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 優先順位1: config.get_main_option("sqlalchemy.url") を使用（database.py から設定済みの場合）
    # これが「正」として扱う（DATABASE_URL必須を撤廃）
    db_url = config.get_main_option("sqlalchemy.url")
    
    # 優先順位2: DATABASE_URL 環境変数（フォールバック）
    if not db_url:
        db_url = os.getenv("DATABASE_URL")
    
    # 優先順位3: st.secrets から取得を試みる（フォールバック）
    if not db_url:
        try:
            import streamlit as st
            # connections.materialbase_db.url を優先
            try:
                db_url = st.secrets.get("connections", {}).get("materialbase_db", {}).get("url")
            except Exception:
                pass
            # それも無ければ DATABASE_URL を試す
            if not db_url:
                try:
                    db_url = st.secrets.get("DATABASE_URL")
                except Exception:
                    pass
        except Exception:
            pass  # streamlit が import できない場合は無視
    
    # 優先順位4: utils.settings を使用（最後のフォールバック）
    if not db_url:
        try:
            import utils.settings as settings
            db_url = settings.get_database_url()
        except Exception:
            pass
    
    # sqlalchemy.url が設定されていない場合のみエラー（DATABASE_URL必須を撤廃）
    if not db_url:
        raise RuntimeError(
            "Database URL is not set. "
            "Please ensure one of the following:\n"
            "1. database.py sets sqlalchemy.url via alembic_cfg.set_main_option() (recommended)\n"
            "2. Set DATABASE_URL environment variable\n"
            "3. Set in Streamlit Secrets (connections.materialbase_db.url or DATABASE_URL)\n"
            "4. Use utils.settings.get_database_url() (fallback)"
        )
    
    # config に設定（まだ設定されていない場合のみ）
    if not config.get_main_option("sqlalchemy.url"):
        config.set_main_option("sqlalchemy.url", db_url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
