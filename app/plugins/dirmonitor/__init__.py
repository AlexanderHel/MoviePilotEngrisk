import re
import shutil
import threading
import traceback
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import List, Tuple, Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.chain.tmdb import TmdbChain
from app.chain.transfer import TransferChain
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.metainfo import MetaInfoPath
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.transferhistory_oper import TransferHistoryOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import Notification, NotificationType, TransferInfo
from app.schemas.types import EventType, MediaType, SystemConfigKey
from app.utils.string import StringUtils
from app.utils.system import SystemUtils

lock = threading.Lock()


class FileMonitorHandler(FileSystemEventHandler):
    """
    Catalog monitor response class
    """

    def __init__(self, monpath: str, sync: Any, **kwargs):
        super(FileMonitorHandler, self).__init__(**kwargs)
        self._watch_path = monpath
        self.sync = sync

    def on_created(self, event):
        self.sync.event_handler(event=event, text=" Establish",
                                mon_path=self._watch_path, event_path=event.src_path)

    def on_moved(self, event):
        self.sync.event_handler(event=event, text=" Mobility",
                                mon_path=self._watch_path, event_path=event.dest_path)


class DirMonitor(_PluginBase):
    #  Plug-in name
    plugin_name = " Catalog monitoring"
    #  Plugin description
    plugin_desc = " Monitor changes to directory files and organize them in the media library in real time.。"
    #  Plug-in icons
    plugin_icon = "directory.png"
    #  Theme color
    plugin_color = "#E0995E"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "dirmonitor_"
    #  Loading sequence
    plugin_order = 4
    #  Available user levels
    auth_level = 1

    #  Private property
    _scheduler = None
    transferhis = None
    downloadhis = None
    transferchian = None
    tmdbchain = None
    _observer = []
    _enabled = False
    _notify = False
    #  Paradigm compatibility/fast
    _mode = "fast"
    #  Migration pattern
    _transfer_type = settings.TRANSFER_TYPE
    _monitor_dirs = ""
    _exclude_keywords = ""
    #  Store source and destination directory relationships
    _dirconf: Dict[str, Path] = {}
    #  Storage source catalog transfer method
    _transferconf: Dict[str, str] = {}
    _medias = {}
    #  Logout event
    _event = Event()

    def init_plugin(self, config: dict = None):
        self.transferhis = TransferHistoryOper(self.db)
        self.downloadhis = DownloadHistoryOper(self.db)
        self.transferchian = TransferChain(self.db)
        self.tmdbchain = TmdbChain(self.db)
        #  Clear configuration
        self._dirconf = {}
        self._transferconf = {}

        #  Read configuration
        if config:
            self._enabled = config.get("enabled")
            self._notify = config.get("notify")
            self._mode = config.get("mode")
            self._transfer_type = config.get("transfer_type")
            self._monitor_dirs = config.get("monitor_dirs") or ""
            self._exclude_keywords = config.get("exclude_keywords") or ""

        #  Discontinuation of existing mandates
        self.stop_service()

        if self._enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            #  Initiate tasks
            monitor_dirs = self._monitor_dirs.split("\n")
            if not monitor_dirs:
                return
            for mon_path in monitor_dirs:
                #  Format source catalog: Destination catalog
                if not mon_path:
                    continue

                #  Customizing the transfer method
                _transfer_type = self._transfer_type
                if mon_path.count("#") == 1:
                    _transfer_type = mon_path.split("#")[1]
                    mon_path = mon_path.split("#")[0]

                #  Storage destination directory
                if SystemUtils.is_windows():
                    if mon_path.count(":") > 1:
                        paths = [mon_path.split(":")[0] + ":" + mon_path.split(":")[1],
                                 mon_path.split(":")[2] + ":" + mon_path.split(":")[3]]
                    else:
                        paths = [mon_path]
                else:
                    paths = mon_path.split(":")

                # 目的目录
                target_path = None
                if len(paths) > 1:
                    mon_path = paths[0]
                    target_path = Path(paths[1])
                    self._dirconf[mon_path] = target_path

                #  Migration pattern
                self._transferconf[mon_path] = _transfer_type

                #  Check that the media library directory is not a subdirectory of the download directory
                try:
                    if target_path and target_path.is_relative_to(Path(mon_path)):
                        logger.warn(f"{target_path}  Is the download directory {mon_path}  Subdirectories， Unmonitored")
                        self.systemmessage.put(f"{target_path}  Is the download directory {mon_path}  Subdirectories， Unmonitored")
                        continue
                except Exception as e:
                    logger.debug(str(e))
                    pass

                try:
                    if self._mode == "compatibility":
                        #  Compatibility mode， Reduced directory synchronization performance andNAS Cannot hibernate， However, it is compatible with mounted remote shared directories such asSMB
                        observer = PollingObserver(timeout=10)
                    else:
                        #  Selection of the optimal solution for the type of operation of the internal processing system
                        observer = Observer(timeout=10)
                    self._observer.append(observer)
                    observer.schedule(FileMonitorHandler(mon_path, self), path=mon_path, recursive=True)
                    observer.daemon = True
                    observer.start()
                    logger.info(f"{mon_path}  The catalog monitoring service starts")
                except Exception as e:
                    err_msg = str(e)
                    if "inotify" in err_msg and "reached" in err_msg:
                        logger.warn(
                            f" Abnormal startup of the catalog monitoring service：{err_msg}， On the host computer, please（ Faultdocker Container） Execute the following command and reboot："
                            + """
                                 echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
                                 echo fs.inotify.max_user_instances=524288 | sudo tee -a /etc/sysctl.conf
                                 sudo sysctl -p
                                 """)
                    else:
                        logger.error(f"{mon_path}  Failed to start directory monitoring：{err_msg}")
                    self.systemmessage.put(f"{mon_path}  Failed to start directory monitoring：{err_msg}")

            #  Harmonized service for the delivery of additional inbound messages
            self._scheduler.add_job(self.send_msg, trigger='interval', seconds=15)
            #  Starting services
            self._scheduler.print_jobs()
            self._scheduler.start()

    def event_handler(self, event, mon_path: str, text: str, event_path: str):
        """
        Processing of document changes
        :param event:  Event
        :param mon_path:  Monitor catalog
        :param text:  Event description
        :param event_path:  Event file path
        """
        if not event.is_directory:
            #  Changes in documentation
            file_path = Path(event_path)
            try:
                if not file_path.exists():
                    return

                logger.debug(" File%s：%s" % (text, event_path))

                #  Fully locked
                with lock:
                    transfer_history = self.transferhis.get_by_src(event_path)
                    if transfer_history:
                        logger.debug(" Documentation has been processed：%s" % event_path)
                        return

                    #  Recycle bin and hidden files not handled
                    if event_path.find('/@Recycle/') != -1 \
                            or event_path.find('/#recycle/') != -1 \
                            or event_path.find('/.') != -1 \
                            or event_path.find('/@eaDir') != -1:
                        logger.debug(f"{event_path}  It's the recycle bin or hidden files")
                        return

                    #  Hit filter keywords are not processed
                    if self._exclude_keywords:
                        for keyword in self._exclude_keywords.split("\n"):
                            if keyword and re.findall(keyword, event_path):
                                logger.info(f"{event_path}  Hit filter keywords {keyword}， Not dealt with")
                                return

                    #  Sorting out blocked words not dealt with
                    transfer_exclude_words = self.systemconfig.get(SystemConfigKey.TransferExcludeWords)
                    if transfer_exclude_words:
                        for keyword in transfer_exclude_words:
                            if not keyword:
                                continue
                            if keyword and re.search(r"%s" % keyword, event_path, re.IGNORECASE):
                                logger.info(f"{event_path}  Hit listener's blocking words (computing) {keyword}， Not dealt with")
                                return

                    #  Not media files are not processed
                    if file_path.suffix not in settings.RMT_MEDIAEXT:
                        logger.debug(f"{event_path}  It's not a media file.")
                        return

                    #  Query history， Transferred not processed
                    if self.transferhis.get_by_src(event_path):
                        logger.info(f"{event_path}  Organized.")
                        return

                    #  Metadata
                    file_meta = MetaInfoPath(file_path)
                    if not file_meta.name:
                        logger.error(f"{file_path.name}  Unable to recognize valid information")
                        return

                    #  Query the transfer destination directory
                    target: Path = self._dirconf.get(mon_path)
                    #  Enquire about the transfer method
                    transfer_type = self._transferconf.get(mon_path)

                    #  Identify media messages
                    mediainfo: MediaInfo = self.chain.recognize_media(meta=file_meta)
                    if not mediainfo:
                        logger.warn(f' No media messages recognized， Caption：{file_meta.name}')
                        if self._notify:
                            self.chain.post_message(Notification(
                                mtype=NotificationType.Manual,
                                title=f"{file_path.name}  No media messages recognized， Out of stock！"
                            ))
                        #  Add transfer success history
                        self.transferhis.add_fail(
                            src_path=file_path,
                            mode=transfer_type,
                            meta=file_meta
                        )
                        return

                    #  If not enabled does the new inbound media follow theTMDB Information changes are then based ontmdbid Query the previoustitle
                    if not settings.SCRAP_FOLLOW_TMDB:
                        transfer_history = self.transferhis.get_by_type_tmdbid(tmdbid=mediainfo.tmdb_id,
                                                                               mtype=mediainfo.type.value)
                        if transfer_history:
                            mediainfo.title = transfer_history.title
                    logger.info(f"{file_path.name}  Identify as：{mediainfo.type.value} {mediainfo.title_year}")

                    #  Updating media images
                    self.chain.obtain_images(mediainfo=mediainfo)

                    #  Get set data
                    if mediainfo.type == MediaType.TV:
                        episodes_info = self.tmdbchain.tmdb_episodes(tmdbid=mediainfo.tmdb_id,
                                                                     season=file_meta.begin_season or 1)
                    else:
                        episodes_info = None

                    #  Gaindownloadhash
                    download_hash = self.get_download_hash(src=str(file_path))

                    #  Divert or distract (attention etc)
                    transferinfo: TransferInfo = self.chain.transfer(mediainfo=mediainfo,
                                                                     path=file_path,
                                                                     transfer_type=transfer_type,
                                                                     target=target,
                                                                     meta=file_meta,
                                                                     episodes_info=episodes_info)

                    if not transferinfo:
                        logger.error(" Failure to run the file transfer module")
                        return
                    if not transferinfo.success:
                        #  Divert or distract (attention etc)失败
                        logger.warn(f"{file_path.name}  Failure to stock：{transferinfo.message}")
                        #  Added transfer failure history
                        self.transferhis.add_fail(
                            src_path=file_path,
                            mode=transfer_type,
                            download_hash=download_hash,
                            meta=file_meta,
                            mediainfo=mediainfo,
                            transferinfo=transferinfo
                        )
                        if self._notify:
                            self.chain.post_message(Notification(
                                title=f"{mediainfo.title_year}{file_meta.season_episode}  Failure to stock！",
                                text=f" Rationale：{transferinfo.message or ' Uncharted'}",
                                image=mediainfo.get_message_image()
                            ))
                        return

                    #  Add transfer success history
                    self.transferhis.add_success(
                        src_path=file_path,
                        mode=transfer_type,
                        download_hash=download_hash,
                        meta=file_meta,
                        mediainfo=mediainfo,
                        transferinfo=transferinfo
                    )

                    #  Scraping of individual documents
                    if settings.SCRAP_METADATA:
                        self.chain.scrape_metadata(path=transferinfo.target_path,
                                                   mediainfo=mediainfo)

                    """
                    {
                        "title_year season": {
                            "files": [
                                {
                                    "path":,
                                    "mediainfo":,
                                    "file_meta":,
                                    "transferinfo":
                                }
                            ],
                            "time": "2023-08-24 23:23:23.332"
                        }
                    }
                    """
                    #  Send message summary
                    media_list = self._medias.get(mediainfo.title_year + " " + file_meta.season) or {}
                    if media_list:
                        media_files = media_list.get("files") or []
                        if media_files:
                            file_exists = False
                            for file in media_files:
                                if str(event_path) == file.get("path"):
                                    file_exists = True
                                    break
                            if not file_exists:
                                media_files.append({
                                    "path": event_path,
                                    "mediainfo": mediainfo,
                                    "file_meta": file_meta,
                                    "transferinfo": transferinfo
                                })
                            else:
                                media_files = [
                                    {
                                        "path": event_path,
                                        "mediainfo": mediainfo,
                                        "file_meta": file_meta,
                                        "transferinfo": transferinfo
                                    }
                                ]
                        media_list = {
                            "files": media_files,
                            "time": datetime.now()
                        }
                    else:
                        media_list = {
                            "files": [
                                {
                                    "path": event_path,
                                    "mediainfo": mediainfo,
                                    "file_meta": file_meta,
                                    "transferinfo": transferinfo
                                }
                            ],
                            "time": datetime.now()
                        }
                    self._medias[mediainfo.title_year + " " + file_meta.season] = media_list

                    #  Aggregate refresh media library
                    if settings.REFRESH_MEDIASERVER:
                        self.chain.refresh_mediaserver(mediainfo=mediainfo, file_path=transferinfo.target_path)
                    #  Broadcasting incident
                    self.eventmanager.send_event(EventType.TransferComplete, {
                        'meta': file_meta,
                        'mediainfo': mediainfo,
                        'transferinfo': transferinfo
                    })

                    #  Remove empty directories in mobile mode
                    if transfer_type == "move":
                        for file_dir in file_path.parents:
                            if len(str(file_dir)) <= len(str(Path(mon_path))):
                                #  Critical， Delete until you reach the monitoring directory
                                break
                            files = SystemUtils.list_files(file_dir, settings.RMT_MEDIAEXT)
                            if not files:
                                logger.warn(f" Mobile mode， Delete empty directories：{file_dir}")
                                shutil.rmtree(file_dir, ignore_errors=True)

            except Exception as e:
                logger.error(" An error occurred in catalog monitoring：%s - %s" % (str(e), traceback.format_exc()))

    def send_msg(self):
        """
        Regularly check to see if any media has been processed， Send unified messages
        """
        if not self._medias or not self._medias.keys():
            return

        #  Iterate to check if scraping is complete， Send a message
        for medis_title_year_season in list(self._medias.keys()):
            media_list = self._medias.get(medis_title_year_season)
            logger.info(f" Start processing media {medis_title_year_season}  Messages")

            if not media_list:
                continue

            #  Get last update time
            last_update_time = media_list.get("time")
            media_files = media_list.get("files")
            if not last_update_time or not media_files:
                continue

            transferinfo = media_files[0].get("transferinfo")
            file_meta = media_files[0].get("file_meta")
            mediainfo = media_files[0].get("mediainfo")
            #  Determine if the last update is more than5 Unit of angle or arc equivalent one sixtieth of a degree， If exceeded, a message is sent
            if (datetime.now() - last_update_time).total_seconds() > 5:
                #  Send notification
                if self._notify:

                    #  Aggregate total size of processed documents
                    total_size = 0
                    file_count = 0

                    #  Episode summary
                    episodes = []
                    for file in media_files:
                        transferinfo = file.get("transferinfo")
                        total_size += transferinfo.total_size
                        file_count += 1

                        file_meta = file.get("file_meta")
                        if file_meta and file_meta.begin_episode:
                            episodes.append(file_meta.begin_episode)

                    transferinfo.total_size = total_size
                    #  Summary of the number of documents processed
                    transferinfo.file_count = file_count

                    #  Episode season information S01 E01-E04 || S01 E01、E02、E04
                    season_episode = None
                    #  High number of documents processed， Description is episodic， Show seasonal inventory news
                    if mediainfo.type == MediaType.TV:
                        #  Quarterly texts
                        season_episode = f"{file_meta.season} {StringUtils.format_ep(episodes)}"
                    #  Send a message
                    self.transferchian.send_transfer_message(meta=file_meta,
                                                             mediainfo=mediainfo,
                                                             transferinfo=transferinfo,
                                                             season_episode=season_episode)
                #  After sending the message， Move outkey
                del self._medias[medis_title_year_season]
                continue

    def get_download_hash(self, src: str):
        """
        Get from tabledownload_hash， Avoid connecting to the downloader
        """
        downloadHis = self.downloadhis.get_file_by_fullpath(src)
        if downloadHis:
            return downloadHis.download_hash
        return None

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
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
                                    'md': 6
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
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': ' Send notification',
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
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'mode',
                                            'label': ' Monitoring mode',
                                            'items': [
                                                {'title': ' Compatibility mode', 'value': 'compatibility'},
                                                {'title': ' Performance mode', 'value': 'fast'}
                                            ]
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
                                            'model': 'transfer_type',
                                            'label': ' Migration pattern',
                                            'items': [
                                                {'title': ' Mobility', 'value': 'move'},
                                                {'title': ' Make a copy of', 'value': 'copy'},
                                                {'title': ' Hard link', 'value': 'link'},
                                                {'title': ' Soft link (computing)', 'value': 'softlink'}
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
                                            'model': 'monitor_dirs',
                                            'label': ' Monitor catalog',
                                            'rows': 5,
                                            'placeholder': ' One directory per line， Three configuration methods are supported：\n'
                                                           ' Monitor catalog\n'
                                                           ' Monitor catalog# Migration pattern（move|copy|link|softlink|rclone_copy|rclone_move）\n'
                                                           ' Monitor catalog: Transfer purpose catalog（ You must also configure the destination directory in the media library directory.）\n'
                                                           ' Monitor catalog: Transfer purpose catalog# Migration pattern（move|copy|link|softlink|rclone_copy|rclone_move）'
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
                                            'model': 'exclude_keywords',
                                            'label': ' Exclude keywords',
                                            'rows': 2,
                                            'placeholder': ' One keyword per line'
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
            "notify": False,
            "mode": "fast",
            "transfer_type": settings.TRANSFER_TYPE,
            "monitor_dirs": "",
            "exclude_keywords": ""
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        Exit plugin
        """
        if self._observer:
            for observer in self._observer:
                try:
                    observer.stop()
                    observer.join()
                except Exception as e:
                    print(str(e))
        self._observer = []
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._event.set()
                self._scheduler.shutdown()
                self._event.clear()
            self._scheduler = None
