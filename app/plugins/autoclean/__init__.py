import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.chain.transfer import TransferChain
from app.core.config import settings
from app.core.event import eventmanager
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.transferhistory_oper import TransferHistoryOper
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger
from app.schemas import NotificationType, DownloadHistory
from app.schemas.types import EventType


class AutoClean(_PluginBase):
    #  Plug-in name
    plugin_name = " Timed media library cleanup"
    #  Plugin description
    plugin_desc = " Regular cleaning of seeds downloaded by users、 Source file、 Media library files。"
    #  Plug-in icons
    plugin_icon = "clean.png"
    #  Theme color
    plugin_color = "#3377ed"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "autoclean_"
    #  Loading sequence
    plugin_order = 23
    #  Available user levels
    auth_level = 2

    #  Private property
    _enabled = False
    #  Task execution interval
    _cron = None
    _type = None
    _onlyonce = False
    _notify = False
    _cleantype = None
    _cleanuser = None
    _cleandate = None
    _downloadhis = None
    _transferhis = None

    #  Timers
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        #  Discontinuation of existing mandates
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._cleantype = config.get("cleantype")
            self._cleanuser = config.get("cleanuser")
            self._cleandate = config.get("cleandate")

            #  Load modules
        if self._enabled:
            self._downloadhis = DownloadHistoryOper(self.db)
            self._transferhis = TransferHistoryOper(self.db)
            #  Time service
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._cron:
                try:
                    self._scheduler.add_job(func=self.__clean,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Timed media library cleanup")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")

            if self._onlyonce:
                logger.info(f" Timed media library cleanup service starts， Run one immediately")
                self._scheduler.add_job(func=self.__clean, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name=" Timed media library cleanup")
                #  Turn off the disposable switch
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "cron": self._cron,
                    "cleantype": self._cleantype,
                    "enabled": self._enabled,
                    "cleanuser": self._cleanuser,
                    "cleandate": self._cleandate,
                    "notify": self._notify,
                })

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __clean(self):
        """
        Timed media library cleanup
        """
        if not self._cleandate:
            logger.error(" No media library cleanup time configured， Stop running")
            return

        #  Liquidation date
        current_time = datetime.now()
        days_ago = current_time - timedelta(days=int(self._cleandate))
        clean_date = days_ago.strftime("%Y-%m-%d")

        #  Querying download history after a user's purge date
        if not self._cleanuser:
            downloadhis_list = self._downloadhis.list_by_user_date(date=clean_date)
            logger.info(f' Get the date {clean_date}  Subsequent download history {len(downloadhis_list)}  Clause (of law or treaty)')

            self.__clean_history(date=clean_date, downloadhis_list=downloadhis_list)
        else:
            for userid in str(self._cleanuser).split(","):
                downloadhis_list = self._downloadhis.list_by_user_date(date=clean_date,
                                                                       userid=userid)
                logger.info(
                    f' Getting to the user {userid}  Dates {clean_date}  Subsequent download history {len(downloadhis_list)}  Clause (of law or treaty)')
                self.__clean_history(date=clean_date, downloadhis_list=downloadhis_list, userid=userid)

    def __clean_history(self, date: str, downloadhis_list: List[DownloadHistory], userid: str = None):
        """
        Clear download history、 Transfer records
        """
        if not downloadhis_list:
            logger.warn(f" Date not captured {date}  Subsequent downloads， Stop running")
            return

        #  Read history
        history = self.get_data('history') or []

        #  Create a dictionary to hold the grouping results
        downloadhis_grouped_dict: Dict[tuple, List[DownloadHistory]] = defaultdict(list)
        #  (math.) ergodicDownloadHistory Object list
        for downloadhis in downloadhis_list:
            #  Gaintype Cap (a poem)tmdbid Value of
            dtype = downloadhis.type
            tmdbid = downloadhis.tmdbid

            #  Commander-in-chief (military)DownloadHistory Objects are added to the list of the corresponding grouping
            downloadhis_grouped_dict[(dtype, tmdbid)].append(downloadhis)

        #  Output grouping results
        for key, downloadhis_list in downloadhis_grouped_dict.items():
            logger.info(f" Starting to clean up. {key}")

            del_transferhis_cnt = 0
            del_media_name = downloadhis_list[0].title
            del_media_user = downloadhis_list[0].userid
            del_media_type = downloadhis_list[0].type
            del_media_year = downloadhis_list[0].year
            del_media_season = downloadhis_list[0].seasons
            del_media_episode = downloadhis_list[0].episodes
            del_image = downloadhis_list[0].image
            for downloadhis in downloadhis_list:
                if not downloadhis.download_hash:
                    logger.debug(f' Download history {downloadhis.id} {downloadhis.title}  Not availabledownload_hash， Skip processing')
                    continue
                #  According tohash Obtaining transfer records
                transferhis_list = self._transferhis.list_by_hash(download_hash=downloadhis.download_hash)
                if not transferhis_list:
                    logger.warn(f" Download history {downloadhis.download_hash}  No records of transfers were inquired about， Skip processing")
                    continue

                for history in transferhis_list:
                    #  Excluding media library files
                    if str(self._cleantype == "dest") or str(self._cleantype == "all"):
                        TransferChain(self.db).delete_files(Path(history.dest))
                        #  Deletion of records
                        self._transferhis.delete(history.id)
                    #  Deleting source files
                    if str(self._cleantype == "src") or str(self._cleantype == "all"):
                        TransferChain(self.db).delete_files(Path(history.src))
                        #  Send event
                        eventmanager.send_event(
                            EventType.DownloadFileDeleted,
                            {
                                "src": history.src
                            }
                        )

                #  Cumulative number of deletions
                del_transferhis_cnt += len(transferhis_list)

            #  Send a message
            if self._notify:
                self.post_message(
                    mtype=NotificationType.MediaServer,
                    title="【Timed media library cleanup任务完成】",
                    text=f" Clearance of media names {del_media_name}\n"
                         f" Download media users {del_media_user}\n"
                         f" Delete history {del_transferhis_cnt}",
                    userid=userid)

            history.append({
                "type": del_media_type,
                "title": del_media_name,
                "year": del_media_year,
                "season": del_media_season,
                "episode": del_media_episode,
                "image": del_image,
                "del_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
            })

        #  Preserving history
        self.save_data("history", history)

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
                                                   'model': 'notify',
                                                   'label': ' Open notification',
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
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'cron',
                                                   'label': ' Implementation period',
                                                   'placeholder': '0 0 ? ? ?'
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
                                               'component': 'VSelect',
                                               'props': {
                                                   'model': 'cleantype',
                                                   'label': ' Clearance method',
                                                   'items': [
                                                       {'title': ' Media library files', 'value': 'dest'},
                                                       {'title': ' Source file', 'value': 'src'},
                                                       {'title': ' All documents', 'value': 'all'},
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
                                                   'model': 'cleandate',
                                                   'label': ' Date of clearance of media',
                                                   'placeholder': ' Clear downloads from how many days ago（ Sky）'
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
                                                   'model': 'cleanuser',
                                                   'label': ' Clear download users',
                                                   'placeholder': ' Multi-user, Demerger'
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
                   "notify": False,
                   "cleantype": "dest",
                   "cron": "",
                   "cleanuser": "",
                   "cleandate": 30
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
