import base64
import copy
import datetime
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional

import pytz
import zhconv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from requests import RequestException

from app.chain.mediaserver import MediaServerChain
from app.chain.tmdb import TmdbChain
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.core.meta import MetaBase
from app.log import logger
from app.modules.emby import Emby
from app.modules.jellyfin import Jellyfin
from app.modules.plex import Plex
from app.plugins import _PluginBase
from app.schemas import MediaInfo, MediaServerItem
from app.schemas.types import EventType, MediaType
from app.utils.common import retry
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class PersonMeta(_PluginBase):
    #  Plug-in name
    plugin_name = " Performer scraping"
    #  Plugin description
    plugin_desc = " Pictures of scraping staff and their chinese names。"
    #  Plug-in icons
    plugin_icon = "actor.png"
    #  Theme color
    plugin_color = "#E66E72"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "personmeta_"
    #  Loading sequence
    plugin_order = 24
    #  Available user levels
    auth_level = 1

    #  Logout event
    _event = threading.Event()

    #  Private property
    _scheduler = None
    tmdbchain = None
    mschain = None
    _enabled = False
    _onlyonce = False
    _cron = None
    _delay = 0
    _remove_nozh = False

    def init_plugin(self, config: dict = None):
        self.tmdbchain = TmdbChain(self.db)
        self.mschain = MediaServerChain(self.db)
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._delay = config.get("delay") or 0
            self._remove_nozh = config.get("remove_nozh") or False

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Starting services
        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron or self._onlyonce:
                if self._cron:
                    try:
                        self._scheduler.add_job(func=self.scrap_library,
                                                trigger=CronTrigger.from_crontab(self._cron),
                                                name=" Performer scraping")
                        logger.info(f" Performer scraping service launched， Cyclicality：{self._cron}")
                    except Exception as e:
                        logger.error(f" Performer scraping service startup failure， Error message：{str(e)}")
                        self.systemmessage.put(f" Performer scraping service startup failure， Error message：{str(e)}")
                if self._onlyonce:
                    self._scheduler.add_job(func=self.scrap_library, trigger='date',
                                            run_date=datetime.datetime.now(
                                                tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3)
                                            )
                    logger.info(f" Performer scraping service launched， Run one immediately")
                    #  Turn off the disposable switch
                    self._onlyonce = False
                    #  Save configuration
                    self.__update_config()

            if self._scheduler.get_jobs():
                #  Starting services
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __update_config(self):
        """
        Updating the configuration
        """
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "cron": self._cron,
            "delay": self._delay,
            "remove_nozh": self._remove_nozh
        })

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
                                            'label': ' Media library scanning cycle',
                                            'placeholder': '5 Classifier for honorific peoplecron Displayed formula'
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
                                            'model': 'delay',
                                            'label': ' Delays in warehousing（ Unit of angle or arc equivalent one sixtieth of a degree）',
                                            'placeholder': '30'
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
                                            'model': 'remove_nozh',
                                            'label': ' Deletion of non-chinese speaking actors',
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
            "cron": "",
            "delay": 30,
            "remove_nozh": False
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.TransferComplete)
    def scrap_rt(self, event: Event):
        """
        Real-time scraping of actor information based on events
        """
        if not self._enabled:
            return
        #  Event data
        mediainfo: MediaInfo = event.event_data.get("mediainfo")
        meta: MetaBase = event.event_data.get("meta")
        if not mediainfo or not meta:
            return
        #  Procrastinate
        if self._delay:
            time.sleep(int(self._delay))
        #  Querying entries in the media server
        existsinfo = self.chain.media_exists(mediainfo=mediainfo)
        if not existsinfo or not existsinfo.itemid:
            logger.warn(f" Performer scraping {mediainfo.title_year}  Doesn't exist in the media library")
            return
        #  Search for entry details
        iteminfo = self.mschain.iteminfo(server=existsinfo.server, item_id=existsinfo.itemid)
        if not iteminfo:
            logger.warn(f" Performer scraping {mediainfo.title_year}  Failed to get entry details")
            return
        #  Scraping cast and crew information
        self.__update_item(server=existsinfo.server, item=iteminfo,
                           mediainfo=mediainfo, season=meta.begin_season)

    def scrap_library(self):
        """
        Scanning the entire media library， Scraping actor information
        """
        #  All media servers
        if not settings.MEDIASERVER:
            return
        for server in settings.MEDIASERVER.split(","):
            #  Scan all media libraries
            logger.info(f" Start scraping servers {server}  Cast information ...")
            for library in self.mschain.librarys(server):
                logger.info(f" Start scraping the media library {library.name}  Cast information ...")
                for item in self.mschain.items(server, library.id):
                    if not item:
                        continue
                    if not item.item_id:
                        continue
                    if "Series" not in item.item_type \
                            and "Movie" not in item.item_type:
                        continue
                    if self._event.is_set():
                        logger.info(f" Discontinuation of cast shaving services")
                        return
                    #  Processing of entries
                    logger.info(f" Start scraping {item.title}  Cast information ...")
                    self.__update_item(server=server, item=item)
                    logger.info(f"{item.title}  The actor's information is scraped to completion")
                logger.info(f" Media library {library.name}  The actor's information is scraped to completion")
            logger.info(f" Server (computer) {server}  The actor's information is scraped to completion")

    def __update_peoples(self, server: str, itemid: str, iteminfo: dict, douban_actors):
        #  Handling character information in media items
        """
        "People": [
            {
              "Name": " Daniel (name)· Craig (name)",
              "Id": "33625",
              "Role": "James Bond",
              "Type": "Actor",
              "PrimaryImageTag": "bef4f764540f10577f804201d8d27918"
            }
        ]
        """
        peoples = []
        #  Updating current media item characters
        for people in iteminfo["People"] or []:
            if self._event.is_set():
                logger.info(f" Discontinuation of cast shaving services")
                return
            if not people.get("Name"):
                continue
            if StringUtils.is_chinese(people.get("Name")) \
                    and StringUtils.is_chinese(people.get("Role")):
                peoples.append(people)
                continue
            info = self.__update_people(server=server, people=people,
                                        douban_actors=douban_actors)
            if info:
                peoples.append(info)
            elif not self._remove_nozh:
                peoples.append(people)
        #  Saving media item information
        if peoples:
            iteminfo["People"] = peoples
            self.set_iteminfo(server=server, itemid=itemid, iteminfo=iteminfo)

    def __update_item(self, server: str, item: MediaServerItem,
                      mediainfo: MediaInfo = None, season: int = None):
        """
        Updating entries in the media server
        """

        def __need_trans_actor(_item):
            #  Whether character information needs to be processed
            _peoples = [x for x in _item.get("People", []) if
                        (x.get("Name") and not StringUtils.is_chinese(x.get("Name")))
                        or (x.get("Role") and not StringUtils.is_chinese(x.get("Role")))]
            if _peoples:
                return True
            return False

        #  Identify media messages
        if not mediainfo:
            if not item.tmdbid:
                logger.warn(f"{item.title}  Not foundtmdbid， Unable to recognize media messages")
                return
            mtype = MediaType.TV if item.item_type in ['Series', 'show'] else MediaType.MOVIE
            mediainfo = self.chain.recognize_media(mtype=mtype, tmdbid=item.tmdbid)
            if not mediainfo:
                logger.warn(f"{item.title}  No media messages recognized")
                return

        #  Get media items
        iteminfo = self.get_iteminfo(server=server, itemid=item.item_id)
        if not iteminfo:
            logger.warn(f"{item.title}  No media items found")
            return

        if __need_trans_actor(iteminfo):
            #  Get douban cast information
            logger.info(f" Start acquiring {item.title}  Douban cast information ...")
            douban_actors = self.__get_douban_actors(mediainfo=mediainfo, season=season)
            self.__update_peoples(server=server, itemid=item.item_id, iteminfo=iteminfo, douban_actors=douban_actors)
        else:
            logger.info(f"{item.title}  The character information is already in chinese， No need to update")

        #  Dealing with season and set characters
        if iteminfo.get("Type") and "Series" in iteminfo["Type"]:
            #  Access to seasonal media items
            seasons = self.get_items(server=server, parentid=item.item_id, mtype="Season")
            if not seasons:
                logger.warn(f"{item.title}  Seasonal media items not found")
                return
            for season in seasons["Items"]:
                #  Get douban cast information
                season_actors = self.__get_douban_actors(mediainfo=mediainfo, season=season.get("IndexNumber"))
                #  If it isJellyfin， Characters of the renewal season，Emby/Plex There are no characters in the season.
                if server == "jellyfin":
                    seasoninfo = self.get_iteminfo(server=server, itemid=season.get("Id"))
                    if not seasoninfo:
                        logger.warn(f"{item.title}  Seasonal media items not found：{season.get('Id')}")
                        continue

                    if __need_trans_actor(seasoninfo):
                        #  Renewal season media item characters
                        self.__update_peoples(server=server, itemid=season.get("Id"), iteminfo=seasoninfo,
                                              douban_actors=season_actors)
                        logger.info(f" Classifier for seasonal crop yield or seasons of a tv series {seasoninfo.get('Id')}  The update of the character information is completed")
                    else:
                        logger.info(f" Classifier for seasonal crop yield or seasons of a tv series {seasoninfo.get('Id')}  The character information is already in chinese， No need to update")
                #  Access to media sets
                episodes = self.get_items(server=server, parentid=season.get("Id"), mtype="Episode")
                if not episodes:
                    logger.warn(f"{item.title}  No media sets found")
                    continue
                #  Updated set of media items characters
                for episode in episodes["Items"]:
                    #  Access to media sets详情
                    episodeinfo = self.get_iteminfo(server=server, itemid=episode.get("Id"))
                    if not episodeinfo:
                        logger.warn(f"{item.title}  No media sets found：{episode.get('Id')}")
                        continue
                    if __need_trans_actor(episodeinfo):
                        #  Updated set of media items characters
                        self.__update_peoples(server=server, itemid=episode.get("Id"), iteminfo=episodeinfo,
                                              douban_actors=season_actors)
                        logger.info(f" Classifier for sections of a tv series e.g. episode {episodeinfo.get('Id')}  The update of the character information is completed")
                    else:
                        logger.info(f" Classifier for sections of a tv series e.g. episode {episodeinfo.get('Id')}  The character information is already in chinese， No need to update")

    def __update_people(self, server: str, people: dict, douban_actors: list = None) -> Optional[dict]:
        """
        Update character information， Returns the replaced character information
        """

        def __get_peopleid(p: dict) -> Tuple[Optional[str], Optional[str]]:
            """
            Get the character'sTMDBID、IMDBID
            """
            if not p.get("ProviderIds"):
                return None, None
            peopletmdbid, peopleimdbid = None, None
            if "Tmdb" in p["ProviderIds"]:
                peopletmdbid = p["ProviderIds"]["Tmdb"]
            if "tmdb" in p["ProviderIds"]:
                peopletmdbid = p["ProviderIds"]["tmdb"]
            if "Imdb" in p["ProviderIds"]:
                peopleimdbid = p["ProviderIds"]["Imdb"]
            if "imdb" in p["ProviderIds"]:
                peopleimdbid = p["ProviderIds"]["imdb"]
            return peopletmdbid, peopleimdbid

        #  Returned character information
        ret_people = copy.deepcopy(people)

        try:
            #  Find out more about the people in the media library
            personinfo = self.get_iteminfo(server=server, itemid=people.get("Id"))
            if not personinfo:
                logger.warn(f" Characters not found {people.get('Name')}  Such information")
                return None

            #  Whether to update the flag
            updated_name = False
            updated_overview = False
            update_character = False
            profile_path = None

            #  Through (a gap)TMDB Update character information in the message
            person_tmdbid, person_imdbid = __get_peopleid(personinfo)
            if person_tmdbid:
                person_tmdbinfo = self.tmdbchain.person_detail(int(person_tmdbid))
                if person_tmdbinfo:
                    cn_name = self.__get_chinese_name(person_tmdbinfo)
                    if cn_name:
                        #  Update chinese name
                        logger.info(f"{people.get('Name')}  Through (a gap)TMDB Get the chinese name：{cn_name}")
                        personinfo["Name"] = cn_name
                        ret_people["Name"] = cn_name
                        updated_name = True
                        #  Updated chinese description
                        biography = person_tmdbinfo.get("biography")
                        if biography and StringUtils.is_chinese(biography):
                            logger.info(f"{people.get('Name')}  Through (a gap)TMDB Get the chinese description")
                            personinfo["Overview"] = biography
                            updated_overview = True
                        #  Photograph
                        profile_path = person_tmdbinfo.get('profile_path')
                        if profile_path:
                            logger.info(f"{people.get('Name')}  Through (a gap)TMDB Get the image：{profile_path}")
                            profile_path = f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{profile_path}"

            #  Updating character information from doujinshi
            """
            {
              "name": " Daniel (name)· Craig (name)",
              "roles": [
                " Actor or actress",
                " Moviemaker",
                " Dubbing (filmmaking)"
              ],
              "title": " Daniel (name)· Craig (name)（ Self-titled (album)） United kingdom of great britain and northern ireland, England, Cheshire (english county), Chester's movie and tv actors",
              "url": "https://movie.douban.com/celebrity/1025175/",
              "user": null,
              "character": " Impersonate  James (name)· Bond (name) James Bond 007",
              "uri": "douban://douban.com/celebrity/1025175?subject_id=27230907",
              "avatar": {
                "large": "https://qnmob3.doubanio.com/view/celebrity/raw/public/p42588.jpg?imageView2/2/q/80/w/600/h/3000/format/webp",
                "normal": "https://qnmob3.doubanio.com/view/celebrity/raw/public/p42588.jpg?imageView2/2/q/80/w/200/h/300/format/webp"
              },
              "sharing_url": "https://www.douban.com/doubanapp/dispatch?uri=/celebrity/1025175/",
              "type": "celebrity",
              "id": "1025175",
              "latin_name": "Daniel Craig"
            }
            """
            if douban_actors and (not updated_name
                                  or not updated_overview
                                  or not update_character):
                #  Matching chinese names from douban actors、 Roles and profiles
                for douban_actor in douban_actors:
                    if douban_actor.get("latin_name") == people.get("Name") \
                            or douban_actor.get("name") == people.get("Name"):
                        #  Name (of a thing)
                        if not updated_name:
                            logger.info(f"{people.get('Name')}  Get the chinese name from douban：{douban_actor.get('name')}")
                            personinfo["Name"] = douban_actor.get("name")
                            ret_people["Name"] = douban_actor.get("name")
                            updated_name = True
                        #  Descriptive
                        if not updated_overview:
                            if douban_actor.get("title"):
                                logger.info(f"{people.get('Name')}  Get the chinese description from douban：{douban_actor.get('title')}")
                                personinfo["Overview"] = douban_actor.get("title")
                                updated_overview = True
                        #  Role
                        if not update_character:
                            if douban_actor.get("character"):
                                # " Impersonate  James (name)· Bond (name) James Bond 007"
                                character = re.sub(r" Impersonate\s+", "",
                                                   douban_actor.get("character"))
                                character = re.sub(" Actor or actress", "",
                                                   character)
                                if character:
                                    logger.info(f"{people.get('Name')}  Getting to play a character from douban：{character}")
                                    ret_people["Role"] = character
                                    update_character = True
                        #  Photograph
                        if not profile_path:
                            avatar = douban_actor.get("avatar") or {}
                            if avatar.get("large"):
                                logger.info(f"{people.get('Name')}  Getting images from douban：{avatar.get('large')}")
                                profile_path = avatar.get("large")
                        break

            #  Update character pictures
            if profile_path:
                logger.info(f" Update a character {people.get('Name')}  Pictures：{profile_path}")
                self.set_item_image(server=server, itemid=people.get("Id"), imageurl=profile_path)

            #  Locked character information
            if updated_name:
                if "Name" not in personinfo["LockedFields"]:
                    personinfo["LockedFields"].append("Name")
            if updated_overview:
                if "Overview" not in personinfo["LockedFields"]:
                    personinfo["LockedFields"].append("Overview")

            #  Update character information
            if updated_name or updated_overview or update_character:
                logger.info(f" Update a character {people.get('Name')}  Such information：{personinfo}")
                ret = self.set_iteminfo(server=server, itemid=people.get("Id"), iteminfo=personinfo)
                if ret:
                    return ret_people
            else:
                logger.info(f" Character (in a play, novel etc) {people.get('Name')}  No chinese data found")
        except Exception as err:
            logger.error(f" Failed to update character information：{err}")
        return None

    def __get_douban_actors(self, mediainfo: MediaInfo, season: int = None) -> List[dict]:
        """
        Get douban cast information
        """
        #  Random hibernation1-5 Unit of angle or arc equivalent one sixtieth of a degree
        time.sleep(1 + int(time.time()) % 5)
        #  Match douban information
        doubaninfo = self.chain.match_doubaninfo(name=mediainfo.title,
                                                 mtype=mediainfo.type.value,
                                                 year=mediainfo.year,
                                                 season=season)
        #  Douban actor
        if doubaninfo:
            doubanitem = self.chain.douban_info(doubaninfo.get("id")) or {}
            return (doubanitem.get("actors") or []) + (doubanitem.get("directors") or [])
        else:
            logger.warn(f" No doujin information found：{mediainfo.title_year}")
        return []

    @staticmethod
    def get_iteminfo(server: str, itemid: str) -> dict:
        """
        Obtain media item details
        """

        def __get_emby_iteminfo() -> dict:
            """
            AttainmentEmby Media item details
            """
            try:
                url = f'[HOST]emby/Users/[USER]/Items/{itemid}?' \
                      f'Fields=ChannelMappingInfo&api_key=[APIKEY]'
                res = Emby().get_data(url=url)
                if res:
                    return res.json()
            except Exception as err:
                logger.error(f" GainEmby Media item details failed：{err}")
            return {}

        def __get_jellyfin_iteminfo() -> dict:
            """
            AttainmentJellyfin Media item details
            """
            try:
                url = f'[HOST]Users/[USER]/Items/{itemid}?Fields=ChannelMappingInfo&api_key=[APIKEY]'
                res = Jellyfin().get_data(url=url)
                if res:
                    result = res.json()
                    if result:
                        result['FileName'] = Path(result['Path']).name
                    return result
            except Exception as err:
                logger.error(f" GainJellyfin Media item details failed：{err}")
            return {}

        def __get_plex_iteminfo() -> dict:
            """
            AttainmentPlex Media item details
            """
            iteminfo = {}
            try:
                plexitem = Plex().get_plex().library.fetchItem(ekey=itemid)
                if 'movie' in plexitem.METADATA_TYPE:
                    iteminfo['Type'] = 'Movie'
                    iteminfo['IsFolder'] = False
                elif 'episode' in plexitem.METADATA_TYPE:
                    iteminfo['Type'] = 'Series'
                    iteminfo['IsFolder'] = False
                    if 'show' in plexitem.TYPE:
                        iteminfo['ChildCount'] = plexitem.childCount
                iteminfo['Name'] = plexitem.title
                iteminfo['Id'] = plexitem.key
                iteminfo['ProductionYear'] = plexitem.year
                iteminfo['ProviderIds'] = {}
                for guid in plexitem.guids:
                    idlist = str(guid.id).split(sep='://')
                    if len(idlist) < 2:
                        continue
                    iteminfo['ProviderIds'][idlist[0]] = idlist[1]
                for location in plexitem.locations:
                    iteminfo['Path'] = location
                    iteminfo['FileName'] = Path(location).name
                iteminfo['Overview'] = plexitem.summary
                iteminfo['CommunityRating'] = plexitem.audienceRating
                return iteminfo
            except Exception as err:
                logger.error(f" GainPlex Media item details failed：{err}")
            return {}

        if server == "emby":
            return __get_emby_iteminfo()
        elif server == "jellyfin":
            return __get_jellyfin_iteminfo()
        else:
            return __get_plex_iteminfo()

    @staticmethod
    def get_items(server: str, parentid: str, mtype: str = None) -> dict:
        """
        Get all submedia items of the media
        """
        pass

        def __get_emby_items() -> dict:
            """
            AttainmentEmby All sub-media items of the media
            """
            try:
                if parentid:
                    url = f'[HOST]emby/Users/[USER]/Items?ParentId={parentid}&api_key=[APIKEY]'
                else:
                    url = '[HOST]emby/Users/[USER]/Items?api_key=[APIKEY]'
                res = Emby().get_data(url=url)
                if res:
                    return res.json()
            except Exception as err:
                logger.error(f" GainEmby All submedia items of the media failed：{err}")
            return {}

        def __get_jellyfin_items() -> dict:
            """
            AttainmentJellyfin All sub-media items of the media
            """
            try:
                if parentid:
                    url = f'[HOST]Users/[USER]/Items?ParentId={parentid}&api_key=[APIKEY]'
                else:
                    url = '[HOST]Users/[USER]/Items?api_key=[APIKEY]'
                res = Jellyfin().get_data(url=url)
                if res:
                    return res.json()
            except Exception as err:
                logger.error(f" GainJellyfin All submedia items of the media failed：{err}")
            return {}

        def __get_plex_items(t: str) -> dict:
            """
            AttainmentPlex All sub-media items of the media
            """
            items = {}
            try:
                plex = Plex().get_plex()
                items['Items'] = []
                if parentid:
                    if mtype and 'Season' in t:
                        plexitem = plex.library.fetchItem(ekey=parentid)
                        items['Items'] = []
                        for season in plexitem.seasons():
                            item = {
                                'Name': season.title,
                                'Id': season.key,
                                'IndexNumber': season.seasonNumber,
                                'Overview': season.summary
                            }
                            items['Items'].append(item)
                    elif mtype and 'Episode' in t:
                        plexitem = plex.library.fetchItem(ekey=parentid)
                        items['Items'] = []
                        for episode in plexitem.episodes():
                            item = {
                                'Name': episode.title,
                                'Id': episode.key,
                                'IndexNumber': episode.episodeNumber,
                                'Overview': episode.summary,
                                'CommunityRating': episode.audienceRating
                            }
                            items['Items'].append(item)
                    else:
                        plexitems = plex.library.sectionByID(sectionID=parentid)
                        for plexitem in plexitems.all():
                            item = {}
                            if 'movie' in plexitem.METADATA_TYPE:
                                item['Type'] = 'Movie'
                                item['IsFolder'] = False
                            elif 'episode' in plexitem.METADATA_TYPE:
                                item['Type'] = 'Series'
                                item['IsFolder'] = False
                            item['Name'] = plexitem.title
                            item['Id'] = plexitem.key
                            items['Items'].append(item)
                else:
                    plexitems = plex.library.sections()
                    for plexitem in plexitems:
                        item = {}
                        if 'Directory' in plexitem.TAG:
                            item['Type'] = 'Folder'
                            item['IsFolder'] = True
                        elif 'movie' in plexitem.METADATA_TYPE:
                            item['Type'] = 'Movie'
                            item['IsFolder'] = False
                        elif 'episode' in plexitem.METADATA_TYPE:
                            item['Type'] = 'Series'
                            item['IsFolder'] = False
                        item['Name'] = plexitem.title
                        item['Id'] = plexitem.key
                        items['Items'].append(item)
                return items
            except Exception as err:
                logger.error(f" GainPlex All submedia items of the media failed：{err}")
            return {}

        if server == "emby":
            return __get_emby_items()
        elif server == "jellyfin":
            return __get_jellyfin_items()
        else:
            return __get_plex_items(mtype)

    @staticmethod
    def set_iteminfo(server: str, itemid: str, iteminfo: dict):
        """
        Update media item details
        """

        def __set_emby_iteminfo():
            """
            UpdateEmby Media item details
            """
            try:
                res = Emby().post_data(
                    url=f'[HOST]emby/Items/{itemid}?api_key=[APIKEY]&reqformat=json',
                    data=json.dumps(iteminfo),
                    headers={
                        "Content-Type": "application/json"
                    }
                )
                if res and res.status_code in [200, 204]:
                    return True
                else:
                    logger.error(f"UpdateEmby Media item details失败，错误码：{res.status_code}")
                    return False
            except Exception as err:
                logger.error(f"UpdateEmby Media item details失败：{err}")
            return False

        def __set_jellyfin_iteminfo():
            """
            UpdateJellyfin Media item details
            """
            try:
                res = Jellyfin().post_data(
                    url=f'[HOST]Items/{itemid}?api_key=[APIKEY]',
                    data=json.dumps(iteminfo),
                    headers={
                        "Content-Type": "application/json"
                    }
                )
                if res and res.status_code in [200, 204]:
                    return True
                else:
                    logger.error(f"UpdateJellyfin Media item details失败，错误码：{res.status_code}")
                    return False
            except Exception as err:
                logger.error(f"UpdateJellyfin Media item details失败：{err}")
            return False

        def __set_plex_iteminfo():
            """
            UpdatePlex Media item details
            """
            try:
                plexitem = Plex().get_plex().library.fetchItem(ekey=itemid)
                if 'CommunityRating' in iteminfo:
                    edits = {
                        'audienceRating.value': iteminfo['CommunityRating'],
                        'audienceRating.locked': 1
                    }
                    plexitem.edit(**edits)
                plexitem.editTitle(iteminfo['Name']).editSummary(iteminfo['Overview']).reload()
                return True
            except Exception as err:
                logger.error(f"UpdatePlex Media item details失败：{err}")
            return False

        if server == "emby":
            return __set_emby_iteminfo()
        elif server == "jellyfin":
            return __set_jellyfin_iteminfo()
        else:
            return __set_plex_iteminfo()

    @staticmethod
    @retry(RequestException, logger=logger)
    def set_item_image(server: str, itemid: str, imageurl: str):
        """
        Update media item images
        """

        def __download_image():
            """
            Download images
            """
            try:
                if "doubanio.com" in imageurl:
                    r = RequestUtils(headers={
                        'Referer': "https://movie.douban.com/"
                    }, ua=settings.USER_AGENT).get_res(url=imageurl, raise_exception=True)
                else:
                    r = RequestUtils().get_res(url=imageurl, raise_exception=True)
                if r:
                    return base64.b64encode(r.content).decode()
                else:
                    logger.info(f"{imageurl}  Image download failed， Please check network connectivity")
            except Exception as err:
                logger.error(f"Download images失败：{err}")
            return None

        def __set_emby_item_image(_base64: str):
            """
            UpdateEmby Pictures of media items
            """
            try:
                url = f'[HOST]emby/Items/{itemid}/Images/Primary?api_key=[APIKEY]'
                res = Emby().post_data(
                    url=url,
                    data=_base64,
                    headers={
                        "Content-Type": "image/png"
                    }
                )
                if res and res.status_code in [200, 204]:
                    return True
                else:
                    logger.error(f"UpdateEmby Pictures of media items失败，错误码：{res.status_code}")
                    return False
            except Exception as result:
                logger.error(f"UpdateEmby Pictures of media items失败：{result}")
            return False

        def __set_jellyfin_item_image():
            """
            UpdateJellyfin Pictures of media items
            # FIXME 改为预Download images
            """
            try:
                url = f'[HOST]Items/{itemid}/RemoteImages/Download?' \
                      f'Type=Primary&ImageUrl={imageurl}&ProviderName=TheMovieDb&api_key=[APIKEY]'
                res = Jellyfin().post_data(url=url)
                if res and res.status_code in [200, 204]:
                    return True
                else:
                    logger.error(f"UpdateJellyfin Pictures of media items失败，错误码：{res.status_code}")
                    return False
            except Exception as err:
                logger.error(f"UpdateJellyfin Pictures of media items失败：{err}")
            return False

        def __set_plex_item_image():
            """
            UpdatePlex Pictures of media items
            # FIXME 改为预Download images
            """
            try:
                plexitem = Plex().get_plex().library.fetchItem(ekey=itemid)
                plexitem.uploadPoster(url=imageurl)
                return True
            except Exception as err:
                logger.error(f"UpdatePlex Pictures of media items失败：{err}")
            return False

        if server == "emby":
            # Download images获取base64
            image_base64 = __download_image()
            if image_base64:
                return __set_emby_item_image(image_base64)
        elif server == "jellyfin":
            return __set_jellyfin_item_image()
        else:
            return __set_plex_item_image()
        return None

    @staticmethod
    def __get_chinese_name(personinfo: dict) -> str:
        """
        GainTMDB Chinese names in aliases
        """
        try:
            also_known_as = personinfo.get("also_known_as") or []
            if also_known_as:
                for name in also_known_as:
                    if name and StringUtils.is_chinese(name):
                        #  Utilizationcn2an Convert traditional chinese to simplified chinese
                        return zhconv.convert(name, "zh-hans")
        except Exception as err:
            logger.error(f" Failed to get character's chinese name：{err}")
        return ""

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
