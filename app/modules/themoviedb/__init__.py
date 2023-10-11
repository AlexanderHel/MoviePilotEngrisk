from pathlib import Path
from typing import Optional, List, Tuple, Union

from app import schemas
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.log import logger
from app.modules import _ModuleBase
from app.modules.themoviedb.category import CategoryHelper
from app.modules.themoviedb.scraper import TmdbScraper
from app.modules.themoviedb.tmdb_cache import TmdbCache
from app.modules.themoviedb.tmdbapi import TmdbHelper
from app.schemas.types import MediaType, MediaImageType
from app.utils.system import SystemUtils


class TheMovieDbModule(_ModuleBase):
    """
    TMDB Media information matching
    """

    #  Metadata cache
    cache: TmdbCache = None
    # TMDB
    tmdb: TmdbHelper = None
    #  Secondary classification
    category: CategoryHelper = None
    #  Scraper
    scraper: TmdbScraper = None

    def init_module(self) -> None:
        self.cache = TmdbCache()
        self.tmdb = TmdbHelper()
        self.category = CategoryHelper()
        self.scraper = TmdbScraper(self.tmdb)

    def stop(self):
        self.cache.save()

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

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
        if not meta:
            cache_info = {}
        else:
            if mtype:
                meta.type = mtype
            cache_info = self.cache.get(meta)
        if not cache_info:
            #  Cache no or force no cache
            if tmdbid:
                #  Direct access to details
                info = self.tmdb.get_info(mtype=mtype, tmdbid=tmdbid)
            elif meta:
                if meta.begin_season:
                    logger.info(f"Recognizing {meta.name} season {meta.begin_season}...")
                else:
                    logger.info(f" Recognition in progress {meta.name} ...")
                if meta.type == MediaType.UNKNOWN and not meta.year:
                    info = self.tmdb.match_multi(meta.name)
                else:
                    if meta.type == MediaType.TV:
                        #  Make sure it's a tv.
                        info = self.tmdb.match(name=meta.name,
                                               year=meta.year,
                                               mtype=meta.type,
                                               season_year=meta.year,
                                               season_number=meta.begin_season)
                        if not info:
                            #  Remove the year and check again.
                            info = self.tmdb.match(name=meta.name,
                                                   mtype=meta.type)
                    else:
                        #  Look up the year by movie first.
                        info = self.tmdb.match(name=meta.name,
                                               year=meta.year,
                                               mtype=MediaType.MOVIE)
                        #  No more tv shows.
                        if not info:
                            info = self.tmdb.match(name=meta.name,
                                                   year=meta.year,
                                                   mtype=MediaType.TV)
                        if not info:
                            #  Remove the year and type and check again
                            info = self.tmdb.match_multi(name=meta.name)

                if not info:
                    #  Search from website
                    info = self.tmdb.match_web(name=meta.name,
                                               mtype=meta.type)
                #  Supplementary full information
                if info and not info.get("genres"):
                    info = self.tmdb.get_info(mtype=info.get("media_type"),
                                              tmdbid=info.get("id"))
            else:
                logger.error("Identify media messages时未提供元数据或tmdbid")
                return None
            #  Save to cache
            if meta:
                self.cache.update(meta, info)
        else:
            #  Using cached information
            if cache_info.get("title"):
                logger.info(f"{meta.name}  Using the recognition cache：{cache_info.get('title')}")
                info = self.tmdb.get_info(mtype=cache_info.get("type"),
                                          tmdbid=cache_info.get("id"))
            else:
                logger.info(f"{meta.name}  Using the recognition cache： Unrecognizable")
                info = None

        if info:
            #  Identification of secondary classifications
            if info.get('media_type') == MediaType.TV:
                cat = self.category.get_tv_category(info)
            else:
                cat = self.category.get_movie_category(info)
            #  Assign a value to somethingTMDB Message and returns the
            mediainfo = MediaInfo(tmdb_info=info)
            mediainfo.set_category(cat)
            if meta:
                logger.info(f"{meta.name}  Identification results：{mediainfo.type.value} "
                            f"{mediainfo.title_year} "
                            f"{mediainfo.tmdb_id}")
            else:
                logger.info(f"{tmdbid}  Identification results：{mediainfo.type.value} "
                            f"{mediainfo.title_year}")

            #  Year of additional episodes
            if mediainfo.type == MediaType.TV:
                episode_years = self.tmdb.get_tv_episode_years(info.get("id"))
                if episode_years:
                    mediainfo.season_years = episode_years
            return mediainfo
        else:
            logger.info(f"{meta.name if meta else tmdbid}  No media matches were found")

        return None

    def tmdb_info(self, tmdbid: int, mtype: MediaType) -> Optional[dict]:
        """
        GainTMDB Text
        :param tmdbid: int
        :param mtype:   Media type
        :return: TVDB Text
        """
        return self.tmdb.get_info(mtype=mtype, tmdbid=tmdbid)

    def search_medias(self, meta: MetaBase) -> Optional[List[MediaInfo]]:
        """
        Search for media information
        :param meta:   Identified metadata
        :reutrn:  Media information list
        """
        #  Returns when not enabledNone
        if settings.SEARCH_SOURCE != "themoviedb":
            return None

        if not meta.name:
            return []
        if meta.type == MediaType.UNKNOWN and not meta.year:
            results = self.tmdb.search_multiis(meta.name)
        else:
            if meta.type == MediaType.UNKNOWN:
                results = self.tmdb.search_movies(meta.name, meta.year)
                results.extend(self.tmdb.search_tvs(meta.name, meta.year))
                #  Sorting in case of combined results
                results = sorted(
                    results,
                    key=lambda x: x.get("release_date") or x.get("first_air_date") or "0000-00-00",
                    reverse=True
                )
            elif meta.type == MediaType.MOVIE:
                results = self.tmdb.search_movies(meta.name, meta.year)
            else:
                results = self.tmdb.search_tvs(meta.name, meta.year)

        return [MediaInfo(tmdb_info=info) for info in results]

    def scrape_metadata(self, path: Path, mediainfo: MediaInfo) -> None:
        """
        Scraping metadata
        :param path:  Media file path
        :param mediainfo:   Identified media messages
        :return:  Success or failure
        """
        if settings.SCRAP_SOURCE != "themoviedb":
            return None

        if SystemUtils.is_bluray_dir(path):
            #  Blu-ray disk
            logger.info(f" Start scraping the original blu-ray discs：{path} ...")
            scrape_path = path / path.name
            self.scraper.gen_scraper_files(mediainfo=mediainfo,
                                           file_path=scrape_path)
        elif path.is_file():
            #  Single document
            logger.info(f" Start scraping media library files：{path} ...")
            self.scraper.gen_scraper_files(mediainfo=mediainfo,
                                           file_path=path)
        else:
            #  All files in the directory
            logger.info(f" Start scraping catalog：{path} ...")
            for file in SystemUtils.list_files(path, settings.RMT_MEDIAEXT):
                if not file:
                    continue
                self.scraper.gen_scraper_files(mediainfo=mediainfo,
                                               file_path=file)
        logger.info(f"{path}  Scraping finish")

    def tmdb_discover(self, mtype: MediaType, sort_by: str, with_genres: str, with_original_language: str,
                      page: int = 1) -> Optional[List[dict]]:
        """
        :param mtype:   Media type
        :param sort_by:   Sort by
        :param with_genres:   Typology
        :param with_original_language:   Multilingualism
        :param page:   Pagination
        :return:  Media information list
        """
        if mtype == MediaType.MOVIE:
            return self.tmdb.discover_movies(sort_by=sort_by,
                                             with_genres=with_genres,
                                             with_original_language=with_original_language,
                                             page=page)
        elif mtype == MediaType.TV:
            return self.tmdb.discover_tvs(sort_by=sort_by,
                                          with_genres=with_genres,
                                          with_original_language=with_original_language,
                                          page=page)
        else:
            return None

    def tmdb_trending(self, page: int = 1) -> List[dict]:
        """
        TMDB Fashionable trend
        :param page:  Page
        :return: TMDB Information list
        """
        return self.tmdb.trending.all_week(page=page)

    def tmdb_seasons(self, tmdbid: int) -> List[schemas.TmdbSeason]:
        """
        According toTMDBID Consult (a document etc)themoviedb All season information
        :param tmdbid:  TMDBID
        """
        tmdb_info = self.tmdb.get_info(tmdbid=tmdbid, mtype=MediaType.TV)
        if not tmdb_info:
            return []
        return [schemas.TmdbSeason(**season)
                for season in tmdb_info.get("seasons", []) if season.get("season_number")]

    def tmdb_episodes(self, tmdbid: int, season: int) -> List[schemas.TmdbEpisode]:
        """
        According toTMDBID Query all letters for a particular season
        :param tmdbid:  TMDBID
        :param season:   Classifier for seasonal crop yield or seasons of a tv series
        """
        season_info = self.tmdb.get_tv_season_detail(tmdbid=tmdbid, season=season)
        if not season_info:
            return []
        return [schemas.TmdbEpisode(**episode) for episode in season_info.get("episodes", [])]

    def scheduler_job(self) -> None:
        """
        Timed task， Each10 One call per minute
        """
        self.cache.save()

    def obtain_images(self, mediainfo: MediaInfo) -> Optional[MediaInfo]:
        """
        Supplemental grabbing of media information images
        :param mediainfo:   Identified media messages
        :return:  Updated media information
        """
        if mediainfo.logo_path \
                and mediainfo.poster_path \
                and mediainfo.backdrop_path:
            #  No pictures are missing
            return mediainfo
        #  Call (programming)TMDB Photo interface
        if mediainfo.type == MediaType.MOVIE:
            images = self.tmdb.get_movie_images(mediainfo.tmdb_id)
        else:
            images = self.tmdb.get_tv_images(mediainfo.tmdb_id)
        if not images:
            return mediainfo
        if isinstance(images, list):
            images = images[0]
        #  Background image
        if not mediainfo.backdrop_path:
            backdrops = images.get("backdrops")
            if backdrops:
                backdrops = sorted(backdrops, key=lambda x: x.get("vote_average"), reverse=True)
                mediainfo.backdrop_path = backdrops[0].get("file_path")
        #  Symbolize
        if not mediainfo.logo_path:
            logos = images.get("logos")
            if logos:
                logos = sorted(logos, key=lambda x: x.get("vote_average"), reverse=True)
                mediainfo.logo_path = logos[0].get("file_path")
        #  Playbill
        if not mediainfo.poster_path:
            posters = images.get("posters")
            if posters:
                posters = sorted(posters, key=lambda x: x.get("vote_average"), reverse=True)
                mediainfo.poster_path = posters[0].get("file_path")
        return mediainfo

    def obtain_specific_image(self, mediaid: Union[str, int], mtype: MediaType,
                              image_type: MediaImageType, image_prefix: str = "w500",
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
        if not str(mediaid).isdigit():
            return None
        #  Image relative path
        image_path = None
        image_prefix = image_prefix or "w500"
        if not season and not episode:
            tmdbinfo = self.tmdb.get_info(mtype=mtype, tmdbid=int(mediaid))
            if tmdbinfo:
                image_path = tmdbinfo.get(image_type.value)
        elif season and episode:
            episodeinfo = self.tmdb.get_tv_episode_detail(tmdbid=int(mediaid), season=season, episode=episode)
            if episodeinfo:
                image_path = episodeinfo.get("still_path")
        elif season:
            seasoninfo = self.tmdb.get_tv_season_detail(tmdbid=int(mediaid), season=season)
            if seasoninfo:
                image_path = seasoninfo.get(image_type.value)

        if image_path:
            return f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/{image_prefix}{image_path}"
        return None

    def movie_similar(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Search for similar movies
        :param tmdbid:  TMDBID
        """
        return self.tmdb.get_movie_similar(tmdbid=tmdbid)

    def tv_similar(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Search for similar tv series
        :param tmdbid:  TMDBID
        """
        return self.tmdb.get_tv_similar(tmdbid=tmdbid)

    def movie_recommend(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Check recommended movies
        :param tmdbid:  TMDBID
        """
        return self.tmdb.get_movie_recommend(tmdbid=tmdbid)

    def tv_recommend(self, tmdbid: int) -> List[dict]:
        """
        According toTMDBID Search for recommended tv series
        :param tmdbid:  TMDBID
        """
        return self.tmdb.get_tv_recommend(tmdbid=tmdbid)

    def movie_credits(self, tmdbid: int, page: int = 1) -> List[dict]:
        """
        According toTMDBID Check movie cast list
        :param tmdbid:  TMDBID
        :param page:   Pagination
        """
        return self.tmdb.get_movie_credits(tmdbid=tmdbid, page=page)

    def tv_credits(self, tmdbid: int, page: int = 1) -> List[dict]:
        """
        According toTMDBID Check drama cast list
        :param tmdbid:  TMDBID
        :param page:   Pagination
        """
        return self.tmdb.get_tv_credits(tmdbid=tmdbid, page=page)

    def person_detail(self, person_id: int) -> dict:
        """
        According toTMDBID Check character details
        :param person_id:   Character (in a play, novel etc)ID
        """
        return self.tmdb.get_person_detail(person_id=person_id)

    def person_credits(self, person_id: int, page: int = 1) -> List[dict]:
        """
        According toTMDBID Enquire about a person's acting credits
        :param person_id:   Character (in a play, novel etc)ID
        :param page:   Pagination
        """
        return self.tmdb.get_person_credits(person_id=person_id, page=page)

    def clear_cache(self):
        """
        Clear the cache
        """
        self.tmdb.clear_cache()
        self.cache.clear()
