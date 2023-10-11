import time
from typing import Optional, Union, Tuple, List

import qbittorrentapi
from qbittorrentapi import TorrentDictionary, TorrentFilesList
from qbittorrentapi.client import Client
from qbittorrentapi.transfer import TransferInfoDictionary

from app.core.config import settings
from app.log import logger
from app.utils.singleton import Singleton
from app.utils.string import StringUtils


class Qbittorrent(metaclass=Singleton):
    _host: str = None
    _port: int = None
    _username: str = None
    _passowrd: str = None

    qbc: Client = None

    def __init__(self):
        self._host, self._port = StringUtils.get_domain_address(address=settings.QB_HOST, prefix=True)
        self._username = settings.QB_USER
        self._password = settings.QB_PASSWORD
        if self._host and self._port:
            self.qbc = self.__login_qbittorrent()

    def is_inactive(self) -> bool:
        """
        Determine if reconnection is required
        """
        if not self._host or not self._port:
            return False
        return True if not self.qbc else False

    def reconnect(self):
        """
        Reconnect
        """
        self.qbc = self.__login_qbittorrent()

    def __login_qbittorrent(self) -> Optional[Client]:
        """
        Groutqbittorrent
        :return: qbittorrent Boyfriend
        """
        try:
            #  Log in
            qbt = qbittorrentapi.Client(host=self._host,
                                        port=self._port,
                                        username=self._username,
                                        password=self._password,
                                        VERIFY_WEBUI_CERTIFICATE=False,
                                        REQUESTS_ARGS={'timeout': (15, 60)})
            try:
                qbt.auth_log_in()
            except qbittorrentapi.LoginFailed as e:
                logger.error(f"qbittorrent  Login failure：{e}")
            return qbt
        except Exception as err:
            logger.error(f"qbittorrent  Something is wrong with the connection.：{err}")
            return None

    def get_torrents(self, ids: Union[str, list] = None,
                     status: Union[str, list] = None,
                     tags: Union[str, list] = None) -> Tuple[List[TorrentDictionary], bool]:
        """
        Get seed list
        return:  Seed list,  Whether or not an abnormality occurs
        """
        if not self.qbc:
            return [], True
        try:
            torrents = self.qbc.torrents_info(torrent_hashes=ids,
                                              status_filter=status)
            if tags:
                results = []
                if not isinstance(tags, list):
                    tags = [tags]
                for torrent in torrents:
                    torrent_tags = [str(tag).strip() for tag in torrent.get("tags").split(',')]
                    if set(tags).issubset(set(torrent_tags)):
                        results.append(torrent)
                return results, False
            return torrents or [], False
        except Exception as err:
            logger.error(f"Get seed list出错：{err}")
            return [], True

    def get_completed_torrents(self, ids: Union[str, list] = None,
                               tags: Union[str, list] = None) -> Optional[List[TorrentDictionary]]:
        """
        Access to completed seeds
        return:  Seed list,  Returns if an exception occursNone
        """
        if not self.qbc:
            return None
        # completed Will contain the movement state  Replace with obtainingseeding State of affairs  Includes event uploads,  It's being planted.,  And compulsory seeding
        torrents, error = self.get_torrents(status=["seeding"], ids=ids, tags=tags)
        return None if error else torrents or []

    def get_downloading_torrents(self, ids: Union[str, list] = None,
                                 tags: Union[str, list] = None) -> Optional[List[TorrentDictionary]]:
        """
        Get the seed being downloaded
        return:  Seed list,  Returns if an exception occursNone
        """
        if not self.qbc:
            return None
        torrents, error = self.get_torrents(ids=ids,
                                            status=["downloading"],
                                            tags=tags)
        return None if error else torrents or []

    def remove_torrents_tag(self, ids: Union[str, list], tag: Union[str, list]) -> bool:
        """
        Remove seedsTag
        :param ids:  TorrentHash Listings
        :param tag:  Tagged content
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_delete_tags(torrent_hashes=ids, tags=tag)
            return True
        except Exception as err:
            logger.error(f"Remove seedsTag出错：{err}")
            return False

    def set_torrents_tag(self, ids: Union[str, list], tags: list):
        """
        Set seed status to collated， And whether seeding is mandatory
        """
        if not self.qbc:
            return
        try:
            #  Labeling
            self.qbc.torrents_add_tags(tags=tags, torrent_hashes=ids)
        except Exception as err:
            logger.error(f" Setting the seedTag Make a mistake：{err}")

    def torrents_set_force_start(self, ids: Union[str, list]):
        """
        Setting up a strong production species
        """
        if not self.qbc:
            return
        try:
            self.qbc.torrents_set_force_start(enable=True, torrent_hashes=ids)
        except Exception as err:
            logger.error(f"Setting up a strong production species出错：{err}")

    def __get_last_add_torrentid_by_tag(self, tags: Union[str, list],
                                        status: Union[str, list] = None) -> Optional[str]:
        """
        According to the download link of the seed to get the download in progress or suspended clock of theID
        :return:  TorrentID
        """
        try:
            torrents, _ = self.get_torrents(status=status, tags=tags)
        except Exception as err:
            logger.error(f"Get seed list出错：{err}")
            return None
        if torrents:
            return torrents[0].get("hash")
        else:
            return None

    def get_torrent_id_by_tag(self, tags: Union[str, list],
                              status: Union[str, list] = None) -> Optional[str]:
        """
        Multiple attempts to get the just-added seed by taggingID， And remove the label
        """
        torrent_id = None
        # QB Takes time after adding downloads， Retry5 Times per wait5 Unit of angle or arc equivalent one sixtieth of a degree
        for i in range(1, 10):
            time.sleep(3)
            torrent_id = self.__get_last_add_torrentid_by_tag(tags=tags,
                                                              status=status)
            if torrent_id is None:
                continue
            else:
                self.remove_torrents_tag(torrent_id, tags)
                break
        return torrent_id

    def add_torrent(self,
                    content: Union[str, bytes],
                    is_paused: bool = False,
                    download_dir: str = None,
                    tag: Union[str, list] = None,
                    category: str = None,
                    cookie=None,
                    **kwargs
                    ) -> bool:
        """
        Add seeds
        :param content:  Torrenturls Or the contents of the document
        :param is_paused:  Pause after adding
        :param tag:  Tab (of a window) (computing)
        :param category:  Seed classification
        :param download_dir:  Download path
        :param cookie:  WebsiteCookie Used to assist in downloading seeds
        :return: bool
        """
        if not self.qbc or not content:
            return False

        #  Download contents
        if isinstance(content, str):
            urls = content
            torrent_files = None
        else:
            urls = None
            torrent_files = content

        #  Save directory
        if download_dir:
            save_path = download_dir
        else:
            save_path = None

        #  Tab (of a window) (computing)
        if tag:
            tags = tag
        else:
            tags = None

        #  Automatic management of classifications
        if category and settings.QB_CATEGORY:
            is_auto = True
        else:
            is_auto = False
            category = None

        try:
            #  Add download
            qbc_ret = self.qbc.torrents_add(urls=urls,
                                            torrent_files=torrent_files,
                                            save_path=save_path,
                                            is_paused=is_paused,
                                            tags=tags,
                                            use_auto_torrent_management=is_auto,
                                            is_sequential_download=True,
                                            cookie=cookie,
                                            category=category,
                                            **kwargs)
            return True if qbc_ret and str(qbc_ret).find("Ok") != -1 else False
        except Exception as err:
            logger.error(f"Add seeds出错：{err}")
            return False

    def start_torrents(self, ids: Union[str, list]) -> bool:
        """
        Seeding
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_resume(torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"Seeding出错：{err}")
            return False

    def stop_torrents(self, ids: Union[str, list]) -> bool:
        """
        Suspension of seeds
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_pause(torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"Suspension of seeds出错：{err}")
            return False

    def delete_torrents(self, delete_file: bool, ids: Union[str, list]) -> bool:
        """
        Delete seeds
        """
        if not self.qbc:
            return False
        if not ids:
            return False
        try:
            self.qbc.torrents_delete(delete_files=delete_file, torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"Delete seeds出错：{err}")
            return False

    def get_files(self, tid: str) -> Optional[TorrentFilesList]:
        """
        Access to the list of seed files
        """
        if not self.qbc:
            return None
        try:
            return self.qbc.torrents_files(torrent_hash=tid)
        except Exception as err:
            logger.error(f" Error getting list of seed files：{err}")
            return None

    def set_files(self, **kwargs) -> bool:
        """
        Setting the status of downloaded files，priority Because of0 In order not to download，priority Because of1 Downloads
        """
        if not self.qbc:
            return False
        if not kwargs.get("torrent_hash") or not kwargs.get("file_ids"):
            return False
        try:
            self.qbc.torrents_file_priority(torrent_hash=kwargs.get("torrent_hash"),
                                            file_ids=kwargs.get("file_ids"),
                                            priority=kwargs.get("priority"))
            return True
        except Exception as err:
            logger.error(f" Error setting seed file status：{err}")
            return False

    def transfer_info(self) -> Optional[TransferInfoDictionary]:
        """
        Getting transmission information
        """
        if not self.qbc:
            return None
        try:
            return self.qbc.transfer_info()
        except Exception as err:
            logger.error(f"Getting transmission information出错：{err}")
            return None

    def set_speed_limit(self, download_limit: float = None, upload_limit: float = None) -> bool:
        """
        Setting speed limits
        :param download_limit:  Download speed limit， Work unit (one's workplace)KB/s
        :param upload_limit:  Upload speed limit， Work unit (one's workplace)kB/s
        """
        if not self.qbc:
            return False
        download_limit = download_limit * 1024
        upload_limit = upload_limit * 1024
        try:
            self.qbc.transfer.upload_limit = int(upload_limit)
            self.qbc.transfer.download_limit = int(download_limit)
            return True
        except Exception as err:
            logger.error(f"Setting speed limits出错：{err}")
            return False

    def recheck_torrents(self, ids: Union[str, list]):
        """
        Re-calibrate seeds
        """
        if not self.qbc:
            return False
        try:
            return self.qbc.torrents_recheck(torrent_hashes=ids)
        except Exception as err:
            logger.error(f"Re-calibrate seeds出错：{err}")
            return False

    def add_trackers(self, ids: Union[str, list], trackers: list):
        """
        Increasetracker
        """
        if not self.qbc:
            return False
        try:
            return self.qbc.torrents_add_trackers(torrent_hashes=ids, urls=trackers)
        except Exception as err:
            logger.error(f"Increasetracker出错：{err}")
            return False
