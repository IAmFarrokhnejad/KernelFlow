from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ==================== OUR CUSTOM IMPORTS ====================
from app.database.base import Base, engine   # ← engine imported here
from app.models.image import ImageRecord     # ensures model is loaded

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ==================== TARGET METADATA ====================
target_metadata = Base.metadata

# ==================== RUN MIGRATIONS OFFLINE ====================
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ==================== RUN MIGRATIONS ONLINE (FIXED) ====================
def run_migrations_online() -> None:
    """Use OUR pre-created engine instead of engine_from_config"""
    connectable = engine   # ← This is the key change I mentioned earlier

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()