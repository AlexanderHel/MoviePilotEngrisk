import os
import re
from datetime import datetime, timedelta
from threading import Event
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.helper.sites import SitesHelper

from app.core.event import eventmanager
from app.db.models.site import Site
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.plugins.iyuuautoseed.iyuu_helper import IyuuHelper
from app.schemas import NotificationType
from app.schemas.types import EventType
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class IYUUAutoSeed(_PluginBase):
    #  Plug-in name
    plugin_name = "IYUU Automatic auxiliary seeding"
    #  Plugin description
    plugin_desc = " On the basis ofIYUU Official (relating a government office)Api Realization of automatic seed supplementation。"
    #  Plug-in icons
    plugin_icon = "iyuu.png"
    #  Theme color
    plugin_color = "#F3B70B"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "iyuuautoseed_"
    #  Loading sequence
    plugin_order = 17
    #  Available user levels
    auth_level = 2

    #  Private property
    _scheduler = None
    iyuuhelper = None
    qb = None
    tr = None
    sites = None
    torrent = None
    #  Switchgear
    _enabled = False
    _cron = None
    _onlyonce = False
    _token = None
    _downloaders = []
    _sites = []
    _notify = False
    _nolabels = None
    _nopaths = None
    _clearcache = False
    #  Logout event
    _event = Event()
    #  Seed linksxpaths
    _torrent_xpaths = [
        "//form[contains(@action, 'download.php?id=')]/@action",
        "//a[contains(@href, 'download.php?hash=')]/@href",
        "//a[contains(@href, 'download.php?id=')]/@href",
        "//a[@class='index'][contains(@href, '/dl/')]/@href",
    ]
    _torrent_tags = [" Collated", " Auxiliary species"]
    #  Full seeds to be schooledhash List of items
    _recheck_torrents = {}
    _is_recheck_running = False
    #  Accessory species cache， Erroneous seeds will not be replanted， Removable
    _error_caches = []
    #  Accessory species cache， Auxiliary seeds of success， Removable
    _success_caches = []
    #  Accessory species cache， Erroneous seeds will not be replanted， And cannot be cleared。 Seeds deleted404 Et cetera
    _permanent_error_caches = []
    #  Accessory species count
    total = 0
    realtotal = 0
    success = 0
    exist = 0
    fail = 0
    cached = 0

    def init_plugin(self, config: dict = None):
        self.sites = SitesHelper()
        self.torrent = TorrentHelper()
        #  Read configuration
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._token = config.get("token")
            self._downloaders = config.get("downloaders")
            self._sites = config.get("sites") or []
            self._notify = config.get("notify")
            self._nolabels = config.get("nolabels")
            self._nopaths = config.get("nopaths")
            self._clearcache = config.get("clearcache")
            self._permanent_error_caches = [] if self._clearcache else config.get("permanent_error_caches") or []
            self._error_caches = [] if self._clearcache else config.get("error_caches") or []
            self._success_caches = [] if self._clearcache else config.get("success_caches") or []

            #  Filter out deleted sites
            self._sites = [site.get("id") for site in self.sites.get_indexers() if
                           not site.get("public") and site.get("id") in self._sites]
            self.__update_config()

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Starting a timed task &  Run one immediately
        if self.get_state() or self._onlyonce:
            self.iyuuhelper = IyuuHelper(token=self._token)
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self.qb = Qbittorrent()
            self.tr = Transmission()

            if self._cron:
                try:
                    self._scheduler.add_job(self.auto_seed,
                                            CronTrigger.from_crontab(self._cron))
                    logger.info(f" Auxiliary seed service launched， Cyclicality：{self._cron}")
                except Exception as err:
                    logger.error(f" Auxiliary seed service startup failure：{str(err)}")
                    self.systemmessage.put(f" Auxiliary seed service startup failure：{str(err)}")
            if self._onlyonce:
                logger.info(f" Auxiliary seed service launched， Run one immediately")
                self._scheduler.add_job(self.auto_seed, 'date',
                                        run_date=datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3)
                                        )
                #  Turn off the disposable switch
                self._onlyonce = False

            if self._clearcache:
                #  Turn off the clear cache switch
                self._clearcache = False

            if self._clearcache or self._onlyonce:
                #  Save configuration
                self.__update_config()

            if self._scheduler.get_jobs():
                #  Additional seed verification services
                self._scheduler.add_job(self.check_recheck, 'interval', minutes=3)
                #  Starting services
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return True if self._enabled and self._cron and self._token and self._downloaders else False

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
        site_options = [{"title": site.name, "value": site.id}
                        for site in Site.list_order_by_pri(self.db)]
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
                                            'model': 'token',
                                            'label': 'IYUU Token',
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
                                            'model': 'cron',
                                            'label': ' Implementation period',
                                            'placeholder': '0 0 0 ? *'
                                        }
                                    }
                                ]
                            },
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
                                            'label': ' Auxiliary seed downloader',
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'sites',
                                            'label': ' Auxiliary seeding sites',
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'nolabels',
                                            'label': ' Non-complementary labeling',
                                            'placeholder': ' Utilization, Separate multiple tags'
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
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'nopaths',
                                            'label': ' Directory of non-subsidized data files',
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
                                            'model': 'clearcache',
                                            'label': ' Clear the cache and run',
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
            "clearcache": False,
            "cron": "",
            "token": "",
            "downloaders": [],
            "sites": [],
            "nopaths": "",
            "nolabels": ""
        }

    def get_page(self) -> List[dict]:
        pass

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "clearcache": self._clearcache,
            "cron": self._cron,
            "token": self._token,
            "downloaders": self._downloaders,
            "sites": self._sites,
            "notify": self._notify,
            "nolabels": self._nolabels,
            "nopaths": self._nopaths,
            "success_caches": self._success_caches,
            "error_caches": self._error_caches,
            "permanent_error_caches": self._permanent_error_caches
        })

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

    def auto_seed(self):
        """
        Starting auxiliary seeding
        """
        if not self.iyuuhelper:
            return
        logger.info("Starting auxiliary seeding任务 ...")

        #  Counter initialization
        self.total = 0
        self.realtotal = 0
        self.success = 0
        self.exist = 0
        self.fail = 0
        self.cached = 0
        #  Scanning downloader auxiliary
        for downloader in self._downloaders:
            logger.info(f" Start scanning the downloader {downloader} ...")
            downloader_obj = self.__get_downloader(downloader)
            #  Getting completed seeds in the downloader
            torrents = downloader_obj.get_completed_torrents()
            if torrents:
                logger.info(f" Downloader {downloader}  Number of seeds completed：{len(torrents)}")
            else:
                logger.info(f" Downloader {downloader}  No completed seeds")
                continue
            hash_strs = []
            for torrent in torrents:
                if self._event.is_set():
                    logger.info(f" Discontinuation of auxiliary seed services")
                    return
                #  Getting seedshash
                hash_str = self.__get_hash(torrent, downloader)
                if hash_str in self._error_caches or hash_str in self._permanent_error_caches:
                    logger.info(f" Torrent {hash_str}  Co-seeding failed and cached， Skip over ...")
                    continue
                save_path = self.__get_save_path(torrent, downloader)

                if self._nopaths and save_path:
                    #  Filtering paths that do not need to be transferred
                    nopath_skip = False
                    for nopath in self._nopaths.split('\n'):
                        if os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                            logger.info(f" Torrent {hash_str}  Save path {save_path}  No auxiliary seeds required， Skip over ...")
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
                            logger.info(f" Torrent {hash_str}  Contains non-compliant labeling {label}， Skip over ...")
                            is_skip = True
                            break
                    if is_skip:
                        continue
                hash_strs.append({
                    "hash": hash_str,
                    "save_path": save_path
                })
            if hash_strs:
                logger.info(f" Total number of seeds to be co-seeded：{len(hash_strs)}")
                #  Grouping， MinimizeIYUU Api Number of requests
                chunk_size = 200
                for i in range(0, len(hash_strs), chunk_size):
                    #  Slicing operations
                    chunk = hash_strs[i:i + chunk_size]
                    #  Process grouping
                    self.__seed_torrents(hash_strs=chunk,
                                         downloader=downloader)
                #  Trigger calibration check
                self.check_recheck()
            else:
                logger.info(f" There are no seeds that need to be supplemented")
        #  Save cache
        self.__update_config()
        #  Send a message
        if self._notify:
            if self.success or self.fail:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【IYUU Completion of automated seed supplementation tasks】",
                    text=f" Total number of complementary species returned by the server：{self.total}\n"
                         f" Actual number of complementary species：{self.realtotal}\n"
                         f" Pre-existing：{self.exist}\n"
                         f" Successes：{self.success}\n"
                         f" Fail (e.g. experiments)：{self.fail}\n"
                         f"{self.cached}  Failed records have been added to the cache"
                )
        logger.info(" Completion of the implementation of the auxiliary species mandate")

    def check_recheck(self):
        """
        定时检查下载器中种子是否校验完成，校验完成且完整的自动Starting auxiliary seeding
        """
        if not self._recheck_torrents:
            return
        if self._is_recheck_running:
            return
        self._is_recheck_running = True
        for downloader in self._downloaders:
            #  Seeds to be checked
            recheck_torrents = self._recheck_torrents.get(downloader) or []
            if not recheck_torrents:
                continue
            logger.info(f" Start checking the downloader {downloader}  Of the calibration task ...")
            #  Downloader
            downloader_obj = self.__get_downloader(downloader)
            #  Get the status of the seed in the downloader
            torrents, _ = downloader_obj.get_torrents(ids=recheck_torrents)
            if torrents:
                can_seeding_torrents = []
                for torrent in torrents:
                    #  Getting seedshash
                    hash_str = self.__get_hash(torrent, downloader)
                    if self.__can_seeding(torrent, downloader):
                        can_seeding_torrents.append(hash_str)
                if can_seeding_torrents:
                    logger.info(f"共 {len(can_seeding_torrents)} 个任务校验完成，Starting auxiliary seeding ...")
                    #  Commencement of mission
                    downloader_obj.start_torrents(ids=can_seeding_torrents)
                    #  Removal of already treated seeds
                    self._recheck_torrents[downloader] = list(
                        set(recheck_torrents).difference(set(can_seeding_torrents)))
            elif torrents is None:
                logger.info(f" Downloader {downloader}  Query validation task failed， Will continue to inquire next time ...")
                continue
            else:
                logger.info(f" Downloader {downloader}  There are no calibration tasks that need to be checked in the， Empty the pending list ...")
                self._recheck_torrents[downloader] = []
        self._is_recheck_running = False

    def __seed_torrents(self, hash_strs: list, downloader: str):
        """
        Implementation of a seed lot of auxiliary seeds
        """
        if not hash_strs:
            return
        logger.info(f" Downloader {downloader}  Start searching for auxiliary species， Quantities：{len(hash_strs)} ...")
        #  Downloader中的Hashs
        hashs = [item.get("hash") for item in hash_strs]
        #  EveryoneHash The save directory of the
        save_paths = {}
        for item in hash_strs:
            save_paths[item.get("hash")] = item.get("save_path")
        #  Search for data on complementary species
        seed_list, msg = self.iyuuhelper.get_seed_info(hashs)
        if not isinstance(seed_list, dict):
            logger.warn(f" There are no sites available for supplemental seeding in the current seed list：{msg}")
            return
        else:
            logger.info(f"IYUU Return the number of complementary species：{len(seed_list)}")
        #  (math.) ergodic
        for current_hash, seed_info in seed_list.items():
            if not seed_info:
                continue
            seed_torrents = seed_info.get("torrent")
            if not isinstance(seed_torrents, list):
                seed_torrents = [seed_torrents]

            #  Seeds of success for this auxiliary
            success_torrents = []

            for seed in seed_torrents:
                if not seed:
                    continue
                if not isinstance(seed, dict):
                    continue
                if not seed.get("sid") or not seed.get("info_hash"):
                    continue
                if seed.get("info_hash") in hashs:
                    logger.info(f"{seed.get('info_hash')}  Already in the downloader， Skip over ...")
                    continue
                if seed.get("info_hash") in self._success_caches:
                    logger.info(f"{seed.get('info_hash')}  Auxiliary species processed， Skip over ...")
                    continue
                if seed.get("info_hash") in self._error_caches or seed.get("info_hash") in self._permanent_error_caches:
                    logger.info(f" Torrent {seed.get('info_hash')}  Co-seeding failed and cached， Skip over ...")
                    continue
                #  Add tasks
                success = self.__download_torrent(seed=seed,
                                                  downloader=downloader,
                                                  save_path=save_paths.get(current_hash))
                if success:
                    success_torrents.append(seed.get("info_hash"))

            #  Successful de-weighting of auxiliary species into history
            if len(success_torrents) > 0:
                self.__save_history(current_hash=current_hash,
                                    downloader=downloader,
                                    success_torrents=success_torrents)

        logger.info(f" Downloader {downloader}  Auxiliary seeding completed")

    def __save_history(self, current_hash: str, downloader: str, success_torrents: []):
        """
        [
            {
                "downloader":"2",
                "torrents":[
                    "248103a801762a66c201f39df7ea325f8eda521b",
                    "bd13835c16a5865b01490962a90b3ec48889c1f0"
                ]
            },
            {
                "downloader":"3",
                "torrents":[
                    "248103a801762a66c201f39df7ea325f8eda521b",
                    "bd13835c16a5865b01490962a90b3ec48889c1f0"
                ]
            }
        ]
        """
        try:
            #  Query the currentHash The history of auxiliary species
            seed_history = self.get_data(key=current_hash) or []

            new_history = True
            if len(seed_history) > 0:
                for history in seed_history:
                    if not history:
                        continue
                    if not isinstance(history, dict):
                        continue
                    if not history.get("downloader"):
                        continue
                    #  Continue to add if there is a previous record for this auxiliary seed downloader.
                    if str(history.get("downloader")) == downloader:
                        history_torrents = history.get("torrents") or []
                        history["torrents"] = list(set(history_torrents + success_torrents))
                        new_history = False
                        break

            #  If the downloader has no previous success record, then add
            if new_history:
                seed_history.append({
                    "downloader": downloader,
                    "torrents": list(set(success_torrents))
                })

            #  Preserving history
            self.save_data(key=current_hash,
                           value=seed_history)
        except Exception as e:
            print(str(e))

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
                                        tag=[" Collated", " Auxiliary species", tag])
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
                                          labels=[" Collated", " Auxiliary species"])
            if not torrent:
                return None
            else:
                return torrent.hashString

        logger.error(f" Unsupported downloaders：{downloader}")
        return None

    def __download_torrent(self, seed: dict, downloader: str, save_path: str):
        """
        Download seeds
        torrent: {
                    "sid": 3,
                    "torrent_id": 377467,
                    "info_hash": "a444850638e7a6f6220e2efdde94099c53358159"
                }
        """

        def __is_special_site(url):
            """
            Determine if a site is special（ Is it necessary to addhttps）
            """
            if "hdsky.me" in url:
                return False
            return True

        self.total += 1
        #  Get seed sites and download address templates
        site_url, download_page = self.iyuuhelper.get_torrent_url(seed.get("sid"))
        if not site_url or not download_page:
            #  Add to cache
            self._error_caches.append(seed.get("info_hash"))
            self.fail += 1
            self.cached += 1
            return False
        #  Search site
        site_domain = StringUtils.get_url_domain(site_url)
        #  Site information
        site_info = self.sites.get_indexer(site_domain)
        if not site_info:
            logger.debug(f" No maintenance of seeded counterparts：{site_url}")
            return False
        if self._sites and site_info.get('id') not in self._sites:
            logger.info(" The current site is not in the range of selected auxiliary species sites， Skip over ...")
            return False
        self.realtotal += 1
        #  Consult (a document etc)hash Whether the value is already in the downloader
        downloader_obj = self.__get_downloader(downloader)
        torrent_info, _ = downloader_obj.get_torrents(ids=[seed.get("info_hash")])
        if torrent_info:
            logger.info(f"{seed.get('info_hash')}  Already in the downloader， Skip over ...")
            self.exist += 1
            return False
        #  Site flow control
        check, checkmsg = self.sites.check(site_domain)
        if check:
            logger.warn(checkmsg)
            self.fail += 1
            return False
        # Download seeds
        torrent_url = self.__get_download_url(seed=seed,
                                              site=site_info,
                                              base_url=download_page)
        if not torrent_url:
            #  Add failure cache
            self._error_caches.append(seed.get("info_hash"))
            self.fail += 1
            self.cached += 1
            return False
        #  Compulsory useHttps
        if __is_special_site(torrent_url):
            if "?" in torrent_url:
                torrent_url += "&https=1"
            else:
                torrent_url += "?https=1"
        # Download seeds文件
        _, content, _, _, error_msg = self.torrent.download_torrent(
            url=torrent_url,
            cookie=site_info.get("cookie"),
            ua=site_info.get("ua") or settings.USER_AGENT,
            proxy=site_info.get("proxy"))
        if not content:
            #  Failed to download
            self.fail += 1
            #  Add failure cache
            if error_msg and (' Unable to open link' in error_msg or ' Trigger site flow control' in error_msg):
                self._error_caches.append(seed.get("info_hash"))
            else:
                #  Situations where seeds do not exist
                self._permanent_error_caches.append(seed.get("info_hash"))
            logger.error(f"Download seeds文件失败：{torrent_url}")
            return False
        #  Add download， Default pause for auxiliary species tasks
        logger.info(f"Add download tasks：{torrent_url} ...")
        download_id = self.__download(downloader=downloader,
                                      content=content,
                                      save_path=save_path)
        if not download_id:
            #  Failed to download
            self.fail += 1
            #  Add failure cache
            self._error_caches.append(seed.get("info_hash"))
            return False
        else:
            self.success += 1
            #  Additional calibration tasks
            logger.info(f" Add a calibration check task：{download_id} ...")
            if not self._recheck_torrents.get(downloader):
                self._recheck_torrents[downloader] = []
            self._recheck_torrents[downloader].append(download_id)
            #  Download successfully
            logger.info(f" Successful addition of co-species download， Website：{site_info.get('name')}， Seed links：{torrent_url}")
            # TR It will be automatically calibrated
            if downloader == "qbittorrent":
                #  Start calibrating seeds
                downloader_obj.recheck_torrents(ids=[download_id])
            #  Successfully added to the cache as well， There are some changed paths that don't pass the checksum.， After manual deletion， Next time it'll be on the side.
            self._success_caches.append(seed.get("info_hash"))
            return True

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
    def __can_seeding(torrent: Any, dl_type: str):
        """
        Determine if a seed is ready to be seeded and is in a suspended state
        """
        try:
            return torrent.get("state") == "pausedUP" if dl_type == "qbittorrent" \
                else (torrent.status.stopped and torrent.percent_done == 1)
        except Exception as e:
            print(str(e))
            return False

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

    def __get_download_url(self, seed: dict, site: CommentedMap, base_url: str):
        """
        Patchwork seeds download links
        """

        def __is_special_site(url):
            """
            Determine if a site is special
            """
            spec_params = ["hash=", "authkey="]
            if any(field in base_url for field in spec_params):
                return True
            if "hdchina.org" in url:
                return True
            if "hdsky.me" in url:
                return True
            if "hdcity.in" in url:
                return True
            if "totheglory.im" in url:
                return True
            return False

        try:
            if __is_special_site(site.get('url')):
                #  Get the download link from the details page
                return self.__get_torrent_url_from_page(seed=seed, site=site)
            else:
                download_url = base_url.replace(
                    "id={}",
                    "id={id}"
                ).replace(
                    "/{}",
                    "/{id}"
                ).replace(
                    "/{torrent_key}",
                    ""
                ).format(
                    **{
                        "id": seed.get("torrent_id"),
                        "passkey": site.get("passkey") or '',
                        "uid": site.get("uid") or '',
                    }
                )
                if download_url.count("{"):
                    logger.warn(f" Ancillary tasks for this site are not currently supported，Url Conversion failure：{seed}")
                    return None
                download_url = re.sub(r"[&?]passkey=", "",
                                      re.sub(r"[&?]uid=", "",
                                             download_url,
                                             flags=re.IGNORECASE),
                                      flags=re.IGNORECASE)
                return f"{site.get('url')}{download_url}"
        except Exception as e:
            logger.warn(f" Website {site.get('name')} Url Conversion failure：{str(e)}， Try to get the seed download link via the details page ...")
            return self.__get_torrent_url_from_page(seed=seed, site=site)

    def __get_torrent_url_from_page(self, seed: dict, site: dict):
        """
        Get the download link from the details page
        """
        if not site.get('url'):
            logger.warn(f" Website {site.get('name')}  Site address not obtained， Unable to get seed download link")
            return None
        try:
            page_url = f"{site.get('url')}details.php?id={seed.get('torrent_id')}&hit=1"
            logger.info(f" Getting the seed download link now：{page_url} ...")
            res = RequestUtils(
                cookies=site.get("cookie"),
                ua=site.get("ua"),
                proxies=settings.PROXY if site.get("proxy") else None
            ).get_res(url=page_url)
            if res is not None and res.status_code in (200, 500):
                if "charset=utf-8" in res.text or "charset=UTF-8" in res.text:
                    res.encoding = "UTF-8"
                else:
                    res.encoding = res.apparent_encoding
                if not res.text:
                    logger.warn(f" Failed to get seed download link， Page content is empty：{page_url}")
                    return None
                #  Utilizationxpath Get the download link from the page
                html = etree.HTML(res.text)
                for xpath in self._torrent_xpaths:
                    download_url = html.xpath(xpath)
                    if download_url:
                        download_url = download_url[0]
                        logger.info(f" Get seed download link successfully：{download_url}")
                        if not download_url.startswith("http"):
                            if download_url.startswith("/"):
                                download_url = f"{site.get('url')}{download_url[1:]}"
                            else:
                                download_url = f"{site.get('url')}{download_url}"
                        return download_url
                logger.warn(f" Failed to get seed download link， Download link not found：{page_url}")
                return None
            else:
                logger.error(f" Failed to get seed download link， Request failed：{page_url}，{res.status_code if res else ''}")
                return None
        except Exception as e:
            logger.warn(f" Failed to get seed download link：{str(e)}")
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

    @eventmanager.register(EventType.SiteDeleted)
    def site_deleted(self, event):
        """
        Delete the corresponding site selection
        """
        site_id = event.event_data.get("site_id")
        config = self.get_config()
        if config:
            sites = config.get("sites")
            if sites:
                if isinstance(sites, str):
                    sites = [sites]

                #  Delete the corresponding site
                if site_id:
                    sites = [site for site in sites if int(site) != int(site_id)]
                else:
                    #  Empty
                    sites = []

                #  If no site， Failing agreement
                if len(sites) == 0:
                    self._enabled = False

                self._sites = sites
                #  Save configuration
                self.__update_config()
