import logging
from typing import Final

from sqlalchemy import Engine, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..config import Configuration, SettingEntity

logger: Final = logging.getLogger(__name__)


def load(db: Engine) -> Configuration:
    """Load configuration from the database.

    Returns valid settings and discards any unknown keys with a warning.
    """
    with Session(db) as session:
        (config, ignored_values) = Configuration.from_values(((setting.name, setting.value)) for setting in session.scalars(select(SettingEntity)))

    if ignored_values:
        save(db, config)  # showed warnings, now save valid config
    return config


def save(db: Engine, configuration: Configuration):
    """Persist configuration to the database, replacing all stored settings."""
    settings = configuration.to_values()
    with Session(db) as session:
        stmt = insert(SettingEntity).values([{"name": k, "value": v} for k, v in settings.items()])
        stmt = stmt.on_conflict_do_update(index_elements=[SettingEntity.name], set_=dict(value_json=stmt.excluded.value_json))
        session.execute(stmt)
        session.execute(delete(SettingEntity).where(SettingEntity.name.not_in(settings.keys())))
        session.commit()
