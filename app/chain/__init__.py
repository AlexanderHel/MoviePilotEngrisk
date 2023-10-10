import gc
import pickle
import traceback
from abc import ABCMeta
from pathlib import Path
from typing import Optional, Any, Tuple, List, Set, Union, Dict

from qbittorrentapi import TorrentFilesList
from ruamel.yaml import CommentedMap
from sqlalchemy.orm import Session
from transmission_rpc import File

from app.core.config import settings
from app.core.context import Context
from app.core.context import MediaInfo, TorrentInfo
from app.core.event import EventManager
from app.core.meta import MetaBase
from app.core.module import ModuleManager
from app.log import logger
from app.schemas import TransferInfo, TransferTorrent, ExistMediaInfo, DownloadingTorrent, CommingMessage, Notification, \
    WebhookEventInfo, TmdbEpisode
from app.schemas.types import TorrentStatus, MediaType, MediaImageType, EventType
from app.utils.object import ObjectUtils


class ChainBase(metaclass=ABCMeta):
    """
    Processing chain base class
    """

    def __init__(self, db: Session = None):
        """
        Public initialization
        """
        self._db = db
        self.modulemanager = ModuleManager()
        self.eventmanager = EventManager()

    @staticmethod
    def load_cache(filename: str) -> Any:
        """
        Load cache from local
        """
        cache_path = settings.TEMP_PATH / filename
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as err:
                logger.error(f" Load cache {filename}  Make a mistake：{err}")
        return None

    @staticmethod
    def save_cache(cache: Any, filename: str) -> None:
        """
        Save cache locally
        """
        try:
            with open(settings.TEMP_PATH / filename, 'wb') as f:
                pickle.dump(cache, f)
        except Exception as err:
            logger.error(f" Save cache {filename}  Make a mistake：{err}")
        finally:
            #  Proactive resource recovery
            del cache
            gc.collect()

    def run_module(self, method: str, *args, **kwargs) -> Any:
        """
        Run all modules that contain this method， Then return the result
        """

        def is_result_empty(ret):
            """
            Determine if the result is null
            """
            if isinstance(ret, tuple):
                return all(value is None for value in ret)
            else:
                return result is None

        logger.debug(f" Request module execution：{method} ...")
        result = None
        modules = self.modulemanager.get_modules(method)
        for module in modules:
            try:
                func = getattr(module, method)
                if is_result_empty(result):
                    #  Come (or go) backNone， First implementation or need to continue to the next module
                    result = func(*args, **kwargs)
                elif ObjectUtils.check_signature(func, result):
                    #  The return result is consistent with the method signature， Pass the results into the（ Cannot run multiple modules at the same time need to be controlled by a switch）
                    result = func(result)
                elif isinstance(result, list):
                    #  Return to list， Merge the results of multiple module runs（ Cannot run multiple modules at the same time need to be controlled by a switch）
                    temp = func(*args, **kwargs)
                    if isinstance(temp, list):
                        result.extend(temp)
                else:
                    #  Suspension of continuation
                    break
            except Exception as err:
                logger.error(f" Runtime module {method}  Make a mistake：{module.__class__.__name__} - {err}\n{traceback.print_exc()}")
        return result

    def recognize_media(self, meta: MetaBase = None,
                        mtype: MediaType = None,
                        tmdbid: int = None) -> Optional[MediaInfo]:
        """
        Identify media messages
        :param meta:      Identified metadata
        :param mtype:     Types of media identified， Together withtmdbid Form a complete set
        :param tmdbid:   tmdbid
        :return:  Identified media messages， Includes episode information
        """
        return self.run_module("recognize_media", meta=meta, mtype=mtype, tmdbid=tmdbid)

    def match_doubaninfo(self, name: str, mtype: str = None,
                         year: str = None, season: int = None) -> Optional[dict]:
        """
        Search and match douban information
        :param name:  Caption
        :param mtype:  Typology
        :param year:  Particular year
        :param season:  Classifier for seasonal crop yield or seasons of a tv series
        """
        return self.run_module("match_doubaninfo", name=name, mtype=mtype, year=year, season=season)

    def obtain_images(self, mediainfo: MediaInfo) -> Optional[MediaInfo]:
        """
        Supplemental grabbing of media information images
        :param mediainfo:   Identified media messages
        :return:  Updated media information
        """
        return self.run_module("obtain_images", mediainfo=mediainfo)

    def obtain_specific_image(self, mediaid: Union[str, int], mtype: MediaType,
                              image_type: MediaImageType, image_prefix: str = None,
                              season: int = None, episode: int = None) -> Optional[str]:
        """
        Get the specified media information image， Return to image address
        :param mediaid:      Media, esp. news mediaID
        :param mtype:        Media type
        :param image_type:   Image type
        :param image_prefix:  Image prefix
        :param season:       Classifier for seasonal crop yield or seasons of a tv series
        :param episode:      Classifier for sections of a tv series e.g. episode
        """
        return self.run_module("obtain_specific_image", mediaid=mediaid, mtype=mtype,
                               image_prefix=image_prefix, image_type=image_type,
                               season=season, episode=episode)

    def douban_info(self, doubanid: str) -> Optional[dict]:
        """
        Get douban information
        :param doubanid:  Douban, prc social networking websiteID
        :return:  Douban information
        """
        return self.run_module("douban_info", doubanid=doubanid)

    def tvdb_info(self, tvdbid: int) -> Optional[dict]:
        """
        GainTVDB Text
        :param tvdbid: int
        :return: TVDB Text
        """
        return self.run_module("tvdb_info", tvdbid=tvdbid)

    def tmdb_info(self, tmdbid: int, mtype: MediaType) -> Optional[dict]:
        """
        GainTMDB Text
        :param tmdbid: int
        :param mtype:   Media type
        :return: TVDB Text
        """
        return self.run_module("tmdb_info", tmdbid=tmdbid, mtype=mtype)

    def message_parser(self, body: Any, form: Any,
                       args: Any) -> Optional[CommingMessage]:
        """
        Parsing message content， Return to dictionary， Note the following convention values：
        userid:  SubscribersID
        username:  User id
        text:  Element
        :param body:  Requestor
        :param form:  Form (document)
        :param args:  Parameters
        :return:  News channel、 Message
        """
        return self.run_module("message_parser", body=body, form=form, args=args)

    def webhook_parser(self, body: Any, form: Any, args: Any) -> Optional[WebhookEventInfo]:
        """
        AnalyzeWebhook Style of telegram
        :param body:   Requestor
        :param form:   Request form
        :param args:   Request parameters
        :return:  Dictionaries， Parsing into a message requires the inclusion of the：title、text、image
        """
        return self.run_module("webhook_parser", body=body, form=form, args=args)

    def search_medias(self, meta: MetaBase) -> Optional[List[MediaInfo]]:
        """
        Search for media information
        :param meta:   Identified metadata
        :reutrn:  Media information list
        """
        return self.run_module("search_medias", meta=meta)

    def search_torrents(self, site: CommentedMap,
                        keywords: List[str],
                        mtype: MediaType = None,
                        page: int = 0) -> List[TorrentInfo]:
        """
        Searching a site for seed resources
        :param site:   Website
        :param keywords:   Search keyword list
        :param mtype:   Media type
        :param page:   Pagination
        :reutrn:  Resource list
        """
        return self.run_module("search_torrents", site=site, keywords=keywords,
                               mtype=mtype, page=page)

    def refresh_torrents(self, site: CommentedMap) -> List[TorrentInfo]:
        """
        Get seeds for the latest page of the site， Multiple sites require multithreading
        :param site:   Website
        :reutrn:  List of seed resources
        """
        return self.run_module("refresh_torrents", site=site)

    def filter_torrents(self, rule_string: str,
                        torrent_list: List[TorrentInfo],
                        season_episodes: Dict[int, list] = None,
                        mediainfo: MediaInfo = None) -> List[TorrentInfo]:
        """
        Filtering seed resources
        :param rule_string:   Filter rules
        :param torrent_list:   Resource list
        :param season_episodes:   Season episode filter {season:[episodes]}
        :param mediainfo:   Identified media messages
        :return:  Filtered resource list， Add resource prioritization
        """
        return self.run_module("filter_torrents", rule_string=rule_string,
                               torrent_list=torrent_list, season_episodes=season_episodes,
                               mediainfo=mediainfo)

    def download(self, content: Union[Path, str], download_dir: Path, cookie: str,
                 episodes: Set[int] = None, category: str = None
                 ) -> Optional[Tuple[Optional[str], str]]:
        """
        Based on seed documents， Select and add a download task
        :param content:   Seed file address or magnet link
        :param download_dir:   Download catalog
        :param cookie:  cookie
        :param episodes:   Number of episodes to download
        :param category:   Seed classification
        :return:  TorrentHash， Error message
        """
        return self.run_module("download", content=content, download_dir=download_dir,
                               cookie=cookie, episodes=episodes, category=category)

    def download_added(self, context: Context, download_dir: Path, torrent_path: Path = None) -> None:
        """
        After adding a successful download task， Download subtitles from the site， Save to download directory
        :param context:   (textual) context， Includes identifying information、 Media information、 Seed information
        :param download_dir:   Download catalog
        :param torrent_path:   Seed file address
        :return: None， This method can be processed by multiple modules simultaneously
        """
        return self.run_module("download_added", context=context, torrent_path=torrent_path,
                               download_dir=download_dir)

    def list_torrents(self, status: TorrentStatus = None,
                      hashs: Union[list, str] = None) -> Optional[List[Union[TransferTorrent, DownloadingTorrent]]]:
        """
        Get downloader seed list
        :param status:   Seed state
        :param hashs:   TorrentHash
        :return:  List of seeds in the downloader that match the status
        """
        return self.run_module("list_torrents", status=status, hashs=hashs)

    def transfer(self, path: Path, meta: MetaBase, mediainfo: MediaInfo,
                 transfer_type: str, target: Path = None,
                 episodes_info: List[TmdbEpisode] = None) -> Optional[TransferInfo]:
        """
        File transfer
        :param path:   File path
        :param meta:  Pre-identified metadata
        :param mediainfo:   Identified media messages
        :param transfer_type:   Transfer mode
        :param target:   Transfer of target paths
        :param episodes_info:  All episode information for the current season
        :return: {path, target_path, message}
        """
        return self.run_module("transfer", path=path, meta=meta, mediainfo=mediainfo,
                               transfer_type=transfer_type, target=target,
                               episodes_info=episodes_info)

    def transfer_completed(self, hashs: Union[str, list], path: Path = None) -> None:
        """
        Disposal upon completion of the transfer
        :param hashs:   TorrentHash
        :param path:   Source catalog
        """
        return self.run_module("transfer_completed", hashs=hashs, path=path)

    def remove_torrents(self, hashs: Union[str, list]) -> bool:
        """
        Delete downloader seeds
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.run_module("remove_torrents", hashs=hashs)

    def start_torrents(self, hashs: Union[list, str]) -> bool:
        """
        Start download
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.run_module("start_torrents", hashs=hashs)

    def stop_torrents(self, hashs: Union[list, str]) -> bool:
        """
        Stop downloading
        :param hashs:   TorrentHash
        :return: bool
        """
        return self.run_module("stop_torrents", hashs=hashs)

    def torrent_files(self, tid: str) -> Optional[Union[TorrentFilesList, List[File]]]:
        """
        Getting the seed file
        :param tid:   TorrentHash
        :return:  Seed file
        """
        return self.run_module("torrent_files", tid=tid)

    def media_exists(self, mediainfo: MediaInfo, itemid: str = None) -> Optional[ExistMediaInfo]:
        """
        Determine if a media file exists
        :param mediainfo:   Identified media messages
        :param itemid:   Media serverItemID
        :return:  Returns if not presentNone， Return information when present， Includes all existing episodes of each season{type: movie/tv, seasons: {season: [episodes]}}
        """
        return self.run_module("media_exists", mediainfo=mediainfo, itemid=itemid)

    def refresh_mediaserver(self, mediainfo: MediaInfo, file_path: Path) -> None:
        """
        Refresh media library
        :param mediainfo:   Identified media messages
        :param file_path:   File path
        :return:  Success or failure
        """
        self.run_module("refresh_mediaserver", mediainfo=mediainfo, file_path=file_path)

    def post_message(self, message: Notification) -> None:
        """
        Send a message
        :param message:   Message body
        :return:  Success or failure
        """
        #  Send event
        self.eventmanager.send_event(etype=EventType.NoticeMessage,
                                     data={
                                         "channel": message.channel,
                                         "title": message.title,
                                         "text": message.text,
                                         "image": message.image,
                                         "userid": message.userid,
                                     })
        logger.info(f"Send a message：channel={message.channel}，"
                    f"title={message.title}, "
                    f"text={message.text}，"
                    f"userid={message.userid}")
        self.run_module("post_message", message=message)

    def post_medias_message(self, message: Notification, medias: List[MediaInfo]) -> Optional[bool]:
        """
        Send media message selection list
        :param message:   Message body
        :param medias:   Media list
        :return:  Success or failure
        """
        return self.run_module("post_medias_message", message=message, medias=medias)

    def post_torrents_message(self, message: Notification, torrents: List[Context]) -> Optional[bool]:
        """
        Send seed message selection list
        :param message:   Message body
        :param torrents:   Seed list
        :return:  Success or failure
        """
        return self.run_module("post_torrents_message", message=message, torrents=torrents)

    def scrape_metadata(self, path: Path, mediainfo: MediaInfo) -> None:
        """
        Scraping metadata
        :param path:  Media file path
        :param mediainfo:   Identified media messages
        :return:  Success or failure
        """
        self.run_module("scrape_metadata", path=path, mediainfo=mediainfo)

    def register_commands(self, commands: Dict[str, dict]) -> None:
        """
        Registration menu commands
        """
        self.run_module("register_commands", commands=commands)

    def scheduler_job(self) -> None:
        """
        Timed task， Each10 One call per minute， Module implements this interface to implement a timed service
        """
        self.run_module("scheduler_job")

    def clear_cache(self) -> None:
        """
        Clearing the cache， The module implements this interface in response to a clear cache event
        """
        self.run_module("clear_cache")
