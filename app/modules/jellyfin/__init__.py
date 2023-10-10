from pathlib import Path
from typing import Optional, Tuple, Union, Any, List, Generator

from app import schemas
from app.core.context import MediaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.jellyfin.jellyfin import Jellyfin
from app.schemas.types import MediaType


class JellyfinModule(_ModuleBase):
    jellyfin: Jellyfin = None

    def init_module(self) -> None:
        self.jellyfin = Jellyfin()

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "MEDIASERVER", "jellyfin"

    def scheduler_job(self) -> None:
        """
        Timed task， Each10 One call per minute
        """
        #  Scheduled reconnection
        if not self.jellyfin.is_inactive():
            self.jellyfin.reconnect()

    def stop(self):
        pass

    def user_authenticate(self, name: str, password: str) -> Optional[str]:
        """
        UtilizationEmby User-assisted completion of user authentication
        :param name:  User id
        :param password:  Cryptographic
        :return: Token or None
        """
        # Jellyfin Accreditation
        return self.jellyfin.authenticate(name, password)

    def webhook_parser(self, body: Any, form: Any, args: Any) -> Optional[schemas.WebhookEventInfo]:
        """
        AnalyzeWebhook Style of telegram
        :param body:   Requestor
        :param form:   Request form
        :param args:   Request parameters
        :return:  Dictionaries， Parsing into a message requires the inclusion of the：title、text、image
        """
        return self.jellyfin.get_webhook_message(body)

    def media_exists(self, mediainfo: MediaInfo, itemid: str = None) -> Optional[schemas.ExistMediaInfo]:
        """
        Determine if a media file exists
        :param mediainfo:   Identified media messages
        :param itemid:   Media serverItemID
        :return:  Returns if not presentNone， Return information when present， Includes all existing episodes of each season{type: movie/tv, seasons: {season: [episodes]}}
        """
        if mediainfo.type == MediaType.MOVIE:
            if itemid:
                movie = self.jellyfin.get_iteminfo(itemid)
                if movie:
                    logger.info(f" Already exists in the media library：{movie}")
                    return schemas.ExistMediaInfo(
                        type=MediaType.MOVIE,
                        server="jellyfin",
                        itemid=movie.item_id
                    )
            movies = self.jellyfin.get_movies(title=mediainfo.title, year=mediainfo.year, tmdb_id=mediainfo.tmdb_id)
            if not movies:
                logger.info(f"{mediainfo.title_year}  Doesn't exist in the media library")
                return None
            else:
                logger.info(f" Already exists in the media library：{movies}")
                return schemas.ExistMediaInfo(
                    type=MediaType.MOVIE,
                    server="jellyfin",
                    itemid=movies[0].item_id
                )
        else:
            itemid, tvs = self.jellyfin.get_tv_episodes(title=mediainfo.title,
                                                        year=mediainfo.year,
                                                        tmdb_id=mediainfo.tmdb_id,
                                                        item_id=itemid)
            if not tvs:
                logger.info(f"{mediainfo.title_year}  Doesn't exist in the media library")
                return None
            else:
                logger.info(f"{mediainfo.title_year}  Already exists in the media library：{tvs}")
                return schemas.ExistMediaInfo(
                    type=MediaType.TV,
                    seasons=tvs,
                    server="jellyfin",
                    itemid=itemid
                )

    def refresh_mediaserver(self, mediainfo: MediaInfo, file_path: Path) -> None:
        """
        Refresh media library
        :param mediainfo:   Identified media messages
        :param file_path:   File path
        :return:  Success or failure
        """
        self.jellyfin.refresh_root_library()

    def media_statistic(self) -> List[schemas.Statistic]:
        """
        Statistics on the number of media
        """
        media_statistic = self.jellyfin.get_medias_count()
        media_statistic.user_count = self.jellyfin.get_user_count()
        return [media_statistic]

    def mediaserver_librarys(self, server: str) -> Optional[List[schemas.MediaServerLibrary]]:
        """
        Media library list
        """
        if server != "jellyfin":
            return None
        return self.jellyfin.get_librarys()

    def mediaserver_items(self, server: str, library_id: str) -> Optional[Generator]:
        """
        Media library project list
        """
        if server != "jellyfin":
            return None
        return self.jellyfin.get_items(library_id)

    def mediaserver_iteminfo(self, server: str, item_id: str) -> Optional[schemas.MediaServerItem]:
        """
        Media library project details
        """
        if server != "jellyfin":
            return None
        return self.jellyfin.get_iteminfo(item_id)

    def mediaserver_tv_episodes(self, server: str,
                                item_id: Union[str, int]) -> Optional[List[schemas.MediaServerSeasonInfo]]:
        """
        Get episode information
        """
        if server != "jellyfin":
            return None
        _, seasoninfo = self.jellyfin.get_tv_episodes(item_id=item_id)
        if not seasoninfo:
            return []
        return [schemas.MediaServerSeasonInfo(
            season=season,
            episodes=episodes
        ) for season, episodes in seasoninfo.items()]
