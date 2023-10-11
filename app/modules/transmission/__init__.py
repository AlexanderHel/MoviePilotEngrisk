import shutil
from pathlib import Path
from typing import Set, Tuple, Optional, Union, List

from transmission_rpc import File

from app import schemas
from app.core.config import settings
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.transmission.transmission import Transmission
from app.schemas import TransferTorrent, DownloadingTorrent
from app.schemas.types import TorrentStatus
from app.utils.string import StringUtils
from app.utils.system import SystemUtils


class TransmissionModule(_ModuleBase):
    transmission: Transmission = None

    def init_module(self) -> None:
        self.transmission = Transmission()

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "DOWNLOADER", "transmission"

    def scheduler_job(self) -> None:
        """
        Timed task， Each10 One call per minute
        """
        #  Scheduled reconnection
        if not self.transmission.is_inactive():
            self.transmission.reconnect()

    def download(self, content: Union[Path, str], download_dir: Path, cookie: str,
                 episodes: Set[int] = None, category: str = None) -> Optional[Tuple[Optional[str], str]]:
        """
        Based on seed documents， Select and add a download task
        :param content:   Seed file address or magnet link
        :param download_dir:   Download catalog
        :param cookie:  cookie
        :param episodes:   Number of episodes to download
        :param category:   Categorization，TR Not used in
        :return:  TorrentHash
        """
        if not content:
            return
        if isinstance(content, Path) and not content.exists():
            return None, f" Seed file does not exist：{content}"

        #  Pause if you want to select a file
        is_paused = True if episodes else False
        #  Tab (of a window) (computing)
        if settings.TORRENT_TAG:
            labels = [settings.TORRENT_TAG]
        else:
            labels = None
        #  Add tasks
        torrent = self.transmission.add_torrent(
            content=content.read_bytes() if isinstance(content, Path) else content,
            download_dir=str(download_dir),
            is_paused=is_paused,
            labels=labels,
            cookie=cookie
        )
        if not torrent:
            return None, f" Failed to add seed task：{content}"
        else:
            torrent_hash = torrent.hashString
            if is_paused:
                #  Select file
                torrent_files = self.transmission.get_files(torrent_hash)
                if not torrent_files:
                    return torrent_hash, " Failed to get seed file， The download task may be in a suspended state"
                #  Required documentation information
                file_ids = []
                for torrent_file in torrent_files:
                    file_id = torrent_file.id
                    file_name = torrent_file.name
                    meta_info = MetaInfo(file_name)
                    if not meta_info.episode_list:
                        continue
                    selected = set(meta_info.episode_list).issubset(set(episodes))
                    if not selected:
                        continue
                    file_ids.append(file_id)
                #  Select file
                self.transmission.set_files(torrent_hash, file_ids)
                #  Commencement of mission
                self.transmission.start_torrents(torrent_hash)
            else:
                return torrent_hash, " Add download task successfully"

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
            torrents, _ = self.transmission.get_torrents(ids=hashs, tags=settings.TORRENT_TAG)
            for torrent in torrents or []:
                ret_torrents.append(TransferTorrent(
                    title=torrent.name,
                    path=Path(torrent.download_dir) / torrent.name,
                    hash=torrent.hashString,
                    tags=",".join(torrent.labels or [])
                ))
        elif status == TorrentStatus.TRANSFER:
            #  Get the completed and unorganized
            torrents = self.transmission.get_completed_torrents(tags=settings.TORRENT_TAG)
            for torrent in torrents or []:
                #  Suck (keep in your mouth without chewing)" Collated"tag Failure to deal with
                if " Collated" in torrent.labels or []:
                    continue
                #  Download path
                path = torrent.download_dir
                #  Unable to get download path not handled
                if not path:
                    logger.debug(f" Not available {torrent.name}  Download save path")
                    continue
                ret_torrents.append(TransferTorrent(
                    title=torrent.name,
                    path=Path(torrent.download_dir) / torrent.name,
                    hash=torrent.hashString,
                    tags=",".join(torrent.labels or [])
                ))
        elif status == TorrentStatus.DOWNLOADING:
            #  Get the task being downloaded
            torrents = self.transmission.get_downloading_torrents(tags=settings.TORRENT_TAG)
            for torrent in torrents or []:
                meta = MetaInfo(torrent.name)
                dlspeed = torrent.rate_download if hasattr(torrent, "rate_download") else torrent.rateDownload
                upspeed = torrent.rate_upload if hasattr(torrent, "rate_upload") else torrent.rateUpload
                ret_torrents.append(DownloadingTorrent(
                    hash=torrent.hashString,
                    title=torrent.name,
                    name=meta.name,
                    year=meta.year,
                    season_episode=meta.season_episode,
                    progress=torrent.progress,
                    size=torrent.total_size,
                    state="paused" if torrent.status == "stopped" else "downloading",
                    dlspeed=StringUtils.str_filesize(dlspeed),
                    upspeed=StringUtils.str_filesize(upspeed),
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
        :return: None
        """
        self.transmission.set_torrent_tag(ids=hashs, tags=[' Collated'])
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
        return self.transmission.delete_torrents(delete_file=True, ids=hashs)

    def start_torrents(self, hashs: Union[list, str]) -> bool:
        """
        Start download
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.transmission.start_torrents(ids=hashs)

    def stop_torrents(self, hashs: Union[list, str]) -> bool:
        """
        Stop downloading
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.transmission.start_torrents(ids=hashs)

    def torrent_files(self, tid: str) -> Optional[List[File]]:
        """
        Get a list of seed files
        """
        return self.transmission.get_files(tid=tid)

    def downloader_info(self) -> schemas.DownloaderInfo:
        """
        Downloader information
        """
        info = self.transmission.transfer_info()
        if not info:
            return schemas.DownloaderInfo()
        return schemas.DownloaderInfo(
            download_speed=info.download_speed,
            upload_speed=info.upload_speed,
            download_size=info.current_stats.downloaded_bytes,
            upload_size=info.current_stats.uploaded_bytes
        )
