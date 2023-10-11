from typing import Optional, Union, Tuple, List

import transmission_rpc
from transmission_rpc import Client, Torrent, File
from transmission_rpc.session import SessionStats

from app.core.config import settings
from app.log import logger
from app.utils.singleton import Singleton
from app.utils.string import StringUtils


class Transmission(metaclass=Singleton):
    _host: str = None
    _port: int = None
    _username: str = None
    _passowrd: str = None

    trc: Optional[Client] = None

    #  Consultationtransmission web， Query only the required parameters， Accelerated seed search
    _trarg = ["id", "name", "status", "labels", "hashString", "totalSize", "percentDone", "addedDate", "trackerStats",
              "leftUntilDone", "rateDownload", "rateUpload", "recheckProgress", "rateDownload", "rateUpload",
              "peersGettingFromUs", "peersSendingToUs", "uploadRatio", "uploadedEver", "downloadedEver", "downloadDir",
              "error", "errorString", "doneDate", "queuePosition", "activityDate", "trackers"]

    def __init__(self):
        self._host, self._port = StringUtils.get_domain_address(address=settings.TR_HOST, prefix=False)
        self._username = settings.TR_USER
        self._password = settings.TR_PASSWORD
        if self._host and self._port:
            self.trc = self.__login_transmission()

    def __login_transmission(self) -> Optional[Client]:
        """
        Grouttransmission
        :return: transmission Boyfriend
        """
        try:
            #  Log in
            trt = transmission_rpc.Client(host=self._host,
                                          port=self._port,
                                          username=self._username,
                                          password=self._password,
                                          timeout=60)
            return trt
        except Exception as err:
            logger.error(f"transmission  Something is wrong with the connection.：{err}")
            return None

    def is_inactive(self) -> bool:
        """
        Determine if reconnection is required
        """
        if not self._host or not self._port:
            return False
        return True if not self.trc else False

    def reconnect(self):
        """
        Reconnect
        """
        self.trc = self.__login_transmission()

    def get_torrents(self, ids: Union[str, list] = None, status: Union[str, list] = None,
                     tags: Union[str, list] = None) -> Tuple[List[Torrent], bool]:
        """
        Get seed list
        Return results  Seed list,  Are there any errors
        """
        if not self.trc:
            return [], True
        try:
            torrents = self.trc.get_torrents(ids=ids, arguments=self._trarg)
        except Exception as err:
            logger.error(f"Get seed list出错：{err}")
            return [], True
        if status and not isinstance(status, list):
            status = [status]
        if tags and not isinstance(tags, list):
            tags = [tags]
        ret_torrents = []
        for torrent in torrents:
            #  State filtering
            if status and torrent.status not in status:
                continue
            #  Seed labels
            labels = [str(tag).strip()
                      for tag in torrent.labels] if hasattr(torrent, "labels") else []
            if tags and not set(tags).issubset(set(labels)):
                continue
            ret_torrents.append(torrent)
        return ret_torrents, False

    def get_completed_torrents(self, ids: Union[str, list] = None,
                               tags: Union[str, list] = None) -> Optional[List[Torrent]]:
        """
        Get a list of completed seeds
        return  Seed list,  Returns when an error occursNone
        """
        if not self.trc:
            return None
        try:
            torrents, error = self.get_torrents(status=["seeding", "seed_pending"], ids=ids, tags=tags)
            return None if error else torrents or []
        except Exception as err:
            logger.error(f"Get a list of completed seeds出错：{err}")
            return None

    def get_downloading_torrents(self, ids: Union[str, list] = None,
                                 tags: Union[str, list] = None) -> Optional[List[Torrent]]:
        """
        Get a list of seeds being downloaded
        return  Seed list,  Returns when an error occursNone
        """
        if not self.trc:
            return None
        try:
            torrents, error = self.get_torrents(ids=ids,
                                                status=["downloading", "download_pending", "stopped"],
                                                tags=tags)
            return None if error else torrents or []
        except Exception as err:
            logger.error(f"Get a list of seeds being downloaded出错：{err}")
            return None

    def set_torrent_tag(self, ids: str, tags: list) -> bool:
        """
        Setting seed labels
        """
        if not self.trc:
            return False
        if not ids or not tags:
            return False
        try:
            self.trc.change_torrent(labels=tags, ids=ids)
            return True
        except Exception as err:
            logger.error(f"Setting seed labels出错：{err}")
            return False

    def add_torrent(self, content: Union[str, bytes],
                    is_paused: bool = False,
                    download_dir: str = None,
                    labels=None,
                    cookie=None) -> Optional[Torrent]:
        """
        Add download tasks
        :param content:  Torrenturls Or the contents of the document
        :param is_paused:  Pause after adding
        :param download_dir:  Download path
        :param labels:  Tab (of a window) (computing)
        :param cookie:  WebsiteCookie Used to assist in downloading seeds
        :return: Torrent
        """
        if not self.trc:
            return None
        try:
            return self.trc.add_torrent(torrent=content,
                                        download_dir=download_dir,
                                        paused=is_paused,
                                        labels=labels,
                                        cookies=cookie)
        except Exception as err:
            logger.error(f" Error adding seed：{err}")
            return None

    def start_torrents(self, ids: Union[str, list]) -> bool:
        """
        Seeding
        """
        if not self.trc:
            return False
        try:
            self.trc.start_torrent(ids=ids)
            return True
        except Exception as err:
            logger.error(f"Seeding出错：{err}")
            return False

    def stop_torrents(self, ids: Union[str, list]) -> bool:
        """
        Stop seed
        """
        if not self.trc:
            return False
        try:
            self.trc.stop_torrent(ids=ids)
            return True
        except Exception as err:
            logger.error(f"Stop seed出错：{err}")
            return False

    def delete_torrents(self, delete_file: bool, ids: Union[str, list]) -> bool:
        """
        Delete seeds
        """
        if not self.trc:
            return False
        if not ids:
            return False
        try:
            self.trc.remove_torrent(delete_data=delete_file, ids=ids)
            return True
        except Exception as err:
            logger.error(f"Delete seeds出错：{err}")
            return False

    def get_files(self, tid: str) -> Optional[List[File]]:
        """
        Get a list of seed files
        """
        if not self.trc:
            return None
        if not tid:
            return None
        try:
            torrent = self.trc.get_torrent(tid)
        except Exception as err:
            logger.error(f"Get a list of seed files出错：{err}")
            return None
        if torrent:
            return torrent.files()
        else:
            return None

    def set_files(self, tid: str, file_ids: list) -> bool:
        """
        Setting the status of downloaded files
        """
        if not self.trc:
            return False
        try:
            self.trc.change_torrent(ids=tid, files_wanted=file_ids)
            return True
        except Exception as err:
            logger.error(f" Error setting download file status：{err}")
            return False

    def transfer_info(self) -> Optional[SessionStats]:
        """
        Getting transmission information
        """
        if not self.trc:
            return None
        try:
            return self.trc.session_stats()
        except Exception as err:
            logger.error(f"Getting transmission information出错：{err}")
            return None

    def set_speed_limit(self, download_limit: float = None, upload_limit: float = None) -> bool:
        """
        Setting speed limits
        :param download_limit:  Download speed limit， Work unit (one's workplace)KB/s
        :param upload_limit:  Upload speed limit， Work unit (one's workplace)kB/s
        """
        if not self.trc:
            return False
        try:
            download_limit_enabled = True if download_limit else False
            upload_limit_enabled = True if upload_limit else False
            self.trc.set_session(
                speed_limit_down=int(download_limit),
                speed_limit_up=int(upload_limit),
                speed_limit_down_enabled=download_limit_enabled,
                speed_limit_up_enabled=upload_limit_enabled
            )
            return True
        except Exception as err:
            logger.error(f"Setting speed limits出错：{err}")
            return False

    def recheck_torrents(self, ids: Union[str, list]):
        """
        Re-calibrate seeds
        """
        if not self.trc:
            return False
        try:
            return self.trc.verify_torrent(ids=ids)
        except Exception as err:
            logger.error(f"Re-calibrate seeds出错：{err}")
            return False

    def add_trackers(self, ids: Union[str, list], trackers: list):
        """
        IncreaseTracker
        """
        if not self.trc:
            return False
        try:
            return self.trc.change_torrent(ids=ids, tracker_list=[trackers])
        except Exception as err:
            logger.error(f"IncreaseTracker出错：{err}")
            return False

    def change_torrent(self,
                       hash_string: str,
                       upload_limit=None,
                       download_limit=None,
                       ratio_limit=None,
                       seeding_time_limit=None):
        """
        Setting the seed
        :param hash_string: ID
        :param upload_limit:  Upload speed limit Kb/s
        :param download_limit:  Download speed limit Kb/s
        :param ratio_limit:  Sharing rate limit
        :param seeding_time_limit:  Time limit for seeding
        :return: bool
        """
        if not hash_string:
            return False
        if upload_limit:
            uploadLimited = True
            uploadLimit = int(upload_limit)
        else:
            uploadLimited = False
            uploadLimit = 0
        if download_limit:
            downloadLimited = True
            downloadLimit = int(download_limit)
        else:
            downloadLimited = False
            downloadLimit = 0
        if ratio_limit:
            seedRatioMode = 1
            seedRatioLimit = round(float(ratio_limit), 2)
        else:
            seedRatioMode = 2
            seedRatioLimit = 0
        if seeding_time_limit:
            seedIdleMode = 1
            seedIdleLimit = int(seeding_time_limit)
        else:
            seedIdleMode = 2
            seedIdleLimit = 0
        try:
            self.trc.change_torrent(ids=hash_string,
                                    uploadLimited=uploadLimited,
                                    uploadLimit=uploadLimit,
                                    downloadLimited=downloadLimited,
                                    downloadLimit=downloadLimit,
                                    seedRatioMode=seedRatioMode,
                                    seedRatioLimit=seedRatioLimit,
                                    seedIdleMode=seedIdleMode,
                                    seedIdleLimit=seedIdleLimit)
        except Exception as err:
            logger.error(f"Setting the seed出错：{err}")
            return False
