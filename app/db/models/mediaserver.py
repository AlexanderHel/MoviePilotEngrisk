from datetime import datetime

from sqlalchemy import Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.db.models import Base


class MediaServerItem(Base):
    """
    Site list
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Server type
    server = Column(String)
    #  Media libraryID
    library = Column(String)
    # ID
    item_id = Column(String, index=True)
    #  Typology
    item_type = Column(String)
    #  Caption
    title = Column(String, index=True)
    #  Original title
    original_title = Column(String)
    #  Particular year
    year = Column(String)
    # TMDBID
    tmdbid = Column(Integer, index=True)
    # IMDBID
    imdbid = Column(String, index=True)
    # TVDBID
    tvdbid = Column(String, index=True)
    #  Trails
    path = Column(String)
    #  End of a season
    seasoninfo = Column(String)
    #  Note
    note = Column(String)
    #  Synchronous time
    lst_mod_date = Column(String, default=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @staticmethod
    def get_by_itemid(db: Session, item_id: str):
        return db.query(MediaServerItem).filter(MediaServerItem.item_id == item_id).first()

    @staticmethod
    def empty(db: Session, server: str):
        db.query(MediaServerItem).filter(MediaServerItem.server == server).delete()
        Base.commit(db)

    @staticmethod
    def exist_by_tmdbid(db: Session, tmdbid: int, mtype: str):
        return db.query(MediaServerItem).filter(MediaServerItem.tmdbid == tmdbid,
                                                MediaServerItem.item_type == mtype).first()

    @staticmethod
    def exists_by_title(db: Session, title: str, mtype: str, year: str):
        return db.query(MediaServerItem).filter(MediaServerItem.title == title,
                                                MediaServerItem.item_type == mtype,
                                                MediaServerItem.year == str(year)).first()
