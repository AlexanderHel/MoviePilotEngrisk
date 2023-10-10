import traceback
from functools import lru_cache
from typing import Optional, List
from urllib.parse import quote

import zhconv
from lxml import etree

from app.core.config import settings
from app.log import logger
from app.schemas.types import MediaType
from app.utils.http import RequestUtils
from app.utils.string import StringUtils
from .tmdbv3api import TMDb, Search, Movie, TV, Season, Episode, Discover, Trending, Person
from .tmdbv3api.exceptions import TMDbException


class TmdbHelper:
    """
    TMDB Recognition match
    """

    def __init__(self):
        # TMDB Main part
        self.tmdb = TMDb()
        #  Domain name
        self.tmdb.domain = settings.TMDB_API_DOMAIN
        #  Enable cache
        self.tmdb.cache = True
        #  Cache size
        self.tmdb.REQUEST_CACHE_MAXSIZE = settings.CACHE_CONF.get('tmdb')
        # APIKEY
        self.tmdb.api_key = settings.TMDB_API_KEY
        #  Language type (in a classification)
        self.tmdb.language = 'zh'
        #  Act on behalf of sb. in a responsible position
        self.tmdb.proxies = settings.PROXY
        #  Debug mode
        self.tmdb.debug = False
        # TMDB Query subject
        self.search = Search()
        self.movie = Movie()
        self.tv = TV()
        self.season = Season()
        self.episode = Episode()
        self.discover = Discover()
        self.trending = Trending()
        self.person = Person()

    def search_multiis(self, title: str) -> List[dict]:
        """
        Simultaneous query for fuzzy matched movies、 DramasTMDB Text
        """
        if not title:
            return []
        ret_infos = []
        multis = self.search.multi(term=title) or []
        for multi in multis:
            if multi.get("media_type") in ["movie", "tv"]:
                multi['media_type'] = MediaType.MOVIE if multi.get("media_type") == "movie" else MediaType.TV
                ret_infos.append(multi)
        return ret_infos

    def search_movies(self, title: str, year: str) -> List[dict]:
        """
        Query all movies with fuzzy matchesTMDB Text
        """
        if not title:
            return []
        ret_infos = []
        if year:
            movies = self.search.movies(term=title, year=year) or []
        else:
            movies = self.search.movies(term=title) or []
        for movie in movies:
            if title in movie.get("title"):
                movie['media_type'] = MediaType.MOVIE
                ret_infos.append(movie)
        return ret_infos

    def search_tvs(self, title: str, year: str) -> List[dict]:
        """
        Query all tv series with fuzzy matchesTMDB Text
        """
        if not title:
            return []
        ret_infos = []
        if year:
            tvs = self.search.tv_shows(term=title, release_year=year) or []
        else:
            tvs = self.search.tv_shows(term=title) or []
        for tv in tvs:
            if title in tv.get("name"):
                tv['media_type'] = MediaType.TV
                ret_infos.append(tv)
        return ret_infos

    @staticmethod
    def __compare_names(file_name: str, tmdb_names: list) -> bool:
        """
        Compare file name matches， Ignore case and special characters
        :param file_name:  Recognized file name or seed name
        :param tmdb_names: TMDB Translations returned
        :return: True or False
        """
        if not file_name or not tmdb_names:
            return False
        if not isinstance(tmdb_names, list):
            tmdb_names = [tmdb_names]
        file_name = StringUtils.clear(file_name).upper()
        for tmdb_name in tmdb_names:
            tmdb_name = StringUtils.clear(tmdb_name).strip().upper()
            if file_name == tmdb_name:
                return True
        return False

    @staticmethod
    def __get_names(tmdb_info: dict) -> List[str]:
        """
        Look for sth.tmdb All titles and translations in， For name matching
        :param tmdb_info: TMDB Text
        :return:  List of all translations
        """
        if not tmdb_info:
            return []
        ret_names = []
        if tmdb_info.get('media_type') == MediaType.MOVIE:
            alternative_titles = tmdb_info.get("alternative_titles", {}).get("titles", [])
            for alternative_title in alternative_titles:
                title = alternative_title.get("title")
                if title and title not in ret_names:
                    ret_names.append(title)
            translations = tmdb_info.get("translations", {}).get("translations", [])
            for translation in translations:
                title = translation.get("data", {}).get("title")
                if title and title not in ret_names:
                    ret_names.append(title)
        else:
            alternative_titles = tmdb_info.get("alternative_titles", {}).get("results", [])
            for alternative_title in alternative_titles:
                name = alternative_title.get("title")
                if name and name not in ret_names:
                    ret_names.append(name)
            translations = tmdb_info.get("translations", {}).get("translations", [])
            for translation in translations:
                name = translation.get("data", {}).get("name")
                if name and name not in ret_names:
                    ret_names.append(name)
        return ret_names

    def match(self, name: str,
              mtype: MediaType,
              year: str = None,
              season_year: str = None,
              season_number: int = None) -> Optional[dict]:
        """
        Look for sth.tmdb Media information in， The match returns a message that is as correct as possible
        :param name:  The name of the fencing rope
        :param mtype:  Typology： Cinematic、 Dramas
        :param year:  Particular year， If it's a seasonal episode, it needs to be the year it premiered.(first_air_date)
        :param season_year:  Current season episode year
        :param season_number:  End of a season， Integer (math.)
        :return: TMDB (used form a nominal expression)INFO， At the same time, it willmtype Assign tomedia_type Center
        """
        if not self.search:
            return None
        if not name:
            return None
        # TMDB Look for sth.
        info = {}
        if mtype == MediaType.MOVIE:
            year_range = [year]
            if year:
                year_range.append(str(int(year) + 1))
                year_range.append(str(int(year) - 1))
            for year in year_range:
                logger.debug(
                    f" Recognition in progress{mtype.value}：{name},  Particular year={year} ...")
                info = self.__search_movie_by_name(name, year)
                if info:
                    info['media_type'] = MediaType.MOVIE
                    break
        else:
            #  Current season and current episode year available， Using exact match
            if season_year and season_number:
                logger.debug(
                    f" Recognition in progress{mtype.value}：{name},  End of a season={season_number},  Season set year={season_year} ...")
                info = self.__search_tv_by_season(name,
                                                  season_year,
                                                  season_number)
            if not info:
                logger.debug(
                    f" Recognition in progress{mtype.value}：{name},  Particular year={year} ...")
                info = self.__search_tv_by_name(name, year)
            if info:
                info['media_type'] = MediaType.TV
        #  Come (or go) back
        return info

    def __search_movie_by_name(self, name: str, year: str) -> Optional[dict]:
        """
        Search for movies by nameTMDB Match
        :param name:  Recognized file name or seed name
        :param year:  Movie release date
        :return:  Matching media messages
        """
        try:
            if year:
                movies = self.search.movies(term=name, year=year)
            else:
                movies = self.search.movies(term=name)
        except TMDbException as err:
            logger.error(f" GroutTMDB Make a mistake：{err}")
            return None
        except Exception as e:
            logger.error(f" GroutTMDB Make a mistake：{e}")
            print(traceback.print_exc())
            return None
        logger.debug(f"API Come (or go) back：{str(self.search.total_results)}")
        if len(movies) == 0:
            logger.debug(f"{name}  No relevant movie information found!")
            return {}
        else:
            #  Sort by year in descending order
            movies = sorted(
                movies,
                key=lambda x: x.get('release_date') or '0000-00-00',
                reverse=True
            )
            for movie in movies:
                #  Particular year
                movie_year = movie.get('release_date')[0:4] if movie.get('release_date') else None
                if year and movie_year != year:
                    #  Particular year不匹配
                    continue
                #  Match title、 Original title
                if self.__compare_names(name, movie.get('title')):
                    return movie
                if self.__compare_names(name, movie.get('original_title')):
                    return movie
                #  Match alias、 Translated names
                if not movie.get("names"):
                    movie = self.get_info(mtype=MediaType.MOVIE, tmdbid=movie.get("id"))
                if movie and self.__compare_names(name, movie.get("names")):
                    return movie
        return {}

    def __search_tv_by_name(self, name: str, year: str) -> Optional[dict]:
        """
        Search tv series by nameTMDB Match
        :param name:  Recognized file name or seed name
        :param year:  Year of premiere of the tv series
        :return:  Matching media messages
        """
        try:
            if year:
                tvs = self.search.tv_shows(term=name, release_year=year)
            else:
                tvs = self.search.tv_shows(term=name)
        except TMDbException as err:
            logger.error(f" GroutTMDB Make a mistake：{err}")
            return None
        except Exception as e:
            logger.error(f" GroutTMDB Make a mistake：{e}")
            print(traceback.print_exc())
            return None
        logger.debug(f"API Come (or go) back：{str(self.search.total_results)}")
        if len(tvs) == 0:
            logger.debug(f"{name}  No relevant episode information found!")
            return {}
        else:
            #  Sort by year in descending order
            tvs = sorted(
                tvs,
                key=lambda x: x.get('first_air_date') or '0000-00-00',
                reverse=True
            )
            for tv in tvs:
                tv_year = tv.get('first_air_date')[0:4] if tv.get('first_air_date') else None
                if year and tv_year != year:
                    #  Particular year不匹配
                    continue
                #  Match title、 Original title
                if self.__compare_names(name, tv.get('name')):
                    return tv
                if self.__compare_names(name, tv.get('original_name')):
                    return tv
                #  Match alias、 Translated names
                if not tv.get("names"):
                    tv = self.get_info(mtype=MediaType.TV, tmdbid=tv.get("id"))
                if tv and self.__compare_names(name, tv.get("names")):
                    return tv
        return {}

    def __search_tv_by_season(self, name: str, season_year: str, season_number: int) -> Optional[dict]:
        """
        Match the name of the tv series with the year and serial number of the seasonTMDB
        :param name:  Recognized file name or seed name
        :param season_year:  Year of the season
        :param season_number:  Ordinal number
        :return:  Matching media messages
        """

        def __season_match(tv_info: dict, _season_year: str) -> bool:
            if not tv_info:
                return False
            try:
                seasons = self.__get_tv_seasons(tv_info)
                for season, season_info in seasons.items():
                    if season_info.get("air_date"):
                        if season_info.get("air_date")[0:4] == str(_season_year) \
                                and season == int(season_number):
                            return True
            except Exception as e1:
                logger.error(f" GroutTMDB Make a mistake：{e1}")
                print(traceback.print_exc())
                return False
            return False

        try:
            tvs = self.search.tv_shows(term=name)
        except TMDbException as err:
            logger.error(f" GroutTMDB Make a mistake：{err}")
            return None
        except Exception as e:
            logger.error(f" GroutTMDB Make a mistake：{e}")
            print(traceback.print_exc())
            return None

        if len(tvs) == 0:
            logger.debug("%s  No season found%s Related information!" % (name, season_number))
            return {}
        else:
            #  Sort by year in descending order
            tvs = sorted(
                tvs,
                key=lambda x: x.get('first_air_date') or '0000-00-00',
                reverse=True
            )
            for tv in tvs:
                #  Particular year
                tv_year = tv.get('first_air_date')[0:4] if tv.get('first_air_date') else None
                if (self.__compare_names(name, tv.get('name'))
                    or self.__compare_names(name, tv.get('original_name'))) \
                        and (tv_year == str(season_year)):
                    return tv
                #  Match alias、 Translated names
                if not tv.get("names"):
                    tv = self.get_info(mtype=MediaType.TV, tmdbid=tv.get("id"))
                if not tv or not self.__compare_names(name, tv.get("names")):
                    continue
                if __season_match(tv_info=tv, _season_year=season_year):
                    return tv
        return {}

    @staticmethod
    def __get_tv_seasons(tv_info: dict) -> Optional[dict]:
        """
        Consult (a document etc)TMDB All seasons of the tv series
        :param tv_info: TMDB  Seasonal information
        :return:  Includes a dictionary of episodes per season
        """
        """
        "seasons": [
            {
              "air_date": "2006-01-08",
              "episode_count": 11,
              "id": 3722,
              "name": " Special edition (of a newspaper)",
              "overview": "",
              "poster_path": "/snQYndfsEr3Sto2jOmkmsQuUXAQ.jpg",
              "season_number": 0
            },
            {
              "air_date": "2005-03-27",
              "episode_count": 9,
              "id": 3718,
              "name": " (prefix indicating ordinal number, e.g. first, number two etc) 1  Classifier for seasonal crop yield or seasons of a tv series",
              "overview": "",
              "poster_path": "/foM4ImvUXPrD2NvtkHyixq5vhPx.jpg",
              "season_number": 1
            }
        ]
        """
        if not tv_info:
            return {}
        ret_seasons = {}
        for season_info in tv_info.get("seasons") or []:
            if not season_info.get("season_number"):
                continue
            ret_seasons[season_info.get("season_number")] = season_info
        return ret_seasons

    def match_multi(self, name: str) -> Optional[dict]:
        """
        Search for both movies and tv shows by name， Used when there is no type or year
        :param name:  Recognized file name or seed name
        :return:  Matching media messages
        """
        try:
            multis = self.search.multi(term=name) or []
        except TMDbException as err:
            logger.error(f" GroutTMDB Make a mistake：{err}")
            return None
        except Exception as e:
            logger.error(f" GroutTMDB Make a mistake：{e}")
            print(traceback.print_exc())
            return None
        logger.debug(f"API Come (or go) back：{str(self.search.total_results)}")
        #  Come (or go) back结果
        ret_info = {}
        if len(multis) == 0:
            logger.debug(f"{name}  No relevant media information found!")
            return {}
        else:
            #  Sort by year in descending order，电影在前面
            multis = sorted(
                multis,
                key=lambda x: ("1"
                               if x.get("media_type") == "movie"
                               else "0") + (x.get('release_date')
                                            or x.get('first_air_date')
                                            or '0000-00-00'),
                reverse=True
            )
            for multi in multis:
                if multi.get("media_type") == "movie":
                    if self.__compare_names(name, multi.get('title')) \
                            or self.__compare_names(name, multi.get('original_title')):
                        ret_info = multi
                        break
                    #  Match alias、 Translated names
                    if not multi.get("names"):
                        multi = self.get_info(mtype=MediaType.MOVIE, tmdbid=multi.get("id"))
                    if multi and self.__compare_names(name, multi.get("names")):
                        ret_info = multi
                        break
                elif multi.get("media_type") == "tv":
                    if self.__compare_names(name, multi.get('name')) \
                            or self.__compare_names(name, multi.get('original_name')):
                        ret_info = multi
                        break
                    #  Match alias、 Translated names
                    if not multi.get("names"):
                        multi = self.get_info(mtype=MediaType.TV, tmdbid=multi.get("id"))
                    if multi and self.__compare_names(name, multi.get("names")):
                        ret_info = multi
                        break
            #  Type change
            if (ret_info
                    and not isinstance(ret_info.get("media_type"), MediaType)):
                ret_info['media_type'] = MediaType.MOVIE if ret_info.get("media_type") == "movie" else MediaType.TV

            return ret_info

    @lru_cache(maxsize=settings.CACHE_CONF.get('tmdb'))
    def match_web(self, name: str, mtype: MediaType) -> Optional[dict]:
        """
        Look for sth.TMDB Node， Direct grab results， Returns when there is only one result
        :param name:  Name (of a thing)
        :param mtype:  Media type
        """
        if not name:
            return None
        if StringUtils.is_chinese(name):
            return {}
        logger.info(" In the process of being withdrawn fromTheDbMovie Website search：%s ..." % name)
        tmdb_url = "https://www.themoviedb.org/search?query=%s" % quote(name)
        res = RequestUtils(timeout=5, ua=settings.USER_AGENT).get_res(url=tmdb_url)
        if res and res.status_code == 200:
            html_text = res.text
            if not html_text:
                return None
            try:
                tmdb_links = []
                html = etree.HTML(html_text)
                if mtype == MediaType.TV:
                    links = html.xpath("//a[@data-id and @data-media-type='tv']/@href")
                else:
                    links = html.xpath("//a[@data-id]/@href")
                for link in links:
                    if not link or (not link.startswith("/tv") and not link.startswith("/movie")):
                        continue
                    if link not in tmdb_links:
                        tmdb_links.append(link)
                if len(tmdb_links) == 1:
                    tmdbinfo = self.get_info(
                        mtype=MediaType.TV if tmdb_links[0].startswith("/tv") else MediaType.MOVIE,
                        tmdbid=tmdb_links[0].split("/")[-1])
                    if tmdbinfo:
                        if mtype == MediaType.TV and tmdbinfo.get('media_type') != MediaType.TV:
                            return {}
                        if tmdbinfo.get('media_type') == MediaType.MOVIE:
                            logger.info("%s  Through (a gap)WEB Recognize  Cinematic：TMDBID=%s,  Name (of a thing)=%s,  Release date=%s" % (
                                name,
                                tmdbinfo.get('id'),
                                tmdbinfo.get('title'),
                                tmdbinfo.get('release_date')))
                        else:
                            logger.info("%s  Through (a gap)WEB Recognize  Dramas：TMDBID=%s,  Name (of a thing)=%s,  Premiere date=%s" % (
                                name,
                                tmdbinfo.get('id'),
                                tmdbinfo.get('name'),
                                tmdbinfo.get('first_air_date')))
                    return tmdbinfo
                elif len(tmdb_links) > 1:
                    logger.info("%s TMDB Excessive website return data：%s" % (name, len(tmdb_links)))
                else:
                    logger.info("%s TMDB No media information was available on the website！" % name)
            except Exception as err:
                logger.error(f" Through (a gap)TheDbMovie Website query error：{err}")
                return None
        return None

    def get_info(self,
                 mtype: MediaType,
                 tmdbid: int) -> dict:
        """
        State in advanceTMDB Horn (wind instrument)， Search for a piece of media information
        :param mtype:  Typology： Cinematic、 Dramas、动漫，为空时都查（此时用不上年份）
        :param tmdbid: TMDB (used form a nominal expression)ID， There aretmdbid Priority is given to the use oftmdbid， Otherwise use year and title
        """

        def __get_genre_ids(genres: list) -> list:
            """
            Through (a gap)TMDB Get it in the detailsgenre_id Listings
            """
            if not genres:
                return []
            genre_ids = []
            for genre in genres:
                genre_ids.append(genre.get('id'))
            return genre_ids

        #  Consult (a document etc)TMDB Comprehensivengeq
        if mtype == MediaType.MOVIE:
            tmdb_info = self.__get_movie_detail(tmdbid)
            if tmdb_info:
                tmdb_info['media_type'] = MediaType.MOVIE
        elif mtype == MediaType.TV:
            tmdb_info = self.__get_tv_detail(tmdbid)
            if tmdb_info:
                tmdb_info['media_type'] = MediaType.TV
        else:
            tmdb_info = self.__get_tv_detail(tmdbid)
            if tmdb_info:
                tmdb_info['media_type'] = MediaType.TV
            else:
                tmdb_info = self.__get_movie_detail(tmdbid)
                if tmdb_info:
                    tmdb_info['media_type'] = MediaType.MOVIE

        if tmdb_info:
            #  Conversionsgenreid
            tmdb_info['genre_ids'] = __get_genre_ids(tmdb_info.get('genres'))
            #  Alias and translation
            tmdb_info['names'] = self.__get_names(tmdb_info)
            #  Convert chinese title
            self.__update_tmdbinfo_cn_title(tmdb_info)

        return tmdb_info

    @staticmethod
    def __update_tmdbinfo_cn_title(tmdb_info: dict):
        """
        UpdateTMDB Chinese name in the message
        """

        def __get_tmdb_chinese_title(tmdbinfo):
            """
            Get chinese title from alias
            """
            if not tmdbinfo:
                return None
            if tmdbinfo.get("media_type") == MediaType.MOVIE:
                alternative_titles = tmdbinfo.get("alternative_titles", {}).get("titles", [])
            else:
                alternative_titles = tmdbinfo.get("alternative_titles", {}).get("results", [])
            for alternative_title in alternative_titles:
                iso_3166_1 = alternative_title.get("iso_3166_1")
                if iso_3166_1 == "CN":
                    title = alternative_title.get("title")
                    if title and StringUtils.is_chinese(title) \
                            and zhconv.convert(title, "zh-hans") == title:
                        return title
            return tmdbinfo.get("title") if tmdbinfo.get("media_type") == MediaType.MOVIE else tmdbinfo.get("name")

        #  Find chinese name
        org_title = tmdb_info.get("title") \
            if tmdb_info.get("media_type") == MediaType.MOVIE \
            else tmdb_info.get("name")
        if not StringUtils.is_chinese(org_title):
            cn_title = __get_tmdb_chinese_title(tmdb_info)
            if cn_title and cn_title != org_title:
                if tmdb_info.get("media_type") == MediaType.MOVIE:
                    tmdb_info['title'] = cn_title
                else:
                    tmdb_info['name'] = cn_title

    def __get_movie_detail(self,
                           tmdbid: int,
                           append_to_response: str = "images,"
                                                     "credits,"
                                                     "alternative_titles,"
                                                     "translations,"
                                                     "external_ids") -> Optional[dict]:
        """
        Get the details of the movie
        :param tmdbid: TMDB ID
        :return: TMDB Text
        """
        """
        {
          "adult": false,
          "backdrop_path": "/r9PkFnRUIthgBp2JZZzD380MWZy.jpg",
          "belongs_to_collection": {
            "id": 94602,
            "name": " Puss in boots (computer game)（ Range）",
            "poster_path": "/anHwj9IupRoRZZ98WTBvHpTiE6A.jpg",
            "backdrop_path": "/feU1DWV5zMWxXUHJyAIk3dHRQ9c.jpg"
          },
          "budget": 90000000,
          "genres": [
            {
              "id": 16,
              "name": " Anime"
            },
            {
              "id": 28,
              "name": " Movements"
            },
            {
              "id": 12,
              "name": " Take chances"
            },
            {
              "id": 35,
              "name": " Comedy"
            },
            {
              "id": 10751,
              "name": " Household"
            },
            {
              "id": 14,
              "name": " Fantastical"
            }
          ],
          "homepage": "",
          "id": 315162,
          "imdb_id": "tt3915174",
          "original_language": "en",
          "original_title": "Puss in Boots: The Last Wish",
          "overview": " Separated in time (usu. followed by a quantity of time)11 Surname nian， The pompous, pompous, pompous, pompous, pompous cat warrior is back.！ Today's cat warrior（ Antonio (name)· Banderas (name)  Dubbing (filmmaking)）， He's still funny and unpretentious.、 Several times“ Get oneself killed in a fancy way” Empress， Nine lives and now only one.， So he had to ask his old partner and“ Old enemy”—— Charming soft-clawed chick.（ Salma (name)· Hayek (name)  Dubbing (filmmaking)） To give a helping hand to restore his nine lives.。",
          "popularity": 8842.129,
          "poster_path": "/rnn30OlNPiC3IOoWHKoKARGsBRK.jpg",
          "production_companies": [
            {
              "id": 33,
              "logo_path": "/8lvHyhjr8oUKOOy2dKXoALWKdp0.png",
              "name": "Universal Pictures",
              "origin_country": "US"
            },
            {
              "id": 521,
              "logo_path": "/kP7t6RwGz2AvvTkvnI1uteEwHet.png",
              "name": "DreamWorks Animation",
              "origin_country": "US"
            }
          ],
          "production_countries": [
            {
              "iso_3166_1": "US",
              "name": "United States of America"
            }
          ],
          "release_date": "2022-12-07",
          "revenue": 260725470,
          "runtime": 102,
          "spoken_languages": [
            {
              "english_name": "English",
              "iso_639_1": "en",
              "name": "English"
            },
            {
              "english_name": "Spanish",
              "iso_639_1": "es",
              "name": "Español"
            }
          ],
          "status": "Released",
          "tagline": "",
          "title": " Puss in boots (computer game)2",
          "video": false,
          "vote_average": 8.614,
          "vote_count": 2291
        }
        """
        if not self.movie:
            return {}
        try:
            logger.info(" Inquiry in progressTMDB Cinematic：%s ..." % tmdbid)
            tmdbinfo = self.movie.details(tmdbid, append_to_response)
            if tmdbinfo:
                logger.info(f"{tmdbid}  Inquiry results：{tmdbinfo.get('title')}")
            return tmdbinfo or {}
        except Exception as e:
            print(str(e))
            return None

    def __get_tv_detail(self,
                        tmdbid: int,
                        append_to_response: str = "images,"
                                                  "credits,"
                                                  "alternative_titles,"
                                                  "translations,"
                                                  "external_ids") -> Optional[dict]:
        """
        Get details about the tv series
        :param tmdbid: TMDB ID
        :return: TMDB Text
        """
        """
        {
          "adult": false,
          "backdrop_path": "/uDgy6hyPd82kOHh6I95FLtLnj6p.jpg",
          "created_by": [
            {
              "id": 35796,
              "credit_id": "5e84f06a3344c600153f6a57",
              "name": "Craig Mazin",
              "gender": 2,
              "profile_path": "/uEhna6qcMuyU5TP7irpTUZ2ZsZc.jpg"
            },
            {
              "id": 1295692,
              "credit_id": "5e84f03598f1f10016a985c0",
              "name": "Neil Druckmann",
              "gender": 2,
              "profile_path": "/bVUsM4aYiHbeSYE1xAw2H5Z1ANU.jpg"
            }
          ],
          "episode_run_time": [],
          "first_air_date": "2023-01-15",
          "genres": [
            {
              "id": 18,
              "name": " Plots"
            },
            {
              "id": 10765,
              "name": "Sci-Fi & Fantasy"
            },
            {
              "id": 10759,
              "name": " Action adventure"
            }
          ],
          "homepage": "https://www.hbo.com/the-last-of-us",
          "id": 100088,
          "in_production": true,
          "languages": [
            "en"
          ],
          "last_air_date": "2023-01-15",
          "last_episode_to_air": {
            "air_date": "2023-01-15",
            "episode_number": 1,
            "id": 2181581,
            "name": " When you're lost in the dark",
            "overview": " After a global pandemic destroys civilization.， A hardy survivor charged with caring for a 14  Little girl.， She may be mankind's last hope.。",
            "production_code": "",
            "runtime": 81,
            "season_number": 1,
            "show_id": 100088,
            "still_path": "/aRquEWm8wWF1dfa9uZ1TXLvVrKD.jpg",
            "vote_average": 8,
            "vote_count": 33
          },
          "name": " Last survivor",
          "next_episode_to_air": {
            "air_date": "2023-01-22",
            "episode_number": 2,
            "id": 4071039,
            "name": " Cordyceps sinensis",
            "overview": "",
            "production_code": "",
            "runtime": 55,
            "season_number": 1,
            "show_id": 100088,
            "still_path": "/jkUtYTmeap6EvkHI4n0j5IRFrIr.jpg",
            "vote_average": 10,
            "vote_count": 1
          },
          "networks": [
            {
              "id": 49,
              "name": "HBO",
              "logo_path": "/tuomPhY2UtuPTqqFnKMVHvSb724.png",
              "origin_country": "US"
            }
          ],
          "number_of_episodes": 9,
          "number_of_seasons": 1,
          "origin_country": [
            "US"
          ],
          "original_language": "en",
          "original_name": "The Last of Us",
          "overview": " U.s. after unidentified fungus outbreaks， People infected with the fungus become horrible monsters.， Joel (name)（Joel） In exchange for the weapon, he promised to take the little girl, ellie.（Ellie） Delivered to the designated location， Thus began their long journey across america.。",
          "popularity": 5585.639,
          "poster_path": "/nOY3VBFO0VnlN9nlRombnMTztyh.jpg",
          "production_companies": [
            {
              "id": 3268,
              "logo_path": "/tuomPhY2UtuPTqqFnKMVHvSb724.png",
              "name": "HBO",
              "origin_country": "US"
            },
            {
              "id": 11073,
              "logo_path": "/aCbASRcI1MI7DXjPbSW9Fcv9uGR.png",
              "name": "Sony Pictures Television Studios",
              "origin_country": "US"
            },
            {
              "id": 23217,
              "logo_path": "/kXBZdQigEf6QiTLzo6TFLAa7jKD.png",
              "name": "Naughty Dog",
              "origin_country": "US"
            },
            {
              "id": 115241,
              "logo_path": null,
              "name": "The Mighty Mint",
              "origin_country": "US"
            },
            {
              "id": 119645,
              "logo_path": null,
              "name": "Word Games",
              "origin_country": "US"
            },
            {
              "id": 125281,
              "logo_path": "/3hV8pyxzAJgEjiSYVv1WZ0ZYayp.png",
              "name": "PlayStation Productions",
              "origin_country": "US"
            }
          ],
          "production_countries": [
            {
              "iso_3166_1": "US",
              "name": "United States of America"
            }
          ],
          "seasons": [
            {
              "air_date": "2023-01-15",
              "episode_count": 9,
              "id": 144593,
              "name": " (prefix indicating ordinal number, e.g. first, number two etc) 1  Classifier for seasonal crop yield or seasons of a tv series",
              "overview": "",
              "poster_path": "/aUQKIpZZ31KWbpdHMCmaV76u78T.jpg",
              "season_number": 1
            }
          ],
          "spoken_languages": [
            {
              "english_name": "English",
              "iso_639_1": "en",
              "name": "English"
            }
          ],
          "status": "Returning Series",
          "tagline": "",
          "type": "Scripted",
          "vote_average": 8.924,
          "vote_count": 601
        }
        """
        if not self.tv:
            return {}
        try:
            logger.info(" Inquiry in progressTMDB Dramas：%s ..." % tmdbid)
            tmdbinfo = self.tv.details(tv_id=tmdbid, append_to_response=append_to_response)
            if tmdbinfo:
                logger.info(f"{tmdbid}  Inquiry results：{tmdbinfo.get('name')}")
            return tmdbinfo or {}
        except Exception as e:
            print(str(e))
            return None

    def get_tv_season_detail(self, tmdbid: int, season: int):
        """
        Get details on the tv season
        :param tmdbid: TMDB ID
        :param season:  Classifier for seasonal crop yield or seasons of a tv series， Digital (electronics etc)
        :return: TMDB Text
        """
        """
        {
          "_id": "5e614cd3357c00001631a6ef",
          "air_date": "2023-01-15",
          "episodes": [
            {
              "air_date": "2023-01-15",
              "episode_number": 1,
              "id": 2181581,
              "name": " When you're lost in the dark",
              "overview": " After a global pandemic destroys civilization.， A hardy survivor charged with caring for a 14  Little girl.， She may be mankind's last hope.。",
              "production_code": "",
              "runtime": 81,
              "season_number": 1,
              "show_id": 100088,
              "still_path": "/aRquEWm8wWF1dfa9uZ1TXLvVrKD.jpg",
              "vote_average": 8,
              "vote_count": 33,
              "crew": [
                {
                  "job": "Writer",
                  "department": "Writing",
                  "credit_id": "619c370063536a00619a08ee",
                  "adult": false,
                  "gender": 2,
                  "id": 35796,
                  "known_for_department": "Writing",
                  "name": "Craig Mazin",
                  "original_name": "Craig Mazin",
                  "popularity": 15.211,
                  "profile_path": "/uEhna6qcMuyU5TP7irpTUZ2ZsZc.jpg"
                },
              ],
              "guest_stars": [
                {
                  "character": "Marlene",
                  "credit_id": "63c4ca5e5f2b8d00aed539fc",
                  "order": 500,
                  "adult": false,
                  "gender": 1,
                  "id": 1253388,
                  "known_for_department": "Acting",
                  "name": "Merle Dandridge",
                  "original_name": "Merle Dandridge",
                  "popularity": 21.679,
                  "profile_path": "/lKwHdTtDf6NGw5dUrSXxbfkZLEk.jpg"
                }
              ]
            },
          ],
          "name": " (prefix indicating ordinal number, e.g. first, number two etc) 1  Classifier for seasonal crop yield or seasons of a tv series",
          "overview": "",
          "id": 144593,
          "poster_path": "/aUQKIpZZ31KWbpdHMCmaV76u78T.jpg",
          "season_number": 1
        }
        """
        if not self.season:
            return {}
        try:
            logger.info(" Inquiry in progressTMDB Dramas：%s， Classifier for seasonal crop yield or seasons of a tv series：%s ..." % (tmdbid, season))
            tmdbinfo = self.season.details(tv_id=tmdbid, season_num=season)
            return tmdbinfo or {}
        except Exception as e:
            print(str(e))
            return {}

    def get_tv_episode_detail(self, tmdbid: int, season: int, episode: int):
        """
        Get details of tv episodes
        :param tmdbid: TMDB ID
        :param season:  Classifier for seasonal crop yield or seasons of a tv series， Digital (electronics etc)
        :param episode:  Classifier for sections of a tv series e.g. episode， Digital (electronics etc)
        """
        if not self.episode:
            return {}
        try:
            logger.info(" Inquiry in progressTMDB Picture collection：%s， Classifier for seasonal crop yield or seasons of a tv series：%s， Classifier for sections of a tv series e.g. episode：%s ..." % (tmdbid, season, episode))
            tmdbinfo = self.episode.details(tv_id=tmdbid, season_num=season, episode_num=episode)
            return tmdbinfo or {}
        except Exception as e:
            print(str(e))
            return {}

    def discover_movies(self, **kwargs):
        """
        Discover the movie
        :param kwargs:
        :return:
        """
        if not self.discover:
            return []
        try:
            logger.info(f"正在Discover the movie：{kwargs}...")
            tmdbinfo = self.discover.discover_movies(kwargs)
            if tmdbinfo:
                for info in tmdbinfo:
                    info['media_type'] = MediaType.MOVIE
            return tmdbinfo or []
        except Exception as e:
            print(str(e))
            return []

    def discover_tvs(self, **kwargs):
        """
        Discovery tv series
        :param kwargs:
        :return:
        """
        if not self.discover:
            return []
        try:
            logger.info(f"正在Discovery tv series：{kwargs}...")
            tmdbinfo = self.discover.discover_tv_shows(kwargs)
            if tmdbinfo:
                for info in tmdbinfo:
                    info['media_type'] = MediaType.TV
            return tmdbinfo or []
        except Exception as e:
            print(str(e))
            return []

    def get_movie_images(self, tmdbid: int) -> dict:
        """
        Get the picture of the movie
        """
        if not self.movie:
            return {}
        try:
            logger.info(f" Getting movie pictures now：{tmdbid}...")
            return self.movie.images(movie_id=tmdbid) or {}
        except Exception as e:
            print(str(e))
            return {}

    def get_tv_images(self, tmdbid: int) -> dict:
        """
        Get pictures of tv shows
        """
        if not self.tv:
            return {}
        try:
            logger.info(f" Getting drama pictures：{tmdbid}...")
            return self.tv.images(tv_id=tmdbid) or {}
        except Exception as e:
            print(str(e))
            return {}

    def get_movie_similar(self, tmdbid: int) -> List[dict]:
        """
        Get movies similar to the movie
        """
        if not self.movie:
            return []
        try:
            logger.info(f" Getting similar movies now：{tmdbid}...")
            return self.movie.similar(movie_id=tmdbid) or []
        except Exception as e:
            print(str(e))
            return []

    def get_tv_similar(self, tmdbid: int) -> List[dict]:
        """
        Get similar tv shows to tv shows
        """
        if not self.tv:
            return []
        try:
            logger.info(f" Getting similar tv shows：{tmdbid}...")
            return self.tv.similar(tv_id=tmdbid) or []
        except Exception as e:
            print(str(e))
            return []

    def get_movie_recommend(self, tmdbid: int) -> List[dict]:
        """
        Get movie recommendations for movies
        """
        if not self.movie:
            return []
        try:
            logger.info(f" Getting recommended movies：{tmdbid}...")
            return self.movie.recommendations(movie_id=tmdbid) or []
        except Exception as e:
            print(str(e))
            return []

    def get_tv_recommend(self, tmdbid: int) -> List[dict]:
        """
        Get recommended tv shows for tv shows
        """
        if not self.tv:
            return []
        try:
            logger.info(f" Getting recommended tv shows：{tmdbid}...")
            return self.tv.recommendations(tv_id=tmdbid) or []
        except Exception as e:
            print(str(e))
            return []

    def get_movie_credits(self, tmdbid: int, page: int = 1, count: int = 24) -> List[dict]:
        """
        Get a list of the cast and crew of the movie
        """
        if not self.movie:
            return []
        try:
            logger.info(f" Getting the movie cast now：{tmdbid}...")
            info = self.movie.credits(movie_id=tmdbid) or {}
            cast = info.get('cast') or []
            if cast:
                return cast[(page - 1) * count: page * count]
            return []
        except Exception as e:
            print(str(e))
            return []

    def get_tv_credits(self, tmdbid: int, page: int = 1, count: int = 24) -> List[dict]:
        """
        Get a list of the cast and crew of the tv series
        """
        if not self.tv:
            return []
        try:
            logger.info(f" In the process of acquiring the cast of the tv series：{tmdbid}...")
            info = self.tv.credits(tv_id=tmdbid) or {}
            cast = info.get('cast') or []
            if cast:
                return cast[(page - 1) * count: page * count]
            return []
        except Exception as e:
            print(str(e))
            return []

    def get_person_detail(self, person_id: int) -> dict:
        """
        Get character details
        {
            "adult": false,
            "also_known_as": [
                "Michael Chen",
                "Chen He",
                " Chen he (1961-), chinese actor"
            ],
            "biography": " Chen he (1961-), chinese actor，xxx",
            "birthday": "1985-11-09",
            "deathday": null,
            "gender": 2,
            "homepage": "https://movie.douban.com/celebrity/1313841/",
            "id": 1397016,
            "imdb_id": "nm4369305",
            "known_for_department": "Acting",
            "name": "Chen He",
            "place_of_birth": "Fuzhou，Fujian Province，China",
            "popularity": 9.228,
            "profile_path": "/2Bk39zVuoHUNHtpZ7LVg7OgkDd4.jpg"
        }
        """
        if not self.person:
            return {}
        try:
            logger.info(f"正在Get character details：{person_id}...")
            return self.person.details(person_id=person_id) or {}
        except Exception as e:
            print(str(e))
            return {}

    def get_person_credits(self, person_id: int, page: int = 1, count: int = 24) -> List[dict]:
        """
        Get character acting credits
        """
        if not self.person:
            return []
        try:
            logger.info(f"正在Get character acting credits：{person_id}...")
            info = self.person.movie_credits(person_id=person_id) or {}
            cast = info.get('cast') or []
            if cast:
                return cast[(page - 1) * count: page * count]
            return []
        except Exception as e:
            print(str(e))
            return []

    def clear_cache(self):
        """
        Clear the cache
        """
        self.tmdb.cache_clear()

    def get_tv_episode_years(self, tv_id: int):
        """
        Check the year of the episode group
        """
        try:
            episode_groups = self.tv.episode_groups(tv_id)
            if not episode_groups:
                return {}
            episode_years = {}
            for episode_group in episode_groups:
                logger.info(f" The year of the episode group is being obtained：{episode_group.get('id')}...")
                if episode_group.get('type') != 6:
                    #  Processing only the episode portion
                    continue
                group_episodes = self.tv.group_episodes(episode_group.get('id'))
                if not group_episodes:
                    continue
                for group_episode in group_episodes:
                    order = group_episode.get('order')
                    episodes = group_episode.get('episodes')
                    if not episodes or not order:
                        continue
                    #  Current season season 1 time
                    first_date = episodes[0].get("air_date")
                    if not first_date and str(first_date).split("-") != 3:
                        continue
                    episode_years[order] = str(first_date).split("-")[0]
            return episode_years
        except Exception as e:
            print(str(e))
            return {}
