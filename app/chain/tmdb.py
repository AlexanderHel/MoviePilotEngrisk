import random
from typing import Optional, List

from cachetools import cached, TTLCache

from app import schemas
from app.chain import ChainBase
from app.core.config import settings
from app.schemas import MediaType
from app.utils.singleton import Singleton


class TmdbChain(ChainBase, metaclass=Singleton):
    """
    TheMovieDB Process chain
    """

    def tmdb_discover(self, mtype: MediaType, sort_by: str, with_genres: str,
                      with_original_language: str, page: int = 1) -> Optional[List[dict]]:
        """
        :param mtype:   Media type
        :param sort_by:   Sort by
        :param with_genres:   Typology
        :param with_original_language:   Multilingualism
        :param page:   Pagination
        :return:  Media information list
        """
        return self.run_module("tmdb_discover", mtype=mtype,
                               sort_by=sort_by, with_genres=with_genres,
                               with_original_language=with_original_language,
                               page=page)

    def tmdb_trending(self, page: int = 1) -> List[dict]:
        """
        TMDB Fashionable trend
        :param page:  Page
        :return: TMDB Information list
        """
        return self.run_module("tmdb_trending", page=page)

    def tmdb_seasons(self, tmdbid: int) -> List[schemas.TmdbSeason]:
        """
        According toTMDBID Consult (a document etc)themoviedb All season information
        :param tmdbid:  TMDBID
        """
        return self.run_module("tmdb_seasons", tmdbid=tmdbid)

    def tmdb_episodes(self, tmdbid: int, season: int) -> List[schemas.TmdbEpisode]:
        """
        According toTMDBID Query all letters for a particular season
        :param tmdbid:  TMDBID
        :param season:   Classifier for seasonal crop yield or seasons of a tv series
        """
        return self.run_module("tmdb_episodes", tmdbid=tmdbid, season=season)

    def movie_similar(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Search for similar movies
        :param tmdbid:  TMDBID
        """
        return self.run_module("movie_similar", tmdbid=tmdbid)

    def tv_similar(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Search for similar tv series
        :param tmdbid:  TMDBID
        """
        return self.run_module("tv_similar", tmdbid=tmdbid)

    def movie_recommend(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Check recommended movies
        :param tmdbid:  TMDBID
        """
        return self.run_module("movie_recommend", tmdbid=tmdbid)

    def tv_recommend(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Search for recommended tv series
        :param tmdbid:  TMDBID
        """
        return self.run_module("tv_recommend", tmdbid=tmdbid)

    def movie_credits(self, tmdbid: int, page: int = 1) -> List[dict]:
        """
        According toTMDBID Search for movie cast and crew
        :param tmdbid:  TMDBID
        :param page:   Pagination
        """
        return self.run_module("movie_credits", tmdbid=tmdbid, page=page)

    def tv_credits(self, tmdbid: int, page: int = 1) -> List[dict]:
        """
        According toTMDBID Search for drama cast
        :param tmdbid:  TMDBID
        :param page:   Pagination
        """
        return self.run_module("tv_credits", tmdbid=tmdbid, page=page)

    def person_detail(self, person_id: int) -> dict:
        """
        According toTMDBID Find out more about the cast and crew
        :param person_id:   Character (in a play, novel etc)ID
        """
        return self.run_module("person_detail", person_id=person_id)

    def person_credits(self, person_id: int, page: int = 1) -> List[dict]:
        """
        Character-basedID Enquire about a person's acting credits
        :param person_id:   Character (in a play, novel etc)ID
        :param page:   Pagination
        """
        return self.run_module("person_credits", person_id=person_id, page=page)

    @cached(cache=TTLCache(maxsize=1, ttl=3600))
    def get_random_wallpager(self):
        """
        Get random wallpaper， (computing) cache1 Hour
        """
        infos = self.tmdb_trending()
        if infos:
            #  A random movie
            while True:
                info = random.choice(infos)
                if info and info.get("backdrop_path"):
                    return f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{info.get('backdrop_path')}"
        return None
