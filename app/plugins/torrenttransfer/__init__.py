import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bencode import bdecode, bencode

from app.core.config import settings
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.string import StringUtils


class TorrentTransfer(_PluginBase):
    #  Plug-in name
    plugin_name = " Autotransfer seeding"
    #  Plugin description
    plugin_desc = " Regularly transfer seeding tasks from a downloader to another downloader。"
    #  Plug-in icons
    plugin_icon = "torrenttransfer.jpg"
    #  Theme color
    plugin_color = "#272636"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "torrenttransfer_"
    #  Loading sequence
    plugin_order = 18
    #  Available user levels
    auth_level = 2

    #  Private property
    _scheduler = None
    qb = None
    tr = None
    torrent = None
    #  Switchgear
    _enabled = False
    _cron = None
    _onlyonce = False
    _fromdownloader = None
    _todownloader = None
    _frompath = None
    _topath = None
    _notify = False
    _nolabels = None
    _nopaths = None
    _deletesource = False
    _fromtorrentpath = None
    _autostart = False
    #  Logout event
    _event = Event()
    #  List of seeds to be checked
    _recheck_torrents = {}
    _is_recheck_running = False
    #  Mission label
    _torrent_tags = [" Collated", " Master sth."]

    def init_plugin(self, config: dict = None):
        self.torrent = TorrentHelper()
        #  Read configuration
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._nolabels = config.get("nolabels")
            self._frompath = config.get("frompath")
            self._topath = config.get("topath")
            self._fromdownloader = config.get("fromdownloader")
            self._todownloader = config.get("todownloader")
            self._deletesource = config.get("deletesource")
            self._fromtorrentpath = config.get("fromtorrentpath")
            self._nopaths = config.get("nopaths")
            self._autostart = config.get("autostart")

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Starting a timed task &  Run one immediately
        if self.get_state() or self._onlyonce:
            self.qb = Qbittorrent()
            self.tr = Transmission()
            #  Check configuration
            if self._fromtorrentpath and not Path(self._fromtorrentpath).exists():
                logger.error(f" Source downloader seed file save path does not exist：{self._fromtorrentpath}")
                self.systemmessage.put(f" Source downloader seed file save path does not exist：{self._fromtorrentpath}")
                return
            if self._fromdownloader == self._todownloader:
                logger.error(f" Source and destination downloaders cannot be the same")
                self.systemmessage.put(f" Source and destination downloaders cannot be the same")
                return
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                logger.info(f" Transfer seeding service launched， Cyclicality：{self._cron}")
                try:
                    self._scheduler.add_job(self.transfer,
                                            CronTrigger.from_crontab(self._cron))
                except Exception as e:
                    logger.error(f" Failure to start the transfer seeding service：{e}")
                    self.systemmessage.put(f" Failure to start the transfer seeding service：{e}")
                    return
            if self._onlyonce:
                logger.info(f" Transfer seeding service launched， Run one immediately")
                self._scheduler.add_job(self.transfer, 'date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(
                                            seconds=3))
                #  Turn off the disposable switch
                self._onlyonce = False
                self.update_config({
                    "enabled": self._enabled,
                    "onlyonce": self._onlyonce,
                    "cron": self._cron,
                    "notify": self._notify,
                    "nolabels": self._nolabels,
                    "frompath": self._frompath,
                    "topath": self._topath,
                    "fromdownloader": self._fromdownloader,
                    "todownloader": self._todownloader,
                    "deletesource": self._deletesource,
                    "fromtorrentpath": self._fromtorrentpath,
                    "nopaths": self._nopaths,
                    "autostart": self._autostart
                })
            if self._scheduler.get_jobs():
                if self._autostart:
                    #  Additional seed verification services
                    self._scheduler.add_job(self.check_recheck, 'interval', minutes=3)
                #  Starting services
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self):
        return True if self._enabled \
                       and self._cron \
                       and self._fromdownloader \
                       and self._todownloader \
                       and self._fromtorrentpath else False

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
                                            'placeholder': '0 0 0 ? *'
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
                                            'model': 'nolabels',
                                            'label': ' No transfer of seed labels',
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
                                            'model': 'fromdownloader',
                                            'label': ' Source downloader',
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
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'fromtorrentpath',
                                            'label': ' Source downloader seed file path',
                                            'placeholder': 'BT_backup、torrents'
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
                                            'model': 'frompath',
                                            'label': ' Source data file root path',
                                            'placeholder': ' Root path， Leave blank for no path conversion'
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
                                            'model': 'todownloader',
                                            'label': ' Destination downloader',
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'topath',
                                            'label': ' Destination data file root path',
                                            'placeholder': ' Root path， Leave blank for no path conversion'
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
                                            'model': 'nopaths',
                                            'label': ' No transfer of data file directories',
                                            'rows': 3,
                                            'placeholder': ' One directory per line'
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
                                            'model': 'autostart',
                                            'label': ' Automatically starts when calibration is complete',
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
                                            'model': 'deletesource',
                                            'label': ' Deletion of source seeds',
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
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify": False,
            "onlyonce": False,
            "cron": "",
            "nolabels": "",
            "frompath": "",
            "topath": "",
            "fromdownloader": "",
            "todownloader": "",
            "deletesource": False,
            "fromtorrentpath": "",
            "nopaths": "",
            "autostart": True
        }

    def get_page(self) -> List[dict]:
        pass

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

    def __download(self, downloader: str, content: bytes,
                   save_path: str) -> Optional[str]:
        """
        Add download tasks
        """
        if downloader == "qbittorrent":
            #  Generate randomTag
            tag = StringUtils.generate_random_str(10)
            state = self.qb.add_torrent(content=content,
                                        download_dir=save_path,
                                        is_paused=True,
                                        tag=[" Collated", " Master sth.", tag])
            if not state:
                return None
            else:
                #  Getting seedsHash
                torrent_hash = self.qb.get_torrent_id_by_tag(tags=tag)
                if not torrent_hash:
                    logger.error(f"{downloader}  Getting seedsHash Fail (e.g. experiments)")
                    return None
            return torrent_hash
        elif downloader == "transmission":
            #  Add tasks
            torrent = self.tr.add_torrent(content=content,
                                          download_dir=save_path,
                                          is_paused=True,
                                          labels=[" Collated", " Master sth."])
            if not torrent:
                return None
            else:
                return torrent.hashString

        logger.error(f" Unsupported downloaders：{downloader}")
        return None

    def transfer(self):
        """
        Beginning of transfer for seeding
        """
        logger.info("Beginning of transfer for seeding任务 ...")

        #  Source downloader
        downloader = self._fromdownloader
        #  Destination downloader
        todownloader = self._todownloader

        #  Getting completed seeds in the downloader
        downloader_obj = self.__get_downloader(downloader)
        torrents = downloader_obj.get_completed_torrents()
        if torrents:
            logger.info(f" Downloader {downloader}  Number of seeds completed：{len(torrents)}")
        else:
            logger.info(f" Downloader {downloader}  No completed seeds")
            return

        #  Filtering seeds， Records retention catalog
        trans_torrents = []
        for torrent in torrents:
            if self._event.is_set():
                logger.info(f" Discontinuation of transfer services")
                return

            #  Getting seedshash
            hash_str = self.__get_hash(torrent, downloader)
            #  Get save path
            save_path = self.__get_save_path(torrent, downloader)

            if self._nopaths and save_path:
                #  Filtering paths that do not need to be transferred
                nopath_skip = False
                for nopath in self._nopaths.split('\n'):
                    if os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                        logger.info(f" Torrent {hash_str}  Save path {save_path}  No transfer required， Skip over ...")
                        nopath_skip = True
                        break
                if nopath_skip:
                    continue

            #  Get seed label
            torrent_labels = self.__get_label(torrent, downloader)
            if torrent_labels and self._nolabels:
                is_skip = False
                for label in self._nolabels.split(','):
                    if label in torrent_labels:
                        logger.info(f" Torrent {hash_str}  Contains non-transferable labels {label}， Skip over ...")
                        is_skip = True
                        break
                if is_skip:
                    continue

            #  Add transfer data
            trans_torrents.append({
                "hash": hash_str,
                "save_path": save_path,
                "torrent": torrent
            })

        #  Commencement of the transfer of tasks
        if trans_torrents:
            logger.info(f" Number of seeds to be transferred：{len(trans_torrents)}")
            #  Keep count of the number of people
            total = len(trans_torrents)
            #  Total number of successes
            success = 0
            #  Total number of failures
            fail = 0
            #  Skip count
            skip = 0

            for torrent_item in trans_torrents:
                #  Check if the seed file exists
                torrent_file = Path(self._fromtorrentpath) / f"{torrent_item.get('hash')}.torrent"
                if not torrent_file.exists():
                    logger.error(f" Seed file does not exist：{torrent_file}")
                    #  Failure count
                    fail += 1
                    continue

                #  Consult (a document etc)hash Whether the value is already in the destination downloader
                todownloader_obj = self.__get_downloader(todownloader)
                torrent_info, _ = todownloader_obj.get_torrents(ids=[torrent_item.get('hash')])
                if torrent_info:
                    logger.info(f"{torrent_item.get('hash')}  Already in the destination downloader， Skip over ...")
                    #  Skip count
                    skip += 1
                    continue

                #  Convert save path
                download_dir = self.__convert_save_path(torrent_item.get('save_path'),
                                                        self._frompath,
                                                        self._topath)
                if not download_dir:
                    logger.error(f" Failed to convert save path：{torrent_item.get('save_path')}")
                    #  Failure count
                    fail += 1
                    continue

                #  If the source downloader isQB Check for the presence ofTracker， Get extra if you don't have it
                if downloader == "qbittorrent":
                    #  Read the contents of the seed、 Parsing seed files
                    content = torrent_file.read_bytes()
                    if not content:
                        logger.warn(f" Failed to read seed file：{torrent_file}")
                        fail += 1
                        continue
                    #  Retrievetrackers
                    try:
                        torrent_main = bdecode(content)
                        main_announce = torrent_main.get('announce')
                    except Exception as err:
                        logger.warn(f" Parsing seed files {torrent_file}  Fail (e.g. experiments)：{err}")
                        fail += 1
                        continue

                    if not main_announce:
                        logger.info(f"{torrent_item.get('hash')}  Not foundtracker Text， Trying to supplementtracker Text...")
                        #  Retrievefastresume File
                        fastresume_file = Path(self._fromtorrentpath) / f"{torrent_item.get('hash')}.fastresume"
                        if not fastresume_file.exists():
                            logger.warn(f"fastresume File does not exist：{fastresume_file}")
                            fail += 1
                            continue
                        #  Trying to supplementtrackers
                        try:
                            #  Analyzefastresume File
                            fastresume = fastresume_file.read_bytes()
                            torrent_fastresume = bdecode(fastresume)
                            #  Retrievetrackers
                            fastresume_trackers = torrent_fastresume.get('trackers')
                            if isinstance(fastresume_trackers, list) \
                                    and len(fastresume_trackers) > 0 \
                                    and fastresume_trackers[0]:
                                #  Reassign
                                torrent_main['announce'] = fastresume_trackers[0][0]
                                #  Replace the seed file path
                                torrent_file = settings.TEMP_PATH / f"{torrent_item.get('hash')}.torrent"
                                #  Encoded and saved to a temporary file
                                torrent_file.write_bytes(bencode(torrent_main))
                        except Exception as err:
                            logger.error(f" Analyzefastresume File {fastresume_file}  Make a mistake：{err}")
                            fail += 1
                            continue

                #  Send to another downloader to download： Default pause、 Transfer download path、 Disable automatic management mode
                logger.info(f" Add transfer seeding tasks to the downloader {todownloader}：{torrent_file}")
                download_id = self.__download(downloader=todownloader,
                                              content=torrent_file.read_bytes(),
                                              save_path=download_dir)
                if not download_id:
                    #  Failed to download
                    fail += 1
                    logger.error(f"Add download tasks失败：{torrent_file}")
                    continue
                else:
                    #  Download successfully
                    logger.info(f" Successful addition of transfer seeding tasks， Seed file：{torrent_file}")

                    # TR It will be automatically calibrated，QB Manual calibration required
                    if todownloader == "qbittorrent":
                        logger.info(f"qbittorrent  Start calibration {download_id} ...")
                        todownloader_obj.recheck_torrents(ids=[download_id])

                    #  Additional calibration tasks
                    logger.info(f" Add a calibration check task：{download_id} ...")
                    if not self._recheck_torrents.get(todownloader):
                        self._recheck_torrents[todownloader] = []
                    self._recheck_torrents[todownloader].append(download_id)

                    #  Deletion of source seeds， Cannot delete files！
                    if self._deletesource:
                        logger.info(f" Delete source downloader task（ No documents）：{torrent_item.get('hash')} ...")
                        downloader_obj.delete_torrents(delete_file=False, ids=[torrent_item.get('hash')])

                    #  Success rate
                    success += 1
                    #  Insertion of trans-species records
                    history_key = "%s-%s" % (self._fromdownloader, torrent_item.get('hash'))
                    self.save_data(key=history_key,
                                   value={
                                       "to_download": self._todownloader,
                                       "to_download_id": download_id,
                                       "delete_source": self._deletesource,
                                   })
            #  Trigger the calibration task
            if success > 0 and self._autostart:
                self.check_recheck()

            #  Send notification
            if self._notify:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【 Transfer of seeding tasks completed】",
                    text=f" Aggregate：{total}， Successes：{success}， Fail (e.g. experiments)：{fail}， Skip over：{skip}"
                )
        else:
            logger.info(f" No seeds to be transferred")
        logger.info(" Transfer of seeding tasks completed")

    def check_recheck(self):
        """
        Regularly check if the seeds in the downloader have been verified.， Automatic start of auxiliary seeding when calibration is complete and intact
        """
        if not self._recheck_torrents:
            return
        if not self._todownloader:
            return
        if self._is_recheck_running:
            return

        #  Calibration downloader
        downloader = self._todownloader

        #  Seeds to be checked
        recheck_torrents = self._recheck_torrents.get(downloader, [])
        if not recheck_torrents:
            return

        logger.info(f" Start checking the downloader {downloader}  Of the calibration task ...")

        #  Operational state
        self._is_recheck_running = True

        #  Obtaining mandates
        downloader_obj = self.__get_downloader(downloader)
        torrents, _ = downloader_obj.get_torrents(ids=recheck_torrents)
        if torrents:
            #  Seed that can be used for planting
            can_seeding_torrents = []
            for torrent in torrents:
                #  Getting seedshash
                hash_str = self.__get_hash(torrent, downloader)
                #  Determination of seedability
                if self.__can_seeding(torrent, downloader):
                    can_seeding_torrents.append(hash_str)

            if can_seeding_torrents:
                logger.info(f" Common {len(can_seeding_torrents)}  Completion of mission calibration， Start the seeds.")
                #  Start the seeds.
                downloader_obj.start_torrents(ids=can_seeding_torrents)
                #  Removal of already treated seeds
                self._recheck_torrents[downloader] = list(
                    set(recheck_torrents).difference(set(can_seeding_torrents)))
            else:
                logger.info(f" No new task calibration completed， To be continued in the next cycle ...")

        elif torrents is None:
            logger.info(f" Downloader {downloader}  Query validation task failed， Will continue to inquire next time ...")
        else:
            logger.info(f" Downloader {downloader}  There are no calibration tasks that need to be checked in the， Empty the pending list")
            self._recheck_torrents[downloader] = []

        self._is_recheck_running = False

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

    @staticmethod
    def __get_label(torrent: Any, dl_type: str):
        """
        Get seed label
        """
        try:
            return [str(tag).strip() for tag in torrent.get("tags").split(',')] \
                if dl_type == "qbittorrent" else torrent.labels or []
        except Exception as e:
            print(str(e))
            return []

    @staticmethod
    def __get_save_path(torrent: Any, dl_type: str):
        """
        Get seed save path
        """
        try:
            return torrent.get("save_path") if dl_type == "qbittorrent" else torrent.download_dir
        except Exception as e:
            print(str(e))
            return ""

    @staticmethod
    def __can_seeding(torrent: Any, dl_type: str):
        """
        Determine if a seed is ready to be seeded and is in a suspended state
        """
        try:
            return (torrent.get("state") == "pausedUP") if dl_type == "qbittorrent" \
                else (torrent.status.stopped and torrent.percent_done == 1)
        except Exception as e:
            print(str(e))
            return False

    @staticmethod
    def __convert_save_path(save_path: str, from_root: str, to_root: str):
        """
        Convert save path
        """
        try:
            #  No save directory， Based on the destination root directory
            if not save_path:
                return to_root
            #  Returns if the root directory is not setsave_path
            if not to_root or not from_root:
                return save_path
            #  Harmonized directory format
            save_path = os.path.normpath(save_path).replace("\\", "/")
            from_root = os.path.normpath(from_root).replace("\\", "/")
            to_root = os.path.normpath(to_root).replace("\\", "/")
            #  Replace the root directory
            if save_path.startswith(from_root):
                return save_path.replace(from_root, to_root, 1)
        except Exception as e:
            print(str(e))
        return None

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
