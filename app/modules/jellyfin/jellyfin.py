import json
from typing import List, Union, Optional, Dict, Generator, Tuple

from requests import Response

from app import schemas
from app.core.config import settings
from app.log import logger
from app.schemas import MediaType
from app.utils.http import RequestUtils
from app.utils.singleton import Singleton


class Jellyfin(metaclass=Singleton):

    def __init__(self):
        self._host = settings.JELLYFIN_HOST
        if self._host:
            if not self._host.endswith("/"):
                self._host += "/"
            if not self._host.startswith("http"):
                self._host = "http://" + self._host
        self._apikey = settings.JELLYFIN_API_KEY
        self.user = self.get_user()
        self.serverid = self.get_server_id()

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
        self.serverid = self.get_server_id()

    def __get_jellyfin_librarys(self) -> List[dict]:
        """
        GainJellyfin Information on the media library
        """
        if not self._host or not self._apikey:
            return []
        req_url = f"{self._host}Users/{self.user}/Views?api_key={self._apikey}"
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json().get("Items")
            else:
                logger.error(f"Users/Views  Return data not obtained")
                return []
        except Exception as e:
            logger.error(f" GroutUsers/Views  Make a mistake：" + str(e))
            return []

    def get_librarys(self):
        """
        Get a list of all media libraries on the media server
        """
        if not self._host or not self._apikey:
            return []
        libraries = []
        for library in self.__get_jellyfin_librarys() or []:
            match library.get("CollectionType"):
                case "movies":
                    library_type = MediaType.MOVIE.value
                case "tvshows":
                    library_type = MediaType.TV.value
                case _:
                    continue
            libraries.append(
                schemas.MediaServerLibrary(
                    server="jellyfin",
                    id=library.get("Id"),
                    name=library.get("Name"),
                    path=library.get("Path"),
                    type=library_type
                ))
        return libraries

    def get_user_count(self) -> int:
        """
        Number of users acquired
        """
        if not self._host or not self._apikey:
            return 0
        req_url = "%sUsers?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return len(res.json())
            else:
                logger.error(f"Users  Return data not obtained")
                return 0
        except Exception as e:
            logger.error(f" GroutUsers Make a mistake：" + str(e))
            return 0

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
        :return:  Authentication success returnstoken， Otherwise, returnNone
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sUsers/authenticatebyname" % self._host
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
                    logger.info(f" Subscribers {username} Jellyfin Certification success")
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

    def get_medias_count(self) -> schemas.Statistic:
        """
        Get the movie、 Dramas、 Number of anime and manga media
        :return: MovieCount SeriesCount SongCount
        """
        if not self._host or not self._apikey:
            return schemas.Statistic()
        req_url = "%sItems/Counts?api_key=%s" % (self._host, self._apikey)
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

    def __get_jellyfin_series_id_by_name(self, name: str, year: str) -> Optional[str]:
        """
        Search by nameJellyfin Mid-episodeSeriesId
        """
        if not self._host or not self._apikey or not self.user:
            return None
        req_url = ("%sUsers/%s/Items?"
                   "api_key=%s&searchTerm=%s&IncludeItemTypes=Series&Limit=10&Recursive=true") % (
            self._host, self.user, self._apikey, name)
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
        By title and year， Check if the movie is onJellyfin Exist in， Returns the list if it exists
        :param title:  Caption
        :param year:  Particular year， No filtering if empty
        :param tmdb_id: TMDB ID
        :return:  Suck (keep in your mouth without chewing)title、year Dictionary list of attributes
        """
        if not self._host or not self._apikey or not self.user:
            return None
        req_url = ("%sUsers/%s/Items?"
                   "api_key=%s&searchTerm=%s&IncludeItemTypes=Movie&Limit=10&Recursive=true") % (
            self._host, self.user, self._apikey, title)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                res_items = res.json().get("Items")
                if res_items:
                    ret_movies = []
                    for item in res_items:
                        item_tmdbid = item.get("ProviderIds", {}).get("Tmdb")
                        mediaserver_item = schemas.MediaServerItem(
                            server="jellyfin",
                            library=item.get("ParentId"),
                            item_id=item.get("Id"),
                            item_type=item.get("Type"),
                            title=item.get("Name"),
                            original_title=item.get("OriginalTitle"),
                            year=item.get("ProductionYear"),
                            tmdbid=int(item_tmdbid) if item_tmdbid else None,
                            imdbid=item.get("ProviderIds", {}).get("Imdb"),
                            tvdbid=item.get("ProviderIds", {}).get("Tvdb"),
                            path=item.get("Path")
                        )
                        if tmdb_id and item_tmdbid:
                            if str(item_tmdbid) != str(tmdb_id):
                                continue
                            else:
                                ret_movies.append(mediaserver_item)
                                continue
                        if mediaserver_item.title == title and (
                                not year or str(mediaserver_item.year) == str(year)):
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
                        season: int = None) -> Tuple[Optional[str], Optional[Dict[int, list]]]:
        """
        By title and year and season， Come (or go) backJellyfin List of episodes in
        :param item_id: Jellyfin Hit the nail on the headId
        :param title:  Caption
        :param year:  Particular year
        :param tmdb_id: TMDBID
        :param season:  Classifier for seasonal crop yield or seasons of a tv series
        :return:  List of set numbers
        """
        if not self._host or not self._apikey or not self.user:
            return None, None
        #  Surname zhaTVID
        if not item_id:
            item_id = self.__get_jellyfin_series_id_by_name(title, year)
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
        if not season:
            season = ""
        try:
            req_url = "%sShows/%s/Episodes?season=%s&&userId=%s&isMissing=false&api_key=%s" % (
                self._host, item_id, season, self.user, self._apikey)
            res_json = RequestUtils().get_res(req_url)
            if res_json:
                tv_info = res_json.json()
                res_items = tv_info.get("Items")
                #  Returned season set information
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
                    if not season_episodes.get(season_index):
                        season_episodes[season_index] = []
                    season_episodes[season_index].append(episode_index)
                return tv_info.get('Id'), season_episodes
        except Exception as e:
            logger.error(f" GroutShows/Id/Episodes Make a mistake：" + str(e))
            return None, None
        return None, {}

    def get_remote_image_by_id(self, item_id: str, image_type: str) -> Optional[str]:
        """
        According toItemId Through (a gap)Jellyfin Consult (a document etc)TMDB Image address
        :param item_id:  ExistEmby Hit the nail on the headID
        :param image_type:  Classes of pictures to get the ground，poster Orbackdrop Et al. (and other authors)
        :return:  The image corresponds to an image in theTMDB Hit the nail on the headURL
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sItems/%s/RemoteImages?api_key=%s" % (self._host, item_id, self._apikey)
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

    def refresh_root_library(self) -> bool:
        """
        NotificationsJellyfin Refresh the entire media library
        """
        if not self._host or not self._apikey:
            return False
        req_url = "%sLibrary/Refresh?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().post_res(req_url)
            if res:
                return True
            else:
                logger.info(f" Failed to refresh media library， ConnectionlessJellyfin！")
        except Exception as e:
            logger.error(f" GroutLibrary/Refresh Make a mistake：" + str(e))
            return False

    def get_webhook_message(self, body: any) -> Optional[schemas.WebhookEventInfo]:
        """
        AnalyzeJellyfin Telegram
        {
          "ServerId": "d79d3a6261614419a114595a585xxxxx",
          "ServerName": "nyanmisaka-jellyfin1",
          "ServerVersion": "10.8.10",
          "ServerUrl": "http://xxxxxxxx:8098",
          "NotificationType": "PlaybackStart",
          "Timestamp": "2023-09-10T08:35:25.3996506+00:00",
          "UtcTimestamp": "2023-09-10T08:35:25.3996527Z",
          "Name": " Mucho scorch leaves by running away from the wedding",
          "Overview": " Mucho pretends to be reading.， She's afraid the first mistress will say she's not doing her job.。",
          "Tagline": "",
          "ItemId": "4b92551344f53b560fb55cd6700xxxxx",
          "ItemType": "Episode",
          "RunTimeTicks": 27074985984,
          "RunTime": "00:45:07",
          "Year": 2023,
          "SeriesName": " Scorching wind flow (idiom); whirlwind of activity",
          "SeasonNumber": 1,
          "SeasonNumber00": "01",
          "SeasonNumber000": "001",
          "EpisodeNumber": 1,
          "EpisodeNumber00": "01",
          "EpisodeNumber000": "001",
          "Provider_tmdb": "229210",
          "Video_0_Title": "4K HEVC SDR",
          "Video_0_Type": "Video",
          "Video_0_Codec": "hevc",
          "Video_0_Profile": "Main",
          "Video_0_Level": 150,
          "Video_0_Height": 2160,
          "Video_0_Width": 3840,
          "Video_0_AspectRatio": "16:9",
          "Video_0_Interlaced": false,
          "Video_0_FrameRate": 25,
          "Video_0_VideoRange": "SDR",
          "Video_0_ColorSpace": "bt709",
          "Video_0_ColorTransfer": "bt709",
          "Video_0_ColorPrimaries": "bt709",
          "Video_0_PixelFormat": "yuv420p",
          "Video_0_RefFrames": 1,
          "Audio_0_Title": "AAC - Stereo - Default",
          "Audio_0_Type": "Audio",
          "Audio_0_Language": "und",
          "Audio_0_Codec": "aac",
          "Audio_0_Channels": 2,
          "Audio_0_Bitrate": 125360,
          "Audio_0_SampleRate": 48000,
          "Audio_0_Default": true,
          "PlaybackPositionTicks": 1000000,
          "PlaybackPosition": "00:00:00",
          "MediaSourceId": "4b92551344f53b560fb55cd6700ebc86",
          "IsPaused": false,
          "IsAutomated": false,
          "DeviceId": "TW96aWxsxxxxxjA",
          "DeviceName": "Edge Chromium",
          "ClientName": "Jellyfin Web",
          "NotificationUsername": "Jeaven",
          "UserId": "9783d2432b0d40a8a716b6aa46xxxxx"
        }
        """
        if not body:
            return None
        try:
            message = json.loads(body)
        except Exception as e:
            logger.debug(f" AnalyzeJellyfin Webhook Error in telegram：" + str(e))
            return None
        if not message:
            return None
        logger.info(f" Receivejellyfin webhook：{message}")
        eventType = message.get('NotificationType')
        if not eventType:
            return None
        eventItem = schemas.WebhookEventInfo(
            event=eventType,
            channel="jellyfin"
        )
        eventItem.item_id = message.get('ItemId')
        eventItem.tmdb_id = message.get('Provider_tmdb')
        eventItem.overview = message.get('Overview')
        eventItem.device_name = message.get('DeviceName')
        eventItem.user_name = message.get('NotificationUsername')
        eventItem.client = message.get('ClientName')
        if message.get("ItemType") == "Episode":
            #  Episode
            eventItem.item_type = "TV"
            eventItem.season_id = message.get('SeasonNumber')
            eventItem.episode_id = message.get('EpisodeNumber')
            eventItem.item_name = "%s %s%s %s" % (
                message.get('SeriesName'),
                "S" + str(eventItem.season_id),
                "E" + str(eventItem.episode_id),
                message.get('Name'))
        else:
            #  Cinematic
            eventItem.item_type = "MOV"
            eventItem.item_name = "%s %s" % (
                message.get('Name'), "(" + str(message.get('Year')) + ")")

        #  Get message image
        if eventItem.item_id:
            #  Based on the returneditem_id Go call the media server to get the
            eventItem.image_url = self.get_remote_image_by_id(
                item_id=eventItem.item_id,
                image_type="Backdrop"
            )

        return eventItem

    def get_iteminfo(self, itemid: str) -> Optional[schemas.MediaServerItem]:
        """
        Get individual program details
        """
        if not itemid:
            return None
        if not self._host or not self._apikey:
            return None
        req_url = "%sUsers/%s/Items/%s?api_key=%s" % (
            self._host, self.user, itemid, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res and res.status_code == 200:
                item = res.json()
                tmdbid = item.get("ProviderIds", {}).get("Tmdb")
                return schemas.MediaServerItem(
                    server="jellyfin",
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
            logger.error(f" GroutUsers/Items Make a mistake：" + str(e))
        return None

    def get_items(self, parent: str) -> Generator:
        """
        Get a list of all media libraries on the media server
        """
        if not parent:
            yield None
        if not self._host or not self._apikey:
            yield None
        req_url = "%sUsers/%s/Items?parentId=%s&api_key=%s" % (self._host, self.user, parent, self._apikey)
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
                        for item in self.get_items(result.get("Id")):
                            yield item
        except Exception as e:
            logger.error(f" GroutUsers/Items Make a mistake：" + str(e))
        yield None

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
            return RequestUtils(accept_type="application/json").get_res(url=url)
        except Exception as e:
            logger.error(f" GroutJellyfin Make a mistake：" + str(e))
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
                headers=headers
            ).post_res(url=url, data=data)
        except Exception as e:
            logger.error(f" GroutJellyfin Make a mistake：" + str(e))
            return None
