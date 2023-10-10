import importlib
from pathlib import Path

from alembic.command import upgrade
from alembic.config import Config

from app.core.config import settings
from app.core.security import get_password_hash
from app.db import Engine, SessionFactory
from app.db.models import Base
from app.db.models.user import User
from app.log import logger


def init_db():
    """
    Initializing the database
    """
    #  Import module， Avoid building missing tables
    for module in Path(__file__).with_name("models").glob("*.py"):
        importlib.import_module(f"app.db.models.{module.stem}")
    #  Full table construction
    Base.metadata.create_all(bind=Engine)
    #  Initialize super administrator
    db = SessionFactory()
    user = User.get_by_name(db=db, name=settings.SUPERUSER)
    if not user:
        user = User(
            name=settings.SUPERUSER,
            hashed_password=get_password_hash(settings.SUPERUSER_PASSWORD),
            is_superuser=True,
        )
        user.create(db)
    db.close()


def update_db():
    """
    Updating the database
    """
    db_location = settings.CONFIG_PATH / 'user.db'
    script_location = settings.ROOT_PATH / 'database'
    try:
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', str(script_location))
        alembic_cfg.set_main_option('sqlalchemy.url', f"sqlite:///{db_location}")
        upgrade(alembic_cfg, 'head')
    except Exception as e:
        logger.error(f' Database update failure：{e}')
