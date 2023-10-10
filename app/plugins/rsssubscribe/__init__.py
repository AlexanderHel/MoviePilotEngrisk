import datetime
import re
from pathlib import Path
from threading import Lock
from typing import Optional, Any, List, Dict, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.chain.download import DownloadChain
from app.chain.search import SearchChain
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.context import MediaInfo, TorrentInfo, Context
from app.core.metainfo import MetaInfo
from app.helper.rss import RssHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import SystemConfigKey, MediaType

lock = Lock()


class RssSubscribe(_PluginBase):
    #  Plug-in name
    plugin_name = " Custom subscriptions"
    #  Plugin description
    plugin_desc = " Timed refreshRSS Telegram， Add a subscription or download directly after recognizing the content。"
    #  Plug-in icons
    plugin_icon = "rss.png"
    #  Theme color
    plugin_color = "#F78421"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "rsssubscribe_"
    #  Loading sequence
    plugin_order = 19
    #  Available user levels
    auth_level = 2

    #  Private variable
    _scheduler: Optional[BackgroundScheduler] = None
    _cache_path: Optional[Path] = None
    rsshelper = None
    downloadchain = None
    searchchain = None
    subscribechain = None

    #  Configuration properties
    _enabled: bool = False
    _cron: str = ""
    _notify: bool = False
    _onlyonce: bool = False
    _address: str = ""
    _include: str = ""
    _exclude: str = ""
    _proxy: bool = False
    _filter: bool = False
    _clear: bool = False
    _clearflag: bool = False
    _action: str = "subscribe"
    _save_path: str = ""

    def init_plugin(self, config: dict = None):
        self.rsshelper = RssHelper()
        self.downloadchain = DownloadChain(self.db)
        self.searchchain = SearchChain(self.db)
        self.subscribechain = SubscribeChain(self.db)

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Configure
        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")
            self._address = config.get("address")
            self._include = config.get("include")
            self._exclude = config.get("exclude")
            self._proxy = config.get("proxy")
            self._filter = config.get("filter")
            self._clear = config.get("clear")
            self._action = config.get("action")
            self._save_path = config.get("save_path")

        if self._enabled or self._onlyonce:

            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                try:
                    self._scheduler.add_job(func=self.check,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name="RSS Subscribe to")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")
                    #  Push real-time messages
                    self.systemmessage.put(f" Execution cycle misconfiguration：{err}")
            else:
                self._scheduler.add_job(self.check, "interval", minutes=30, name="RSS Subscribe to")

            if self._onlyonce:
                logger.info(f"RSS Subscription service startup， Run one immediately")
                self._scheduler.add_job(func=self.check, trigger='date',
                                        run_date=datetime.datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3)
                                        )

            if self._onlyonce or self._clear:
                #  Turn off the disposable switch
                self._onlyonce = False
                #  Record clear cache settings
                self._clearflag = self._clear
                #  Turn off the clear cache switch
                self._clear = False
                #  Save settings
                self.__update_config()

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        Defining remote control commands
        :return:  Command keywords、 Event、 Descriptive、 Accompanying data
        """
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        Get pluginsAPI
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API Clarification"
        }]
        """
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
                                            'placeholder': '5 Classifier for honorific peoplecron Displayed formula， Leave blank spaces in writing'
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
                                                {'title': ' Subscribe to', 'value': 'subscribe'},
                                                {'title': ' Downloading', 'value': 'download'}
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
                                            'model': 'address',
                                            'label': 'RSS Address',
                                            'rows': 3,
                                            'placeholder': ' One per lineRSS Address'
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
                                            'model': 'include',
                                            'label': ' Embody',
                                            'placeholder': ' Regular expression support'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'exclude',
                                            'label': ' Rule out',
                                            'placeholder': ' Regular expression support'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'save_path',
                                            'label': ' Save directory',
                                            'placeholder': ' Valid for download， Leave blank spaces in writing'
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
                                            'model': 'proxy',
                                            'label': ' Using a proxy server',
                                        }
                                    }
                                ]
                            }, {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'filter',
                                            'label': ' Using filter rules',
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
                                            'label': ' Clear history',
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
            "cron": "*/30 * * * *",
            "address": "",
            "include": "",
            "exclude": "",
            "proxy": False,
            "clear": False,
            "filter": False,
            "action": "subscribe",
            "save_path": ""
        }

    def get_page(self) -> List[dict]:
        """
        Patchwork plug-in detail page， Need to return to page configuration， Also with data
        """
        #  Query synchronization details
        historys = self.get_data('history')
        if not historys:
            return [
                {
                    'component': 'div',
                    'text': ' No data available',
                    'props': {
                        'class': 'text-center',
                    }
                }
            ]
        #  Data is sorted in descending chronological order
        historys = sorted(historys, key=lambda x: x.get('time'), reverse=True)
        #  Assembly page
        contents = []
        for history in historys:
            title = history.get("title")
            poster = history.get("poster")
            mtype = history.get("type")
            time_str = history.get("time")
            contents.append(
                {
                    'component': 'VCard',
                    'content': [
                        {
                            'component': 'div',
                            'props': {
                                'class': 'd-flex justify-space-start flex-nowrap flex-row',
                            },
                            'content': [
                                {
                                    'component': 'div',
                                    'content': [
                                        {
                                            'component': 'VImg',
                                            'props': {
                                                'src': poster,
                                                'height': 120,
                                                'width': 80,
                                                'aspect-ratio': '2/3',
                                                'class': 'object-cover shadow ring-gray-500',
                                                'cover': True
                                            }
                                        }
                                    ]
                                },
                                {
                                    'component': 'div',
                                    'content': [
                                        {
                                            'component': 'VCardSubtitle',
                                            'props': {
                                                'class': 'pa-2 font-bold break-words whitespace-break-spaces'
                                            },
                                            'text': title
                                        },
                                        {
                                            'component': 'VCardText',
                                            'props': {
                                                'class': 'pa-0 px-2'
                                            },
                                            'text': f' Typology：{mtype}'
                                        },
                                        {
                                            'component': 'VCardText',
                                            'props': {
                                                'class': 'pa-0 px-2'
                                            },
                                            'text': f' Timing：{time_str}'
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            )

        return [
            {
                'component': 'div',
                'props': {
                    'class': 'grid gap-3 grid-info-card',
                },
                'content': contents
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
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("Exit plugin失败：%s" % str(e))

    def __update_config(self):
        """
        Update settings
        """
        self.update_config({
            "enabled": self._enabled,
            "notify": self._notify,
            "onlyonce": self._onlyonce,
            "cron": self._cron,
            "address": self._address,
            "include": self._include,
            "exclude": self._exclude,
            "proxy": self._proxy,
            "clear": self._clear
        })

    def check(self):
        """
        Via the userRSS Synchronized douban wants to see the data
        """
        if not self._address:
            return
        #  Read history
        if self._clearflag:
            history = []
        else:
            history: List[dict] = self.get_data('history') or []
        for url in self._address.split("\n"):
            #  Handling of eachRSS Link (on a website)
            if not url:
                continue
            logger.info(f" Start refreshingRSS：{url} ...")
            results = self.rsshelper.parse(url, proxy=self._proxy)
            if not results:
                logger.error(f" Not availableRSS Digital：{url}")
                return
            #  Filter rules
            filter_rule = self.systemconfig.get(SystemConfigKey.SubscribeFilterRules)
            #  Parsing data
            for result in results:
                try:
                    title = result.get("title")
                    description = result.get("description")
                    enclosure = result.get("enclosure")
                    link = result.get("link")
                    sise = result.get("sise")
                    pubdate: datetime.datetime = result.get("pubdate")
                    #  Check to see if it's been handled
                    if not title or title in [h.get("key") for h in history]:
                        continue
                    #  Inspection rules
                    if self._include and not re.search(r"%s" % self._include,
                                                       f"{title} {description}", re.IGNORECASE):
                        logger.info(f"{title} - {description}  Failure to comply with inclusion rules")
                        continue
                    if self._exclude and re.search(r"%s" % self._exclude,
                                                   f"{title} {description}", re.IGNORECASE):
                        logger.info(f"{title} - {description}  Failure to meet the exclusionary rule")
                        continue
                    #  Identify media messages
                    meta = MetaInfo(title=title, subtitle=description)
                    if not meta.name:
                        logger.warn(f"{title}  No valid data recognized")
                        continue
                    mediainfo: MediaInfo = self.chain.recognize_media(meta=meta)
                    if not mediainfo:
                        logger.warn(f' No media messages recognized， Caption：{title}')
                        continue
                    #  Torrent
                    torrentinfo = TorrentInfo(
                        title=title,
                        description=description,
                        enclosure=enclosure,
                        page_url=link,
                        size=sise,
                        pubdate=pubdate.strftime("%Y-%m-%d %H:%M:%S") if pubdate else None,
                    )
                    #  Filtering seeds
                    if self._filter:
                        result = self.chain.filter_torrents(
                            rule_string=filter_rule,
                            torrent_list=[torrentinfo],
                            mediainfo=mediainfo
                        )
                        if not result:
                            logger.info(f"{title} {description}  Mismatch filter rules")
                            continue
                    #  Querying missing media information
                    exist_flag, no_exists = self.downloadchain.get_no_exists_info(meta=meta, mediainfo=mediainfo)
                    if exist_flag:
                        logger.info(f'{mediainfo.title_year}  Already exists in the media library')
                        continue
                    else:
                        if self._action == "download":
                            if mediainfo.type == MediaType.TV:
                                if no_exists:
                                    exist_info = no_exists.get(mediainfo.tmdb_id)
                                    season_info = exist_info.get(meta.begin_season or 1)
                                    if not season_info:
                                        logger.info(f'{mediainfo.title_year} {meta.season}  Exist on one's own')
                                        continue
                                    if (season_info.episodes
                                            and not set(meta.episode_list).issubset(set(season_info.episodes))):
                                        logger.info(f'{mediainfo.title_year} {meta.season_episode}  Exist on one's own')
                                        continue
                            #  Add download
                            result = self.downloadchain.download_single(
                                context=Context(
                                    meta_info=meta,
                                    media_info=mediainfo,
                                    torrent_info=torrentinfo,
                                ),
                                save_path=self._save_path
                            )
                            if not result:
                                logger.error(f'{title}  Failed to download')
                                continue
                        else:
                            #  Check if the subscription is in
                            subflag = self.subscribechain.exists(mediainfo=mediainfo, meta=meta)
                            if subflag:
                                logger.info(f'{mediainfo.title_year} {meta.season}  Subscription in progress')
                                continue
                            #  Add subscription
                            self.subscribechain.add(title=mediainfo.title,
                                                    year=mediainfo.year,
                                                    mtype=mediainfo.type,
                                                    tmdbid=mediainfo.tmdb_id,
                                                    season=meta.begin_season,
                                                    exist_ok=True,
                                                    username="RSS Subscribe to")
                    #  Storing history
                    history.append({
                        "title": f"{mediainfo.title} {meta.season}",
                        "key": f"{title}",
                        "type": mediainfo.type.value,
                        "year": mediainfo.year,
                        "poster": mediainfo.get_poster_image(),
                        "overview": mediainfo.overview,
                        "tmdbid": mediainfo.tmdb_id,
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except Exception as err:
                    logger.error(f' Refresh (computer window)RSS Data error：{err}')
            logger.info(f"RSS {url}  Refresh complete.")
        #  Save history
        self.save_data('history', history)
        #  Cache is only cleared once
        self._clearflag = False
