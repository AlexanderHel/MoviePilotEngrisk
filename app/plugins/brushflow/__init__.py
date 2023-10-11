import re
import threading
import time
from datetime import datetime, timedelta
from threading import Event
from typing import Any, List, Dict, Tuple, Optional, Union

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app import schemas
from app.chain.torrents import TorrentsChain
from app.core.config import settings
from app.db.site_oper import SiteOper
from app.helper.sites import SitesHelper
from app.log import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.schemas import Notification, NotificationType, TorrentInfo
from app.utils.string import StringUtils

lock = threading.Lock()


class BrushFlow(_PluginBase):
    #  Plug-in name
    plugin_name = " Site brush flow"
    #  Plugin description
    plugin_desc = " Automatically hosted brush streams， Will increase the frequency of visits to the corresponding site。"
    #  Plug-in icons
    plugin_icon = "brush.jpg"
    #  Theme color
    plugin_color = "#FFD54E"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "brushflow_"
    #  Loading sequence
    plugin_order = 21
    #  Available user levels
    auth_level = 2

    #  Private property
    siteshelper = None
    siteoper = None
    torrents = None
    sites = None
    qb = None
    tr = None
    #  Add seed timing
    _cron = 10
    #  Check seed timing
    _check_interval = 5
    #  Logout event
    _event = Event()
    _scheduler = None
    _enabled = False
    _notify = True
    _onlyonce = False
    _brushsites = []
    _downloader = "qbittorrent"
    _disksize = 0
    _freeleech = "free"
    _maxupspeed = 0
    _maxdlspeed = 0
    _maxdlcount = 0
    _include = ""
    _exclude = ""
    _size = 0
    _seeder = 0
    _pubtime = 0
    _seed_time = 0
    _seed_ratio = 0
    _seed_size = 0
    _download_time = 0
    _seed_avgspeed = 0
    _seed_inactivetime = 0
    _up_speed = 0
    _dl_speed = 0
    _save_path = ""
    _clear_task = False

    def init_plugin(self, config: dict = None):
        self.siteshelper = SitesHelper()
        self.siteoper = SiteOper()
        self.torrents = TorrentsChain()
        self.sites = SitesHelper()
        if config:
            self._enabled = config.get("enabled")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")
            self._brushsites = config.get("brushsites")
            self._downloader = config.get("downloader")
            self._disksize = config.get("disksize")
            self._freeleech = config.get("freeleech")
            self._maxupspeed = config.get("maxupspeed")
            self._maxdlspeed = config.get("maxdlspeed")
            self._maxdlcount = config.get("maxdlcount")
            self._include = config.get("include")
            self._exclude = config.get("exclude")
            self._size = config.get("size")
            self._seeder = config.get("seeder")
            self._pubtime = config.get("pubtime")
            self._seed_time = config.get("seed_time")
            self._seed_ratio = config.get("seed_ratio")
            self._seed_size = config.get("seed_size")
            self._download_time = config.get("download_time")
            self._seed_avgspeed = config.get("seed_avgspeed")
            self._seed_inactivetime = config.get("seed_inactivetime")
            self._up_speed = config.get("up_speed")
            self._dl_speed = config.get("dl_speed")
            self._save_path = config.get("save_path")
            self._clear_task = config.get("clear_task")

            #  Filter out deleted sites
            self._brushsites = [site.get("id") for site in self.sites.get_indexers() if
                                not site.get("public") and site.get("id") in self._brushsites]

            #  Save configuration
            self.__update_config()

            if self._clear_task:
                #  Clearing statistics
                self.save_data("statistic", {})
                #  Clearing seed records
                self.save_data("torrents", {})
                #  Turn off the disposable switch
                self._clear_task = False
                self.__update_config()

            #  Discontinuation of existing mandates
            self.stop_service()

            #  Starting a timed task &  Run one immediately
            if self.get_state() or self._onlyonce:
                self.qb = Qbittorrent()
                self.tr = Transmission()
                #  Check configuration
                if self._downloader == "qbittorrent":
                    if self.qb.is_inactive():
                        logger.error(" Error in site scrubbing task：Qbittorrent Unconnected")
                        self.systemmessage.put(" Error in site scrubbing task：Qbittorrent Unconnected")
                        return
                elif self._downloader == "transmission":
                    if self.tr.is_inactive():
                        logger.error(" Error in site scrubbing task：Transmission Unconnected")
                        self.systemmessage.put(" Error in site scrubbing task：Transmission Unconnected")
                        return
                if self._disksize and not StringUtils.is_number(self._disksize):
                    logger.error(f" Error in site scrubbing task， Incorrect setting of preservation volume：{self._disksize}")
                    self.systemmessage.put(f" Error in site scrubbing task， Incorrect setting of preservation volume：{self._disksize}")
                    self._disksize = 0
                    return
                if self._maxupspeed and not StringUtils.is_number(self._maxupspeed):
                    logger.error(f" Error in site scrubbing task， The total upload bandwidth is set incorrectly：{self._maxupspeed}")
                    self.systemmessage.put(f" Error in site scrubbing task， The total upload bandwidth is set incorrectly：{self._maxupspeed}")
                    self._maxupspeed = 0
                    return
                if self._maxdlspeed and not StringUtils.is_number(self._maxdlspeed):
                    logger.error(f" Error in site scrubbing task， The total download bandwidth is set incorrectly：{self._maxdlspeed}")
                    self.systemmessage.put(f" Error in site scrubbing task， The total download bandwidth is set incorrectly：{self._maxdlspeed}")
                    self._maxdlspeed = 0
                    return
                if self._maxdlcount and not StringUtils.is_number(self._maxdlcount):
                    logger.error(f" Error in site scrubbing task， Error in setting the number of simultaneous downloads：{self._maxdlcount}")
                    self.systemmessage.put(f" Error in site scrubbing task， Error in setting the number of simultaneous downloads：{self._maxdlcount}")
                    self._maxdlcount = 0
                    return
                if self._size:
                    size = str(self._size).split("-")[0]
                    if not StringUtils.is_number(size):
                        logger.error(f" Error in site scrubbing task， Seed size setting error：{self._size}")
                        self.systemmessage.put(f" Error in site scrubbing task， Seed size setting error：{self._size}")
                        self._size = 0
                        return
                if self._seeder:
                    seeder = str(self._seeder).split("-")[0]
                    if not StringUtils.is_number(seeder):
                        logger.error(f" Error in site scrubbing task， Incorrect setting of the number of breeders：{self._seeder}")
                        self.systemmessage.put(f" Error in site scrubbing task， Incorrect setting of the number of breeders：{self._seeder}")
                        self._seeder = 0
                        return
                if self._seed_time and not StringUtils.is_number(self._seed_time):
                    logger.error(f" Error in site scrubbing task， Incorrect setting of seeding time：{self._seed_time}")
                    self.systemmessage.put(f" Error in site scrubbing task， Incorrect setting of seeding time：{self._seed_time}")
                    self._seed_time = 0
                    return
                if self._seed_ratio and not StringUtils.is_number(self._seed_ratio):
                    logger.error(f" Error in site scrubbing task， Incorrect sharing rate setting：{self._seed_ratio}")
                    self.systemmessage.put(f" Error in site scrubbing task， Incorrect sharing rate setting：{self._seed_ratio}")
                    self._seed_ratio = 0
                    return
                if self._seed_size and not StringUtils.is_number(self._seed_size):
                    logger.error(f" Error in site scrubbing task， Upload volume setting error：{self._seed_size}")
                    self.systemmessage.put(f" Error in site scrubbing task， Upload volume setting error：{self._seed_size}")
                    self._seed_size = 0
                    return
                if self._download_time and not StringUtils.is_number(self._download_time):
                    logger.error(f" Error in site scrubbing task， Download timeout set incorrectly：{self._download_time}")
                    self.systemmessage.put(f" Error in site scrubbing task， Download timeout set incorrectly：{self._download_time}")
                    self._download_time = 0
                    return
                if self._seed_avgspeed and not StringUtils.is_number(self._seed_avgspeed):
                    logger.error(f" Error in site scrubbing task， Average upload speed set incorrectly：{self._seed_avgspeed}")
                    self.systemmessage.put(f" Error in site scrubbing task， Average upload speed set incorrectly：{self._seed_avgspeed}")
                    self._seed_avgspeed = 0
                    return
                if self._seed_inactivetime and not StringUtils.is_number(self._seed_inactivetime):
                    logger.error(f" Error in site scrubbing task， Inactive time setup error：{self._seed_inactivetime}")
                    self.systemmessage.put(f" Error in site scrubbing task， Inactive time setup error：{self._seed_inactivetime}")
                    self._seed_inactivetime = 0
                    return
                if self._up_speed and not StringUtils.is_number(self._up_speed):
                    logger.error(f" Error in site scrubbing task， Single task upload speed limit setting error：{self._up_speed}")
                    self.systemmessage.put(f" Error in site scrubbing task， Single task upload speed limit setting error：{self._up_speed}")
                    self._up_speed = 0
                    return
                if self._dl_speed and not StringUtils.is_number(self._dl_speed):
                    logger.error(f" Error in site scrubbing task， Error in setting speed limit for single-task downloads：{self._dl_speed}")
                    self.systemmessage.put(f" Error in site scrubbing task， Error in setting speed limit for single-task downloads：{self._dl_speed}")
                    self._dl_speed = 0
                    return

                #  Checking the necessary conditions
                if not self._brushsites or not self._downloader:
                    return

                #  Initiate tasks
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                logger.info(f" Site scrubbing service activated， Cyclicality：{self._cron} Minutes")
                try:
                    self._scheduler.add_job(self.brush, 'interval', minutes=self._cron)
                except Exception as e:
                    logger.error(f" Site scrubbing service failed to start：{e}")
                    self.systemmessage.put(f" Site scrubbing service failed to start：{e}")
                    return
                if self._onlyonce:
                    logger.info(f" Site scrubbing service activated， Run one immediately")
                    self._scheduler.add_job(self.brush, 'date',
                                            run_date=datetime.now(
                                                tz=pytz.timezone(settings.TZ)
                                            ) + timedelta(seconds=3),
                                            name=" Site streaming service")
                    #  Turn off the disposable switch
                    self._onlyonce = False
                    self.__update_config()
                if self._scheduler.get_jobs():
                    #  Increased number of inspection missions
                    self._scheduler.add_job(self.check, 'interval',
                                            minutes=self._check_interval,
                                            name=" Site brush flow checking service")
                    #  Starting services
                    self._scheduler.print_jobs()
                    self._scheduler.start()

    def get_state(self) -> bool:
        return True if self._enabled and self._brushsites and self._downloader else False

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Assembly plugin configuration page， Two pieces of data need to be returned：1、 Page configuration；2、 Data structure
        """
        #  Options for the site
        site_options = [{"title": site.get("name"), "value": site.get("id")}
                        for site in self.siteshelper.get_indexers()]
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
                                            'model': 'notify',
                                            'label': ' Send notification',
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
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'brushsites',
                                            'label': ' Swipe site',
                                            'items': site_options
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
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'downloader',
                                            'label': ' Downloader',
                                            'items': [
                                                {'title': 'Qbittorrent', 'value': 'qbittorrent'},
                                                {'title': 'Transmission', 'value': 'transmission'}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'disksize',
                                            'label': ' Seed preservation volume（GB）',
                                            'placeholder': ' Stop adding new tasks when reached'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'freeleech',
                                            'label': ' Promote',
                                            'items': [
                                                {'title': ' Full（ Includes general）', 'value': ''},
                                                {'title': ' Free (of charge)', 'value': 'free'},
                                                {'title': '2X Free (of charge)', 'value': '2xfree'},
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'maxupspeed',
                                            'label': ' Total upload bandwidth（KB/s）',
                                            'placeholder': ' Stop adding new tasks when reached'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'maxdlspeed',
                                            'label': ' Total download bandwidth（KB/s）',
                                            'placeholder': ' Stop adding new tasks when reached'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'maxdlcount',
                                            'label': ' Number of simultaneous downloads',
                                            'placeholder': ' Stop adding new tasks when reached'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'include',
                                            'label': ' Inclusion rules',
                                            'placeholder': ' Support for formal expressions'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'exclude',
                                            'label': ' Exclusion rules',
                                            'placeholder': ' Support for formal expressions'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'size',
                                            'label': ' Seed size（GB）',
                                            'placeholder': ' As if：5  Maybe 5-10'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'seeder',
                                            'label': ' Number of vaccinations',
                                            'placeholder': ' As if：5  Maybe 5-10'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'pubtime',
                                            'label': ' Release time（ Minutes）',
                                            'placeholder': ' As if：5  Maybe 5-10'
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
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'seed_time',
                                            'label': ' Time of planting（ Hourly）',
                                            'placeholder': ' Deletion of tasks after attainment'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'seed_ratio',
                                            'label': ' Sharing rate',
                                            'placeholder': ' Deletion of tasks after attainment'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'seed_size',
                                            'label': ' Upload volume（GB）',
                                            'placeholder': ' Deletion of tasks after attainment'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'download_time',
                                            'label': ' Download timeout（ Hourly）',
                                            'placeholder': ' Deletion of tasks after attainment'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'seed_avgspeed',
                                            'label': ' Average upload speed（KB/s）',
                                            'placeholder': ' Delete task if below'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'seed_inactivetime',
                                            'label': ' Inactive time（ Minutes） ',
                                            'placeholder': ' Delete tasks when exceeded'
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
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'up_speed',
                                            'label': ' Single-task upload speed limit（KB/s）',
                                            'placeholder': ' Seed upload speed limit'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'dl_speed',
                                            'label': ' Single-task download speed limit（KB/s）',
                                            'placeholder': ' Speed limit for seed downloads'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    "cols": 12,
                                    "md": 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'save_path',
                                            'label': ' Save directory',
                                            'placeholder': ' Leave blank spaces in writing'
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
                                            'model': 'clear_task',
                                            'label': ' Clearing statistics',
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
            "notify": True,
            "onlyonce": False,
            "clear_task": False,
            "freeleech": "free"
        }

    def get_page(self) -> List[dict]:
        #  Seed breakdown
        data_list = self.get_data("torrents") or {}
        #  Statistical data
        stattistic_data: Dict[str, dict] = self.get_data("statistic") or {
            "count": 0,
            "deleted": 0,
            "uploaded": 0,
            "downloaded": 0,
        }
        if not data_list:
            return [
                {
                    'component': 'div',
                    'text': ' No data available',
                    'props': {
                        'class': 'text-center',
                    }
                }
            ]
        else:
            data_list = data_list.values()
        #  Total uploads formatted
        total_upload = StringUtils.str_filesize(stattistic_data.get("uploaded") or 0)
        #  Total downloads formatted
        total_download = StringUtils.str_filesize(stattistic_data.get("downloaded") or 0)
        #  Number of seeds downloaded
        total_count = stattistic_data.get("count") or 0
        #  Number of seeds deleted
        total_deleted = stattistic_data.get("deleted") or 0
        #  Breakdown of seed data
        torrent_trs = [
            {
                'component': 'tr',
                'props': {
                    'class': 'text-sm'
                },
                'content': [
                    {
                        'component': 'td',
                        'props': {
                            'class': 'whitespace-nowrap break-keep text-high-emphasis'
                        },
                        'text': data.get("site_name")
                    },
                    {
                        'component': 'td',
                        'text': data.get("title")
                    },
                    {
                        'component': 'td',
                        'text': StringUtils.str_filesize(data.get("size"))
                    },
                    {
                        'component': 'td',
                        'text': StringUtils.str_filesize(data.get("uploaded") or 0)
                    },
                    {
                        'component': 'td',
                        'text': StringUtils.str_filesize(data.get("downloaded") or 0)
                    },
                    {
                        'component': 'td',
                        'text': round(data.get('ratio') or 0, 2)
                    },
                    {
                        'component': 'td',
                        'props': {
                            'class': 'text-no-wrap'
                        },
                        'text': " Deleted" if data.get("deleted") else " Normalcy"
                    }
                ]
            } for data in data_list
        ]

        #  Assembly page
        return [
            {
                'component': 'VRow',
                'content': [
                    #  Total uploads
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin_icon/upload.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Total uploads'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': total_upload
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                        ]
                    },
                    #  Total downloads
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin_icon/download.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Total downloads'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': total_download
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                        ]
                    },
                    #  Number of seeds downloaded
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin_icon/seed.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Number of seeds downloaded'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': total_count
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                        ]
                    },
                    #  Number of seeds deleted
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin_icon/delete.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Number of seeds deleted'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': total_deleted
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    #  Seed breakdown
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
                            {
                                'component': 'VTable',
                                'props': {
                                    'hover': True
                                },
                                'content': [
                                    {
                                        'component': 'thead',
                                        'props': {
                                            'class': 'text-no-wrap'
                                        },
                                        'content': [
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Website'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Caption'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Adults and children'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Upload volume'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Downloads'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Sharing rate'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' State of affairs'
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'tbody',
                                        'content': torrent_trs
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

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

    def __update_config(self):
        """
        Updating the configuration
        """
        self.update_config({
            "onlyonce": self._onlyonce,
            "enabled": self._enabled,
            "notify": self._notify,
            "brushsites": self._brushsites,
            "downloader": self._downloader,
            "disksize": self._disksize,
            "freeleech": self._freeleech,
            "maxupspeed": self._maxupspeed,
            "maxdlspeed": self._maxdlspeed,
            "maxdlcount": self._maxdlcount,
            "include": self._include,
            "exclude": self._exclude,
            "size": self._size,
            "seeder": self._seeder,
            "pubtime": self._pubtime,
            "seed_time": self._seed_time,
            "seed_ratio": self._seed_ratio,
            "seed_size": self._seed_size,
            "download_time": self._download_time,
            "seed_avgspeed": self._seed_avgspeed,
            "seed_inactivetime": self._seed_inactivetime,
            "up_speed": self._up_speed,
            "dl_speed": self._dl_speed,
            "save_path": self._save_path,
            "clear_task": self._clear_task
        })

    def brush(self):
        """
        Implementation of the brush flow action， Add download tasks
        """
        if not self._brushsites or not self._downloader:
            return

        with lock:
            logger.info(f" Beginning of the scrubbing task ...")
            #  Read seed records
            task_info: Dict[str, dict] = self.get_data("torrents") or {}
            if task_info:
                #  Current insured size
                torrents_size = sum([
                    task.get("size") or 0
                    for task in task_info.values() if not task.get("deleted")
                ])
            else:
                torrents_size = 0
            #  Read statistics
            statistic_info = self.get_data("statistic") or {
                "count": 0,
                "deleted": 0,
            }
            #  Processing of all sites
            for siteid in self._brushsites:
                siteinfo = self.siteoper.get(siteid)
                if not siteinfo:
                    logger.warn(f" Site does not exist：{siteid}")
                    continue
                logger.info(f" Start acquiring sites {siteinfo.name}  New seed ...")
                torrents = self.torrents.browse(domain=siteinfo.domain)
                if not torrents:
                    logger.info(f" Website {siteinfo.name}  No access to seeds")
                    continue
                #  Check or refer topubdate Descending order
                torrents.sort(key=lambda x: x.pubdate or '', reverse=True)
                #  Filtering seeds
                for torrent in torrents:
                    #  Weight control
                    if f"{torrent.site_name}{torrent.title}" in [
                        f"{task.get('site_name')}{task.get('title')}" for task in task_info.values()
                    ]:
                        continue
                    #  Promote
                    if self._freeleech and torrent.downloadvolumefactor != 0:
                        continue
                    if self._freeleech == "2xfree" and torrent.uploadvolumefactor != 2:
                        continue
                    #  Inclusion rules
                    if self._include and not re.search(r"%s" % self._include, torrent.title, re.I):
                        continue
                    #  Exclusion rules
                    if self._exclude and re.search(r"%s" % self._exclude, torrent.title, re.I):
                        continue
                    #  Seed size（GB）
                    if self._size:
                        sizes = str(self._size).split("-")
                        begin_size = sizes[0]
                        if len(sizes) > 1:
                            end_size = sizes[-1]
                        else:
                            end_size = 0
                        if begin_size and not end_size \
                                and torrent.size > float(begin_size) * 1024 ** 3:
                            continue
                        elif begin_size and end_size \
                                and not float(begin_size) * 1024 ** 3 <= torrent.size <= float(end_size) * 1024 ** 3:
                            continue
                    #  Number of vaccinations
                    if self._seeder:
                        seeders = str(self._seeder).split("-")
                        begin_seeder = seeders[0]
                        if len(seeders) > 1:
                            end_seeder = seeders[-1]
                        else:
                            end_seeder = 0
                        if begin_seeder and not end_seeder \
                                and torrent.seeders > int(begin_seeder):
                            continue
                        elif begin_seeder and end_seeder \
                                and not int(begin_seeder) <= torrent.seeders <= int(end_seeder):
                            continue
                    #  Calculate release time， Converting strings to time
                    pubdate_minutes = self.__get_pubminutes(torrent.pubdate)
                    #  Release time（ Minutes）
                    if self._pubtime:
                        pubtimes = str(self._pubtime).split("-")
                        begin_pubtime = pubtimes[0]
                        if len(pubtimes) > 1:
                            end_pubtime = pubtimes[-1]
                        else:
                            end_pubtime = 0
                        #  Convert seed release logs to difference from current time
                        if begin_pubtime and not end_pubtime \
                                and pubdate_minutes > int(begin_pubtime):
                            continue
                        elif begin_pubtime and end_pubtime \
                                and not int(begin_pubtime) <= pubdate_minutes <= int(end_pubtime):
                            continue
                    #  Number of simultaneous downloads
                    downloads = self.__get_downloading_count()
                    if self._maxdlcount and downloads >= int(self._maxdlcount):
                        logger.warn(f" Current number of simultaneous downloads {downloads}  Maximum value reached {self._maxdlcount}， Discontinuation of additional mandates")
                        break
                    #  Get download information from the downloader
                    downloader_info = self.__get_downloader_info()
                    if downloader_info:
                        current_upload_speed = downloader_info.upload_speed or 0
                        current_download_speed = downloader_info.download_speed or 0
                        #  Total upload bandwidth(KB/s)
                        if self._maxupspeed \
                                and current_upload_speed >= float(self._maxupspeed) * 1024:
                            logger.warn(f" Current total upload bandwidth {StringUtils.str_filesize(current_upload_speed)} "
                                        f" Maximum value reached {self._maxupspeed} KB/s， Temporary suspension of additional mandates")
                            break
                        #  Total download bandwidth(KB/s)
                        if self._maxdlspeed \
                                and current_download_speed >= float(self._maxdlspeed) * 1024:
                            logger.warn(f" Current total download bandwidth {StringUtils.str_filesize(current_download_speed)} "
                                        f" Maximum value reached {self._maxdlspeed} KB/s， Temporary suspension of additional mandates")
                            break
                    #  Seed preservation volume（GB）
                    if self._disksize \
                            and (torrents_size + torrent.size) > float(self._disksize) * 1024 ** 3:
                        logger.warn(f" Current seeding volume {StringUtils.str_filesize(torrents_size)} "
                                    f" Has exceeded the preservation volume {self._disksize}， Discontinuation of additional mandates")
                        break
                    #  Add download tasks
                    hash_string = self.__download(torrent=torrent)
                    if not hash_string:
                        logger.warn(f"{torrent.title}  Failed to add a streaming task！")
                        continue
                    #  Saving task information
                    task_info[hash_string] = {
                        "site": siteinfo.id,
                        "site_name": siteinfo.name,
                        "title": torrent.title,
                        "size": torrent.size,
                        "pubdate": torrent.pubdate,
                        "ratio": 0,
                        "downloaded": 0,
                        "uploaded": 0,
                        "deleted": False,
                    }
                    #  Statistical data
                    torrents_size += torrent.size
                    statistic_info["count"] += 1
                    #  Send a message
                    self.__send_add_message(torrent)

            #  Save data
            self.save_data("torrents", task_info)
            #  Save statistics
            self.save_data("statistic", statistic_info)
            logger.info(f" Brush flow task execution completed")

    def check(self):
        """
        Timing control， Delete download tasks
        {
            hash: {
                site_name:
                size:
            }
        }
        """
        if not self._downloader:
            return

        with lock:
            logger.info(f" Start checking for swipe streaming download tasks ...")
            #  Read seed records
            task_info: Dict[str, dict] = self.get_data("torrents") or {}
            #  TorrentHash
            check_hashs = list(task_info.keys())
            if not task_info or not check_hashs:
                logger.info(f" There are no brush streaming download tasks that need to be checked")
                return
            logger.info(f" Have altogether {len(check_hashs)}  A mission is brushing the stream.， Start checking task status")
            #  Get downloader example
            downloader = self.__get_downloader(self._downloader)
            if not downloader:
                return
            #  Read statistics
            statistic_info = self.get_data("statistic") or {
                "count": 0,
                "deleted": 0,
                "uploaded": 0,
                "downloaded": 0
            }
            #  Getting seeds from the downloader
            torrents, error = downloader.get_torrents(ids=check_hashs)
            if error:
                logger.warn(" Error connecting to downloader， Will retry at next time cycle")
                return
            if not torrents:
                logger.warn(f" Swipe streaming task does not exist in the downloader， Clearing records")
                self.save_data("hashs", {})
                return
            #  Check seed status， Determine whether to delete seeds
            remove_torrents = []
            for torrent in torrents:
                torrent_hash = self.__get_hash(torrent)
                site_name = task_info.get(torrent_hash).get("site_name")
                torrent_info = self.__get_torrent_info(torrent)
                #  Update uploads、 Downloads
                if not task_info.get(torrent_info.get("hash")):
                    task_info[torrent_hash] = {
                        "downloaded": torrent_info.get("downloaded"),
                        "uploaded": torrent_info.get("uploaded"),
                        "ratio": torrent_info.get("ratio"),
                    }
                else:
                    task_info[torrent_hash]["downloaded"] = torrent_info.get("downloaded")
                    task_info[torrent_hash]["uploaded"] = torrent_info.get("uploaded")
                    task_info[torrent_hash]["ratio"] = torrent_info.get("ratio")
                #  Time of planting（ Hourly）
                if self._seed_time:
                    if torrent_info.get("seeding_time") >= float(self._seed_time) * 3600:
                        logger.info(f" Seeding time up to {self._seed_time}  Hourly， Delete seeds：{torrent_info.get('title')}")
                        downloader.delete_torrents(ids=torrent_hash, delete_file=True)
                        remove_torrents.append(torrent_info)
                        self.__send_delete_message(site_name=site_name,
                                                   torrent_title=torrent_info.get("title"),
                                                   reason=f" Seeding time up to {self._seed_time}  Hourly")
                        continue
                #  Sharing rate
                if self._seed_ratio:
                    if torrent_info.get("ratio") >= float(self._seed_ratio):
                        logger.info(f" Sharing rate reached {self._seed_ratio}， Delete seeds：{torrent_info.get('title')}")
                        downloader.delete_torrents(ids=torrent_hash, delete_file=True)
                        remove_torrents.append(torrent_info)
                        self.__send_delete_message(site_name=site_name,
                                                   torrent_title=torrent_info.get("title"),
                                                   reason=f" Sharing rate reached {self._seed_ratio}")
                        continue
                #  Upload volume（GB）
                if self._seed_size:
                    if torrent_info.get("uploaded") >= float(self._seed_size) * 1024 * 1024 * 1024:
                        logger.info(f" Uploads reached {self._seed_size} GB， Delete seeds：{torrent_info.get('title')}")
                        downloader.delete_torrents(ids=torrent_hash, delete_file=True)
                        remove_torrents.append(torrent_info)
                        self.__send_delete_message(site_name=site_name,
                                                   torrent_title=torrent_info.get("title"),
                                                   reason=f" Uploads reached {self._seed_size} GB")
                        continue
                #  Download time（ Hourly）
                if self._download_time \
                        and torrent_info.get("downloaded") < torrent_info.get("total_size"):
                    if torrent_info.get("dltime") >= float(self._download_time) * 3600:
                        logger.info(f" The download takes up to {self._download_time}  Hourly， Delete seeds：{torrent_info.get('title')}")
                        downloader.delete_torrents(ids=torrent_hash, delete_file=True)
                        remove_torrents.append(torrent_info)
                        self.__send_delete_message(site_name=site_name,
                                                   torrent_title=torrent_info.get("title"),
                                                   reason=f" The download takes up to {self._download_time}  Hourly")
                        continue
                #  Average upload speed（KB / s）， More than30 It takes minutes to work.
                if self._seed_avgspeed:
                    if torrent_info.get("avg_upspeed") <= float(self._seed_avgspeed) * 1024 and \
                            torrent_info.get("seeding_time") >= 30 * 60:
                        logger.info(f" Average upload speeds below {self._seed_avgspeed} KB/s， Delete seeds：{torrent_info.get('title')}")
                        downloader.delete_torrents(ids=torrent_hash, delete_file=True)
                        remove_torrents.append(torrent_info)
                        self.__send_delete_message(site_name=site_name,
                                                   torrent_title=torrent_info.get("title"),
                                                   reason=f" Average upload speeds below {self._seed_avgspeed} KB/s")
                        continue
                #  Inactive time（ Minutes）
                if self._seed_inactivetime:
                    if torrent_info.get("iatime") >= float(self._seed_inactivetime) * 60:
                        logger.info(
                            f" Inactive time up to {self._seed_inactivetime}  Minutes， Delete seeds：{torrent_info.get('title')}")
                        downloader.delete_torrents(ids=torrent_hash, delete_file=True)
                        remove_torrents.append(torrent_info)
                        self.__send_delete_message(site_name=site_name,
                                                   torrent_title=torrent_info.get("title"),
                                                   reason=f" Inactive time up to {self._seed_inactivetime}  Minutes")
                        continue
            #  Statistics on deletion status
            if remove_torrents:
                if not statistic_info.get("deleted"):
                    statistic_info["deleted"] = 0
                statistic_info["deleted"] += len(remove_torrents)
                #  Deletion of task records
                for torrent in remove_torrents:
                    task_info[torrent.get("hash")].update({
                        "deleted": True,
                    })
            #  Statistical total uploads、 Downloads
            total_uploaded = 0
            total_downloaded = 0
            for hash_str, task in task_info.items():
                total_downloaded += task.get("downloaded") or 0
                total_uploaded += task.get("uploaded") or 0
            #  Updated statistics
            statistic_info["uploaded"] = total_uploaded
            statistic_info["downloaded"] = total_downloaded
            #  Printing statistics
            logger.info(f" Statistics on streaming tasks："
                        f" Total number of assignments：{len(task_info)}，"
                        f" Deleted：{statistic_info.get('deleted')}，"
                        f" Total uploads：{StringUtils.str_filesize(statistic_info.get('uploaded'))}，"
                        f" Total downloads：{StringUtils.str_filesize(statistic_info.get('downloaded'))}")
            #  Save statistics
            self.save_data("statistic", statistic_info)
            #  Keeping a record of tasks
            self.save_data("torrents", task_info)
            logger.info(f" Swipe streaming download task check complete")

    def __get_downloader(self, dtype: str) -> Optional[Union[Transmission, Qbittorrent]]:
        """
        Returns downloader instances by type
        """
        if dtype == "qbittorrent":
            return self.qb
        elif dtype == "transmission":
            return self.tr
        else:
            return None

    def __download(self, torrent: TorrentInfo) -> Optional[str]:
        """
        Add download tasks
        """
        #  Upload speed limit
        up_speed = int(self._up_speed) if self._up_speed else None
        #  Download speed limit
        down_speed = int(self._dl_speed) if self._dl_speed else None
        if self._downloader == "qbittorrent":
            if not self.qb:
                return None
            #  The speed limit value is shifted tobytes
            up_speed = up_speed * 1024 if up_speed else None
            down_speed = down_speed * 1024 if down_speed else None
            #  Generate randomTag
            tag = StringUtils.generate_random_str(10)
            state = self.qb.add_torrent(content=torrent.enclosure,
                                        download_dir=self._save_path or None,
                                        cookie=torrent.site_cookie,
                                        tag=[" Collated", " Brush", tag],
                                        upload_limit=up_speed,
                                        download_limit=down_speed)
            if not state:
                return None
            else:
                #  Getting seedsHash
                torrent_hash = self.qb.get_torrent_id_by_tag(tags=tag)
                if not torrent_hash:
                    logger.error(f"{self._downloader}  Getting seedsHash Fail (e.g. experiments)")
                    return None
            return torrent_hash
        elif self._downloader == "transmission":
            if not self.tr:
                return None
            #  Add tasks
            torrent = self.tr.add_torrent(content=torrent.enclosure,
                                          download_dir=self._save_path or None,
                                          cookie=torrent.site_cookie,
                                          labels=[" Collated", " Brush"])
            if not torrent:
                return None
            else:
                if self._up_speed or self._dl_speed:
                    self.tr.change_torrent(hash_string=torrent.hashString,
                                           upload_limit=up_speed,
                                           download_limit=down_speed)
                return torrent.hashString
        return None

    def __get_hash(self, torrent: Any):
        """
        Getting seedshash
        """
        try:
            return torrent.get("hash") if self._downloader == "qbittorrent" else torrent.hashString
        except Exception as e:
            print(str(e))
            return ""

    def __get_label(self, torrent: Any):
        """
        Get seed label
        """
        try:
            return [str(tag).strip() for tag in torrent.get("tags").split(',')] \
                if self._downloader == "qbittorrent" else torrent.labels or []
        except Exception as e:
            print(str(e))
            return []

    def __get_torrent_info(self, torrent: Any) -> dict:

        #  Current timestamp
        date_now = int(time.time())
        # QB
        if self._downloader == "qbittorrent":
            """
            {
              "added_on": 1693359031,
              "amount_left": 0,
              "auto_tmm": false,
              "availability": -1,
              "category": "tJU",
              "completed": 67759229411,
              "completion_on": 1693609350,
              "content_path": "/mnt/sdb/qb/downloads/Steel.Division.2.Men.of.Steel-RUNE",
              "dl_limit": -1,
              "dlspeed": 0,
              "download_path": "",
              "downloaded": 67767365851,
              "downloaded_session": 0,
              "eta": 8640000,
              "f_l_piece_prio": false,
              "force_start": false,
              "hash": "116bc6f3efa6f3b21a06ce8f1cc71875",
              "infohash_v1": "116bc6f306c40e072bde8f1cc71875",
              "infohash_v2": "",
              "last_activity": 1693609350,
              "magnet_uri": "magnet:?xt=",
              "max_ratio": -1,
              "max_seeding_time": -1,
              "name": "Steel.Division.2.Men.of.Steel-RUNE",
              "num_complete": 1,
              "num_incomplete": 0,
              "num_leechs": 0,
              "num_seeds": 0,
              "priority": 0,
              "progress": 1,
              "ratio": 0,
              "ratio_limit": -2,
              "save_path": "/mnt/sdb/qb/downloads",
              "seeding_time": 615035,
              "seeding_time_limit": -2,
              "seen_complete": 1693609350,
              "seq_dl": false,
              "size": 67759229411,
              "state": "stalledUP",
              "super_seeding": false,
              "tags": "",
              "time_active": 865354,
              "total_size": 67759229411,
              "tracker": "https://tracker",
              "trackers_count": 2,
              "up_limit": -1,
              "uploaded": 0,
              "uploaded_session": 0,
              "upspeed": 0
            }
            """
            # ID
            torrent_id = torrent.get("hash")
            #  Caption
            torrent_title = torrent.get("name")
            #  Download time
            if (not torrent.get("added_on")
                    or torrent.get("added_on") < 0):
                dltime = 0
            else:
                dltime = date_now - torrent.get("added_on")
            #  Time of planting
            if (not torrent.get("completion_on")
                    or torrent.get("completion_on") < 0):
                seeding_time = 0
            else:
                seeding_time = date_now - torrent.get("completion_on")
            #  Sharing rate
            ratio = torrent.get("ratio") or 0
            #  Upload volume
            uploaded = torrent.get("uploaded") or 0
            #  Average upload speed Byte/s
            if dltime:
                avg_upspeed = int(uploaded / dltime)
            else:
                avg_upspeed = uploaded
            #  Inactive  Unit of angle or arc equivalent one sixtieth of a degree
            if (not torrent.get("last_activity")
                    or torrent.get("last_activity") < 0):
                iatime = 0
            else:
                iatime = date_now - torrent.get("last_activity")
            #  Downloads
            downloaded = torrent.get("downloaded")
            #  Seed size
            total_size = torrent.get("total_size")
            #  Add time
            add_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(torrent.get("added_on") or 0))
        # TR
        else:
            # ID
            torrent_id = torrent.hashString
            #  Caption
            torrent_title = torrent.name
            #  Time of planting
            if (not torrent.date_done
                    or torrent.date_done.timestamp() < 1):
                seeding_time = 0
            else:
                seeding_time = date_now - int(torrent.date_done.timestamp())
            #  Download time
            if (not torrent.date_added
                    or torrent.date_added.timestamp() < 1):
                dltime = 0
            else:
                dltime = date_now - int(torrent.date_added.timestamp())
            #  Downloads
            downloaded = int(torrent.total_size * torrent.progress / 100)
            #  Sharing rate
            ratio = torrent.ratio or 0
            #  Upload volume
            uploaded = int(downloaded * torrent.ratio)
            #  Average upload speed
            if dltime:
                avg_upspeed = int(uploaded / dltime)
            else:
                avg_upspeed = uploaded
            #  Inactive time
            if (not torrent.date_active
                    or torrent.date_active.timestamp() < 1):
                iatime = 0
            else:
                iatime = date_now - int(torrent.date_active.timestamp())
            #  Seed size
            total_size = torrent.total_size
            #  Add time
            add_time = time.strftime('%Y-%m-%d %H:%M:%S',
                                     time.localtime(torrent.date_added.timestamp() if torrent.date_added else 0))

        return {
            "hash": torrent_id,
            "title": torrent_title,
            "seeding_time": seeding_time,
            "ratio": ratio,
            "uploaded": uploaded,
            "downloaded": downloaded,
            "avg_upspeed": avg_upspeed,
            "iatime": iatime,
            "dltime": dltime,
            "total_size": total_size,
            "add_time": add_time
        }

    def __send_delete_message(self, site_name: str, torrent_title: str, reason: str):
        """
        Send a message to delete the seed
        """
        if not self._notify:
            return
        self.chain.post_message(Notification(
            mtype=NotificationType.SiteMessage,
            title=f"【 Brush streaming tasks to delete species】",
            text=f" Website：{site_name}\n"
                 f" Caption：{torrent_title}\n"
                 f" Rationale：{reason}"
        ))

    def __send_add_message(self, torrent: TorrentInfo):
        """
        Send message to add download
        """
        if not self._notify:
            return
        msg_text = ""
        if torrent.site_name:
            msg_text = f" Website：{torrent.site_name}"
        if torrent.title:
            msg_text = f"{msg_text}\n Caption：{torrent.title}"
        if torrent.size:
            if str(torrent.size).replace(".", "").isdigit():
                size = StringUtils.str_filesize(torrent.size)
            else:
                size = torrent.size
            msg_text = f"{msg_text}\n Adults and children：{size}"
        if torrent.pubdate:
            msg_text = f"{msg_text}\n Release time：{torrent.pubdate}"
        if torrent.seeders:
            msg_text = f"{msg_text}\n Determinant (math.)：{torrent.seeders}"
        if torrent.volume_factor:
            msg_text = f"{msg_text}\n Promote：{torrent.volume_factor}"
        if torrent.hit_and_run:
            msg_text = f"{msg_text}\nHit&Run： Be"

        self.chain.post_message(Notification(
            mtype=NotificationType.SiteMessage,
            title="【 Brush streaming task seed download】",
            text=msg_text
        ))

    def __get_torrents_size(self) -> int:
        """
        Get the total size of the seeds in the task
        """
        #  Read seed records
        task_info = self.get_data("torrents") or {}
        if not task_info:
            return 0
        total_size = sum([task.get("size") or 0 for task in task_info.values()])
        return total_size

    def __get_downloader_info(self) -> schemas.DownloaderInfo:
        """
        Get real-time information about the downloader（ All downloaders）
        """
        ret_info = schemas.DownloaderInfo()

        # Qbittorrent
        if self.qb:
            info = self.qb.transfer_info()
            if info:
                ret_info.download_speed += info.get("dl_info_speed")
                ret_info.upload_speed += info.get("up_info_speed")
                ret_info.download_size += info.get("dl_info_data")
                ret_info.upload_size += info.get("up_info_data")

        # Transmission
        if self.tr:
            info = self.tr.transfer_info()
            if info:
                ret_info.download_speed += info.download_speed
                ret_info.upload_speed += info.upload_speed
                ret_info.download_size += info.current_stats.downloaded_bytes
                ret_info.upload_size += info.current_stats.uploaded_bytes

        return ret_info

    def __get_downloading_count(self) -> int:
        """
        Get the number of tasks being downloaded
        """
        downlader = self.__get_downloader(self._downloader)
        if not downlader:
            return 0
        torrents = downlader.get_downloading_torrents()
        return len(torrents) or 0

    @staticmethod
    def __get_pubminutes(pubdate: str) -> int:
        """
        Converting strings to time， And calculate the time difference from the current time）（ Minutes）
        """
        try:
            if not pubdate:
                return 0
            pubdate = pubdate.replace("T", " ").replace("Z", "")
            pubdate = datetime.strptime(pubdate, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            return (now - pubdate).total_seconds() // 60
        except Exception as e:
            print(str(e))
            return 0
