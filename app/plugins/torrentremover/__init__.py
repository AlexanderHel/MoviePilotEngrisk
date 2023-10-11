import re
import threading
import time
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.string import StringUtils

lock = threading.Lock()


class TorrentRemover(_PluginBase):
    #  Plug-in name
    plugin_name = " Automatic seed deletion"
    #  Plugin description
    plugin_desc = " Automatic deletion of download tasks in the downloader。"
    #  Plug-in icons
    plugin_icon = "torrent.png"
    #  Theme color
    plugin_color = "#02853F"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "torrentremover_"
    #  Loading sequence
    plugin_order = 8
    #  Available user levels
    auth_level = 2

    #  Private property
    qb = None
    tr = None
    _event = threading.Event()
    _scheduler = None
    _enabled = False
    _onlyonce = False
    _notify = False
    # pause/delete
    _downloaders = []
    _action = "pause"
    _cron = None
    _samedata = False
    _mponly = False
    _size = None
    _ratio = None
    _time = None
    _upspeed = None
    _labels = None
    _pathkeywords = None
    _trackerkeywords = None
    _errorkeywords = None
    _torrentstates = None
    _torrentcategorys = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._downloaders = config.get("downloaders") or []
            self._action = config.get("action")
            self._cron = config.get("cron")
            self._samedata = config.get("samedata")
            self._mponly = config.get("mponly")
            self._size = config.get("size") or ""
            self._ratio = config.get("ratio")
            self._time = config.get("time")
            self._upspeed = config.get("upspeed")
            self._labels = config.get("labels") or ""
            self._pathkeywords = config.get("pathkeywords") or ""
            self._trackerkeywords = config.get("trackerkeywords") or ""
            self._errorkeywords = config.get("errorkeywords") or ""
            self._torrentstates = config.get("torrentstates") or ""
            self._torrentcategorys = config.get("torrentcategorys") or ""

        self.stop_service()

        if self.get_state() or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self.qb = Qbittorrent()
            self.tr = Transmission()
            if self._cron:
                try:
                    self._scheduler.add_job(func=self.delete_torrents,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Automatic seed deletion service")
                    logger.info(f" Automated seed deletion service activation， Cyclicality：{self._cron}")
                except Exception as err:
                    logger.error(f" Failure to start the auto-delete seeding service：{str(err)}")
                    self.systemmessage.put(f" Failure to start the auto-delete seeding service：{str(err)}")
            if self._onlyonce:
                logger.info(f" Automated seed deletion service activation， Run one immediately")
                self._scheduler.add_job(func=self.delete_torrents, trigger='date',
                                        run_date=datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3)
                                        )
                #  Turn off the disposable switch
                self._onlyonce = False
                #  Save settings
                self.update_config({
                    "enabled": self._enabled,
                    "notify": self._notify,
                    "onlyonce": self._onlyonce,
                    "action": self._action,
                    "cron": self._cron,
                    "downloaders": self._downloaders,
                    "samedata": self._samedata,
                    "mponly": self._mponly,
                    "size": self._size,
                    "ratio": self._ratio,
                    "time": self._time,
                    "upspeed": self._upspeed,
                    "labels": self._labels,
                    "pathkeywords": self._pathkeywords,
                    "trackerkeywords": self._trackerkeywords,
                    "errorkeywords": self._errorkeywords,
                    "torrentstates": self._torrentstates,
                    "torrentcategorys": self._torrentcategorys

                })
            if self._scheduler.get_jobs():
                #  Starting services
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return True if self._enabled and self._cron and self._downloaders else False

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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': ' Implementation period',
                                            'placeholder': '0 */12 * * *'
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
                                            'model': 'action',
                                            'label': ' Movements',
                                            'items': [
                                                {'title': ' Pause (media player)', 'value': 'pause'},
                                                {'title': ' Delete seeds', 'value': 'delete'},
                                                {'title': ' Deleting seeds and files', 'value': 'deletefile'}
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
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'downloaders',
                                            'label': ' Downloader',
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
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'size',
                                            'label': ' Seed size（GB）',
                                            'placeholder': ' For example1-10'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'ratio',
                                            'label': ' Sharing rate',
                                            'placeholder': ''
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'time',
                                            'label': ' Time of planting（ Hourly）',
                                            'placeholder': ''
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'upspeed',
                                            'label': ' Average upload speed',
                                            'placeholder': ''
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'labels',
                                            'label': ' Tab (of a window) (computing)',
                                            'placeholder': ' Expense or outlay, Separate multiple tags'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'pathkeywords',
                                            'label': ' Save path keywords',
                                            'placeholder': ' Support for formal expressions'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'trackerkeywords',
                                            'label': 'Tracker Byword',
                                            'placeholder': ' Support for formal expressions'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'errorkeywords',
                                            'label': ' Error message keywords（TR）',
                                            'placeholder': ' Support for formal expressions， Only applicable toTR'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'torrentstates',
                                            'label': ' Mission status（QB）',
                                            'placeholder': ' Expense or outlay, Separating multiple states， Only applicable toQB'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'torrentcategorys',
                                            'label': ' Classification of tasks',
                                            'placeholder': ' Expense or outlay, Separate multiple classifications'
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'samedata',
                                            'label': ' Auxiliary species',
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
                                            'model': 'mponly',
                                            'label': ' MerelyMoviePilot Mandates',
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
                                            'text': ' Automatic seed deletion is risky， Improper settings may result in data loss！ Suggested action is to select pause first， Make sure the condition is correct before changing it to delete。'
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
            "onlyonce": False,
            "action": 'pause',
            'downloaders': [],
            "cron": '0 */12 * * *',
            "samedata": False,
            "mponly": False,
            "size": "",
            "ratio": "",
            "time": "",
            "upspeed": "",
            "labels": "",
            "pathkeywords": "",
            "trackerkeywords": "",
            "errorkeywords": "",
            "torrentstates": "",
            "torrentcategorys": ""
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
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            print(str(e))

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

    def delete_torrents(self):
        """
        Timed deletion of download tasks in downloader
        """
        for downloader in self._downloaders:
            try:
                with lock:
                    #  Get the list of seeds to be deleted
                    torrents = self.get_remove_torrents(downloader)
                    logger.info(f" Auto-deletion of seed tasks  Obtaining the number of seeds eligible for treatment {len(torrents)}")
                    #  Downloader
                    downlader_obj = self.__get_downloader(downloader)
                    if self._action == "pause":
                        message_text = f"{downloader.title()}  Total suspension{len(torrents)} Seed"
                        for torrent in torrents:
                            if self._event.is_set():
                                logger.info(f" Automatic seed censoring service discontinued")
                                return
                            text_item = f"{torrent.get('name')} " \
                                        f" From the site：{torrent.get('site')} " \
                                        f" Adults and children：{StringUtils.str_filesize(torrent.get('size'))}"
                            #  Suspension of seeds
                            downlader_obj.stop_torrents(ids=[torrent.get("id")])
                            logger.info(f" Auto-deletion of seed tasks  Suspension of seeds：{text_item}")
                            message_text = f"{message_text}\n{text_item}"
                    elif self._action == "delete":
                        message_text = f"{downloader.title()}  Total deleted{len(torrents)} Seed"
                        for torrent in torrents:
                            if self._event.is_set():
                                logger.info(f" Automatic seed censoring service discontinued")
                                return
                            text_item = f"{torrent.get('name')} " \
                                        f" From the site：{torrent.get('site')} " \
                                        f" Adults and children：{StringUtils.str_filesize(torrent.get('size'))}"
                            #  Delete seeds
                            downlader_obj.delete_torrents(delete_file=False,
                                                          ids=[torrent.get("id")])
                            logger.info(f" Auto-deletion of seed tasks  Delete seeds：{text_item}")
                            message_text = f"{message_text}\n{text_item}"
                    elif self._action == "deletefile":
                        message_text = f"{downloader.title()}  Total deleted{len(torrents)} Seeds and documents"
                        for torrent in torrents:
                            if self._event.is_set():
                                logger.info(f" Automatic seed censoring service discontinued")
                                return
                            text_item = f"{torrent.get('name')} " \
                                        f" From the site：{torrent.get('site')} " \
                                        f" Adults and children：{StringUtils.str_filesize(torrent.get('size'))}"
                            #  Delete seeds
                            downlader_obj.delete_torrents(delete_file=True,
                                                          ids=[torrent.get("id")])
                            logger.info(f" Auto-deletion of seed tasks  Deleting seeds and files：{text_item}")
                            message_text = f"{message_text}\n{text_item}"
                    else:
                        continue
                    if torrents and message_text and self._notify:
                        self.post_message(
                            mtype=NotificationType.SiteMessage,
                            title=f"【 Automatic seeding task completion】",
                            text=message_text
                        )
            except Exception as e:
                logger.error(f" Anomalies in automatic seed deletion tasks：{str(e)}")

    def __get_qb_torrent(self, torrent: Any) -> Optional[dict]:
        """
        ProbeQB Download task eligibility
        """
        #  Completion time
        date_done = torrent.completion_on if torrent.completion_on > 0 else torrent.added_on
        #  Current time
        date_now = int(time.mktime(datetime.now().timetuple()))
        #  Time of planting
        torrent_seeding_time = date_now - date_done if date_done else 0
        #  Average upload speed
        torrent_upload_avs = torrent.uploaded / torrent_seeding_time if torrent_seeding_time else 0
        #  Adults and children  Work unit (one's workplace)：GB
        sizes = self._size.split('-') if self._size else []
        minsize = sizes[0] * 1024 * 1024 * 1024 if sizes else 0
        maxsize = sizes[-1] * 1024 * 1024 * 1024 if sizes else 0
        #  Sharing rate
        if self._ratio and torrent.ratio <= float(self._ratio):
            return None
        #  Time of planting 单位：小时
        if self._time and torrent_seeding_time <= float(self._time) * 3600:
            return None
        #  File size
        if self._size and (torrent.size >= int(maxsize) or torrent.size <= int(minsize)):
            return None
        if self._upspeed and torrent_upload_avs >= float(self._upspeed) * 1024:
            return None
        if self._pathkeywords and not re.findall(self._pathkeywords, torrent.save_path, re.I):
            return None
        if self._trackerkeywords and not re.findall(self._trackerkeywords, torrent.tracker, re.I):
            return None
        if self._torrentstates and torrent.state not in self._torrentstates:
            return None
        if self._torrentcategorys and (not torrent.category or torrent.category not in self._torrentcategorys):
            return None
        return {
            "id": torrent.hash,
            "name": torrent.name,
            "site": StringUtils.get_url_sld(torrent.tracker),
            "size": torrent.size
        }

    def __get_tr_torrent(self, torrent: Any) -> Optional[dict]:
        """
        ProbeTR Download task eligibility
        """
        #  Completion time
        date_done = torrent.date_done or torrent.date_added
        #  Current time
        date_now = int(time.mktime(datetime.now().timetuple()))
        #  Time of planting
        torrent_seeding_time = date_now - int(time.mktime(date_done.timetuple())) if date_done else 0
        #  Upload volume
        torrent_uploaded = torrent.ratio * torrent.total_size
        #  Average upload speed
        torrent_upload_avs = torrent_uploaded / torrent_seeding_time if torrent_seeding_time else 0
        #  Adults and children  Work unit (one's workplace)：GB
        sizes = self._size.split('-') if self._size else []
        minsize = sizes[0] * 1024 * 1024 * 1024 if sizes else 0
        maxsize = sizes[-1] * 1024 * 1024 * 1024 if sizes else 0
        #  Sharing rate
        if self._ratio and torrent.ratio <= float(self._ratio):
            return None
        if self._time and torrent_seeding_time <= float(self._time) * 3600:
            return None
        if self._size and (torrent.total_size >= int(maxsize) or torrent.total_size <= int(minsize)):
            return None
        if self._upspeed and torrent_upload_avs >= float(self._upspeed) * 1024:
            return None
        if self._pathkeywords and not re.findall(self._pathkeywords, torrent.download_dir, re.I):
            return None
        if self._trackerkeywords:
            if not torrent.trackers:
                return None
            else:
                tacker_key_flag = False
                for tracker in torrent.trackers:
                    if re.findall(self._trackerkeywords, tracker.get("announce", ""), re.I):
                        tacker_key_flag = True
                        break
                if not tacker_key_flag:
                    return None
        if self._errorkeywords and not re.findall(self._errorkeywords, torrent.error_string, re.I):
            return None
        return {
            "id": torrent.hashString,
            "name": torrent.name,
            "site": torrent.trackers[0].get("sitename") if torrent.trackers else "",
            "size": torrent.total_size
        }

    def get_remove_torrents(self, downloader: str):
        """
        Obtaining seeds for automated deletion tasks
        """
        remove_torrents = []
        #  Downloader对象
        downloader_obj = self.__get_downloader(downloader)
        #  Caption
        if self._labels:
            tags = self._labels.split(',')
        else:
            tags = []
        if self._mponly:
            tags.extend(settings.TORRENT_TAG)
        #  Inquiry seeds
        torrents, error_flag = downloader_obj.get_torrents(tags=tags or None)
        if error_flag:
            return []
        #  Seed treatment
        for torrent in torrents:
            if downloader == "qbittorrent":
                item = self.__get_qb_torrent(torrent)
            else:
                item = self.__get_tr_torrent(torrent)
            if not item:
                continue
            remove_torrents.append(item)
        #  Auxiliary species
        if self._samedata and remove_torrents:
            remove_ids = [t.get("id") for t in remove_torrents]
            remove_torrents_plus = []
            for remove_torrent in remove_torrents:
                name = remove_torrent.get("name")
                size = remove_torrent.get("size")
                for torrent in torrents:
                    if downloader == "qbittorrent":
                        plus_id = torrent.hash
                        plus_name = torrent.name
                        plus_size = torrent.size
                        plus_site = StringUtils.get_url_sld(torrent.tracker)
                    else:
                        plus_id = torrent.hashString
                        plus_name = torrent.name
                        plus_size = torrent.total_size
                        plus_site = torrent.trackers[0].get("sitename") if torrent.trackers else ""
                    #  Compare names and sizes
                    if plus_name == name \
                            and plus_size == size \
                            and plus_id not in remove_ids:
                        remove_torrents_plus.append(
                            {
                                "id": plus_id,
                                "name": plus_name,
                                "site": plus_site,
                                "size": plus_size
                            }
                        )
            if remove_torrents_plus:
                remove_torrents.extend(remove_torrents_plus)
        return remove_torrents
