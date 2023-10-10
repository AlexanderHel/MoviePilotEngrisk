from sqlalchemy import Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.db.models import Base


class DownloadHistory(Base):
    """
    Download history
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Save path
    path = Column(String, nullable=False, index=True)
    #  Typology  Cinematic/ Dramas
    type = Column(String, nullable=False)
    #  Caption
    title = Column(String, nullable=False)
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
    #  Download tasksHash
    download_hash = Column(String, index=True)
    #  Seed name
    torrent_name = Column(String)
    #  Seed description
    torrent_description = Column(String)
    #  Seed site
    torrent_site = Column(String)
    #  Download users
    userid = Column(String)
    #  Download channels
    channel = Column(String)
    #  Creation time
    date = Column(String)
    #  Additional information
    note = Column(String)

    @staticmethod
    def get_by_hash(db: Session, download_hash: str):
        return db.query(DownloadHistory).filter(DownloadHistory.download_hash == download_hash).first()

    @staticmethod
    def list_by_page(db: Session, page: int = 1, count: int = 30):
        return db.query(DownloadHistory).offset((page - 1) * count).limit(count).all()

    @staticmethod
    def get_by_path(db: Session, path: str):
        return db.query(DownloadHistory).filter(DownloadHistory.path == path).first()

    @staticmethod
    def get_last_by(db: Session, mtype: str = None, title: str = None, year: int = None, season: str = None,
                    episode: str = None, tmdbid: int = None):
        """
        Act in accordance withtmdbid、season、season_episode Access to transfer records
        """
        if tmdbid and not season and not episode:
            return db.query(DownloadHistory).filter(DownloadHistory.tmdbid == tmdbid).order_by(
                DownloadHistory.id.desc()).all()
        if tmdbid and season and not episode:
            return db.query(DownloadHistory).filter(DownloadHistory.tmdbid == tmdbid,
                                                    DownloadHistory.seasons == season).order_by(
                DownloadHistory.id.desc()).all()
        if tmdbid and season and episode:
            return db.query(DownloadHistory).filter(DownloadHistory.tmdbid == tmdbid,
                                                    DownloadHistory.seasons == season,
                                                    DownloadHistory.episodes == episode).order_by(
                DownloadHistory.id.desc()).all()
        #  All seasons of tv series｜ Cinematic
        if not season and not episode:
            return db.query(DownloadHistory).filter(DownloadHistory.type == mtype,
                                                    DownloadHistory.title == title,
                                                    DownloadHistory.year == year).order_by(
                DownloadHistory.id.desc()).all()
        #  A certain season of a tv series
        if season and not episode:
            return db.query(DownloadHistory).filter(DownloadHistory.type == mtype,
                                                    DownloadHistory.title == title,
                                                    DownloadHistory.year == year,
                                                    DownloadHistory.seasons == season).order_by(
                DownloadHistory.id.desc()).all()
        #  A certain season of a tv series某集
        if season and episode:
            return db.query(DownloadHistory).filter(DownloadHistory.type == mtype,
                                                    DownloadHistory.title == title,
                                                    DownloadHistory.year == year,
                                                    DownloadHistory.seasons == season,
                                                    DownloadHistory.episodes == episode).order_by(
                DownloadHistory.id.desc()).all()

    @staticmethod
    def list_by_user_date(db: Session, date: str, userid: str = None):
        """
        Query a user's download history after a certain time
        """
        if userid:
            return db.query(DownloadHistory).filter(DownloadHistory.date < date,
                                                    DownloadHistory.userid == userid).order_by(
                DownloadHistory.id.desc()).all()
        else:
            return db.query(DownloadHistory).filter(DownloadHistory.date < date).order_by(
                DownloadHistory.id.desc()).all()


class DownloadFiles(Base):
    """
    Download file records
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Download tasksHash
    download_hash = Column(String, index=True)
    #  Downloader
    downloader = Column(String)
    #  Full path
    fullpath = Column(String, index=True)
    #  Save path
    savepath = Column(String, index=True)
    #  File relative path/ Name (of a thing)
    filepath = Column(String)
    #  Seed name
    torrentname = Column(String)
    #  State of affairs 0- Deleted 1- Normalcy
    state = Column(Integer, nullable=False, default=1)

    @staticmethod
    def get_by_hash(db: Session, download_hash: str, state: int = None):
        if state:
            return db.query(DownloadFiles).filter(DownloadFiles.download_hash == download_hash,
                                                  DownloadFiles.state == state).all()
        else:
            return db.query(DownloadFiles).filter(DownloadFiles.download_hash == download_hash).all()

    @staticmethod
    def get_by_fullpath(db: Session, fullpath: str):
        return db.query(DownloadFiles).filter(DownloadFiles.fullpath == fullpath).order_by(
            DownloadFiles.id.desc()).first()

    @staticmethod
    def get_by_savepath(db: Session, savepath: str):
        return db.query(DownloadFiles).filter(DownloadFiles.savepath == savepath).all()

    @staticmethod
    def delete_by_fullpath(db: Session, fullpath: str):
        db.query(DownloadFiles).filter(DownloadFiles.fullpath == fullpath,
                                       DownloadFiles.state == 1).update(
            {
                "state": 0
            }
        )
        Base.commit(db)
