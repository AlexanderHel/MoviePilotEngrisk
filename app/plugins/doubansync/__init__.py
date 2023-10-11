import datetime
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
from app.core.context import MediaInfo
from app.core.event import Event
from app.core.event import eventmanager
from app.core.metainfo import MetaInfo
from app.helper.rss import RssHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType

lock = Lock()


class DoubanSync(_PluginBase):
    #  Plug-in name
    plugin_name = " Douban wants to see"
    #  Plugin description
    plugin_desc = " Synchronized douban wants to see the data， Automatically add subscriptions。"
    #  Plug-in icons
    plugin_icon = "douban.png"
    #  Theme color
    plugin_color = "#05B711"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "doubansync_"
    #  Loading sequence
    plugin_order = 3
    #  Available user levels
    auth_level = 2

    #  Private variable
    _interests_url: str = "https://www.douban.com/feed/people/%s/interests"
    _scheduler: Optional[BackgroundScheduler] = None
    _cache_path: Optional[Path] = None
    rsshelper = None
    downloadchain = None
    searchchain = None
    subscribechain = None

    #  Configuration properties
    _enabled: bool = False
    _onlyonce: bool = False
    _cron: str = ""
    _notify: bool = False
    _days: int = 7
    _users: str = ""
    _clear: bool = False
    _clearflag: bool = False

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
            self._days = config.get("days")
            self._users = config.get("users")
            self._onlyonce = config.get("onlyonce")
            self._clear = config.get("clear")

        if self._enabled or self._onlyonce:

            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                try:
                    self._scheduler.add_job(func=self.sync,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Douban wants to see")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")
                    #  Push real-time messages
                    self.systemmessage.put(f" Execution cycle misconfiguration：{err}")
            else:
                self._scheduler.add_job(self.sync, "interval", minutes=30, name=" Douban wants to see")

            if self._onlyonce:
                logger.info(f" Douban wants to see the service launched， Run one immediately")
                self._scheduler.add_job(func=self.sync, trigger='date',
                                        run_date=datetime.datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3)
                                        )

            if self._onlyonce or self._clear:
                #  Turn off the disposable switch
                self._onlyonce = False
                #  Logging cache cleanup flags
                self._clearflag = self._clear
                #  Close clear cache
                self._clear = False
                #  Save configuration
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
        return [{
            "cmd": "/douban_sync",
            "event": EventType.DoubanSync,
            "desc": " Synchronized douban wants to see",
            "category": " Subscribe to",
            "data": {}
        }]

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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'days',
                                            'label': ' Number of days of synchronization'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'users',
                                            'label': ' User list',
                                            'placeholder': ' Douban userID， Separate more than one by english commas'
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
            "days": 7,
            "users": "",
            "clear": False
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
            doubanid = history.get("doubanid")
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
                                            'content': [
                                                {
                                                    'component': 'a',
                                                    'props': {
                                                        'href': f"https://movie.douban.com/subject/{doubanid}",
                                                        'target': '_blank'
                                                    },
                                                    'text': title
                                                }
                                            ]
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

    def __update_config(self):
        """
        Updating the configuration
        """
        self.update_config({
            "enabled": self._enabled,
            "notify": self._notify,
            "onlyonce": self._onlyonce,
            "cron": self._cron,
            "days": self._days,
            "users": self._users,
            "clear": self._clear
        })

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

    def sync(self):
        """
        Via the userRSS Synchronized douban wants to see the data
        """
        if not self._users:
            return
        #  Read history
        if self._clearflag:
            history = []
        else:
            history: List[dict] = self.get_data('history') or []
        for user_id in self._users.split(","):
            #  Synchronize each user's douban data
            if not user_id:
                continue
            logger.info(f" Starting to synchronize users {user_id}  The douban wants to see the data ...")
            url = self._interests_url % user_id
            results = self.rsshelper.parse(url)
            if not results:
                logger.error(f" No users acquired {user_id}  Douban, prc social networking websiteRSS Digital：{url}")
                continue
            else:
                logger.info(f"Get user {user_id} Douban RSS data: {len(results)}")
            #  Parsing data
            for result in results:
                try:
                    dtype = result.get("title", "")[:2]
                    title = result.get("title", "")[2:]
                    if dtype not in [" Want to see"]:
                        logger.info(f'Title: {title}, if you don’t want to see the data, skip')
                        continue
                    if not result.get("link"):
                        logger.warn(f'Title: {title}, link not obtained, skip')
                        continue
                    #  Determine if it is in the range of days
                    pubdate: Optional[datetime.datetime] = result.get("pubdate")
                    if pubdate:
                        if (datetime.datetime.now(datetime.timezone.utc) - pubdate).days > float(self._days):
                            logger.info(f' Days of synchronization exceeded， Caption：{title}， Release time：{pubdate}')
                            continue
                    douban_id = result.get("link", "").split("/")[-2]
                    #  Check to see if it's been handled
                    if not douban_id or douban_id in [h.get("doubanid") for h in history]:
                        logger.info(f'Title: {title}, Douban ID: {douban_id} has been processed')
                        continue
                    #  According to doubanID Get douban data
                    doubaninfo: Optional[dict] = self.chain.douban_info(doubanid=douban_id)
                    if not doubaninfo:
                        logger.warn(f' No doujinshi information obtained， Caption：{title}， Douban, prc social networking websiteID：{douban_id}')
                        continue
                    logger.info(f' Get the doujinshi information， Caption：{title}， Douban, prc social networking websiteID：{douban_id}')
                    #  Identify media messages
                    meta = MetaInfo(doubaninfo.get("original_title") or doubaninfo.get("title"))
                    if doubaninfo.get("year"):
                        meta.year = doubaninfo.get("year")
                    mediainfo: MediaInfo = self.chain.recognize_media(meta=meta)
                    if not mediainfo:
                        logger.warn(f' No media messages recognized， Caption：{title}， Douban, prc social networking websiteID：{douban_id}')
                        continue
                    #  Querying missing media information
                    exist_flag, no_exists = self.downloadchain.get_no_exists_info(meta=meta, mediainfo=mediainfo)
                    if exist_flag:
                        logger.info(f'{mediainfo.title_year}  Already exists in the media library')
                        action = "exist"
                    else:
                        logger.info(f'{mediainfo.title_year}  Not available in the media library， Start searching ...')
                        #  Look for sth.
                        contexts = self.searchchain.process(mediainfo=mediainfo,
                                                            no_exists=no_exists)
                        if not contexts:
                            logger.warn(f'{mediainfo.title_year}  No resources searched')
                            #  Add subscription
                            self.subscribechain.add(title=mediainfo.title,
                                                    year=mediainfo.year,
                                                    mtype=mediainfo.type,
                                                    tmdbid=mediainfo.tmdb_id,
                                                    season=meta.begin_season,
                                                    exist_ok=True,
                                                    username=" Douban wants to see")
                            action = "subscribe"
                        else:
                            #  Automatic download
                            downloads, lefts = self.downloadchain.batch_download(contexts=contexts, no_exists=no_exists)
                            if downloads and not lefts:
                                #  All downloads complete
                                logger.info(f'{mediainfo.title_year}  Download complete')
                                action = "download"
                            else:
                                #  Unfinished downloads
                                logger.info(f'{mediainfo.title_year}  Not downloaded not complete， Add subscription ...')
                                #  Add subscription
                                self.subscribechain.add(title=mediainfo.title,
                                                        year=mediainfo.year,
                                                        mtype=mediainfo.type,
                                                        tmdbid=mediainfo.tmdb_id,
                                                        season=meta.begin_season,
                                                        exist_ok=True,
                                                        username=" Douban wants to see")
                                action = "subscribe"
                    #  Storing history
                    history.append({
                        "action": action,
                        "title": doubaninfo.get("title") or mediainfo.title,
                        "type": mediainfo.type.value,
                        "year": mediainfo.year,
                        "poster": mediainfo.get_poster_image(),
                        "overview": mediainfo.overview,
                        "tmdbid": mediainfo.tmdb_id,
                        "doubanid": douban_id,
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except Exception as err:
                    logger.error(f' Synchronized users {user_id}  Douban wants to see an error in the data：{err}')
            logger.info(f" Subscribers {user_id}  Douban wants to see the synchronization completed")
        #  Save history
        self.save_data('history', history)
        #  Cache is only cleared once
        self._clearflag = False

    @eventmanager.register(EventType.DoubanSync)
    def remote_sync(self, event: Event):
        """
        Douban wants to see synchronization
        """
        if event:
            logger.info("收到命令，开始执行Douban wants to see synchronization ...")
            self.post_message(channel=event.event_data.get("channel"),
                              title=" Started synchronizing with douban wanting to watch ...",
                              userid=event.event_data.get("user"))
        self.sync()

        if event:
            self.post_message(channel=event.event_data.get("channel"),
                              title=" Synchronized douban wants to see data completion！", userid=event.event_data.get("user"))
