import json
import time
from pathlib import Path
from typing import Any, List

from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.db import DbOper
from app.db.models.transferhistory import TransferHistory
from app.schemas import TransferInfo


class TransferHistoryOper(DbOper):
    """
    Transfer of historical management
    """

    def get(self, historyid: int) -> TransferHistory:
        """
        Getting the transfer history
        :param historyid:  Transfer historyid
        """
        return TransferHistory.get(self._db, historyid)

    def get_by_title(self, title: str) -> List[TransferHistory]:
        """
        Search transfer records by title
        :param title:  Digitalkey
        """
        return TransferHistory.list_by_title(self._db, title)

    def get_by_src(self, src: str) -> TransferHistory:
        """
        Search transfer records by source
        :param src:  Digitalkey
        """
        return TransferHistory.get_by_src(self._db, src)

    def list_by_hash(self, download_hash: str) -> List[TransferHistory]:
        """
        By seedhash Access to transfer records
        :param download_hash:  Torrenthash
        """
        return TransferHistory.list_by_hash(self._db, download_hash)

    def add(self, **kwargs) -> TransferHistory:
        """
        Add transfer history
        """
        kwargs.update({
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        })
        return TransferHistory(**kwargs).create(self._db)

    def statistic(self, days: int = 7) -> List[Any]:
        """
        Statistical updatedays Days of download history
        """
        return TransferHistory.statistic(self._db, days)

    def get_by(self, title: str = None, year: str = None, mtype: str = None,
               season: str = None, episode: str = None, tmdbid: int = None, dest: str = None) -> List[TransferHistory]:
        """
        By type、 Caption、 Particular year、 Quarterly set query transfer record
        """
        return TransferHistory.list_by(db=self._db,
                                       mtype=mtype,
                                       title=title,
                                       dest=dest,
                                       year=year,
                                       season=season,
                                       episode=episode,
                                       tmdbid=tmdbid)

    def get_by_type_tmdbid(self, mtype: str = None, tmdbid: int = None) -> TransferHistory:
        """
        By type、tmdb Access to transfer records
        """
        return TransferHistory.get_by_type_tmdbid(db=self._db,
                                                  mtype=mtype,
                                                  tmdbid=tmdbid)

    def delete(self, historyid):
        """
        Deletion of transfer records
        """
        TransferHistory.delete(self._db, historyid)

    def truncate(self):
        """
        Emptying the transfer record
        """
        TransferHistory.truncate(self._db)

    def add_force(self, **kwargs) -> TransferHistory:
        """
        Add transfer history，相同源目录的记录会被删除
        """
        if kwargs.get("src"):
            transferhistory = TransferHistory.get_by_src(self._db, kwargs.get("src"))
            if transferhistory:
                transferhistory.delete(self._db, transferhistory.id)
        kwargs.update({
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        })
        return TransferHistory(**kwargs).create(self._db)

    def update_download_hash(self, historyid, download_hash):
        """
        Supplementary transfer recordsdownload_hash
        """
        TransferHistory.update_download_hash(self._db, historyid, download_hash)

    def add_success(self, src_path: Path, mode: str, meta: MetaBase,
                    mediainfo: MediaInfo, transferinfo: TransferInfo,
                    download_hash: str = None):
        """
        Add transfer success history
        """
        self.add_force(
            src=str(src_path),
            dest=str(transferinfo.target_path),
            mode=mode,
            type=mediainfo.type.value,
            category=mediainfo.category,
            title=mediainfo.title,
            year=mediainfo.year,
            tmdbid=mediainfo.tmdb_id,
            imdbid=mediainfo.imdb_id,
            tvdbid=mediainfo.tvdb_id,
            doubanid=mediainfo.douban_id,
            seasons=meta.season,
            episodes=meta.episode,
            image=mediainfo.get_poster_image(),
            download_hash=download_hash,
            status=1,
            files=json.dumps(transferinfo.file_list)
        )

    def add_fail(self, src_path: Path, mode: str, meta: MetaBase, mediainfo: MediaInfo = None,
                 transferinfo: TransferInfo = None, download_hash: str = None):
        """
        Added transfer failure history
        """
        if mediainfo and transferinfo:
            his = self.add_force(
                src=str(src_path),
                dest=str(transferinfo.target_path),
                mode=mode,
                type=mediainfo.type.value,
                category=mediainfo.category,
                title=mediainfo.title or meta.name,
                year=mediainfo.year or meta.year,
                tmdbid=mediainfo.tmdb_id,
                imdbid=mediainfo.imdb_id,
                tvdbid=mediainfo.tvdb_id,
                doubanid=mediainfo.douban_id,
                seasons=meta.season,
                episodes=meta.episode,
                image=mediainfo.get_poster_image(),
                download_hash=download_hash,
                status=0,
                errmsg=transferinfo.message or ' Unknown error',
                files=json.dumps(transferinfo.file_list)
            )
        else:
            his = self.add_force(
                title=meta.name,
                year=meta.year,
                src=str(src_path),
                mode=mode,
                seasons=meta.season,
                episodes=meta.episode,
                download_hash=download_hash,
                status=0,
                errmsg=" No media messages recognized"
            )
        return his
