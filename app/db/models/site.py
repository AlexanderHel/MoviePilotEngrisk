from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.db.models import Base


class Site(Base):
    """
    Site list
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Site name
    name = Column(String, nullable=False)
    #  Domain nameKey
    domain = Column(String, index=True)
    #  Site address
    url = Column(String, nullable=False)
    #  Site prioritization
    pri = Column(Integer, default=1)
    # RSS Address， Not yet activated
    rss = Column(String)
    # Cookie
    cookie = Column(String)
    # User-Agent
    ua = Column(String)
    #  Whether to use a proxy 0- Clogged，1- Be
    proxy = Column(Integer)
    #  Filter rules
    filter = Column(String)
    #  Whether to render
    render = Column(Integer)
    #  Whether or not the site is public
    public = Column(Integer)
    #  Additional information
    note = Column(String)
    #  Flow control unit cycle
    limit_interval = Column(Integer, default=0)
    #  Number of flow control sessions
    limit_count = Column(Integer, default=0)
    #  Flow control interval
    limit_seconds = Column(Integer, default=0)
    #  Enable or disable
    is_active = Column(Boolean(), default=True)
    #  Creation time
    lst_mod_date = Column(String, default=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @staticmethod
    def get_by_domain(db: Session, domain: str):
        return db.query(Site).filter(Site.domain == domain).first()

    @staticmethod
    def get_actives(db: Session):
        return db.query(Site).filter(Site.is_active == 1).all()

    @staticmethod
    def list_order_by_pri(db: Session):
        return db.query(Site).order_by(Site.pri).all()

    @staticmethod
    def reset(db: Session):
        db.query(Site).delete()
        Base.commit(db)
