import shutil
from pathlib import Path
from typing import Set, Tuple, Optional, Union, List

from qbittorrentapi import TorrentFilesList

from app import schemas
from app.core.config import settings
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.qbittorrent.qbittorrent import Qbittorrent
from app.schemas import TransferTorrent, DownloadingTorrent
from app.schemas.types import TorrentStatus
from app.utils.string import StringUtils
from app.utils.system import SystemUtils


class QbittorrentModule(_ModuleBase):
    qbittorrent: Qbittorrent = None

    def init_module(self) -> None:
        self.qbittorrent = Qbittorrent()

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "DOWNLOADER", "qbittorrent"

    def scheduler_job(self) -> None:
        """
        Timed task， Each10 One call per minute
        """
        #  Scheduled reconnection
        if self.qbittorrent.is_inactive():
            self.qbittorrent.reconnect()

    def download(self, content: Union[Path, str], download_dir: Path, cookie: str,
                 episodes: Set[int] = None, category: str = None) -> Optional[Tuple[Optional[str], str]]:
        """
        Based on seed documents， Select and add a download task
        :param content:   Seed file address or magnet link
        :param download_dir:   Download catalog
        :param cookie:  cookie
        :param episodes:   Number of episodes to download
        :param category:   Categorization
        :return:  TorrentHash， Error message
        """
        if not content:
            return
        if isinstance(content, Path) and not content.exists():
            return None, f" Seed file does not exist：{content}"

        #  Generate randomTag
        tag = StringUtils.generate_random_str(10)
        if settings.TORRENT_TAG:
            tags = [tag, settings.TORRENT_TAG]
        else:
            tags = [tag]
        #  Pause if you want to select a file
        is_paused = True if episodes else False
        #  Add tasks
        state = self.qbittorrent.add_torrent(
            content=content.read_bytes() if isinstance(content, Path) else content,
            download_dir=str(download_dir),
            is_paused=is_paused,
            tag=tags,
            cookie=cookie,
            category=category
        )
        if not state:
            return None, f" Failed to add seed task：{content}"
        else:
            #  Getting seedsHash
            torrent_hash = self.qbittorrent.get_torrent_id_by_tag(tags=tag)
            if not torrent_hash:
                return None, f" Getting seedsHash Fail (e.g. experiments)：{content}"
            else:
                if is_paused:
                    #  Seed file
                    torrent_files = self.qbittorrent.get_files(torrent_hash)
                    if not torrent_files:
                        return torrent_hash, " Failed to get seed file， The download task may be in a suspended state"

                    #  Unwanted documentsID
                    file_ids = []
                    #  List of sets required
                    sucess_epidised = []

                    for torrent_file in torrent_files:
                        file_id = torrent_file.get("id")
                        file_name = torrent_file.get("name")
                        meta_info = MetaInfo(file_name)
                        if not meta_info.episode_list \
                                or not set(meta_info.episode_list).issubset(episodes):
                            file_ids.append(file_id)
                        else:
                            sucess_epidised = list(set(sucess_epidised).union(set(meta_info.episode_list)))
                    if sucess_epidised and file_ids:
                        #  Select file
                        self.qbittorrent.set_files(torrent_hash=torrent_hash, file_ids=file_ids, priority=0)
                    #  Commencement of mission
                    self.qbittorrent.start_torrents(torrent_hash)
                    return torrent_hash, f" Add download successfully， Selected episodes：{sucess_epidised}"
                else:
                    return torrent_hash, " Add download successfully"

    def list_torrents(self, status: TorrentStatus = None,
                      hashs: Union[list, str] = None) -> Optional[List[Union[TransferTorrent, DownloadingTorrent]]]:
        """
        Get downloader seed list
        :param status:   Seed state
        :param hashs:   TorrentHash
        :return:  List of seeds in the downloader that match the status
        """
        ret_torrents = []
        if hashs:
            #  Check or refer toHash Gain
            torrents, _ = self.qbittorrent.get_torrents(ids=hashs, tags=settings.TORRENT_TAG)
            for torrent in torrents or []:
                content_path = torrent.get("content_path")
                if content_path:
                    torrent_path = Path(content_path)
                else:
                    torrent_path = Path(settings.DOWNLOAD_PATH) / torrent.get('name')
                ret_torrents.append(TransferTorrent(
                    title=torrent.get('name'),
                    path=torrent_path,
                    hash=torrent.get('hash'),
                    tags=torrent.get('tags')
                ))
        elif status == TorrentStatus.TRANSFER:
            #  Get the completed and unorganized
            torrents = self.qbittorrent.get_completed_torrents(tags=settings.TORRENT_TAG)
            for torrent in torrents or []:
                tags = torrent.get("tags") or []
                if " Collated" in tags:
                    continue
                #  Content path
                content_path = torrent.get("content_path")
                if content_path:
                    torrent_path = Path(content_path)
                else:
                    torrent_path = Path(settings.DOWNLOAD_PATH) / torrent.get('name')
                ret_torrents.append(TransferTorrent(
                    title=torrent.get('name'),
                    path=torrent_path,
                    hash=torrent.get('hash'),
                    tags=torrent.get('tags')
                ))
        elif status == TorrentStatus.DOWNLOADING:
            #  Get the task being downloaded
            torrents = self.qbittorrent.get_downloading_torrents(tags=settings.TORRENT_TAG)
            for torrent in torrents or []:
                meta = MetaInfo(torrent.get('name'))
                ret_torrents.append(DownloadingTorrent(
                    hash=torrent.get('hash'),
                    title=torrent.get('name'),
                    name=meta.name,
                    year=meta.year,
                    season_episode=meta.season_episode,
                    progress=torrent.get('progress') * 100,
                    size=torrent.get('total_size'),
                    state="paused" if torrent.get('state') == "paused" else "downloading",
                    dlspeed=StringUtils.str_filesize(torrent.get('dlspeed')),
                    upspeed=StringUtils.str_filesize(torrent.get('upspeed')),
                ))
        else:
            return None
        return ret_torrents

    def transfer_completed(self, hashs: Union[str, list],
                           path: Path = None) -> None:
        """
        Disposal upon completion of the transfer
        :param hashs:   TorrentHash
        :param path:   Source catalog
        """
        self.qbittorrent.set_torrents_tag(ids=hashs, tags=[' Collated'])
        #  Remove seeds in mobile mode
        if settings.TRANSFER_TYPE == "move":
            if self.remove_torrents(hashs):
                logger.info(f" Mobile mode deletes seeds successfully：{hashs} ")
            #  Delete residual files
            if path and path.exists():
                files = SystemUtils.list_files(path, settings.RMT_MEDIAEXT)
                if not files:
                    logger.warn(f" Delete residual folders：{path}")
                    shutil.rmtree(path, ignore_errors=True)

    def remove_torrents(self, hashs: Union[str, list]) -> bool:
        """
        Delete downloader seeds
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.qbittorrent.delete_torrents(delete_file=True, ids=hashs)

    def start_torrents(self, hashs: Union[list, str]) -> bool:
        """
        Start download
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.qbittorrent.start_torrents(ids=hashs)

    def stop_torrents(self, hashs: Union[list, str]) -> bool:
        """
        Stop downloading
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.qbittorrent.start_torrents(ids=hashs)

    def torrent_files(self, tid: str) -> Optional[TorrentFilesList]:
        """
        Get a list of seed files
        """
        return self.qbittorrent.get_files(tid=tid)

    def downloader_info(self) -> schemas.DownloaderInfo:
        """
        Downloader information
        """
        #  Call (programming)Qbittorrent API Query real-time information
        info = self.qbittorrent.transfer_info()
        if not info:
            return schemas.DownloaderInfo()
        return schemas.DownloaderInfo(
            download_speed=info.get("dl_info_speed"),
            upload_speed=info.get("up_info_speed"),
            download_size=info.get("dl_info_data"),
            upload_size=info.get("up_info_data")
        )
