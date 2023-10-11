import datetime
import re
import xml.dom.minidom
from threading import Event
from typing import Tuple, List, Dict, Any, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.chain.download import DownloadChain
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.metainfo import MetaInfo
from app.log import logger
from app.plugins import _PluginBase
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils


class DoubanRank(_PluginBase):
    #  Plug-in name
    plugin_name = " Douban list subscription"
    #  Plugin description
    plugin_desc = " Monitor the douban hot list， Automatically add subscriptions。"
    #  Plug-in icons
    plugin_icon = "movie.jpg"
    #  Theme color
    plugin_color = "#01B3E3"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "doubanrank_"
    #  Loading sequence
    plugin_order = 6
    #  Available user levels
    auth_level = 2

    #  Logout event
    _event = Event()
    #  Private property
    downloadchain: DownloadChain = None
    subscribechain: SubscribeChain = None
    _scheduler = None
    _douban_address = {
        'movie-ustop': 'https://rsshub.app/douban/movie/ustop',
        'movie-weekly': 'https://rsshub.app/douban/movie/weekly',
        'movie-real-time': 'https://rsshub.app/douban/movie/weekly/subject_real_time_hotest',
        'show-domestic': 'https://rsshub.app/douban/movie/weekly/show_domestic',
        'movie-hot-gaia': 'https://rsshub.app/douban/movie/weekly/movie_hot_gaia',
        'tv-hot': 'https://rsshub.app/douban/movie/weekly/tv_hot',
        'movie-top250': 'https://rsshub.app/douban/movie/weekly/movie_top250',
    }
    _enabled = False
    _cron = ""
    _onlyonce = False
    _rss_addrs = []
    _ranks = []
    _vote = 0
    _clear = False
    _clearflag = False

    def init_plugin(self, config: dict = None):
        self.downloadchain = DownloadChain(self.db)
        self.subscribechain = SubscribeChain(self.db)

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._onlyonce = config.get("onlyonce")
            self._vote = float(config.get("vote")) if config.get("vote") else 0
            rss_addrs = config.get("rss_addrs")
            if rss_addrs:
                if isinstance(rss_addrs, str):
                    self._rss_addrs = rss_addrs.split('\n')
                else:
                    self._rss_addrs = rss_addrs
            else:
                self._rss_addrs = []
            self._ranks = config.get("ranks") or []
            self._clear = config.get("clear")

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Starting services
        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                logger.info(f" Douban list subscription service launched， Cyclicality：{self._cron}")
                try:
                    self._scheduler.add_job(func=self.__refresh_rss,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Douban list subscription")
                except Exception as e:
                    logger.error(f" Douban list subscription service failed to start， Error message：{str(e)}")
                    self.systemmessage.put(f" Douban list subscription service failed to start， Error message：{str(e)}")
            else:
                self._scheduler.add_job(func=self.__refresh_rss, trigger='date',
                                        run_date=datetime.datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3)
                                        )
                logger.info(" Douban list subscription service launched， Cyclicality： Everyday 08:00")

            if self._onlyonce:
                logger.info(" Douban list subscription service launched， Run one immediately")
                self._scheduler.add_job(func=self.__refresh_rss, trigger='date',
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

            if self._scheduler.get_jobs():
                #  Starting services
                self._scheduler.print_jobs()
                self._scheduler.start()

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
                                            'model': 'vote',
                                            'label': ' Score (of student's work)',
                                            'placeholder': ' Subscribe only if the rating is greater than or equal to this value'
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
                                            'model': 'ranks',
                                            'label': ' Hot list',
                                            'items': [
                                                {'title': ' Movie north american box office chart', 'value': 'movie-ustop'},
                                                {'title': ' Weekly word-of-mouth movie list', 'value': 'movie-weekly'},
                                                {'title': ' Hot movies', 'value': 'movie-real-time'},
                                                {'title': ' Hot variety', 'value': 'show-domestic'},
                                                {'title': ' Hot movies', 'value': 'movie-hot-gaia'},
                                                {'title': ' Popular tv series', 'value': 'tv-hot'},
                                                {'title': ' CinematicTOP10', 'value': 'movie-top250'},
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
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'rss_addrs',
                                            'label': ' Customized list address',
                                            'placeholder': ' One address per line， As if：https://rsshub.app/douban/movie/ustop'
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
            "cron": "",
            "onlyonce": False,
            "vote": "",
            "ranks": [],
            "rss_addrs": "",
            "clear": False
        }

    def get_page(self) -> List[dict]:
        """
        Patchwork plug-in detail page， Need to return to page configuration， Also with data
        """
        #  Query history
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

    def stop_service(self):
        """
        Discontinuation of services
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
        New configuration
        """
        self.update_config({
            "enabled": self._enabled,
            "cron": self._cron,
            "onlyonce": self._onlyonce,
            "vote": self._vote,
            "ranks": self._ranks,
            "rss_addrs": self._rss_addrs,
            "clear": self._clear
        })

    def __refresh_rss(self):
        """
        Refresh (computer window)RSS
        """
        logger.info(f" Start refreshing the beanstalk list ...")
        addr_list = self._rss_addrs + [self._douban_address.get(rank) for rank in self._ranks]
        if not addr_list:
            logger.info(f" No list setRSS Address")
            return
        else:
            logger.info(f" Common {len(addr_list)}  List of namesRSS Address needs to be refreshed")

        #  Read history
        if self._clearflag:
            history = []
        else:
            history: List[dict] = self.get_data('history') or []

        for addr in addr_list:
            if not addr:
                continue
            try:
                logger.info(f" GainRSS：{addr} ...")
                rss_infos = self.__get_rss_info(addr)
                if not rss_infos:
                    logger.error(f"RSS Address：{addr} ， Data not queried")
                    continue
                else:
                    logger.info(f"RSS Address：{addr} ， Common {len(rss_infos)}  Data entry")
                for rss_info in rss_infos:
                    if self._event.is_set():
                        logger.info(f" Subscription service discontinued")
                        return

                    title = rss_info.get('title')
                    douban_id = rss_info.get('doubanid')
                    unique_flag = f"doubanrank: {title} (DB:{douban_id})"
                    #  Check if it has been processed
                    if unique_flag in [h.get("unique") for h in history]:
                        continue
                    #  Identify media messages
                    if douban_id:
                        #  According to doubanID Get douban data
                        doubaninfo: Optional[dict] = self.chain.douban_info(doubanid=douban_id)
                        if not doubaninfo:
                            logger.warn(f' No doujinshi information obtained， Caption：{title}， Douban, prc social networking websiteID：{douban_id}')
                            continue
                        logger.info(f' Get the doujinshi information， Caption：{title}， Douban, prc social networking websiteID：{douban_id}')
                        #  Recognize
                        title = doubaninfo.get("title")
                        meta = MetaInfo(doubaninfo.get("original_title") or title)
                        if doubaninfo.get("year"):
                            meta.year = doubaninfo.get("year")
                    else:
                        meta = MetaInfo(title)
                    #  Matching media messages
                    mediainfo: MediaInfo = self.chain.recognize_media(meta=meta)
                    if not mediainfo:
                        logger.warn(f' No media messages recognized， Caption：{title}， Douban, prc social networking websiteID：{douban_id}')
                        continue
                    #  Querying missing media information
                    exist_flag, _ = self.downloadchain.get_no_exists_info(meta=meta, mediainfo=mediainfo)
                    if exist_flag:
                        logger.info(f'{mediainfo.title_year}  Already exists in the media library')
                        continue
                    #  Add subscription
                    self.subscribechain.add(title=mediainfo.title,
                                            year=mediainfo.year,
                                            mtype=mediainfo.type,
                                            tmdbid=mediainfo.tmdb_id,
                                            season=meta.begin_season,
                                            exist_ok=True,
                                            username=" Douban list")
                    #  Storing history
                    history.append({
                        "title": title,
                        "type": mediainfo.type.value,
                        "year": mediainfo.year,
                        "poster": mediainfo.get_poster_image(),
                        "overview": mediainfo.overview,
                        "tmdbid": mediainfo.tmdb_id,
                        "doubanid": douban_id,
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "unique": unique_flag
                    })
            except Exception as e:
                logger.error(str(e))

        #  Save history
        self.save_data('history', history)
        #  Cache is only cleared once
        self._clearflag = False
        logger.info(f" All listsRSS Refresh complete.")

    @staticmethod
    def __get_rss_info(addr):
        """
        GainRSS
        """
        try:
            ret = RequestUtils().get_res(addr)
            if not ret:
                return []
            ret.encoding = ret.apparent_encoding
            ret_xml = ret.text
            ret_array = []
            #  AnalyzeXML
            dom_tree = xml.dom.minidom.parseString(ret_xml)
            rootNode = dom_tree.documentElement
            items = rootNode.getElementsByTagName("item")
            for item in items:
                try:
                    #  Caption
                    title = DomUtils.tag_value(item, "title", default="")
                    #  Link (on a website)
                    link = DomUtils.tag_value(item, "link", default="")
                    if not title and not link:
                        logger.warn(f" Entry title and link are empty， Cannot be processed")
                        continue
                    doubanid = re.findall(r"/(\d+)/", link)
                    if doubanid:
                        doubanid = doubanid[0]
                    if doubanid and not str(doubanid).isdigit():
                        logger.warn(f" Analyzed doubanID Incorrect formatting：{doubanid}")
                        continue
                    #  Return object
                    ret_array.append({
                        'title': title,
                        'link': link,
                        'doubanid': doubanid
                    })
                except Exception as e1:
                    logger.error(" AnalyzeRSS Entry failure：" + str(e1))
                    continue
            return ret_array
        except Exception as e:
            logger.error("GainRSS失败：" + str(e))
            return []
