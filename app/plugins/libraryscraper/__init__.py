from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from typing import List, Tuple, Dict, Any

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.db.transferhistory_oper import TransferHistoryOper
from app.helper.nfo import NfoReader
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import MediaType
from app.utils.system import SystemUtils


class LibraryScraper(_PluginBase):

    #  Plug-in name
    plugin_name = " Media library scraping"
    #  Plugin description
    plugin_desc = " Scheduled scraping of media libraries， Filling in missing metadata and images。"
    #  Plug-in icons
    plugin_icon = "scraper.png"
    #  Theme color
    plugin_color = "#FF7D00"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "libraryscraper_"
    #  Loading sequence
    plugin_order = 7
    #  Available user levels
    user_level = 1

    #  Private property
    transferhis = None
    _scheduler = None
    _scraper = None
    #  Speed limit switch
    _enabled = False
    _onlyonce = False
    _cron = None
    _mode = ""
    _scraper_paths = ""
    _exclude_paths = ""
    #  Logout event
    _event = Event()
    
    def init_plugin(self, config: dict = None):
        #  Read configuration
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._mode = config.get("mode") or ""
            self._scraper_paths = config.get("scraper_paths") or ""
            self._exclude_paths = config.get("exclude_paths") or ""

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Starting a timed task &  Run one immediately
        if self._enabled or self._onlyonce:
            self.transferhis = TransferHistoryOper(self.db)
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                logger.info(f" Media library scraping service launched， Cyclicality：{self._cron}")
                try:
                    self._scheduler.add_job(func=self.__libraryscraper,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Media library scraping")
                except Exception as e:
                    logger.error(f" Media library scraping service startup failure， Rationale：{e}")
                    self.systemmessage.put(f" Media library scraping service startup failure， Rationale：{e}")
            else:
                logger.info(f" Media library scraping service launched， Cyclicality： Each7 Sky")
                self._scheduler.add_job(func=self.__libraryscraper,
                                        trigger=CronTrigger.from_crontab("0 0 */7 * *"),
                                        name=" Media library scraping")
            if self._onlyonce:
                logger.info(f" Media library scraping services， Run one immediately")
                self._scheduler.add_job(func=self.__libraryscraper, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name="Cloudflare Preferred")
                #  Turn off the disposable switch
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "enabled": self._enabled,
                    "cron": self._cron,
                    "mode": self._mode,
                    "scraper_paths": self._scraper_paths,
                    "exclude_paths": self._exclude_paths
                })
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'mode',
                                            'label': ' Scraping mode',
                                            'items': [
                                                {'title': ' Scraping missing metadata and images only', 'value': ''},
                                                {'title': ' Override all metadata and images', 'value': 'force_all'},
                                                {'title': ' Override all metadata', 'value': 'force_nfo'},
                                                {'title': ' Coverage of all images', 'value': 'force_image'},
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'scraper_paths',
                                            'label': ' Scrape path',
                                            'rows': 5,
                                            'placeholder': ' One directory per line， Needs to be configured to the parent directory of the media file， I.e., you need to configure the secondary category directory when you open the secondary category.'
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
                                            'model': 'exclude_paths',
                                            'label': ' Excluded paths',
                                            'rows': 2,
                                            'placeholder': ' One directory per line'
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
            "cron": "0 0 */7 * *",
            "mode": "",
            "scraper_paths": "",
            "err_hosts": ""
        }

    def get_page(self) -> List[dict]:
        pass

    def __libraryscraper(self):
        """
        Start scraping the media library
        """
        if not self._scraper_paths:
            return
        #  Exclude catalogs
        exclude_paths = self._exclude_paths.split("\n")
        #  Selected catalogs
        paths = self._scraper_paths.split("\n")
        for path in paths:
            if not path:
                continue
            scraper_path = Path(path)
            if not scraper_path.exists():
                logger.warning(f" Media library scraping path does not exist：{path}")
                continue
            logger.info(f"Start scraping the media library：{path} ...")
            #  Traversing a layer of folders
            for sub_path in scraper_path.iterdir():
                if self._event.is_set():
                    logger.info(f" Media library scraping service discontinued")
                    return
                #  Exclude catalogs
                exclude_flag = False
                for exclude_path in exclude_paths:
                    try:
                        if sub_path.is_relative_to(Path(exclude_path)):
                            exclude_flag = True
                            break
                    except Exception as err:
                        print(str(err))
                if exclude_flag:
                    logger.debug(f"{sub_path}  In the excluded directory， Skip over ...")
                    continue
                #  Start scraping catalog
                if sub_path.is_dir():
                    #  Determine if a directory is a media directory
                    dir_meta = MetaInfo(sub_path.name)
                    if not dir_meta.name or not dir_meta.year:
                        logger.warn(f"{sub_path}  Probably not a media catalog， Please check the scraping catalog configuration， Skip over ...")
                        continue
                    logger.info(f" Start scraping catalog：{sub_path} ...")
                    self.__scrape_dir(path=sub_path, dir_meta=dir_meta)
                    logger.info(f" Catalogs {sub_path}  Scraping finish")
            logger.info(f" Media library {path}  Scraping finish")

    def __scrape_dir(self, path: Path, dir_meta: MetaBase):
        """
        Scraping a catalog， The directory must be a media file directory
        """

        #  Media information
        mediainfo = None

        #  Find all files in a directory
        files = SystemUtils.list_files(path, settings.RMT_MEDIAEXT)
        for file in files:
            if self._event.is_set():
                logger.info(f" Media library scraping service discontinued")
                return

            #  Identifying metadata
            meta_info = MetaInfo(file.stem)
            #  Incorporation
            meta_info.merge(dir_meta)
            #  Whether scraping
            scrap_metadata = settings.SCRAP_METADATA

            #  When there is no media information or when there is a name change， Need to re-identify
            if not mediainfo \
                    or meta_info.name != dir_meta.name:
                #  Prioritize local readsnfo File
                tmdbid = None
                if meta_info.type == MediaType.MOVIE:
                    #  Cinematic
                    movie_nfo = file.parent / "movie.nfo"
                    if movie_nfo.exists():
                        tmdbid = self.__get_tmdbid_from_nfo(movie_nfo)
                    file_nfo = file.with_suffix(".nfo")
                    if not tmdbid and file_nfo.exists():
                        tmdbid = self.__get_tmdbid_from_nfo(file_nfo)
                else:
                    #  Dramas
                    tv_nfo = file.parent.parent / "tvshow.nfo"
                    if tv_nfo.exists():
                        tmdbid = self.__get_tmdbid_from_nfo(tv_nfo)
                if tmdbid:
                    #  Check or refer toTMDBID Recognize
                    logger.info(f" Read to localnfo Documentationtmdbid：{tmdbid}")
                    mediainfo = self.chain.recognize_media(tmdbid=tmdbid, mtype=meta_info.type)
                else:
                    #  Identification by name
                    mediainfo = self.chain.recognize_media(meta=meta_info)
                if not mediainfo:
                    logger.warn(f" No media messages recognized：{file}")
                    continue
                    
                #  If not enabled does the new inbound media follow theTMDB Information changes are then based ontmdbid Query the previoustitle
                if not settings.SCRAP_FOLLOW_TMDB:
                    transfer_history = self.transferhis.get_by_type_tmdbid(tmdbid=mediainfo.tmdb_id,
                                                                           mtype=mediainfo.type.value)
                    if transfer_history:
                        mediainfo.title = transfer_history.title

                #  In override mode， Deletion in advancenfo
                if self._mode in ["force_all", "force_nfo"]:
                    scrap_metadata = True
                    nfo_files = SystemUtils.list_files(path, [".nfo"])
                    for nfo_file in nfo_files:
                        try:
                            logger.warn(f" Removingnfo File：{nfo_file}")
                            nfo_file.unlink()
                        except Exception as err:
                            print(str(err))

                #  In override mode， Early deletion of image files
                if self._mode in ["force_all", "force_image"]:
                    scrap_metadata = True
                    image_files = SystemUtils.list_files(path, [".jpg", ".png"])
                    for image_file in image_files:
                        if ".actors" in str(image_file):
                            continue
                        try:
                            logger.warn(f" Deleting image files：{image_file}")
                            image_file.unlink()
                        except Exception as err:
                            print(str(err))

            #  Scraping of individual documents
            if scrap_metadata:
                self.chain.scrape_metadata(path=file, mediainfo=mediainfo)

    @staticmethod
    def __get_tmdbid_from_nfo(file_path: Path):
        """
        Through (a gap)nfo Getting information from documents
        :param file_path:
        :return: tmdbid
        """
        if not file_path:
            return None
        xpaths = [
            "uniqueid[@type='Tmdb']",
            "uniqueid[@type='tmdb']",
            "uniqueid[@type='TMDB']",
            "tmdbid"
        ]
        reader = NfoReader(file_path)
        for xpath in xpaths:
            try:
                tmdbid = reader.get_element_value(xpath)
                if tmdbid:
                    return tmdbid
            except Exception as err:
                print(str(err))
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
