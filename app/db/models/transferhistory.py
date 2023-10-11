import time

from sqlalchemy import Column, Integer, String, Sequence, Boolean, func
from sqlalchemy.orm import Session

from app.db.models import Base


class TransferHistory(Base):
    """
    Transfer history
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Source catalog
    src = Column(String, index=True)
    #  Target catalog
    dest = Column(String)
    #  Transfer mode move/copy/link...
    mode = Column(String)
    #  Typology  Cinematic/ Dramas
    type = Column(String)
    #  Secondary classification
    category = Column(String)
    #  Caption
    title = Column(String, index=True)
    #  Particular year
    year = Column(String)
    tmdbid = Column(Integer, index=True)
    imdbid = Column(String)
    tvdbid = Column(Integer)
    doubanid = Column(String)
    # Sxx
    seasons = Column(String)
    # Exx
    episodes = Column(String)
    #  Playbill
    image = Column(String)
    #  Downloaderhash
    download_hash = Column(String, index=True)
    #  Transfer success status
    status = Column(Boolean(), default=True)
    #  Transfer failure message
    errmsg = Column(String)
    #  Timing
    date = Column(String, index=True)
    #  List of documents， In order toJSON Stockpile
    files = Column(String)

    @staticmethod
    def list_by_title(db: Session, title: str, page: int = 1, count: int = 30):
        return db.query(TransferHistory).filter(TransferHistory.title.like(f'%{title}%')).order_by(
            TransferHistory.date.desc()).offset((page - 1) * count).limit(
            count).all()

    @staticmethod
    def list_by_page(db: Session, page: int = 1, count: int = 30):
        return db.query(TransferHistory).order_by(TransferHistory.date.desc()).offset((page - 1) * count).limit(
            count).all()

    @staticmethod
    def get_by_hash(db: Session, download_hash: str):
        return db.query(TransferHistory).filter(TransferHistory.download_hash == download_hash).first()

    @staticmethod
    def get_by_src(db: Session, src: str):
        return db.query(TransferHistory).filter(TransferHistory.src == src).first()

    @staticmethod
    def list_by_hash(db: Session, download_hash: str):
        return db.query(TransferHistory).filter(TransferHistory.download_hash == download_hash).all()

    @staticmethod
    def statistic(db: Session, days: int = 7):
        """
        Statistical updatedays Days of download history， Return daily quantities grouped by date
        """
        sub_query = db.query(func.substr(TransferHistory.date, 1, 10).label('date'),
                             TransferHistory.id.label('id')).filter(
            TransferHistory.date >= time.strftime("%Y-%m-%d %H:%M:%S",
                                                  time.localtime(time.time() - 86400 * days))).subquery()
        return db.query(sub_query.c.date, func.count(sub_query.c.id)).group_by(sub_query.c.date).all()

    @staticmethod
    def count(db: Session):
        return db.query(func.count(TransferHistory.id)).first()[0]

    @staticmethod
    def count_by_title(db: Session, title: str):
        return db.query(func.count(TransferHistory.id)).filter(TransferHistory.title.like(f'%{title}%')).first()[0]

    @staticmethod
    def list_by(db: Session, mtype: str = None, title: str = None, year: str = None, season: str = None,
                episode: str = None, tmdbid: int = None, dest: str = None):
        """
        Act in accordance withtmdbid、season、season_episode Access to transfer records
        tmdbid + mtype  Maybe title + year  Must lose
        """
        # TMDBID +  Typology
        if tmdbid and mtype:
            #  A certain season of a certain episode of a certain tv show
            if season and episode:
                return db.query(TransferHistory).filter(TransferHistory.tmdbid == tmdbid,
                                                        TransferHistory.type == mtype,
                                                        TransferHistory.seasons == season,
                                                        TransferHistory.episodes == episode,
                                                        TransferHistory.dest == dest).all()
            #  A certain season of a tv series
            elif season:
                return db.query(TransferHistory).filter(TransferHistory.tmdbid == tmdbid,
                                                        TransferHistory.type == mtype,
                                                        TransferHistory.seasons == season).all()
            else:
                if dest:
                    #  Cinematic
                    return db.query(TransferHistory).filter(TransferHistory.tmdbid == tmdbid,
                                                            TransferHistory.type == mtype,
                                                            TransferHistory.dest == dest).all()
                else:
                    #  All seasons of tv series
                    return db.query(TransferHistory).filter(TransferHistory.tmdbid == tmdbid,
                                                            TransferHistory.type == mtype).all()
        #  Caption + 年份
        elif title and year:
            #  A certain season of a certain episode of a certain tv show
            if season and episode:
                return db.query(TransferHistory).filter(TransferHistory.title == title,
                                                        TransferHistory.year == year,
                                                        TransferHistory.seasons == season,
                                                        TransferHistory.episodes == episode,
                                                        TransferHistory.dest == dest).all()
            #  A certain season of a tv series
            elif season:
                return db.query(TransferHistory).filter(TransferHistory.title == title,
                                                        TransferHistory.year == year,
                                                        TransferHistory.seasons == season).all()
            else:
                if dest:
                    #  Cinematic
                    return db.query(TransferHistory).filter(TransferHistory.title == title,
                                                            TransferHistory.year == year,
                                                            TransferHistory.dest == dest).all()
                else:
                    #  All seasons of tv series
                    return db.query(TransferHistory).filter(TransferHistory.title == title,
                                                            TransferHistory.year == year).all()
        return []

    @staticmethod
    def get_by_type_tmdbid(db: Session, mtype: str = None, tmdbid: int = None):
        """
        Act in accordance withtmdbid、type Access to transfer records
        """
        return db.query(TransferHistory).filter(TransferHistory.tmdbid == tmdbid,
                                                TransferHistory.type == mtype).first()

    @staticmethod
    def update_download_hash(db: Session, historyid: int = None, download_hash: str = None):
        db.query(TransferHistory).filter(TransferHistory.id == historyid).update(
            {
                "download_hash": download_hash
            }
        )
        Base.commit(db)
