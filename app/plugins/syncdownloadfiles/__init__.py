import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.transferhistory_oper import TransferHistoryOper
from app.log import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase


class SyncDownloadFiles(_PluginBase):
    #  Plug-in name
    plugin_name = " Downloader file synchronization"
    #  Plugin description
    plugin_desc = " Synchronize downloader file information to database， Delete download tasks when deleting files。"
    #  Plug-in icons
    plugin_icon = "sync_file.png"
    #  Theme color
    plugin_color = "#4686E3"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "syncdownloadfiles_"
    #  Loading sequence
    plugin_order = 20
    #  Available user levels
    auth_level = 1

    #  Private property
    _enabled = False
    #  Task execution interval
    _time = None
    qb = None
    tr = None
    _onlyonce = False
    _history = False
    _clear = False
    _downloaders = []
    _dirs = None
    downloadhis = None
    transferhis = None

    #  Timers
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        #  Discontinuation of existing mandates
        self.stop_service()

        self.qb = Qbittorrent()
        self.tr = Transmission()
        self.downloadhis = DownloadHistoryOper(self.db)
        self.transferhis = TransferHistoryOper(self.db)

        if config:
            self._enabled = config.get('enabled')
            self._time = config.get('time') or 6
            self._history = config.get('history')
            self._clear = config.get('clear')
            self._onlyonce = config.get("onlyonce")
            self._downloaders = config.get('downloaders') or []
            self._dirs = config.get("dirs") or ""

        if self._clear:
            #  Clear downloader file logs
            self.downloadhis.truncate_files()
            #  Clearing the downloader's last processed record
            for downloader in self._downloaders:
                #  Get the last synchronization time
                self.del_data(f"last_sync_time_{downloader}")
            #  Clotureclear
            self._clear = False
            self.__update_config()

        if self._onlyonce:
            #  Execute once
            #  Clotureonlyonce
            self._onlyonce = False
            self.__update_config()

            self.sync()

        if self._enabled:
            #  Time service
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._time:
                try:
                    self._scheduler.add_job(func=self.sync,
                                            trigger="interval",
                                            hours=float(str(self._time).strip()),
                                            name=" Automatic synchronization of downloader file records")
                    logger.info(f" Automatic synchronization of downloader file logging service startup， Time interval {self._time}  Hourly")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")

                #  Initiate tasks
                if self._scheduler.get_jobs():
                    self._scheduler.print_jobs()
                    self._scheduler.start()
            else:
                self._enabled = False
                self.__update_config()

    def sync(self):
        """
        Synchronize selected downloader seed records
        """
        start_time = datetime.now()
        logger.info(" Start synchronizing downloader task file records")

        if not self._downloaders:
            logger.error(" Synchronized downloader not selected， Stop running")
            return

        #  Iterate over downloader synchronization records
        for downloader in self._downloaders:
            #  Get the last synchronization time
            last_sync_time = self.get_data(f"last_sync_time_{downloader}")

            logger.info(f" Start scanning the downloader {downloader} ...")
            downloader_obj = self.__get_downloader(downloader)
            #  Getting completed seeds in the downloader
            torrents = downloader_obj.get_completed_torrents()
            if torrents:
                logger.info(f" Downloader {downloader}  Number of seeds completed：{len(torrents)}")
            else:
                logger.info(f" Downloader {downloader}  No completed seeds")
                continue

            #  Grouping seeds by name and seed size， Get the one with the earliest add time， Determined to be a source seed， The rest are auxiliary species
            torrents = self.__get_origin_torrents(torrents, downloader)
            logger.info(f" Downloader {downloader}  Removal of auxiliary species， Number of source seeds obtained：{len(torrents)}")

            for torrent in torrents:
                #  Come (or go) backfalse， Identifies that subsequent seeds have been synchronized
                sync_flag = self.__compare_time(torrent, downloader, last_sync_time)

                if not sync_flag:
                    logger.info(f" Final synchronization time{last_sync_time},  Seeds were previously synchronized， End current downloader {downloader}  Mandates")
                    break

                #  Getting seedshash
                hash_str = self.__get_hash(torrent, downloader)

                #  Determine if it ismp Downloading， Judgementsdownload_hash Whether or notdownloadhistory Statistical tables， Yes, not processed
                downloadhis = self.downloadhis.get_by_hash(hash_str)
                if downloadhis:
                    downlod_files = self.downloadhis.get_files_by_hash(hash_str)
                    if downlod_files:
                        logger.info(f" Torrent {hash_str}  Pass (a bill or inspection etc)MoviePilot Downloading， Skip processing")
                        continue

                #  Getting seedsdownload_dir
                download_dir = self.__get_download_dir(torrent, downloader)

                #  Handling path mapping
                if self._dirs:
                    paths = self._dirs.split("\n")
                    for path in paths:
                        sub_paths = path.split(":")
                        download_dir = download_dir.replace(sub_paths[0], sub_paths[1]).replace('\\', '/')

                #  Getting seedsname
                torrent_name = self.__get_torrent_name(torrent, downloader)
                #  Seed saving catalog
                save_path = Path(download_dir).joinpath(torrent_name)
                #  Getting the seed file
                torrent_files = self.__get_torrent_files(torrent, downloader, downloader_obj)
                logger.info(f" Start synchronizing seeds {hash_str},  Number of documents {len(torrent_files)}")

                download_files = []
                for file in torrent_files:
                    #  Filtering out un-downloaded files
                    if not self.__is_download(file, downloader):
                        continue
                    #  Seed file path
                    file_path_str = self.__get_file_path(file, downloader)
                    file_path = Path(file_path_str)
                    #  Handles only video formats
                    if not file_path.suffix \
                            or file_path.suffix not in settings.RMT_MEDIAEXT:
                        continue
                    #  Seed file root path
                    root_path = file_path.parts[0]
                    #  Relative path to the seed file without the seed name
                    if root_path == torrent_name:
                        rel_path = str(file_path.relative_to(root_path))
                    else:
                        rel_path = str(file_path)
                    #  Full path
                    full_path = save_path.joinpath(rel_path)
                    if self._history:
                        transferhis = self.transferhis.get_by_src(str(full_path))
                        if transferhis and not transferhis.download_hash:
                            logger.info(f" Commencement of replenishment of transfer records：{transferhis.id} download_hash {hash_str}")
                            self.transferhis.update_download_hash(historyid=transferhis.id,
                                                                  download_hash=hash_str)

                    #  Seed documentation records
                    download_files.append(
                        {
                            "download_hash": hash_str,
                            "downloader": downloader,
                            "fullpath": str(full_path),
                            "savepath": str(save_path),
                            "filepath": rel_path,
                            "torrentname": torrent_name,
                        }
                    )

                if download_files:
                    #  Register to download files
                    self.downloadhis.add_files(download_files)
                logger.info(f" Torrent {hash_str}  Synchronized completion")

            logger.info(f" Downloader seed file synchronization complete！")
            self.save_data(f"last_sync_time_{downloader}",
                           time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))

            #  Computational time
            end_time = datetime.now()

            logger.info(f" Downloader task file record synchronization completed。 Total time consumption {(end_time - start_time).seconds}  Unit of angle or arc equivalent one sixtieth of a degree")

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "time": self._time,
            "history": self._history,
            "clear": self._clear,
            "onlyonce": self._onlyonce,
            "downloaders": self._downloaders,
            "dirs": self._dirs
        })

    @staticmethod
    def __get_origin_torrents(torrents: Any, dl_tpe: str):
        #  Grouping seeds by name and seed size， Get the one with the earliest add time， Determined to be a source seed， The rest are auxiliary species
        grouped_data = {}

        #  Sorting seeds， Seeds added in reverse chronological order
        if dl_tpe == "qbittorrent":
            torrents = sorted(torrents, key=lambda x: x.get("added_on"), reverse=True)
            #  Iterate over the original array， On the basis ofsize Cap (a poem)name Cluster
            for torrent in torrents:
                size = torrent.get('size')
                name = torrent.get('name')
                key = (size, name)  #  Using tuples as keys for dictionaries

                #  If the grouping key does not exist， Then the current element is added to the dictionary as the smallest element
                if key not in grouped_data:
                    grouped_data[key] = torrent
                else:
                    #  If the grouping key already exists， Then compares the current element'stime Is it smaller， Update elements in the dictionary if smaller
                    if torrent.get('added_on') < grouped_data[key].get('added_on'):
                        grouped_data[key] = torrent
        else:
            torrents = sorted(torrents, key=lambda x: x.added_date, reverse=True)
            #  Iterate over the original array， On the basis ofsize Cap (a poem)name Cluster
            for torrent in torrents:
                size = torrent.total_size
                name = torrent.name
                key = (size, name)  #  Using tuples as keys for dictionaries

                #  If the grouping key does not exist， Then the current element is added to the dictionary as the smallest element
                if key not in grouped_data:
                    grouped_data[key] = torrent
                else:
                    #  If the grouping key already exists， Then compares the current element'stime Is it smaller， Update elements in the dictionary if smaller
                    if torrent.added_date < grouped_data[key].added_date:
                        grouped_data[key] = torrent

        #  New arrays
        return list(grouped_data.values())

    @staticmethod
    def __compare_time(torrent: Any, dl_tpe: str, last_sync_time: str = None):
        if last_sync_time:
            #  Getting seed time
            if dl_tpe == "qbittorrent":
                torrent_date = time.gmtime(torrent.get("added_on"))  #  Converting timestamps to time tuples
                torrent_date = time.strftime("%Y-%m-%d %H:%M:%S", torrent_date)  #  Formatting time
            else:
                torrent_date = torrent.added_date

            #  The seeds after that have been synchronized
            if last_sync_time > str(torrent_date):
                return False

        return True

    @staticmethod
    def __is_download(file: Any, dl_type: str):
        """
        Determine if a file has been downloaded
        """
        try:
            if dl_type == "qbittorrent":
                return True
            else:
                return file.completed and file.completed > 0
        except Exception as e:
            print(str(e))
            return True

    @staticmethod
    def __get_file_path(file: Any, dl_type: str):
        """
        Get file path
        """
        try:
            return file.get("name") if dl_type == "qbittorrent" else file.name
        except Exception as e:
            print(str(e))
            return ""

    @staticmethod
    def __get_torrent_files(torrent: Any, dl_type: str, downloader_obj):
        """
        Getting the seed file
        """
        try:
            return torrent.files if dl_type == "qbittorrent" else downloader_obj.get_files(tid=torrent.id)
        except Exception as e:
            print(str(e))
            return ""

    @staticmethod
    def __get_torrent_name(torrent: Any, dl_type: str):
        """
        Getting seedsname
        """
        try:
            return torrent.get("name") if dl_type == "qbittorrent" else torrent.name
        except Exception as e:
            print(str(e))
            return ""

    @staticmethod
    def __get_download_dir(torrent: Any, dl_type: str):
        """
        Getting seedsdownload_dir
        """
        try:
            return torrent.get("save_path") if dl_type == "qbittorrent" else torrent.download_dir
        except Exception as e:
            print(str(e))
            return ""

    @staticmethod
    def __get_hash(torrent: Any, dl_type: str):
        """
        Getting seedshash
        """
        try:
            return torrent.get("hash") if dl_type == "qbittorrent" else torrent.hashString
        except Exception as e:
            print(str(e))
            return ""

    def __get_downloader(self, dtype: str):
        """
        Returns downloader instances by type
        """
        if dtype == "qbittorrent":
            return self.qb
        elif dtype == "transmission":
            return self.tr
        else:
            return None

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Assembly plugin configuration page， Two pieces of data need to be returned：1、 Page configuration；2、 Data structure
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': ' Enabling plug-ins',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': ' Run one immediately',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'history',
                                            'label': ' Supplementing and organizing historical records',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'clear',
                                            'label': ' Cleaning of data',
                                        }
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'time',
                                            'label': ' Synchronization interval'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'downloaders',
                                            'label': ' Synchronous downloader',
                                            'items': [
                                                {'title': 'Qbittorrent', 'value': 'qbittorrent'},
                                                {'title': 'Transmission', 'value': 'transmission'}
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'dirs',
                                            'label': ' Directory map',
                                            'rows': 5,
                                            'placeholder': ' One directory per line， Downloader save directory:MoviePilot Mapping directory'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'text': ' Suitable for nonMoviePilot Downloaded tasks； When the downloader has more seed data， Synchronization will take longer， Please be patient.， Real-time logs can be viewed for synchronization progress； The time interval is recommended to be at least every6 Performed once an hour， In case the last task was not completed。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "history": False,
            "clear": False,
            "time": 6,
            "dirs": "",
            "downloaders": []
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        Exit plugin
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("Exit plugin失败：%s" % str(e))
