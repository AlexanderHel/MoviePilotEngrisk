import json
import re
from pathlib import Path
from typing import List, Optional, Union, Dict, Generator, Tuple

from requests import Response

from app import schemas
from app.core.config import settings
from app.log import logger
from app.schemas.types import MediaType
from app.utils.http import RequestUtils
from app.utils.singleton import Singleton


class Emby(metaclass=Singleton):

    def __init__(self):
        self._host = settings.EMBY_HOST
        if self._host:
            if not self._host.endswith("/"):
                self._host += "/"
            if not self._host.startswith("http"):
                self._host = "http://" + self._host
        self._apikey = settings.EMBY_API_KEY
        self.user = self.get_user(settings.SUPERUSER)
        self.folders = self.get_emby_folders()

    def is_inactive(self) -> bool:
        """
        Determine if reconnection is required
        """
        if not self._host or not self._apikey:
            return False
        return True if not self.user else False

    def reconnect(self):
        """
        Reconnect
        """
        self.user = self.get_user()
        self.folders = self.get_emby_folders()

    def get_emby_folders(self) -> List[dict]:
        """
        GainEmby Media library path list
        """
        if not self._host or not self._apikey:
            return []
        req_url = "%semby/Library/SelectableMediaFolders?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json()
            else:
                logger.error(f"Library/SelectableMediaFolders  Return data not obtained")
                return []
        except Exception as e:
            logger.error(f" GroutLibrary/SelectableMediaFolders  Make a mistake：" + str(e))
            return []

    def __get_emby_librarys(self) -> List[dict]:
        """
        GainEmby Media library list
        """
        if not self._host or not self._apikey:
            return []
        req_url = f"{self._host}emby/Users/{self.user}/Views?api_key={self._apikey}"
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json().get("Items")
            else:
                logger.error(f"User/Views  Return data not obtained")
                return []
        except Exception as e:
            logger.error(f" GroutUser/Views  Make a mistake：" + str(e))
            return []

    def get_librarys(self) -> List[schemas.MediaServerLibrary]:
        """
        Get a list of all media libraries on the media server
        """
        if not self._host or not self._apikey:
            return []
        libraries = []
        for library in self.__get_emby_librarys() or []:
            match library.get("CollectionType"):
                case "movies":
                    library_type = MediaType.MOVIE.value
                case "tvshows":
                    library_type = MediaType.TV.value
                case _:
                    continue
            libraries.append(
                schemas.MediaServerLibrary(
                    server="emby",
                    id=library.get("Id"),
                    name=library.get("Name"),
                    path=library.get("Path"),
                    type=library_type
                )
            )
        return libraries

    def get_user(self, user_name: str = None) -> Optional[Union[str, int]]:
        """
        Getting the administrator user
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sUsers?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                users = res.json()
                #  First check to see if there is a match to the current user name for the
                if user_name:
                    for user in users:
                        if user.get("Name") == user_name:
                            return user.get("Id")
                #  Query manager
                for user in users:
                    if user.get("Policy", {}).get("IsAdministrator"):
                        return user.get("Id")
            else:
                logger.error(f"Users  Return data not obtained")
        except Exception as e:
            logger.error(f" GroutUsers Make a mistake：" + str(e))
        return None

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        User authentication
        :param username:  User id
        :param password:  Cryptographic
        :return:  Accreditationtoken
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%semby/Users/AuthenticateByName" % self._host
        try:
            res = RequestUtils(headers={
                'X-Emby-Authorization': f'MediaBrowser Client="MoviePilot", '
                                        f'Device="requests", '
                                        f'DeviceId="1", '
                                        f'Version="1.0.0", '
                                        f'Token="{self._apikey}"',
                'Content-Type': 'application/json',
                "Accept": "application/json"
            }).post_res(
                url=req_url,
                data=json.dumps({
                    "Username": username,
                    "Pw": password
                })
            )
            if res:
                auth_token = res.json().get("AccessToken")
                if auth_token:
                    logger.info(f" Subscribers {username} Emby Certification success")
                    return auth_token
            else:
                logger.error(f"Users/AuthenticateByName  Return data not obtained")
        except Exception as e:
            logger.error(f" GroutUsers/AuthenticateByName Make a mistake：" + str(e))
        return None

    def get_server_id(self) -> Optional[str]:
        """
        Getting server information
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sSystem/Info?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json().get("Id")
            else:
                logger.error(f"System/Info  Return data not obtained")
        except Exception as e:

            logger.error(f" GroutSystem/Info Make a mistake：" + str(e))
        return None

    def get_user_count(self) -> int:
        """
        Number of users acquired
        """
        if not self._host or not self._apikey:
            return 0
        req_url = "%semby/Users/Query?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json().get("TotalRecordCount")
            else:
                logger.error(f"Users/Query  Return data not obtained")
                return 0
        except Exception as e:
            logger.error(f" GroutUsers/Query Make a mistake：" + str(e))
            return 0

    def get_medias_count(self) -> schemas.Statistic:
        """
        Get the movie、 Dramas、 Number of anime and manga media
        :return: MovieCount SeriesCount SongCount
        """
        if not self._host or not self._apikey:
            return schemas.Statistic()
        req_url = "%semby/Items/Counts?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                result = res.json()
                return schemas.Statistic(
                    movie_count=result.get("MovieCount") or 0,
                    tv_count=result.get("SeriesCount") or 0,
                    episode_count=result.get("EpisodeCount") or 0
                )
            else:
                logger.error(f"Items/Counts  Return data not obtained")
                return schemas.Statistic()
        except Exception as e:
            logger.error(f" GroutItems/Counts Make a mistake：" + str(e))
            return schemas.Statistic()

    def __get_emby_series_id_by_name(self, name: str, year: str) -> Optional[str]:
        """
        Search by nameEmby Mid-episodeSeriesId
        :param name:  Caption
        :param year:  Particular year
        :return: None  Not connect，"" Indicates not found， Find returnsID
        """
        if not self._host or not self._apikey:
            return None
        req_url = ("%semby/Items?"
                   "IncludeItemTypes=Series"
                   "&Fields=ProductionYear"
                   "&StartIndex=0"
                   "&Recursive=true"
                   "&SearchTerm=%s"
                   "&Limit=10"
                   "&IncludeSearchTypes=false"
                   "&api_key=%s") % (
            self._host, name, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                res_items = res.json().get("Items")
                if res_items:
                    for res_item in res_items:
                        if res_item.get('Name') == name and (
                                not year or str(res_item.get('ProductionYear')) == str(year)):
                            return res_item.get('Id')
        except Exception as e:
            logger.error(f" GroutItems Make a mistake：" + str(e))
            return None
        return ""

    def get_movies(self,
                   title: str,
                   year: str = None,
                   tmdb_id: int = None) -> Optional[List[schemas.MediaServerItem]]:
        """
        By title and year， Check if the movie is onEmby Exist in， Returns the list if it exists
        :param title:  Caption
        :param year:  Particular year，可以为空，为空时不按年份过滤
        :param tmdb_id: TMDB ID
        :return:  Suck (keep in your mouth without chewing)title、year Dictionary list of attributes
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%semby/Items?IncludeItemTypes=Movie&Fields=ProductionYear&StartIndex=0" \
                  "&Recursive=true&SearchTerm=%s&Limit=10&IncludeSearchTypes=false&api_key=%s" % (
                      self._host, title, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                res_items = res.json().get("Items")
                if res_items:
                    ret_movies = []
                    for res_item in res_items:
                        item_tmdbid = res_item.get("ProviderIds", {}).get("Tmdb")
                        mediaserver_item = schemas.MediaServerItem(
                            server="emby",
                            library=res_item.get("ParentId"),
                            item_id=res_item.get("Id"),
                            item_type=res_item.get("Type"),
                            title=res_item.get("Name"),
                            original_title=res_item.get("OriginalTitle"),
                            year=res_item.get("ProductionYear"),
                            tmdbid=int(item_tmdbid) if item_tmdbid else None,
                            imdbid=res_item.get("ProviderIds", {}).get("Imdb"),
                            tvdbid=res_item.get("ProviderIds", {}).get("Tvdb"),
                            path=res_item.get("Path")
                        )
                        if tmdb_id and item_tmdbid:
                            if str(item_tmdbid) != str(tmdb_id):
                                continue
                            else:
                                ret_movies.append(mediaserver_item)
                                continue
                        if (mediaserver_item.title == title
                                and (not year or str(mediaserver_item.year) == str(year))):
                            ret_movies.append(mediaserver_item)
                    return ret_movies
        except Exception as e:
            logger.error(f" GroutItems Make a mistake：" + str(e))
            return None
        return []

    def get_tv_episodes(self,
                        item_id: str = None,
                        title: str = None,
                        year: str = None,
                        tmdb_id: int = None,
                        season: int = None
                        ) -> Tuple[Optional[str], Optional[Dict[int, List[Dict[int, list]]]]]:
        """
        By title and year and season， Come (or go) backEmby List of episodes in
        :param item_id: Emby Hit the nail on the headID
        :param title:  Caption
        :param year:  Particular year
        :param tmdb_id: TMDBID
        :param season:  Classifier for seasonal crop yield or seasons of a tv series
        :return:  Number of episodes available for each season
        """
        if not self._host or not self._apikey:
            return None, None
        #  Dramas
        if not item_id:
            item_id = self.__get_emby_series_id_by_name(title, year)
            if item_id is None:
                return None, None
            if not item_id:
                return None, {}
        #  Validate (a theory)tmdbid Whether or not the same
        item_info = self.get_iteminfo(item_id)
        if item_info:
            if tmdb_id and item_info.tmdbid:
                if str(tmdb_id) != str(item_info.tmdbid):
                    return None, {}
        #  Information from chatset
        if not season:
            season = ""
        try:
            req_url = "%semby/Shows/%s/Episodes?Season=%s&IsMissing=false&api_key=%s" % (
                self._host, item_id, season, self._apikey)
            res_json = RequestUtils().get_res(req_url)
            if res_json:
                tv_item = res_json.json()
                res_items = tv_item.get("Items")
                season_episodes = {}
                for res_item in res_items:
                    season_index = res_item.get("ParentIndexNumber")
                    if not season_index:
                        continue
                    if season and season != season_index:
                        continue
                    episode_index = res_item.get("IndexNumber")
                    if not episode_index:
                        continue
                    if season_index not in season_episodes:
                        season_episodes[season_index] = []
                    season_episodes[season_index].append(episode_index)
                #  Come (or go) back
                return tv_item.get("Id"), season_episodes
        except Exception as e:
            logger.error(f" GroutShows/Id/Episodes Make a mistake：" + str(e))
            return None, None
        return None, {}

    def get_remote_image_by_id(self, item_id: str, image_type: str) -> Optional[str]:
        """
        According toItemId Through (a gap)Emby Consult (a document etc)TMDB The address of the picture
        :param item_id:  ExistEmby Hit the nail on the headID
        :param image_type:  Classes of pictures to get the ground，poster Orbackdrop Et al. (and other authors)
        :return:  The image corresponds to an image in theTMDB Hit the nail on the headURL
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%semby/Items/%s/RemoteImages?api_key=%s" % (self._host, item_id, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                images = res.json().get("Images")
                for image in images:
                    if image.get("ProviderName") == "TheMovieDb" and image.get("Type") == image_type:
                        return image.get("Url")
            else:
                logger.error(f"Items/RemoteImages  Return data not obtained")
                return None
        except Exception as e:
            logger.error(f" GroutItems/Id/RemoteImages Make a mistake：" + str(e))
            return None
        return None

    def __refresh_emby_library_by_id(self, item_id: str) -> bool:
        """
        NotificationsEmby Refreshing a project's media library
        """
        if not self._host or not self._apikey:
            return False
        req_url = "%semby/Items/%s/Refresh?Recursive=true&api_key=%s" % (self._host, item_id, self._apikey)
        try:
            res = RequestUtils().post_res(req_url)
            if res:
                return True
            else:
                logger.info(f" Refresh media library objects {item_id}  Fail (e.g. experiments)， ConnectionlessEmby！")
        except Exception as e:
            logger.error(f" GroutItems/Id/Refresh Make a mistake：" + str(e))
            return False
        return False

    def refresh_root_library(self) -> bool:
        """
        NotificationsEmby Refresh the entire media library
        """
        if not self._host or not self._apikey:
            return False
        req_url = "%semby/Library/Refresh?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().post_res(req_url)
            if res:
                return True
            else:
                logger.info(f" Failed to refresh media library， ConnectionlessEmby！")
        except Exception as e:
            logger.error(f" GroutLibrary/Refresh Make a mistake：" + str(e))
            return False
        return False

    def refresh_library_by_items(self, items: List[schemas.RefreshMediaItem]) -> bool:
        """
        By type、 Name (of a thing)、 Year to refresh media library
        :param items:  List of recognized media messages that need to be refreshed in the media library
        """
        if not items:
            return False
        #  Gather information about the media library to be refreshed
        logger.info(f" Start refreshingEmby Media library...")
        library_ids = []
        for item in items:
            library_id = self.__get_emby_library_id_by_item(item)
            if library_id and library_id not in library_ids:
                library_ids.append(library_id)
        #  Start refreshing the media library
        if "/" in library_ids:
            return self.refresh_root_library()
        for library_id in library_ids:
            if library_id != "/":
                return self.__refresh_emby_library_by_id(library_id)
        logger.info(f"Emby Media library refresh complete")

    def __get_emby_library_id_by_item(self, item: schemas.RefreshMediaItem) -> Optional[str]:
        """
        Search in which media library according to media information， Returns the position of theID
        :param item: {title, year, type, category, target_path}
        """
        if not item.title or not item.year or not item.type:
            return None
        if item.type != MediaType.MOVIE.value:
            item_id = self.__get_emby_series_id_by_name(item.title, item.year)
            if item_id:
                #  Presence tv series， Then just refresh the tv show.
                return item_id
        else:
            if self.get_movies(item.title, item.year):
                #  Pre-existing， No need to refresh.
                return None
        #  Find media libraries that need to be refreshedID
        item_path = Path(item.target_path)
        #  Matching subdirectories
        for folder in self.folders:
            for subfolder in folder.get("SubFolders"):
                try:
                    #  Matching subdirectories
                    subfolder_path = Path(subfolder.get("Path"))
                    if item_path.is_relative_to(subfolder_path):
                        return folder.get("Id")
                except Exception as err:
                    print(str(err))
        #  If you can't find， Hits as long as there is a category name in the path
        for folder in self.folders:
            for subfolder in folder.get("SubFolders"):
                if subfolder.get("Path") and re.search(r"[/\\]%s" % item.category,
                                                       subfolder.get("Path")):
                    return folder.get("Id")
        #  Refresh the root directory
        return "/"

    def get_iteminfo(self, itemid: str) -> Optional[schemas.MediaServerItem]:
        """
        Get individual program details
        """
        if not itemid:
            return None
        if not self._host or not self._apikey:
            return None
        req_url = "%semby/Users/%s/Items/%s?api_key=%s" % (self._host, self.user, itemid, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res and res.status_code == 200:
                item = res.json()
                tmdbid = item.get("ProviderIds", {}).get("Tmdb")
                return schemas.MediaServerItem(
                    server="emby",
                    library=item.get("ParentId"),
                    item_id=item.get("Id"),
                    item_type=item.get("Type"),
                    title=item.get("Name"),
                    original_title=item.get("OriginalTitle"),
                    year=item.get("ProductionYear"),
                    tmdbid=int(tmdbid) if tmdbid else None,
                    imdbid=item.get("ProviderIds", {}).get("Imdb"),
                    tvdbid=item.get("ProviderIds", {}).get("Tvdb"),
                    path=item.get("Path")
                )
        except Exception as e:
            logger.error(f" GroutItems/Id Make a mistake：" + str(e))
        return None

    def get_items(self, parent: str) -> Generator:
        """
        Get a list of all media libraries on the media server
        """
        if not parent:
            yield None
        if not self._host or not self._apikey:
            yield None
        req_url = "%semby/Users/%s/Items?ParentId=%s&api_key=%s" % (self._host, self.user, parent, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res and res.status_code == 200:
                results = res.json().get("Items") or []
                for result in results:
                    if not result:
                        continue
                    if result.get("Type") in ["Movie", "Series"]:
                        yield self.get_iteminfo(result.get("Id"))
                    elif "Folder" in result.get("Type"):
                        for item in self.get_items(parent=result.get('Id')):
                            yield item
        except Exception as e:
            logger.error(f" GroutUsers/Items Make a mistake：" + str(e))
        yield None

    def get_webhook_message(self, form: any, args: dict) -> Optional[schemas.WebhookEventInfo]:
        """
        AnalyzeEmby Webhook Telegram
        Cinematic：
        {
          "Title": "admin  Exist Microsoft Edge Windows  Stop playback on  Spiderman： Criss-cross the universe",
          "Date": "2023-08-19T00:49:07.8523469Z",
          "Event": "playback.stop",
          "User": {
            "Name": "admin",
            "Id": "e6a9dd89fd954d689870e7e0e3e72947"
          },
          "Item": {
            "Name": " Spiderman： Criss-cross the universe",
            "OriginalTitle": "Spider-Man: Across the Spider-Verse",
            "ServerId": "f40a5bd0c6b64051bdbed00580fa1118",
            "Id": "240270",
            "DateCreated": "2023-06-21T21:01:27.0000000Z",
            "Container": "mp4",
            "SortName": " Spiderman： Criss-cross the universe",
            "PremiereDate": "2023-05-30T16:00:00.0000000Z",
            "ExternalUrls": [
              {
                "Name": "IMDb",
                "Url": "https://www.imdb.com/title/tt9362722"
              },
              {
                "Name": "TheMovieDb",
                "Url": "https://www.themoviedb.org/movie/569094"
              },
              {
                "Name": "Trakt",
                "Url": "https://trakt.tv/search/tmdb/569094?id_type=movie"
              }
            ],
            "Path": "\\\\10.10.10.10\\Video\\ Cinematic\\ Animated movie\\ Spiderman： Criss-cross the universe (2023)\\ Spiderman： Criss-cross the universe (2023).mp4",
            "OfficialRating": "PG",
            "Overview": " It tells the story of the new generation of spider-man, miles（ Shameik (name)· Moore or moor (name) Shameik Moore  Dubbing (filmmaking)） Together with spider gwen.（ Hayley· Stanfield (name) Hailee Steinfeld  Dubbing (filmmaking)）， The story of a journey through the multiverse on a larger adventure。 Facing the fate of every spider-man who has lost a loved one.， Miles vows to break fate's spell， Find your own path to heroism。 And that decision and spider-man2099（ Oscar· Isaac Oscar Is aac  Dubbing (filmmaking)） The spider alliance, which he leads, is in great conflict.， A great spider-man civil war of one against 100 is about to begin.！",
            "Taglines": [],
            "Genres": [
              " Movements",
              " Take chances",
              " Anime",
              " Sci-fi"
            ],
            "CommunityRating": 8.7,
            "RunTimeTicks": 80439590000,
            "Size": 3170164641,
            "FileName": " Spiderman： Criss-cross the universe (2023).mp4",
            "Bitrate": 3152840,
            "PlayAccess": "Full",
            "ProductionYear": 2023,
            "RemoteTrailers": [
              {
                "Url": "https://www.youtube.com/watch?v=BbXJ3_AQE_o"
              },
              {
                "Url": "https://www.youtube.com/watch?v=cqGjhVJWtEg"
              },
              {
                "Url": "https://www.youtube.com/watch?v=shW9i6k8cB0"
              },
              {
                "Url": "https://www.youtube.com/watch?v=Etv-L2JKCWk"
              },
              {
                "Url": "https://www.youtube.com/watch?v=yFrxzaBLDQM"
              }
            ],
            "ProviderIds": {
              "Tmdb": "569094",
              "Imdb": "tt9362722"
            },
            "IsFolder": false,
            "ParentId": "240253",
            "Type": "Movie",
            "Studios": [
              {
                "Name": "Columbia Pictures",
                "Id": 1252
              },
              {
                "Name": "Sony Pictures Animation",
                "Id": 1814
              },
              {
                "Name": "Lord Miller",
                "Id": 240307
              },
              {
                "Name": "Pascal Pictures",
                "Id": 60101
              },
              {
                "Name": "Arad Productions",
                "Id": 67372
              }
            ],
            "GenreItems": [
              {
                "Name": " Movements",
                "Id": 767
              },
              {
                "Name": " Take chances",
                "Id": 818
              },
              {
                "Name": " Anime",
                "Id": 1382
              },
              {
                "Name": " Sci-fi",
                "Id": 709
              }
            ],
            "TagItems": [],
            "PrimaryImageAspectRatio": 0.7012622720897616,
            "ImageTags": {
              "Primary": "c080830ff3c964a775dd0b011b675a29",
              "Art": "a418b990ca0df95838884b5951883ad5",
              "Logo": "1782310274c108e85d02d2b0b1c7249c",
              "Thumb": "29d499a96b7da07cd1cf37edb58507a8",
              "Banner": "bec236365d57f7f646d8fda16fce2ecb",
              "Disc": "3e32d87be8655f52bcf43bd34ee94c2b"
            },
            "BackdropImageTags": [
              "13acab1246c95a6fbdee22cf65edf3f0"
            ],
            "MediaType": "Video",
            "Width": 1920,
            "Height": 820
          },
          "Server": {
            "Name": "PN41",
            "Id": "f40a5bd0c6b64051bdbed00580fa1118",
            "Version": "4.7.13.0"
          },
          "Session": {
            "RemoteEndPoint": "10.10.10.253",
            "Client": "Emby Web",
            "DeviceName": "Microsoft Edge Windows",
            "DeviceId": "30239450-1748-4855-9799-de3544fc2744",
            "ApplicationVersion": "4.7.13.0",
            "Id": "c336b028b893558b333d1a49238b7db1"
          },
          "PlaybackInfo": {
            "PlayedToCompletion": false,
            "PositionTicks": 17431791950,
            "PlaylistIndex": 0,
            "PlaylistLength": 1
          }
        }

        Dramas：
        {
          "Title": "admin  Exist Microsoft Edge Windows  Start playing on  Lit. ferry across the long wind - S1, Ep11 -  (prefix indicating ordinal number, e.g. first, number two etc) 11  Classifier for sections of a tv series e.g. episode",
          "Date": "2023-08-19T00:52:20.5200050Z",
          "Event": "playback.start",
          "User": {
            "Name": "admin",
            "Id": "e6a9dd89fd954d689870e7e0e3e72947"
          },
          "Item": {
            "Name": " (prefix indicating ordinal number, e.g. first, number two etc) 11  Classifier for sections of a tv series e.g. episode",
            "ServerId": "f40a5bd0c6b64051bdbed00580fa1118",
            "Id": "240252",
            "DateCreated": "2023-06-21T10:51:06.0000000Z",
            "Container": "mp4",
            "SortName": " (prefix indicating ordinal number, e.g. first, number two etc) 11  Classifier for sections of a tv series e.g. episode",
            "PremiereDate": "2023-06-20T16:00:00.0000000Z",
            "ExternalUrls": [
              {
                "Name": "Trakt",
                "Url": "https://trakt.tv/search/tmdb/4533239?id_type=episode"
              }
            ],
            "Path": "\\\\10.10.10.10\\Video\\ Dramas\\ Nationalized drama\\ Lit. ferry across the long wind (2023)\\Season 1\\ Lit. ferry across the long wind - S01E11 -  (prefix indicating ordinal number, e.g. first, number two etc) 11  Classifier for sections of a tv series e.g. episode.mp4",
            "Taglines": [],
            "Genres": [],
            "RunTimeTicks": 28021450000,
            "Size": 707122056,
            "FileName": " Lit. ferry across the long wind - S01E11 -  (prefix indicating ordinal number, e.g. first, number two etc) 11  Classifier for sections of a tv series e.g. episode.mp4",
            "Bitrate": 2018802,
            "PlayAccess": "Full",
            "ProductionYear": 2023,
            "IndexNumber": 11,
            "ParentIndexNumber": 1,
            "RemoteTrailers": [],
            "ProviderIds": {
              "Tmdb": "4533239"
            },
            "IsFolder": false,
            "ParentId": "240203",
            "Type": "Episode",
            "Studios": [],
            "GenreItems": [],
            "TagItems": [],
            "ParentLogoItemId": "240202",
            "ParentBackdropItemId": "240202",
            "ParentBackdropImageTags": [
              "7dd568c67721c1f184b281001ced2f8e"
            ],
            "SeriesName": " Lit. ferry across the long wind",
            "SeriesId": "240202",
            "SeasonId": "240203",
            "PrimaryImageAspectRatio": 2.4,
            "SeriesPrimaryImageTag": "e91c822173e9bcbf7a0efa7d1c16f6bd",
            "SeasonName": " Classifier for seasonal crop yield or seasons of a tv series 1",
            "ImageTags": {
              "Primary": "d6bf1d76150cd86fdff746e4353569ee"
            },
            "BackdropImageTags": [],
            "ParentLogoImageTag": "51cf6b2661c3c9cef3796abafd6a1694",
            "MediaType": "Video",
            "Width": 1920,
            "Height": 800
          },
          "Server": {
            "Name": "PN41",
            "Id": "f40a5bd0c6b64051bdbed00580fa1118",
            "Version": "4.7.13.0"
          },
          "Session": {
            "RemoteEndPoint": "10.10.10.253",
            "Client": "Emby Web",
            "DeviceName": "Microsoft Edge Windows",
            "DeviceId": "30239450-1748-4855-9799-de3544fc2744",
            "ApplicationVersion": "4.7.13.0",
            "Id": "c336b028b893558b333d1a49238b7db1"
          },
          "PlaybackInfo": {
            "PositionTicks": 14256663550,
            "PlaylistIndex": 10,
            "PlaylistLength": 40
          }
        }
        """
        if not form and not args:
            return None
        try:
            if form and form.get("data"):
                result = form.get("data")
            else:
                result = json.dumps(dict(args))
            message = json.loads(result)
        except Exception as e:
            logger.debug(f" Analyzeemby webhook Error in telegram：" + str(e))
            return None
        eventType = message.get('Event')
        if not eventType:
            return None
        logger.info(f" Receiveemby webhook：{message}")
        eventItem = schemas.WebhookEventInfo(event=eventType, channel="emby")
        if message.get('Item'):
            if message.get('Item', {}).get('Type') == 'Episode':
                eventItem.item_type = "TV"
                if message.get('Item', {}).get('SeriesName') \
                        and message.get('Item', {}).get('ParentIndexNumber') \
                        and message.get('Item', {}).get('IndexNumber'):
                    eventItem.item_name = "%s %s%s %s" % (
                        message.get('Item', {}).get('SeriesName'),
                        "S" + str(message.get('Item', {}).get('ParentIndexNumber')),
                        "E" + str(message.get('Item', {}).get('IndexNumber')),
                        message.get('Item', {}).get('Name'))
                else:
                    eventItem.item_name = message.get('Item', {}).get('Name')
                eventItem.item_id = message.get('Item', {}).get('SeriesId')
                eventItem.season_id = message.get('Item', {}).get('ParentIndexNumber')
                eventItem.episode_id = message.get('Item', {}).get('IndexNumber')
            elif message.get('Item', {}).get('Type') == 'Audio':
                eventItem.item_type = "AUD"
                album = message.get('Item', {}).get('Album')
                file_name = message.get('Item', {}).get('FileName')
                eventItem.item_name = album
                eventItem.overview = file_name
                eventItem.item_id = message.get('Item', {}).get('AlbumId')
            else:
                eventItem.item_type = "MOV"
                eventItem.item_name = "%s %s" % (
                    message.get('Item', {}).get('Name'), "(" + str(message.get('Item', {}).get('ProductionYear')) + ")")
                eventItem.item_id = message.get('Item', {}).get('Id')

            eventItem.item_path = message.get('Item', {}).get('Path')
            eventItem.tmdb_id = message.get('Item', {}).get('ProviderIds', {}).get('Tmdb')
            if message.get('Item', {}).get('Overview') and len(message.get('Item', {}).get('Overview')) > 100:
                eventItem.overview = str(message.get('Item', {}).get('Overview'))[:100] + "..."
            else:
                eventItem.overview = message.get('Item', {}).get('Overview')
            eventItem.percentage = message.get('TranscodingInfo', {}).get('CompletionPercentage')
            if not eventItem.percentage:
                if message.get('PlaybackInfo', {}).get('PositionTicks'):
                    eventItem.percentage = message.get('PlaybackInfo', {}).get('PositionTicks') / \
                                           message.get('Item', {}).get('RunTimeTicks') * 100
        if message.get('Session'):
            eventItem.ip = message.get('Session').get('RemoteEndPoint')
            eventItem.device_name = message.get('Session').get('DeviceName')
            eventItem.client = message.get('Session').get('Client')
        if message.get("User"):
            eventItem.user_name = message.get("User").get('Name')
        if message.get("item_isvirtual"):
            eventItem.item_isvirtual = message.get("item_isvirtual")
            eventItem.item_type = message.get("item_type")
            eventItem.item_name = message.get("item_name")
            eventItem.item_path = message.get("item_path")
            eventItem.tmdb_id = message.get("tmdb_id")
            eventItem.season_id = message.get("season_id")
            eventItem.episode_id = message.get("episode_id")

        #  Get message image
        if eventItem.item_id:
            #  Based on the returneditem_id Go call the media server to get the
            eventItem.image_url = self.get_remote_image_by_id(item_id=eventItem.item_id,
                                                              image_type="Backdrop")

        return eventItem

    def get_data(self, url: str) -> Optional[Response]:
        """
        CustomizableURL Getting data from the media server， Included among these[HOST]、[APIKEY]、[USER] Will be replaced with the actual value
        :param url:  Request address
        """
        if not self._host or not self._apikey:
            return None
        url = url.replace("[HOST]", self._host) \
            .replace("[APIKEY]", self._apikey) \
            .replace("[USER]", self.user)
        try:
            return RequestUtils(content_type="application/json").get_res(url=url)
        except Exception as e:
            logger.error(f" GroutEmby Make a mistake：" + str(e))
            return None

    def post_data(self, url: str, data: str = None, headers: dict = None) -> Optional[Response]:
        """
        CustomizableURL Getting data from the media server， Included among these[HOST]、[APIKEY]、[USER] Will be replaced with the actual value
        :param url:  Request address
        :param data:  Request data
        :param headers:  Request header
        """
        if not self._host or not self._apikey:
            return None
        url = url.replace("[HOST]", self._host) \
            .replace("[APIKEY]", self._apikey) \
            .replace("[USER]", self.user)
        try:
            return RequestUtils(
                headers=headers,
            ).post_res(url=url, data=data)
        except Exception as e:
            logger.error(f" GroutEmby Make a mistake：" + str(e))
            return None
