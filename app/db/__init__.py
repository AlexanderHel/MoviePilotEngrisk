from sqlalchemy import create_engine, QueuePool
from sqlalchemy.orm import sessionmaker, Session, scoped_session

from app.core.config import settings

#  Database engine
Engine = create_engine(f"sqlite:///{settings.CONFIG_PATH}/user.db",
                       pool_pre_ping=True,
                       echo=False,
                       poolclass=QueuePool,
                       pool_size=1024,
                       pool_recycle=600,
                       pool_timeout=180,
                       max_overflow=0,
                       connect_args={"timeout": 60})
#  Conversation factory
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=Engine)

#  Multi-threaded globally used database sessions
ScopedSession = scoped_session(SessionFactory)


def get_db():
    """
    Getting a database session
    :return: Session
    """
    db = None
    try:
        db = SessionFactory()
        yield db
    finally:
        if db:
            db.close()


class DbOper:
    _db: Session = None

    def __init__(self, db: Session = None):
        if db:
            self._db = db
        else:
            self._db = ScopedSession()
