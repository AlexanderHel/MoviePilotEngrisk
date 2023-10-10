import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.chain.transfer import TransferChain
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.db.models.transferhistory import TransferHistory
from app.log import logger
from app.modules.emby import Emby
from app.modules.jellyfin import Jellyfin
from app.modules.qbittorrent import Qbittorrent
from app.modules.themoviedb.tmdbv3api import Episode
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.schemas.types import NotificationType, EventType, MediaType


class MediaSyncDel(_PluginBase):
    #  Plug-in name
    plugin_name = " Simultaneous deletion of media files"
    #  Plugin description
    plugin_desc = " Synchronized delete history、 Source files and download tasks。"
    #  Plug-in icons
    plugin_icon = "mediasyncdel.png"
    #  Theme color
    plugin_color = "#ff1a1a"
    #  Plug-in version
    plugin_version = "1.1"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "mediasyncdel_"
    #  Loading sequence
    plugin_order = 9
    #  Available user levels
    auth_level = 1

    #  Private property
    episode = None
    _scheduler: Optional[BackgroundScheduler] = None
    _enabled = False
    _sync_type: str = ""
    _cron: str = ""
    _notify = False
    _del_source = False
    _exclude_path = None
    _library_path = None
    _transferchain = None
    _transferhis = None
    _downloadhis = None
    qb = None
    tr = None

    def init_plugin(self, config: dict = None):
        self._transferchain = TransferChain(self.db)
        self._transferhis = self._transferchain.transferhis
        self._downloadhis = self._transferchain.downloadhis
        self.episode = Episode()
        self.qb = Qbittorrent()
        self.tr = Transmission()

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Read configuration
        if config:
            self._enabled = config.get("enabled")
            self._sync_type = config.get("sync_type")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._del_source = config.get("del_source")
            self._exclude_path = config.get("exclude_path")
            self._library_path = config.get("library_path")

        if self._enabled and str(self._sync_type) == "log":
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                try:
                    self._scheduler.add_job(func=self.sync_del_by_log,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Media library synchronized deletion")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")
                    #  Push real-time messages
                    self.systemmessage.put(f" Execution cycle misconfiguration：{err}")
            else:
                self._scheduler.add_job(self.sync_del_by_log, "interval", minutes=30, name=" Media library synchronized deletion")

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        Defining remote control commands
        :return:  Command keywords、 Event、 Descriptive、 Accompanying data
        """
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
                                            'model': 'del_source',
                                            'label': ' Deleting source files',
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'sync_type',
                                            'label': ' Media library synchronization method',
                                            'items': [
                                                {'title': 'Webhook', 'value': 'webhook'},
                                                {'title': ' Log (computing)', 'value': 'log'},
                                                {'title': 'Scripter X', 'value': 'plugin'}
                                            ]
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': ' Log checking cycle',
                                            'placeholder': '5 Classifier for honorific peoplecron Displayed formula， Leave blank spaces in writing'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'exclude_path',
                                            'label': ' Excluded paths'
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
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'library_path',
                                            'rows': '2',
                                            'label': ' Media library path mapping',
                                            'placeholder': ' Media server path:MoviePilot Trails（ One in a row）'
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
                                            'text': ' The media library synchronization methods are divided intoWebhook、 Log synchronization andScripter X：'
                                                    '1、Webhook NeedEmby4.8.0.45 And above turn on the media deletedWebhook。'
                                                    '2、 Log synchronization requires a configurable check period， Default (setting)30 Performed once a minute。'
                                                    '3、Scripter X The approach needs to beemby Installation and configurationScripter X Plug-in (software component)， No need to configure execution cycles。'
                                                    '4、 After enabling the plugin， Non-media server triggered source file deletion， Download tasks in the downloader are also processed synchronously。'
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
            "del_source": False,
            "library_path": "",
            "sync_type": "webhook",
            "cron": "*/30 * * * *",
            "exclude_path": "",
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
        historys = sorted(historys, key=lambda x: x.get('del_time'), reverse=True)
        #  Assembly page
        contents = []
        for history in historys:
            htype = history.get("type")
            title = history.get("title")
            year = history.get("year")
            season = history.get("season")
            episode = history.get("episode")
            image = history.get("image")
            del_time = history.get("del_time")

            if season:
                sub_contents = [
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Typology：{htype}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Caption：{title}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Particular year：{year}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Classifier for seasonal crop yield or seasons of a tv series：{season}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Classifier for sections of a tv series e.g. episode：{episode}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Timing：{del_time}'
                    }
                ]
            else:
                sub_contents = [
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Typology：{htype}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Caption：{title}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Particular year：{year}'
                    },
                    {
                        'component': 'VCardText',
                        'props': {
                            'class': 'pa-0 px-2'
                        },
                        'text': f' Timing：{del_time}'
                    }
                ]

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
                                                'src': image,
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
                                    'content': sub_contents
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

    @eventmanager.register(EventType.WebhookMessage)
    def sync_del_by_webhook(self, event: Event):
        """
        emby Delete media library synchronized delete history
        webhook
        """
        if not self._enabled or str(self._sync_type) != "webhook":
            return

        event_data = event.event_data
        event_type = event_data.event

        # Emby Webhook event_type = library.deleted
        if not event_type or str(event_type) != 'library.deleted':
            return

        #  Media type
        media_type = event_data.item_type
        #  Media name
        media_name = event_data.item_name
        #  Media path
        media_path = event_data.item_path
        # tmdb_id
        tmdb_id = event_data.tmdb_id
        #  Quarter
        season_num = event_data.season_id
        #  Episode number (of a tv series etc)
        episode_num = event_data.episode_id

        self.__sync_del(media_type=media_type,
                        media_name=media_name,
                        media_path=media_path,
                        tmdb_id=tmdb_id,
                        season_num=season_num,
                        episode_num=episode_num)

    @eventmanager.register(EventType.WebhookMessage)
    def sync_del_by_plugin(self, event):
        """
        emby Delete media library synchronized delete history
        Scripter X Plug-in (software component)
        """
        if not self._enabled or str(self._sync_type) != "plugin":
            return

        event_data = event.event_data
        event_type = event_data.event

        # Scripter X Plug-in (software component) event_type = media_del
        if not event_type or str(event_type) != 'media_del':
            return

        # Scripter X Plug-in (software component) 需要是否虚拟标识
        item_isvirtual = event_data.item_isvirtual
        if not item_isvirtual:
            logger.error("Scripter X Plug-in (software component)方式，item_isvirtual参数未配置，为防止误删除，暂停插件运行")
            self.update_config({
                "enabled": False,
                "del_source": self._del_source,
                "exclude_path": self._exclude_path,
                "library_path": self._library_path,
                "notify": self._notify,
                "cron": self._cron,
                "sync_type": self._sync_type,
            })
            return

        #  If it's a virtualitem， Failing agreementreturn， No deletion
        if item_isvirtual == 'True':
            return

        #  Media type
        media_type = event_data.item_type
        #  Media name
        media_name = event_data.item_name
        #  Media path
        media_path = event_data.item_path
        # tmdb_id
        tmdb_id = event_data.tmdb_id
        #  Quarter
        season_num = event_data.season_id
        #  Episode number (of a tv series etc)
        episode_num = event_data.episode_id

        self.__sync_del(media_type=media_type,
                        media_name=media_name,
                        media_path=media_path,
                        tmdb_id=tmdb_id,
                        season_num=season_num,
                        episode_num=episode_num)

    def __sync_del(self, media_type: str, media_name: str, media_path: str,
                   tmdb_id: int, season_num: str, episode_num: str):
        """
        Execute deletion logic
        """
        if not media_type:
            logger.error(f"{media_name}  Synchronized deletion failure， Media type not captured")
            return
        if not tmdb_id or not str(tmdb_id).isdigit():
            logger.error(f"{media_name}  Synchronized deletion failure， Not availableTMDB ID")
            return

        if self._exclude_path and media_path and any(
                os.path.abspath(media_path).startswith(os.path.abspath(path)) for path in
                self._exclude_path.split(",")):
            logger.info(f" Media path {media_path}  Excluded， Withheld")
            return

        #  Access to transfer records
        msg, transfer_history = self.__get_transfer_his(media_type=media_type,
                                                        media_name=media_name,
                                                        media_path=media_path,
                                                        tmdb_id=tmdb_id,
                                                        season_num=season_num,
                                                        episode_num=episode_num)

        logger.info(f" Deletions are being synchronized{msg}")

        if not transfer_history:
            logger.warn(f"{media_type} {media_name}  Deletable data not captured， All metadata can be overwritten using the media library scraping plugin")
            return

        #  Start deleting
        image = 'https://emby.media/notificationicon.png'
        year = None
        del_cnt = 0
        stop_cnt = 0
        error_cnt = 0
        for transferhis in transfer_history:
            title = transferhis.title
            if title not in media_name:
                logger.warn(
                    f" Current transfer records {transferhis.id} {title} {transferhis.tmdbid}  With the deletion of the media{media_name} Not conform to， Anti-deletion， No automatic deletion for the time being")
                continue
            image = transferhis.image
            year = transferhis.year

            # 0、 Deletion of transfer records
            self._transferhis.delete(transferhis.id)

            #  Deletion of seed tasks
            if self._del_source:
                # 1、 Delete the source file directly
                if transferhis.src and Path(transferhis.src).suffix in settings.RMT_MEDIAEXT:
                    self._transferchain.delete_files(Path(transferhis.src))
                    if transferhis.download_hash:
                        try:
                            # 2、 Determine if a seed has been deleted
                            delete_flag, success_flag, handle_cnt = self.handle_torrent(src=transferhis.src,
                                                                                        torrent_hash=transferhis.download_hash)
                            if not success_flag:
                                error_cnt += 1
                            else:
                                if delete_flag:
                                    del_cnt += handle_cnt
                                else:
                                    stop_cnt += handle_cnt
                        except Exception as e:
                            logger.error(" Failed to delete seed， Try deleting the source file：%s" % str(e))

        logger.info(f" Synchronous deletion {msg}  Fulfillment！")

        #  Send a message
        if self._notify:
            if media_type == "Episode":
                #  According totmdbid Get picture
                images = self.episode.images(tv_id=tmdb_id,
                                             season_num=season_num,
                                             episode_num=episode_num)
                if images:
                    image = self.get_tmdbimage_url(images[-1].get("file_path"), prefix="original")

            torrent_cnt_msg = ""
            if del_cnt:
                torrent_cnt_msg += f" Delete seeds{del_cnt} Classifier for individual things or people, general, catch-all classifier\n"
            if stop_cnt:
                torrent_cnt_msg += f" Suspension of seeds{stop_cnt} Classifier for individual things or people, general, catch-all classifier\n"
            if error_cnt:
                torrent_cnt_msg += f" Seed deletion failure{error_cnt} Classifier for individual things or people, general, catch-all classifier\n"
            #  Send notification
            self.post_message(
                mtype=NotificationType.MediaServer,
                title=" Media library synchronization deletion task completion",
                image=image,
                text=f"{msg}\n"
                     f" Deletion of records{len(transfer_history)} Classifier for individual things or people, general, catch-all classifier\n"
                     f"{torrent_cnt_msg}"
                     f" Timing {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}"
            )

        #  Read history
        history = self.get_data('history') or []

        history.append({
            "type": " Cinematic" if media_type == "Movie" or media_type == "MOV" else " Dramas",
            "title": media_name,
            "year": year,
            "path": media_path,
            "season": season_num,
            "episode": episode_num,
            "image": image,
            "del_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        })

        #  Preserving history
        self.save_data("history", history)

    def __get_transfer_his(self, media_type: str, media_name: str, media_path: str,
                           tmdb_id: int, season_num: str, episode_num: str):
        """
        Access to transfer records
        """
        #  Quarter
        if season_num and season_num.isdigit():
            season_num = str(season_num).rjust(2, '0')
        else:
            season_num = None
        #  Episode number (of a tv series etc)
        if episode_num and episode_num.isdigit():
            episode_num = str(episode_num).rjust(2, '0')
        else:
            episode_num = None

        #  Typology
        mtype = MediaType.MOVIE if media_type in ["Movie", "MOV"] else MediaType.TV

        #  Handling path mapping ( Handling multiple resolutions of the same media)
        if self._library_path:
            paths = self._library_path.split("\n")
            for path in paths:
                sub_paths = path.split(":")
                if len(sub_paths) < 2:
                    continue
                media_path = media_path.replace(sub_paths[0], sub_paths[1]).replace('\\', '/')

        #  Delete movie
        if mtype == MediaType.MOVIE:
            msg = f' Cinematic {media_name} {tmdb_id}'
            transfer_history: List[TransferHistory] = self._transferhis.get_by(tmdbid=tmdb_id,
                                                                               mtype=mtype.value,
                                                                               dest=media_path)
        #  Delete tv series
        elif mtype == MediaType.TV and not season_num and not episode_num:
            msg = f' Episode {media_name} {tmdb_id}'
            transfer_history: List[TransferHistory] = self._transferhis.get_by(tmdbid=tmdb_id,
                                                                               mtype=mtype.value)
        #  Deletion of the season S02
        elif mtype == MediaType.TV and season_num and not episode_num:
            if not season_num or not str(season_num).isdigit():
                logger.error(f"{media_name}  Seasonal synchronization deletion failure， No specific season obtained")
                return
            msg = f' Episode {media_name} S{season_num} {tmdb_id}'
            transfer_history: List[TransferHistory] = self._transferhis.get_by(tmdbid=tmdb_id,
                                                                               mtype=mtype.value,
                                                                               season=f'S{season_num}')
        #  Delete episodeS02E02
        elif mtype == MediaType.TV and season_num and episode_num:
            if not season_num or not str(season_num).isdigit() or not episode_num or not str(episode_num).isdigit():
                logger.error(f"{media_name}  Set synchronization deletion failure， No specific set obtained")
                return
            msg = f' Episode {media_name} S{season_num}E{episode_num} {tmdb_id}'
            transfer_history: List[TransferHistory] = self._transferhis.get_by(tmdbid=tmdb_id,
                                                                               mtype=mtype.value,
                                                                               season=f'S{season_num}',
                                                                               episode=f'E{episode_num}',
                                                                               dest=media_path)
        else:
            return "", []

        return msg, transfer_history

    def sync_del_by_log(self):
        """
        emby Delete media library synchronized delete history
        Logging methods
        """
        #  Read history
        history = self.get_data('history') or []
        last_time = self.get_data("last_time")
        del_medias = []

        #  Media server type， Many of, Segregation
        if not settings.MEDIASERVER:
            return
        media_servers = settings.MEDIASERVER.split(',')
        for media_server in media_servers:
            if media_server == 'emby':
                del_medias.extend(self.parse_emby_log(last_time))
            elif media_server == 'jellyfin':
                del_medias.extend(self.parse_jellyfin_log(last_time))
            elif media_server == 'plex':
                # TODO plex Parsing logs
                return

        if not del_medias:
            logger.error(" No resolution to deleted media messages")
            return

        #  Iterative deletion
        last_del_time = None
        for del_media in del_medias:
            #  Deletion time
            del_time = del_media.get("time")
            last_del_time = del_time
            #  Media type Movie|Series|Season|Episode
            media_type = del_media.get("type")
            #  Media name 蜀山战纪
            media_name = del_media.get("name")
            #  Year of media 2015
            media_year = del_media.get("year")
            #  Media path /data/series/国产剧/蜀山战纪 (2015)/Season 2/蜀山战纪 - S02E01 - 第1集.mp4
            media_path = del_media.get("path")
            #  Quarter S02
            media_season = del_media.get("season")
            #  Episode number (of a tv series etc) E02
            media_episode = del_media.get("episode")

            #  Exclusion paths are not processed
            if self._exclude_path and media_path and any(
                    os.path.abspath(media_path).startswith(os.path.abspath(path)) for path in
                    self._exclude_path.split(",")):
                logger.info(f" Media path {media_path}  Excluded， Withheld")
                return

            #  Handling path mapping ( Handling multiple resolutions of the same media)
            if self._library_path:
                paths = self._library_path.split("\n")
                for path in paths:
                    sub_paths = path.split(":")
                    if len(sub_paths) < 2:
                        continue
                    media_path = media_path.replace(sub_paths[0], sub_paths[1]).replace('\\', '/')

            #  Getting deleted records
            #  Delete movie
            if media_type == "Movie":
                msg = f' Cinematic {media_name}'
                transfer_history: List[TransferHistory] = self._transferhis.get_by(
                    title=media_name,
                    year=media_year,
                    dest=media_path)
            #  Delete tv series
            elif media_type == "Series":
                msg = f' Episode {media_name}'
                transfer_history: List[TransferHistory] = self._transferhis.get_by(
                    title=media_name,
                    year=media_year)
            #  Deletion of the season S02
            elif media_type == "Season":
                msg = f' Episode {media_name} {media_season}'
                transfer_history: List[TransferHistory] = self._transferhis.get_by(
                    title=media_name,
                    year=media_year,
                    season=media_season)
            #  Delete episodeS02E02
            elif media_type == "Episode":
                msg = f' Episode {media_name} {media_season}{media_episode}'
                transfer_history: List[TransferHistory] = self._transferhis.get_by(
                    title=media_name,
                    year=media_year,
                    season=media_season,
                    episode=media_episode,
                    dest=media_path)
            else:
                continue

            logger.info(f" Deletions are being synchronized {msg}")

            if not transfer_history:
                logger.info(f" Not available {msg}  Transfer records")
                continue

            logger.info(f" Get the number of deleted history records {len(transfer_history)}")

            #  Start deleting
            image = 'https://emby.media/notificationicon.png'
            del_cnt = 0
            stop_cnt = 0
            error_cnt = 0
            for transferhis in transfer_history:
                title = transferhis.title
                if title not in media_name:
                    logger.warn(
                        f" Current transfer records {transferhis.id} {title} {transferhis.tmdbid}  With the deletion of the media{media_name} Not conform to， Anti-deletion， No automatic deletion for the time being")
                    continue
                image = transferhis.image
                # 0、 Deletion of transfer records
                self._transferhis.delete(transferhis.id)

                #  Deletion of seed tasks
                if self._del_source:
                    # 1、 Delete the source file directly
                    if transferhis.src and Path(transferhis.src).suffix in settings.RMT_MEDIAEXT:
                        self._transferchain.delete_files(Path(transferhis.src))
                        if transferhis.download_hash:
                            try:
                                # 2、 Determine if a seed has been deleted
                                delete_flag, success_flag, handle_cnt = self.handle_torrent(src=transferhis.src,
                                                                                            torrent_hash=transferhis.download_hash)
                                if not success_flag:
                                    error_cnt += 1
                                else:
                                    if delete_flag:
                                        del_cnt += handle_cnt
                                    else:
                                        stop_cnt += handle_cnt
                            except Exception as e:
                                logger.error(" Failed to delete seed， Try deleting the source file：%s" % str(e))

            logger.info(f" Synchronous deletion {msg}  Fulfillment！")

            #  Send a message
            if self._notify:
                torrent_cnt_msg = ""
                if del_cnt:
                    torrent_cnt_msg += f" Delete seeds{del_cnt} Classifier for individual things or people, general, catch-all classifier\n"
                if stop_cnt:
                    torrent_cnt_msg += f" Suspension of seeds{stop_cnt} Classifier for individual things or people, general, catch-all classifier\n"
                if error_cnt:
                    torrent_cnt_msg += f" Seed deletion failure{error_cnt} Classifier for individual things or people, general, catch-all classifier\n"
                self.post_message(
                    mtype=NotificationType.MediaServer,
                    title=" Media library synchronization deletion task completion",
                    text=f"{msg}\n"
                         f" Deletion of records{len(transfer_history)} Classifier for individual things or people, general, catch-all classifier\n"
                         f"{torrent_cnt_msg}"
                         f" Timing {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}",
                    image=image)

            history.append({
                "type": " Cinematic" if media_type == "Movie" else " Dramas",
                "title": media_name,
                "year": media_year,
                "path": media_path,
                "season": media_season,
                "episode": media_episode,
                "image": image,
                "del_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
            })

        #  Preserving history
        self.save_data("history", history)

        self.save_data("last_time", last_del_time or datetime.datetime.now())

    def handle_torrent(self, src: str, torrent_hash: str):
        """
        Determine if a seed is partially deleted
        Partial deletion suspends the seed
        Deleting them all removes the seeds
        """
        download_id = torrent_hash
        download = settings.DOWNLOADER
        history_key = "%s-%s" % (download, torrent_hash)
        plugin_id = "TorrentTransfer"
        transfer_history = self.get_data(key=history_key,
                                         plugin_id=plugin_id)
        logger.info(f" Got it. {history_key}  History of transplants {transfer_history}")

        handle_cnt = 0
        try:
            #  Delete this seed record
            self._downloadhis.delete_file_by_fullpath(fullpath=src)

            #  Based on seedhash Check all downloader file records
            download_files = self._downloadhis.get_files_by_hash(download_hash=torrent_hash)
            if not download_files:
                logger.error(
                    f" Seed missions not queried {torrent_hash}  Existence of documentary records， Downloader file synchronization not performed or the seed has been deleted")
                return False, False, 0

            #  Query undeleted count
            no_del_cnt = 0
            for download_file in download_files:
                if download_file and download_file.state and int(download_file.state) == 1:
                    no_del_cnt += 1

            if no_del_cnt > 0:
                logger.info(
                    f" Query seeding tasks {torrent_hash}  Remain {no_del_cnt}  Undeleted documents， Perform a pause seed operation")
                delete_flag = False
            else:
                logger.info(
                    f" Query seeding tasks {torrent_hash}  All documents have been deleted.， Perform a delete seed operation")
                delete_flag = True

            #  If there is a record of trans-species， Then delete the downloaded task after the transfer
            if transfer_history and isinstance(transfer_history, dict):
                download = transfer_history['to_download']
                download_id = transfer_history['to_download_id']
                delete_source = transfer_history['delete_source']

                #  Delete seeds
                if delete_flag:
                    #  Deletion of records of trans-species
                    self.del_data(key=history_key, plugin_id=plugin_id)

                    #  When source seed is not deleted after transfer， Synchronized deletion of source species
                    if not delete_source:
                        logger.info(f"{history_key}  Failure to remove source download tasks during replanting， Start deleting source download tasks…")

                        #  Deletion of source seeds
                        logger.info(f" Delete source downloader download task：{settings.DOWNLOADER} - {torrent_hash}")
                        self.chain.remove_torrents(torrent_hash)
                        handle_cnt += 1

                    #  Delete post-transfer mission
                    logger.info(f" Delete the post-transplant download task：{download} - {download_id}")
                    #  Delete the post-transplant download task
                    if download == "transmission":
                        self.tr.delete_torrents(delete_file=True,
                                                ids=download_id)
                    else:
                        self.qb.delete_torrents(delete_file=True,
                                                ids=download_id)
                    handle_cnt += 1
                else:
                    #  Suspension of seeds
                    #  When source seed is not deleted after transfer， Synchronized suspension of source species
                    if not delete_source:
                        logger.info(f"{history_key}  Failure to remove source download tasks during replanting， Start pausing source download tasks…")

                        #  Moratorium on source seeds
                        logger.info(f" Pause source downloader download task：{settings.DOWNLOADER} - {torrent_hash}")
                        self.chain.stop_torrents(torrent_hash)
                        handle_cnt += 1

            else:
                #  Non-transplantedde State of affairs
                if delete_flag:
                    #  Deletion of source seeds
                    logger.info(f" Delete source downloader download task：{download} - {download_id}")
                    self.chain.remove_torrents(download_id)
                else:
                    #  Moratorium on source seeds
                    logger.info(f" Pause source downloader download task：{download} - {download_id}")
                    self.chain.stop_torrents(download_id)
                handle_cnt += 1

            #  Auxiliary species
            handle_cnt = self.__del_seed(download=download,
                                         download_id=download_id,
                                         action_flag="del" if delete_flag else 'stop',
                                         handle_cnt=handle_cnt)

            return delete_flag, True, handle_cnt
        except Exception as e:
            logger.error(f" Seed deletion failure： {e}")
            return False, False, 0

    def __del_seed(self, download, download_id, action_flag, handle_cnt):
        """
        Deletion of auxiliary species
        """
        #  Check if there is a record of auxiliary seeds
        history_key = download_id
        plugin_id = "IYUUAutoSeed"
        seed_history = self.get_data(key=history_key,
                                     plugin_id=plugin_id) or []
        logger.info(f" Got it. {history_key}  Auxiliary species history {seed_history}")

        #  Auxiliary seeds are processed if they are recorded
        if seed_history and isinstance(seed_history, list):
            for history in seed_history:
                downloader = history['downloader']
                torrents = history['torrents']
                if not downloader or not torrents:
                    return
                if not isinstance(torrents, list):
                    torrents = [torrents]

                # Deletion of auxiliary species历史中与本下载器相同的辅种记录
                if str(downloader) == str(download):
                    for torrent in torrents:
                        handle_cnt += 1
                        if str(download) == "qbittorrent":
                            # Deletion of auxiliary species
                            if action_flag == "del":
                                logger.info(f"Deletion of auxiliary species：{downloader} - {torrent}")
                                self.qb.delete_torrents(delete_file=True,
                                                        ids=torrent)
                            #  Suspension of auxiliary seeding
                            if action_flag == "stop":
                                self.qb.stop_torrents(torrent)
                                logger.info(f" Auxiliary species：{downloader} - {torrent}  Pause (media player)")
                        else:
                            # Deletion of auxiliary species
                            if action_flag == "del":
                                logger.info(f"Deletion of auxiliary species：{downloader} - {torrent}")
                                self.tr.delete_torrents(delete_file=True,
                                                        ids=torrent)
                            #  Suspension of auxiliary seeding
                            if action_flag == "stop":
                                self.tr.stop_torrents(torrent)
                                logger.info(f" Auxiliary species：{downloader} - {torrent}  Pause (media player)")
                    #  Delete this downloader's auxiliary seed history
                    if action_flag == "del":
                        del history
                    break

            #  Updating the history of auxiliary species
            self.save_data(key=history_key,
                           value=seed_history,
                           plugin_id=plugin_id)

        return handle_cnt

    @staticmethod
    def parse_emby_log(last_time):
        """
        Gainemby Log list、 Analyzeemby Log (computing)
        """

        def __parse_log(file_name: str, del_list: list):
            """
            Analyzeemby Log (computing)
            """
            log_url = f"[HOST]System/Logs/{file_name}?api_key=[APIKEY]"
            log_res = Emby().get_data(log_url)
            if not log_res or log_res.status_code != 200:
                logger.error(" Gainemby Log failure， Please check the server configuration")
                return del_list

            #  Regular parsing of deleted media messages
            pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{3}) Info App: Removing item from database, Type: (\w+), Name: (.*), Path: (.*), Id: (\d+)'
            matches = re.findall(pattern, log_res.text)

            #  Cyclic access to media information
            for match in matches:
                mtime = match[0]
                #  Exclusion of processed media messages
                if last_time and mtime < last_time:
                    continue

                mtype = match[1]
                name = match[2]
                path = match[3]

                year = None
                year_pattern = r'\(\d+\)'
                year_match = re.search(year_pattern, path)
                if year_match:
                    year = year_match.group()[1:-1]

                season = None
                episode = None
                if mtype == 'Episode' or mtype == 'Season':
                    name_pattern = r"\/([\u4e00-\u9fa5]+)(?= \()"
                    season_pattern = r"Season\s*(\d+)"
                    episode_pattern = r"S\d+E(\d+)"
                    name_match = re.search(name_pattern, path)
                    season_match = re.search(season_pattern, path)
                    episode_match = re.search(episode_pattern, path)

                    if name_match:
                        name = name_match.group(1)

                    if season_match:
                        season = season_match.group(1)
                        if int(season) < 10:
                            season = f'S0{season}'
                        else:
                            season = f'S{season}'
                    else:
                        season = None

                    if episode_match:
                        episode = episode_match.group(1)
                        episode = f'E{episode}'
                    else:
                        episode = None

                media = {
                    "time": mtime,
                    "type": mtype,
                    "name": name,
                    "year": year,
                    "path": path,
                    "season": season,
                    "episode": episode,
                }
                logger.debug(f" Parsing to delete media：{json.dumps(media)}")
                del_list.append(media)

            return del_list

        log_files = []
        try:
            #  Get allemby Log (computing)
            log_list_url = "[HOST]System/Logs/Query?Limit=3&api_key=[APIKEY]"
            log_list_res = Emby().get_data(log_list_url)

            if log_list_res and log_list_res.status_code == 200:
                log_files_dict = json.loads(log_list_res.text)
                for item in log_files_dict.get("Items"):
                    if str(item.get('Name')).startswith("embyserver"):
                        log_files.append(str(item.get('Name')))
        except Exception as e:
            print(str(e))

        if not log_files:
            log_files.append("embyserver.txt")

        del_medias = []
        log_files.reverse()
        for log_file in log_files:
            del_medias = __parse_log(log_file, del_medias)

        return del_medias

    @staticmethod
    def parse_jellyfin_log(last_time: datetime):
        """
        Gainjellyfin Log list、 Analyzejellyfin Log (computing)
        """

        def __parse_log(file_name: str, del_list: list):
            """
            Analyzejellyfin Log (computing)
            """
            log_url = f"[HOST]System/Logs/Log?name={file_name}&api_key=[APIKEY]"
            log_res = Jellyfin().get_data(log_url)
            if not log_res or log_res.status_code != 200:
                logger.error(" Gainjellyfin Log failure， Please check the server configuration")
                return del_list

            #  Regular parsing of deleted media messages
            pattern = r'\[(.*?)\].*?Removing item, Type: "(.*?)", Name: "(.*?)", Path: "(.*?)"'
            matches = re.findall(pattern, log_res.text)

            #  Cyclic access to media information
            for match in matches:
                mtime = match[0]
                #  Exclusion of processed media messages
                if last_time and mtime < last_time:
                    continue

                mtype = match[1]
                name = match[2]
                path = match[3]

                year = None
                year_pattern = r'\(\d+\)'
                year_match = re.search(year_pattern, path)
                if year_match:
                    year = year_match.group()[1:-1]

                season = None
                episode = None
                if mtype == 'Episode' or mtype == 'Season':
                    name_pattern = r"\/([\u4e00-\u9fa5]+)(?= \()"
                    season_pattern = r"Season\s*(\d+)"
                    episode_pattern = r"S\d+E(\d+)"
                    name_match = re.search(name_pattern, path)
                    season_match = re.search(season_pattern, path)
                    episode_match = re.search(episode_pattern, path)

                    if name_match:
                        name = name_match.group(1)

                    if season_match:
                        season = season_match.group(1)
                        if int(season) < 10:
                            season = f'S0{season}'
                        else:
                            season = f'S{season}'
                    else:
                        season = None

                    if episode_match:
                        episode = episode_match.group(1)
                        episode = f'E{episode}'
                    else:
                        episode = None

                media = {
                    "time": mtime,
                    "type": mtype,
                    "name": name,
                    "year": year,
                    "path": path,
                    "season": season,
                    "episode": episode,
                }
                logger.debug(f" Parsing to delete media：{json.dumps(media)}")
                del_list.append(media)

            return del_list

        log_files = []
        try:
            #  Get alljellyfin Log (computing)
            log_list_url = "[HOST]System/Logs?api_key=[APIKEY]"
            log_list_res = Jellyfin().get_data(log_list_url)

            if log_list_res and log_list_res.status_code == 200:
                log_files_dict = json.loads(log_list_res.text)
                for item in log_files_dict:
                    if str(item.get('Name')).startswith("log_"):
                        log_files.append(str(item.get('Name')))
        except Exception as e:
            print(str(e))

        if not log_files:
            log_files.append("log_%s.log" % datetime.date.today().strftime("%Y%m%d"))

        del_medias = []
        log_files.reverse()
        for log_file in log_files:
            del_medias = __parse_log(log_file, del_medias)

        return del_medias

    def get_state(self):
        return self._enabled

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

    @eventmanager.register(EventType.DownloadFileDeleted)
    def downloadfile_del_sync(self, event: Event):
        """
        Download file delete handling event
        """
        if not self._enabled:
            return
        if not event:
            return
        event_data = event.event_data
        src = event_data.get("src")
        if not src:
            return
        #  Inquiry downloadhash
        download_hash = self._downloadhis.get_hash_by_fullpath(src)
        if download_hash:
            self.handle_torrent(src=src, torrent_hash=download_hash)
        else:
            logger.warn(f" No documents were consulted {src}  Corresponding download records")

    @staticmethod
    def get_tmdbimage_url(path: str, prefix="w500"):
        if not path:
            return ""
        tmdb_image_url = f"https://{settings.TMDB_IMAGE_DOMAIN}"
        return tmdb_image_url + f"/t/p/{prefix}{path}"
