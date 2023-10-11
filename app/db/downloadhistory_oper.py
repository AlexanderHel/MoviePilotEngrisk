from pathlib import Path
from typing import List

from app.db import DbOper
from app.db.models.downloadhistory import DownloadHistory, DownloadFiles


class DownloadHistoryOper(DbOper):
    """
    Download history management
    """

    def get_by_path(self, path: Path) -> DownloadHistory:
        """
        Search download records by path
        :param path:  Digitalkey
        """
        return DownloadHistory.get_by_path(self._db, str(path))

    def get_by_hash(self, download_hash: str) -> DownloadHistory:
        """
        Check or refer toHash Check download records
        :param download_hash:  Digitalkey
        """
        return DownloadHistory.get_by_hash(self._db, download_hash)

    def add(self, **kwargs) -> DownloadHistory:
        """
        Added download history
        """
        downloadhistory = DownloadHistory(**kwargs)
        return downloadhistory.create(self._db)

    def add_files(self, file_items: List[dict]):
        """
        Added download history文件
        """
        for file_item in file_items:
            downloadfile = DownloadFiles(**file_item)
            downloadfile.create(self._db)

    def truncate_files(self):
        """
        Empty the download history file record
        """
        DownloadFiles.truncate(self._db)

    def get_files_by_hash(self, download_hash: str, state: int = None) -> List[DownloadFiles]:
        """
        Check or refer toHash Query download file records
        :param download_hash:  Digitalkey
        :param state:  Delete status
        """
        return DownloadFiles.get_by_hash(self._db, download_hash, state)

    def get_file_by_fullpath(self, fullpath: str) -> DownloadFiles:
        """
        Check or refer tofullpath Query download file records
        :param fullpath:  Digitalkey
        """
        return DownloadFiles.get_by_fullpath(self._db, fullpath)

    def get_files_by_savepath(self, fullpath: str) -> List[DownloadFiles]:
        """
        Check or refer tosavepath Query download file records
        :param fullpath:  Digitalkey
        """
        return DownloadFiles.get_by_savepath(self._db, fullpath)

    def delete_file_by_fullpath(self, fullpath: str):
        """
        Check or refer tofullpath Delete download file records
        :param fullpath:  Digitalkey
        """
        DownloadFiles.delete_by_fullpath(self._db, fullpath)

    def get_hash_by_fullpath(self, fullpath: str) -> str:
        """
        Check or refer tofullpath Query download file recordshash
        :param fullpath:  Digitalkey
        """
        fileinfo: DownloadFiles = DownloadFiles.get_by_fullpath(self._db, fullpath)
        if fileinfo:
            return fileinfo.download_hash
        return ""

    def list_by_page(self, page: int = 1, count: int = 30) -> List[DownloadHistory]:
        """
        Pagination query download history
        """
        return DownloadHistory.list_by_page(self._db, page, count)

    def truncate(self):
        """
        Empty download log
        """
        DownloadHistory.truncate(self._db)

    def get_last_by(self, mtype=None, title: str = None, year: str = None,
                    season: str = None, episode: str = None, tmdbid=None) -> List[DownloadHistory]:
        """
        By type、 Caption、 Particular year、 Season set search download records
        """
        return DownloadHistory.get_last_by(db=self._db,
                                           mtype=mtype,
                                           title=title,
                                           year=year,
                                           season=season,
                                           episode=episode,
                                           tmdbid=tmdbid)

    def list_by_user_date(self, date: str, userid: str = None) -> List[DownloadHistory]:
        """
        Query a user's download history after a certain time
        """
        return DownloadHistory.list_by_user_date(db=self._db,
                                                 date=date,
                                                 userid=userid)
