from sqlalchemy import Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.db.models import Base


class Subscribe(Base):
    """
    Subscription form
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Caption
    name = Column(String, nullable=False, index=True)
    #  Particular year
    year = Column(String)
    #  Typology
    type = Column(String)
    #  Search keywords
    keyword = Column(String)
    tmdbid = Column(Integer, index=True)
    imdbid = Column(String)
    tvdbid = Column(Integer)
    doubanid = Column(String, index=True)
    #  Quarter
    season = Column(Integer)
    #  Playbill
    poster = Column(String)
    #  Background image
    backdrop = Column(String)
    #  Score (of student's work)
    vote = Column(Integer)
    #  Synopsis
    description = Column(String)
    #  Filter rules
    filter = Column(String)
    #  Embody
    include = Column(String)
    #  Rule out
    exclude = Column(String)
    #  Total episodes
    total_episode = Column(Integer)
    #  Number of episodes
    start_episode = Column(Integer)
    #  Missing episodes
    lack_episode = Column(Integer)
    #  Additional information
    note = Column(String)
    #  State of affairs：N- Newly built， R- Subscription
    state = Column(String, nullable=False, index=True, default='N')
    #  Last updated
    last_update = Column(String)
    #  Creation time
    date = Column(String)
    #  Subscriber
    username = Column(String)
    #  Subscribe to the site
    sites = Column(String)
    #  Whether or not to wash the plate
    best_version = Column(Integer, default=0)
    #  Current priority
    current_priority = Column(Integer)

    @staticmethod
    def exists(db: Session, tmdbid: int, season: int = None):
        if season:
            return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid,
                                              Subscribe.season == season).first()
        return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid).first()

    @staticmethod
    def get_by_state(db: Session, state: str):
        return db.query(Subscribe).filter(Subscribe.state == state).all()

    @staticmethod
    def get_by_tmdbid(db: Session, tmdbid: int, season: int = None):
        if season:
            return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid,
                                              Subscribe.season == season).all()
        return db.query(Subscribe).filter(Subscribe.tmdbid == tmdbid).all()

    @staticmethod
    def get_by_title(db: Session, title: str):
        return db.query(Subscribe).filter(Subscribe.name == title).first()

    @staticmethod
    def get_by_doubanid(db: Session, doubanid: str):
        return db.query(Subscribe).filter(Subscribe.doubanid == doubanid).first()

    def delete_by_tmdbid(self, db: Session, tmdbid: int, season: int):
        subscrbies = self.get_by_tmdbid(db, tmdbid, season)
        for subscrbie in subscrbies:
            subscrbie.delete(db, subscrbie.id)
        return True

    def delete_by_doubanid(self, db: Session, doubanid: str):
        subscribe = self.get_by_doubanid(db, doubanid)
        if subscribe:
            subscribe.delete(db, subscribe.id)
        return True
