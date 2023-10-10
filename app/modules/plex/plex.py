import json
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Generator, Any
from urllib.parse import quote_plus

from plexapi import media
from plexapi.server import PlexServer

from app import schemas
from app.core.config import settings
from app.log import logger
from app.schemas import MediaType
from app.utils.singleton import Singleton


class Plex(metaclass=Singleton):

    def __init__(self):
        self._host = settings.PLEX_HOST
        if self._host:
            if not self._host.endswith("/"):
                self._host += "/"
            if not self._host.startswith("http"):
                self._host = "http://" + self._host
        self._token = settings.PLEX_TOKEN
        if self._host and self._token:
            try:
                self._plex = PlexServer(self._host, self._token)
                self._libraries = self._plex.library.sections()
            except Exception as e:
                self._plex = None
                logger.error(f"Plex Server connection failure：{str(e)}")

    def is_inactive(self) -> bool:
        """
        Determine if reconnection is required
        """
        if not self._host or not self._token:
            return False
        return True if not self._plex else False

    def reconnect(self):
        """
        Reconnect
        """
        try:
            self._plex = PlexServer(self._host, self._token)
            self._libraries = self._plex.library.sections()
        except Exception as e:
            self._plex = None
            logger.error(f"Plex Server connection failure：{str(e)}")

    def get_librarys(self) -> List[schemas.MediaServerLibrary]:
        """
        Get a list of all media libraries on the media server
        """
        if not self._plex:
            return []
        try:
            self._libraries = self._plex.library.sections()
        except Exception as err:
            logger.error(f"Get a list of all media libraries on the media server出错：{str(err)}")
            return []
        libraries = []
        for library in self._libraries:
            match library.type:
                case "movie":
                    library_type = MediaType.MOVIE.value
                case "show":
                    library_type = MediaType.TV.value
                case _:
                    continue
            libraries.append(
                schemas.MediaServerLibrary(
                    id=library.key,
                    name=library.title,
                    path=library.locations,
                    type=library_type
                )
            )
        return libraries

    def get_medias_count(self) -> schemas.Statistic:
        """
        Get the movie、 Dramas、 Number of anime and manga media
        :return: MovieCount SeriesCount SongCount
        """
        if not self._plex:
            return schemas.Statistic()
        sections = self._plex.library.sections()
        MovieCount = SeriesCount = EpisodeCount = 0
        for sec in sections:
            if sec.type == "movie":
                MovieCount += sec.totalSize
            if sec.type == "show":
                SeriesCount += sec.totalSize
                EpisodeCount += sec.totalViewSize(libtype='episode')
        return schemas.Statistic(
            movie_count=MovieCount,
            tv_count=SeriesCount,
            episode_count=EpisodeCount
        )

    def get_movies(self,
                   title: str,
                   original_title: str = None,
                   year: str = None,
                   tmdb_id: int = None) -> Optional[List[schemas.MediaServerItem]]:
        """
        By title and year， Check if the movie is onPlex Exist in， Returns the list if it exists
        :param title:  Caption
        :param original_title:  Title of origin
        :param year:  Particular year， No filtering if empty
        :param tmdb_id: TMDB ID
        :return:  Suck (keep in your mouth without chewing)title、year Dictionary list of attributes
        """
        if not self._plex:
            return None
        ret_movies = []
        if year:
            movies = self._plex.library.search(title=title,
                                               year=year,
                                               libtype="movie")
            #  Look it up again under the original title
            if original_title and str(original_title) != str(title):
                movies.extend(self._plex.library.search(title=original_title,
                                                        year=year,
                                                        libtype="movie"))
        else:
            movies = self._plex.library.search(title=title,
                                               libtype="movie")
            if original_title and str(original_title) != str(title):
                movies.extend(self._plex.library.search(title=original_title,
                                                        libtype="movie"))
        for item in set(movies):
            ids = self.__get_ids(item.guids)
            if tmdb_id and ids['tmdb_id']:
                if str(ids['tmdb_id']) != str(tmdb_id):
                    continue
            path = None
            if item.locations:
                path = item.locations[0]
            ret_movies.append(
                schemas.MediaServerItem(
                    server="plex",
                    library=item.librarySectionID,
                    item_id=item.key,
                    item_type=item.type,
                    title=item.title,
                    original_title=item.originalTitle,
                    year=item.year,
                    tmdbid=ids['tmdb_id'],
                    imdbid=ids['imdb_id'],
                    tvdbid=ids['tvdb_id'],
                    path=path,
                )
            )
        return ret_movies

    def get_tv_episodes(self,
                        item_id: str = None,
                        title: str = None,
                        original_title: str = None,
                        year: str = None,
                        tmdb_id: int = None,
                        season: int = None) -> Tuple[Optional[str], Optional[Dict[int, list]]]:
        """
        Based on the title、 Particular year、 Quarterly search for all episodes of a tv series
        :param item_id:  Media, esp. news mediaID
        :param title:  Caption
        :param original_title:  Title of origin
        :param year:  Particular year， Can be null， No filtering by year if empty
        :param tmdb_id: TMDB ID
        :param season:  Quarter， Digital (electronics etc)
        :return:  List of all sets
        """
        if not self._plex:
            return None, {}
        if item_id:
            videos = self._plex.fetchItem(item_id)
        else:
            #  Fuzzy search by title and year， This result is not accurate enough
            videos = self._plex.library.search(title=title,
                                               year=year,
                                               libtype="show")
            if (not videos
                    and original_title
                    and str(original_title) != str(title)):
                videos = self._plex.library.search(title=original_title,
                                                   year=year,
                                                   libtype="show")
        if not videos:
            return None, {}
        if isinstance(videos, list):
            videos = videos[0]
        video_tmdbid = self.__get_ids(videos.guids).get('tmdb_id')
        if tmdb_id and video_tmdbid:
            if str(video_tmdbid) != str(tmdb_id):
                return None, {}
        episodes = videos.episodes()
        season_episodes = {}
        for episode in episodes:
            if season and episode.seasonNumber != int(season):
                continue
            if episode.seasonNumber not in season_episodes:
                season_episodes[episode.seasonNumber] = []
            season_episodes[episode.seasonNumber].append(episode.index)
        return videos.key, season_episodes

    def get_remote_image_by_id(self, item_id: str, image_type: str) -> Optional[str]:
        """
        According toItemId Through (a gap)Plex Check the address of the picture
        :param item_id:  ExistEmby Hit the nail on the headID
        :param image_type:  Types of pictures，Poster OrBackdrop Et al. (and other authors)
        :return:  The image corresponds to an image in theTMDB Hit the nail on the headURL
        """
        if not self._plex:
            return None
        try:
            if image_type == "Poster":
                images = self._plex.fetchItems('/library/metadata/%s/posters' % item_id,
                                               cls=media.Poster)
            else:
                images = self._plex.fetchItems('/library/metadata/%s/arts' % item_id,
                                               cls=media.Art)
            for image in images:
                if hasattr(image, 'key') and image.key.startswith('http'):
                    return image.key
        except Exception as e:
            logger.error(f" Error getting cover：" + str(e))
        return None

    def refresh_root_library(self) -> bool:
        """
        NotificationsPlex Refresh the entire media library
        """
        if not self._plex:
            return False
        return self._plex.library.update()

    def refresh_library_by_items(self, items: List[schemas.RefreshMediaItem]) -> bool:
        """
        Refresh media library by path item: target_path
        """
        if not self._plex:
            return False
        result_dict = {}
        for item in items:
            file_path = item.target_path
            lib_key, path = self.__find_librarie(file_path, self._libraries)
            #  If there are multiple episodes of the same series,key(path) The same will be merged
            result_dict[path] = lib_key
        if "" in result_dict:
            #  If there is a failed match, Refresh the entire library
            self._plex.library.update()
        else:
            #  Otherwise, refresh them one by one.
            for path, lib_key in result_dict.items():
                logger.info(f" Refresh media library：{lib_key} - {path}")
                self._plex.query(f'/library/sections/{lib_key}/refresh?path={quote_plus(path)}')

    @staticmethod
    def __find_librarie(path: Path, libraries: List[Any]) -> Tuple[str, str]:
        """
        Determine thispath Which media library to belong to
        Multiple media library configurations should not have duplicate and nested directories,
        """

        def is_subpath(_path: Path, _parent: Path) -> bool:
            """
            Judgements_path Is or isn't_parent Subdirectory of the
            """
            _path = _path.resolve()
            _parent = _parent.resolve()
            return _path.parts[:len(_parent.parts)] == _parent.parts

        if path is None:
            return "", ""

        try:
            for lib in libraries:
                if hasattr(lib, "locations") and lib.locations:
                    for location in lib.locations:
                        if is_subpath(path, Path(location)):
                            return lib.key, str(path)
        except Exception as err:
            logger.error(f" Error finding media library：{err}")
        return "", ""

    def get_iteminfo(self, itemid: str) -> Optional[schemas.MediaServerItem]:
        """
        Get individual program details
        """
        if not self._plex:
            return None
        try:
            item = self._plex.fetchItem(itemid)
            ids = self.__get_ids(item.guids)
            path = None
            if item.locations:
                path = item.locations[0]
            return schemas.MediaServerItem(
                server="plex",
                library=item.librarySectionID,
                item_id=item.key,
                item_type=item.type,
                title=item.title,
                original_title=item.originalTitle,
                year=item.year,
                tmdbid=ids['tmdb_id'],
                imdbid=ids['imdb_id'],
                tvdbid=ids['tvdb_id'],
                path=path,
            )
        except Exception as err:
            logger.error(f" Error getting project details：{err}")
        return None

    @staticmethod
    def __get_ids(guids: List[Any]) -> dict:
        guid_mapping = {
            "imdb://": "imdb_id",
            "tmdb://": "tmdb_id",
            "tvdb://": "tvdb_id"
        }
        ids = {}
        for prefix, varname in guid_mapping.items():
            ids[varname] = None
        for guid in guids:
            for prefix, varname in guid_mapping.items():
                if isinstance(guid, dict):
                    if guid['id'].startswith(prefix):
                        #  Find a matchID
                        ids[varname] = guid['id'][len(prefix):]
                        break
                else:
                    if guid.id.startswith(prefix):
                        #  Find a matchID
                        ids[varname] = guid.id[len(prefix):]
                        break
        return ids

    def get_items(self, parent: str) -> Generator:
        """
        Get a list of all media libraries on the media server
        """
        if not parent:
            yield None
        if not self._plex:
            yield None
        try:
            section = self._plex.library.sectionByID(int(parent))
            if section:
                for item in section.all():
                    if not item:
                        continue
                    ids = self.__get_ids(item.guids)
                    path = None
                    if item.locations:
                        path = item.locations[0]
                    yield schemas.MediaServerItem(
                        server="plex",
                        library=item.librarySectionID,
                        item_id=item.key,
                        item_type=item.type,
                        title=item.title,
                        original_title=item.originalTitle,
                        year=item.year,
                        tmdbid=ids['tmdb_id'],
                        imdbid=ids['imdb_id'],
                        tvdbid=ids['tvdb_id'],
                        path=path,
                    )
        except Exception as err:
            logger.error(f" Error getting media library list：{err}")
        yield None

    def get_webhook_message(self, form: any) -> Optional[schemas.WebhookEventInfo]:
        """
        AnalyzePlex Telegram
        eventItem   Meaning of fields
        event       Event type
        item_type   Media type TV,MOV
        item_name  TV: Mt langya in eastern shandong S1E6  Be completely honest and sincere  Escape from the tiger's mouth
                   MOV: Porky pig adventure(2001)
        overview    Description of the plot
        {
          "event": "media.scrobble",
          "user": false,
          "owner": true,
          "Account": {
            "id": 31646104,
            "thumb": "https://plex.tv/users/xx",
            "title": " Playable"
          },
          "Server": {
            "title": "Media-Server",
            "uuid": "xxxx"
          },
          "Player": {
            "local": false,
            "publicAddress": "xx.xx.xx.xx",
            "title": "MagicBook",
            "uuid": "wu0uoa1ujfq90t0c5p9f7fw0"
          },
          "Metadata": {
            "librarySectionType": "show",
            "ratingKey": "40294",
            "key": "/library/metadata/40294",
            "parentRatingKey": "40291",
            "grandparentRatingKey": "40275",
            "guid": "plex://episode/615580a9fa828e7f1a0caabd",
            "parentGuid": "plex://season/615580a9fa828e7f1a0caab8",
            "grandparentGuid": "plex://show/60e81fd8d8000e002d7d2976",
            "type": "episode",
            "title": "The World's Strongest Senior",
            "titleSort": "World's Strongest Senior",
            "grandparentKey": "/library/metadata/40275",
            "parentKey": "/library/metadata/40291",
            "librarySectionTitle": " Anime & manga episodes",
            "librarySectionID": 7,
            "librarySectionKey": "/library/sections/7",
            "grandparentTitle": " Lit. fanma's blade teeth (idiom); fig. a miracle cure for all ills",
            "parentTitle": "Combat Shadow Fighting Saga / Great Prison Battle Saga",
            "originalTitle": "Baki Hanma",
            "contentRating": "TV-MA",
            "summary": "The world is shaken by news",
            "index": 1,
            "parentIndex": 1,
            "audienceRating": 8.5,
            "viewCount": 1,
            "lastViewedAt": 1694320444,
            "year": 2021,
            "thumb": "/library/metadata/40294/thumb/1693544504",
            "art": "/library/metadata/40275/art/1693952979",
            "parentThumb": "/library/metadata/40291/thumb/1691115271",
            "grandparentThumb": "/library/metadata/40275/thumb/1693952979",
            "grandparentArt": "/library/metadata/40275/art/1693952979",
            "duration": 1500000,
            "originallyAvailableAt": "2021-09-30",
            "addedAt": 1691115281,
            "updatedAt": 1693544504,
            "audienceRatingImage": "themoviedb://image.rating",
            "Guid": [
              {
                "id": "imdb://tt14765720"
              },
              {
                "id": "tmdb://3087250"
              },
              {
                "id": "tvdb://8530933"
              }
            ],
            "Rating": [
              {
                "image": "themoviedb://image.rating",
                "value": 8.5,
                "type": "audience"
              }
            ],
            "Director": [
              {
                "id": 115144,
                "filter": "director=115144",
                "tag": "Keiya Saito",
                "tagKey": "5f401c8d04a86500409ea6c1"
              }
            ],
            "Writer": [
              {
                "id": 115135,
                "filter": "writer=115135",
                "tag": "Tatsuhiko Urahata",
                "tagKey": "5d7768e07a53e9001e6db1ce",
                "thumb": "https://metadata-static.plex.tv/f/people/f6f90dc89fa87d459f85d40a09720c05.jpg"
              }
            ]
          }
        }
        """
        if not form:
            return None
        payload = form.get("payload")
        if not payload:
            return None
        try:
            message = json.loads(payload)
        except Exception as e:
            logger.debug(f" Analyzeplex webhook Make a mistake：{str(e)}")
            return None
        eventType = message.get('event')
        if not eventType:
            return None
        logger.info(f" Receiveplex webhook：{message}")
        eventItem = schemas.WebhookEventInfo(event=eventType, channel="plex")
        if message.get('Metadata'):
            if message.get('Metadata', {}).get('type') == 'episode':
                eventItem.item_type = "TV"
                eventItem.item_name = "%s %s%s %s" % (
                    message.get('Metadata', {}).get('grandparentTitle'),
                    "S" + str(message.get('Metadata', {}).get('parentIndex')),
                    "E" + str(message.get('Metadata', {}).get('index')),
                    message.get('Metadata', {}).get('title'))
                eventItem.item_id = message.get('Metadata', {}).get('ratingKey')
                eventItem.season_id = message.get('Metadata', {}).get('parentIndex')
                eventItem.episode_id = message.get('Metadata', {}).get('index')

                if (message.get('Metadata', {}).get('summary')
                        and len(message.get('Metadata', {}).get('summary')) > 100):
                    eventItem.overview = str(message.get('Metadata', {}).get('summary'))[:100] + "..."
                else:
                    eventItem.overview = message.get('Metadata', {}).get('summary')
            else:
                eventItem.item_type = "MOV" if message.get('Metadata',
                                                           {}).get('type') == 'movie' else "SHOW"
                eventItem.item_name = "%s %s" % (
                    message.get('Metadata', {}).get('title'),
                    "(" + str(message.get('Metadata', {}).get('year')) + ")")
                eventItem.item_id = message.get('Metadata', {}).get('ratingKey')
                if len(message.get('Metadata', {}).get('summary')) > 100:
                    eventItem.overview = str(message.get('Metadata', {}).get('summary'))[:100] + "..."
                else:
                    eventItem.overview = message.get('Metadata', {}).get('summary')
        if message.get('Player'):
            eventItem.ip = message.get('Player').get('publicAddress')
            eventItem.client = message.get('Player').get('title')
            #  Give me a blank here., Prevents spelling messages withNone
            eventItem.device_name = ' '
        if message.get('Account'):
            eventItem.user_name = message.get("Account").get('title')

        #  Get message image
        if eventItem.item_id:
            #  Based on the returneditem_id Go call the media server to get the
            eventItem.image_url = self.get_remote_image_by_id(item_id=eventItem.item_id,
                                                              image_type="Backdrop")

        return eventItem

    def get_plex(self):
        """
        Gainplex Boyfriend， Facilitate direct operation
        """
        return self._plex
