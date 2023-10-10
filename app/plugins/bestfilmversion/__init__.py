from datetime import datetime, timedelta
from functools import reduce
from pathlib import Path
from threading import RLock
from typing import Optional, Any, List, Dict, Tuple
from xml.dom.minidom import parseString

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from requests import Response

from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.event import eventmanager
from app.log import logger
from app.modules.emby import Emby
from app.modules.jellyfin import Jellyfin
from app.modules.plex import Plex
from app.plugins import _PluginBase
from app.schemas import WebhookEventInfo
from app.schemas.types import MediaType, EventType
from app.utils.http import RequestUtils

lock = RLock()


class BestFilmVersion(_PluginBase):
    #  Plug-in name
    plugin_name = " Collection wash"
    #  Plugin description
    plugin_desc = "Jellyfin/Emby/Plex After clicking favorite movies， Automatic subscription washout。"
    #  Plug-in icons
    plugin_icon = "like.jpg"
    #  Theme color
    plugin_color = "#E4003F"
    #  Plug-in version
    plugin_version = "2.0"
    #  Plug-in authors
    plugin_author = "wlj"
    #  Author's homepage
    author_url = "https://github.com/developer-wlj"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "bestfilmversion_"
    #  Loading sequence
    plugin_order = 13
    #  Available user levels
    auth_level = 2

    #  Private variable
    _scheduler: Optional[BackgroundScheduler] = None
    _cache_path: Optional[Path] = None
    subscribechain = None

    #  Configuration properties
    _enabled: bool = False
    _cron: str = ""
    _notify: bool = False
    _webhook_enabled: bool = False
    _only_once: bool = False

    def init_plugin(self, config: dict = None):
        self._cache_path = settings.TEMP_PATH / "__best_film_version_cache__"
        self.subscribechain = SubscribeChain(self.db)

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Configure
        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._webhook_enabled = config.get("webhook_enabled")
            self._only_once = config.get("only_once")

        if self._enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if not self._webhook_enabled:
                if self._cron:
                    try:
                        self._scheduler.add_job(func=self.sync,
                                                trigger=CronTrigger.from_crontab(self._cron),
                                                name=" Collection wash")
                    except Exception as err:
                        logger.error(f" Timed task configuration error：{err}")
                        #  Push real-time messages
                        self.systemmessage.put(f" Execution cycle misconfiguration：{err}")
                else:
                    self._scheduler.add_job(self.sync, "interval", minutes=30, name=" Collection wash")

            if self._only_once:
                self._only_once = False
                self.update_config({
                    "enabled": self._enabled,
                    "cron": self._cron,
                    "notify": self._notify,
                    "webhook_enabled": self._webhook_enabled,
                    "only_once": self._only_once
                })
                self._scheduler.add_job(self.sync, 'date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name=" Run now favorite washed version")
            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
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
                                    'md': 3
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
                                    'md': 3
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
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'only_once',
                                            'label': ' Run one immediately',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'webhook_enabled',
                                            'label': 'Webhook',
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': ' Implementation period',
                                            'placeholder': '5 Classifier for honorific peoplecron Displayed formula， Leave blank spaces in writing'
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
                                            'text': ' Supports proactive timed acquisition of media library data andWebhook Real-time triggering in two ways， It's one or the other.，'
                                                    'Webhook You need to set up the media server to sendWebhook Telegram。'
                                                    'Plex When using active acquisition， It is recommended that the execution period be set greater than1 Hourly，'
                                                    ' FavoriteApi Call (programming)Plex Official website interface， Frequency limited。'
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
            "cron": "*/30 * * * *",
            "webhook_enabled": False,
            "only_once": False
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
            tmdbid = history.get("tmdbid")
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
                                                        'href': f"https://www.themoviedb.org/movie/{tmdbid}",
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
        Favorites via streaming management tool, Automatic plate washing
        """
        #  Acquisition lock
        _is_lock: bool = lock.acquire(timeout=60)
        if not _is_lock:
            return
        try:
            #  Read cache
            caches = self._cache_path.read_text().split("\n") if self._cache_path.exists() else []
            #  Read history
            history = self.get_data('history') or []

            #  Media server type， Many of, Segregation
            if not settings.MEDIASERVER:
                return
            media_servers = settings.MEDIASERVER.split(',')

            #  Read favorites
            all_items = {}
            for media_server in media_servers:
                if media_server == 'jellyfin':
                    all_items['jellyfin'] = self.jellyfin_get_items()
                elif media_server == 'emby':
                    all_items['emby'] = self.emby_get_items()
                else:
                    all_items['plex'] = self.plex_get_watchlist()

            def function(y, x):
                return y if (x['Name'] in [i['Name'] for i in y]) else (lambda z, u: (z.append(u), z))(y, x)[1]

            #  Process all results
            for server, all_item in all_items.items():
                # all_item  De-weighting based on movie titles
                result = reduce(function, all_item, [])
                for data in result:
                    #  Checking the cache
                    if data.get('Name') in caches:
                        continue

                    #  Get details
                    if server == 'jellyfin':
                        item_info_resp = Jellyfin().get_iteminfo(itemid=data.get('Id'))
                    elif server == 'emby':
                        item_info_resp = Emby().get_iteminfo(itemid=data.get('Id'))
                    else:
                        item_info_resp = self.plex_get_iteminfo(itemid=data.get('Id'))
                    logger.debug(f'BestFilmVersion Plug-in (software component) item Printable {item_info_resp}')
                    if not item_info_resp:
                        continue

                    #  Accept onlyMovie Typology
                    if data.get('Type') != 'Movie':
                        continue

                    #  Gaintmdb_id
                    tmdb_id = item_info_resp.tmdbid
                    if not tmdb_id:
                        continue
                    #  Identify media messages
                    mediainfo: MediaInfo = self.chain.recognize_media(tmdbid=tmdb_id, mtype=MediaType.MOVIE)
                    if not mediainfo:
                        logger.warn(f' No media messages recognized， Caption：{data.get("Name")}，tmdbid：{tmdb_id}')
                        continue
                    #  Add subscription
                    self.subscribechain.add(mtype=MediaType.MOVIE,
                                            title=mediainfo.title,
                                            year=mediainfo.year,
                                            tmdbid=mediainfo.tmdb_id,
                                            best_version=True,
                                            username=" Collection wash",
                                            exist_ok=True)
                    #  Add to cache
                    caches.append(data.get('Name'))
                    #  Storing history
                    if mediainfo.tmdb_id not in [h.get("tmdbid") for h in history]:
                        history.append({
                            "title": mediainfo.title,
                            "type": mediainfo.type.value,
                            "year": mediainfo.year,
                            "poster": mediainfo.get_poster_image(),
                            "overview": mediainfo.overview,
                            "tmdbid": mediainfo.tmdb_id,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
            #  Save history
            self.save_data('history', history)
            #  Save cache
            self._cache_path.write_text("\n".join(caches))
        finally:
            lock.release()

    def jellyfin_get_items(self) -> List[dict]:
        #  Get alluser
        users_url = "[HOST]Users?&apikey=[APIKEY]"
        users = self.get_users(Jellyfin().get_data(users_url))
        if not users:
            logger.info(f"bestfilmversion/users_url: {users_url}")
            return []
        all_items = []
        for user in users:
            #  Based on date of accession  Descending order
            url = "[HOST]Users/" + user + "/Items?SortBy=DateCreated%2CSortName" \
                                          "&SortOrder=Descending" \
                                          "&Filters=IsFavorite" \
                                          "&Recursive=true" \
                                          "&Fields=PrimaryImageAspectRatio%2CBasicSyncInfo" \
                                          "&CollapseBoxSetItems=false" \
                                          "&ExcludeLocationTypes=Virtual" \
                                          "&EnableTotalRecordCount=false" \
                                          "&Limit=20" \
                                          "&apikey=[APIKEY]"
            resp = self.get_items(Jellyfin().get_data(url))
            if not resp:
                continue
            all_items.extend(resp)
        return all_items

    def emby_get_items(self) -> List[dict]:
        #  Get alluser
        get_users_url = "[HOST]Users?&api_key=[APIKEY]"
        users = self.get_users(Emby().get_data(get_users_url))
        if not users:
            return []
        all_items = []
        for user in users:
            #  Based on date of accession  Descending order
            url = "[HOST]emby/Users/" + user + "/Items?SortBy=DateCreated%2CSortName" \
                                               "&SortOrder=Descending" \
                                               "&Filters=IsFavorite" \
                                               "&Recursive=true" \
                                               "&Fields=PrimaryImageAspectRatio%2CBasicSyncInfo" \
                                               "&CollapseBoxSetItems=false" \
                                               "&ExcludeLocationTypes=Virtual" \
                                               "&EnableTotalRecordCount=false" \
                                               "&Limit=20&api_key=[APIKEY]"
            resp = self.get_items(Emby().get_data(url))
            if not resp:
                continue
            all_items.extend(resp)
        return all_items

    @staticmethod
    def get_items(resp: Response):
        try:
            if resp:
                return resp.json().get("Items") or []
            else:
                return []
        except Exception as e:
            print(str(e))
            return []

    @staticmethod
    def get_users(resp: Response):
        try:
            if resp:
                return [data['Id'] for data in resp.json()]
            else:
                logger.error(f"BestFilmVersion/Users  Return data not obtained")
                return []
        except Exception as e:
            logger.error(f" GroutBestFilmVersion/Users  Make a mistake：" + str(e))
            return []

    @staticmethod
    def plex_get_watchlist() -> List[dict]:
        #  Based on date of accession  Descending order
        url = f"https://metadata.provider.plex.tv/library/sections/watchlist/all?type=1&sort=addedAt%3Adesc" \
              f"&X-Plex-Container-Start=0&X-Plex-Container-Size=50" \
              f"&X-Plex-Token={settings.PLEX_TOKEN}"
        res = []
        try:
            resp = RequestUtils().get_res(url=url)
            if resp:
                dom = parseString(resp.text)
                #  Getting document element objects
                elem = dom.documentElement
                #  Gain  Specify element
                eles = elem.getElementsByTagName('Video')
                if not eles:
                    return []
                for ele in eles:
                    data = {}
                    #  Getting content in tags
                    ele_id = ele.attributes['ratingKey'].nodeValue
                    ele_title = ele.attributes['title'].nodeValue
                    ele_type = ele.attributes['type'].nodeValue
                    _type = "Movie" if ele_type == "movie" else ""
                    data['Id'] = ele_id
                    data['Name'] = ele_title
                    data['Type'] = _type
                    res.append(data)
                return res
            else:
                logger.error(f"Plex/Watchlist  Return data not obtained")
                return []
        except Exception as e:
            logger.error(f" GroutPlex/Watchlist  Make a mistake：" + str(e))
            return []

    @staticmethod
    def plex_get_iteminfo(itemid):
        url = f"https://metadata.provider.plex.tv/library/metadata/{itemid}" \
              f"?X-Plex-Token={settings.PLEX_TOKEN}"
        ids = []
        try:
            resp = RequestUtils(accept_type="application/json, text/plain, */*").get_res(url=url)
            if resp:
                metadata = resp.json().get('MediaContainer').get('Metadata')
                for item in metadata:
                    _guid = item.get('Guid')
                    if not _guid:
                        continue

                    id_list = [h.get('id') for h in _guid if h.get('id').__contains__("tmdb")]
                    if not id_list:
                        continue

                    ids.append({'Name': 'TheMovieDb', 'Url': id_list[0]})

                if not ids:
                    return []
                return {'ExternalUrls': ids}
            else:
                logger.error(f"Plex/Items  Return data not obtained")
                return []
        except Exception as e:
            logger.error(f" GroutPlex/Items  Make a mistake：" + str(e))
            return []

    @eventmanager.register(EventType.WebhookMessage)
    def webhook_message_action(self, event):

        if not self._enabled:
            return
        if not self._webhook_enabled:
            return

        data: WebhookEventInfo = event.event_data
        #  Exclusion is not a collection call
        if data.channel not in ['jellyfin', 'emby', 'plex']:
            return
        if data.channel in ['emby', 'plex'] and data.event != 'item.rate':
            return
        if data.channel == 'jellyfin' and data.save_reason != 'UpdateUserRating':
            return
        logger.info(f'BestFilmVersion/webhook_message_action WebhookEventInfo Printable：{data}')

        #  Acquisition lock
        _is_lock: bool = lock.acquire(timeout=60)
        if not _is_lock:
            return
        try:
            if not data.tmdb_id:
                info = None
                if (data.channel == 'jellyfin'
                        and data.save_reason == 'UpdateUserRating'
                        and data.item_favorite):
                    info = Jellyfin().get_iteminfo(itemid=data.item_id)
                elif data.channel == 'emby' and data.event == 'item.rate':
                    info = Emby().get_iteminfo(itemid=data.item_id)
                elif data.channel == 'plex' and data.event == 'item.rate':
                    info = Plex().get_iteminfo(itemid=data.item_id)
                logger.debug(f'BestFilmVersion/webhook_message_action item Printable：{info}')
                if not info:
                    return
                if info.item_type not in ['Movie', 'MOV', 'movie']:
                    return
                #  Gaintmdb_id
                tmdb_id = info.tmdbid
            else:
                tmdb_id = data.tmdb_id
                if (data.channel == 'jellyfin'
                        and (data.save_reason != 'UpdateUserRating' or not data.item_favorite)):
                    return
                if data.item_type not in ['Movie', 'MOV', 'movie']:
                    return
            #  Identify media messages
            mediainfo = self.chain.recognize_media(tmdbid=tmdb_id, mtype=MediaType.MOVIE)
            if not mediainfo:
                logger.warn(f' No media messages recognized， Caption：{data.item_name}，tmdbID：{tmdb_id}')
                return
            #  Read cache
            caches = self._cache_path.read_text().split("\n") if self._cache_path.exists() else []
            #  Checking the cache
            if data.item_name in caches:
                return
            #  Read history
            history = self.get_data('history') or []
            #  Add subscription
            self.subscribechain.add(mtype=MediaType.MOVIE,
                                    title=mediainfo.title,
                                    year=mediainfo.year,
                                    tmdbid=mediainfo.tmdb_id,
                                    best_version=True,
                                    username=" Collection wash",
                                    exist_ok=True)
            #  Add to cache
            caches.append(data.item_name)
            #  Storing history
            if mediainfo.tmdb_id not in [h.get("tmdbid") for h in history]:
                history.append({
                    "title": mediainfo.title,
                    "type": mediainfo.type.value,
                    "year": mediainfo.year,
                    "poster": mediainfo.get_poster_image(),
                    "overview": mediainfo.overview,
                    "tmdbid": mediainfo.tmdb_id,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            #  Save history
            self.save_data('history', history)
            #  Save cache
            self._cache_path.write_text("\n".join(caches))
        finally:
            lock.release()
