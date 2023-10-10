import time
from pathlib import Path
from xml.dom import minidom

from requests import RequestException

from app.core.config import settings
from app.core.context import MediaInfo
from app.core.metainfo import MetaInfo
from app.log import logger
from app.schemas.types import MediaType
from app.utils.common import retry
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils


class TmdbScraper:
    tmdb = None

    def __init__(self, tmdb):
        self.tmdb = tmdb

    def gen_scraper_files(self, mediainfo: MediaInfo, file_path: Path):
        """
        Generate scraping files， Including throughNFO And pictures， The incoming path is the file path
        :param mediainfo:  Media information
        :param file_path:  File path or directory path
        """

        def __get_episode_detail(_seasoninfo: dict, _episode: int):
            """
            Getting information about sets based on seasonal information
            """
            for _episode_info in _seasoninfo.get("episodes") or []:
                if _episode_info.get("episode_number") == _episode:
                    return _episode_info
            return {}

        try:
            #  Cinematic， Path is the filename  Name (of a thing)/ Name (of a thing).xxx  Or the original blu-ray catalog  Name (of a thing)/ Name (of a thing)
            if mediainfo.type == MediaType.MOVIE:
                #  Deal with it when it doesn't already exist
                if not file_path.with_name("movie.nfo").exists() \
                        and not file_path.with_suffix(".nfo").exists():
                    #   Generate movie description file
                    self.__gen_movie_nfo_file(mediainfo=mediainfo,
                                              file_path=file_path)
                #  Generate movie images
                for attr_name, attr_value in vars(mediainfo).items():
                    if attr_value \
                            and attr_name.endswith("_path") \
                            and attr_value \
                            and isinstance(attr_value, str) \
                            and attr_value.startswith("http"):
                        image_name = attr_name.replace("_path", "") + Path(attr_value).suffix
                        self.__save_image(url=attr_value,
                                          file_path=file_path.with_name(image_name))
            #  Dramas， The path is the filename of each quarter  Name (of a thing)/Season xx/ Name (of a thing) SxxExx.xxx
            else:
                #  Recognize
                meta = MetaInfo(file_path.stem)
                #  Processing when the root directory does not exist
                if not file_path.parent.with_name("tvshow.nfo").exists():
                    #  Root directory description file
                    self.__gen_tv_nfo_file(mediainfo=mediainfo,
                                           dir_path=file_path.parents[1])
                #  Generate root directory image
                for attr_name, attr_value in vars(mediainfo).items():
                    if attr_value \
                            and attr_name.endswith("_path") \
                            and not attr_name.startswith("season") \
                            and attr_value \
                            and isinstance(attr_value, str) \
                            and attr_value.startswith("http"):
                        image_name = attr_name.replace("_path", "") + Path(attr_value).suffix
                        self.__save_image(url=attr_value,
                                          file_path=file_path.parent.with_name(image_name))
                #  Query season information
                seasoninfo = self.tmdb.get_tv_season_detail(mediainfo.tmdb_id, meta.begin_season)
                if seasoninfo:
                    #  Quarterly catalogNFO
                    if not file_path.with_name("season.nfo").exists():
                        self.__gen_tv_season_nfo_file(seasoninfo=seasoninfo,
                                                      season=meta.begin_season,
                                                      season_path=file_path.parent)
                    # TMDB Classifier for seasonal crop yield or seasons of a tv seriesposter Photograph
                    sea_seq = str(meta.begin_season).rjust(2, '0')
                    if seasoninfo.get("poster_path"):
                        #  Suffix (linguistics)
                        ext = Path(seasoninfo.get('poster_path')).suffix
                        # URL
                        url = f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{seasoninfo.get('poster_path')}"
                        self.__save_image(url, file_path.parent.with_name(f"season{sea_seq}-poster{ext}"))
                    #  Other pictures of season
                    for attr_name, attr_value in vars(mediainfo).items():
                        if attr_value \
                                and attr_name.startswith("season") \
                                and not attr_name.endswith("poster_path") \
                                and attr_value \
                                and isinstance(attr_value, str) \
                                and attr_value.startswith("http"):
                            image_name = attr_name.replace("_path", "") + Path(attr_value).suffix
                            self.__save_image(url=attr_value,
                                              file_path=file_path.parent.with_name(image_name))
                #  Inquiry set details
                episodeinfo = __get_episode_detail(seasoninfo, meta.begin_episode)
                if episodeinfo:
                    #  Classifier for sections of a tv series e.g. episodeNFO
                    if not file_path.with_suffix(".nfo").exists():
                        self.__gen_tv_episode_nfo_file(episodeinfo=episodeinfo,
                                                       tmdbid=mediainfo.tmdb_id,
                                                       season=meta.begin_season,
                                                       episode=meta.begin_episode,
                                                       file_path=file_path)
                    #  Pictures of the set
                    episode_image = episodeinfo.get("still_path")
                    if episode_image:
                        self.__save_image(
                            f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{episode_image}",
                            file_path.with_suffix(Path(episode_image).suffix))
        except Exception as e:
            logger.error(f"{file_path}  Scraping failure：{e}")

    @staticmethod
    def __gen_common_nfo(mediainfo: MediaInfo, doc, root):
        """
        Generate publicNFO
        """
        #  Add time
        DomUtils.add_node(doc, root, "dateadded",
                          time.strftime('%Y-%m-%d %H:%M:%S',
                                        time.localtime(time.time())))
        # TMDB
        DomUtils.add_node(doc, root, "tmdbid", mediainfo.tmdb_id or "")
        uniqueid_tmdb = DomUtils.add_node(doc, root, "uniqueid", mediainfo.tmdb_id or "")
        uniqueid_tmdb.setAttribute("type", "tmdb")
        uniqueid_tmdb.setAttribute("default", "true")
        # TVDB
        if mediainfo.tvdb_id:
            DomUtils.add_node(doc, root, "tvdbid", str(mediainfo.tvdb_id))
            uniqueid_tvdb = DomUtils.add_node(doc, root, "uniqueid", str(mediainfo.tvdb_id))
            uniqueid_tvdb.setAttribute("type", "tvdb")
        # IMDB
        if mediainfo.imdb_id:
            DomUtils.add_node(doc, root, "imdbid", mediainfo.imdb_id)
            uniqueid_imdb = DomUtils.add_node(doc, root, "uniqueid", mediainfo.imdb_id)
            uniqueid_imdb.setAttribute("type", "imdb")
            uniqueid_imdb.setAttribute("default", "true")
            uniqueid_tmdb.setAttribute("default", "false")

        #  Synopsis
        xplot = DomUtils.add_node(doc, root, "plot")
        xplot.appendChild(doc.createCDATASection(mediainfo.overview or ""))
        xoutline = DomUtils.add_node(doc, root, "outline")
        xoutline.appendChild(doc.createCDATASection(mediainfo.overview or ""))
        #  Director (film etc)
        for director in mediainfo.directors:
            xdirector = DomUtils.add_node(doc, root, "director", director.get("name") or "")
            xdirector.setAttribute("tmdbid", str(director.get("id") or ""))
        #  Actor or actress
        for actor in mediainfo.actors:
            #  Get chinese name
            xactor = DomUtils.add_node(doc, root, "actor")
            DomUtils.add_node(doc, xactor, "name", actor.get("name") or "")
            DomUtils.add_node(doc, xactor, "type", "Actor")
            DomUtils.add_node(doc, xactor, "role", actor.get("character") or actor.get("role") or "")
            DomUtils.add_node(doc, xactor, "tmdbid", actor.get("id") or "")
            DomUtils.add_node(doc, xactor, "thumb",
                              f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{actor.get('profile_path')}")
            DomUtils.add_node(doc, xactor, "profile",
                              f"https://www.themoviedb.org/person/{actor.get('id')}")
        #  Hairstyle
        genres = mediainfo.genres or []
        for genre in genres:
            DomUtils.add_node(doc, root, "genre", genre.get("name") or "")
        #  Score (of student's work)
        DomUtils.add_node(doc, root, "rating", mediainfo.vote_average or "0")

        return doc

    def __gen_movie_nfo_file(self,
                             mediainfo: MediaInfo,
                             file_path: Path):
        """
        Movie-generatingNFO Description file
        :param mediainfo:  Recognized media messages
        :param file_path:  Movie file path
        """
        #  Start generatingXML
        logger.info(f" Movie being generatedNFO File：{file_path.name}")
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "movie")
        #  Public section
        doc = self.__gen_common_nfo(mediainfo=mediainfo,
                                    doc=doc,
                                    root=root)
        #  Caption
        DomUtils.add_node(doc, root, "title", mediainfo.title or "")
        DomUtils.add_node(doc, root, "originaltitle", mediainfo.original_title or "")
        #  Release date
        DomUtils.add_node(doc, root, "premiered", mediainfo.release_date or "")
        #  Particular year
        DomUtils.add_node(doc, root, "year", mediainfo.year or "")
        #  Save (a file etc) (computing)
        self.__save_nfo(doc, file_path.with_suffix(".nfo"))

    def __gen_tv_nfo_file(self,
                          mediainfo: MediaInfo,
                          dir_path: Path):
        """
        Generating a tv seriesNFO Description file
        :param mediainfo:  Media information
        :param dir_path:  Tv series roots
        """
        #  Start generatingXML
        logger.info(f" Tv series being generatedNFO File：{dir_path.name}")
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "tvshow")
        #  Public section
        doc = self.__gen_common_nfo(mediainfo=mediainfo,
                                    doc=doc,
                                    root=root)
        #  Caption
        DomUtils.add_node(doc, root, "title", mediainfo.title or "")
        DomUtils.add_node(doc, root, "originaltitle", mediainfo.original_title or "")
        #  Release date
        DomUtils.add_node(doc, root, "premiered", mediainfo.release_date or "")
        #  Particular year
        DomUtils.add_node(doc, root, "year", mediainfo.year or "")
        DomUtils.add_node(doc, root, "season", "-1")
        DomUtils.add_node(doc, root, "episode", "-1")
        #  Save (a file etc) (computing)
        self.__save_nfo(doc, dir_path.joinpath("tvshow.nfo"))

    def __gen_tv_season_nfo_file(self, seasoninfo: dict, season: int, season_path: Path):
        """
        Generate tv season'sNFO Description file
        :param seasoninfo: TMDB Seasonal media information
        :param season:  Quarter
        :param season_path:  Catalog of the tv season
        """
        logger.info(f" Season in progressNFO File：{season_path.name}")
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "season")
        #  Add time
        DomUtils.add_node(doc, root, "dateadded",
                          time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        #  Synopsis
        xplot = DomUtils.add_node(doc, root, "plot")
        xplot.appendChild(doc.createCDATASection(seasoninfo.get("overview") or ""))
        xoutline = DomUtils.add_node(doc, root, "outline")
        xoutline.appendChild(doc.createCDATASection(seasoninfo.get("overview") or ""))
        #  Caption
        DomUtils.add_node(doc, root, "title", " Classifier for seasonal crop yield or seasons of a tv series %s" % season)
        #  Issue date
        DomUtils.add_node(doc, root, "premiered", seasoninfo.get("air_date") or "")
        DomUtils.add_node(doc, root, "releasedate", seasoninfo.get("air_date") or "")
        #  Year of issue
        DomUtils.add_node(doc, root, "year",
                          seasoninfo.get("air_date")[:4] if seasoninfo.get("air_date") else "")
        # seasonnumber
        DomUtils.add_node(doc, root, "seasonnumber", str(season))
        #  Save (a file etc) (computing)
        self.__save_nfo(doc, season_path.joinpath("season.nfo"))

    def __gen_tv_episode_nfo_file(self,
                                  tmdbid: int,
                                  episodeinfo: dict,
                                  season: int,
                                  episode: int,
                                  file_path: Path):
        """
        Generate tv episodes ofNFO Description file
        :param tmdbid: TMDBID
        :param episodeinfo:  Classifier for sections of a tv series e.g. episodeTMDB Metadata
        :param season:  Quarter
        :param episode:  Bugle call
        :param file_path:  Path to the set file
        """
        #  Information to start generating sets
        logger.info(f" Episodes being generatedNFO File：{file_path.name}")
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "episodedetails")
        #  Add time
        DomUtils.add_node(doc, root, "dateadded", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        # TMDBID
        uniqueid = DomUtils.add_node(doc, root, "uniqueid", str(tmdbid))
        uniqueid.setAttribute("type", "tmdb")
        uniqueid.setAttribute("default", "true")
        # tmdbid
        DomUtils.add_node(doc, root, "tmdbid", str(tmdbid))
        #  Caption
        DomUtils.add_node(doc, root, "title", episodeinfo.get("name") or " (prefix indicating ordinal number, e.g. first, number two etc) %s  Classifier for sections of a tv series e.g. episode" % episode)
        #  Synopsis
        xplot = DomUtils.add_node(doc, root, "plot")
        xplot.appendChild(doc.createCDATASection(episodeinfo.get("overview") or ""))
        xoutline = DomUtils.add_node(doc, root, "outline")
        xoutline.appendChild(doc.createCDATASection(episodeinfo.get("overview") or ""))
        #  Release date
        DomUtils.add_node(doc, root, "aired", episodeinfo.get("air_date") or "")
        #  Particular year
        DomUtils.add_node(doc, root, "year",
                          episodeinfo.get("air_date")[:4] if episodeinfo.get("air_date") else "")
        #  Classifier for seasonal crop yield or seasons of a tv series
        DomUtils.add_node(doc, root, "season", str(season))
        #  Classifier for sections of a tv series e.g. episode
        DomUtils.add_node(doc, root, "episode", str(episode))
        #  Score (of student's work)
        DomUtils.add_node(doc, root, "rating", episodeinfo.get("vote_average") or "0")
        #  Director (film etc)
        directors = episodeinfo.get("crew") or []
        for director in directors:
            if director.get("known_for_department") == "Directing":
                xdirector = DomUtils.add_node(doc, root, "director", director.get("name") or "")
                xdirector.setAttribute("tmdbid", str(director.get("id") or ""))
        #  Actor or actress
        actors = episodeinfo.get("guest_stars") or []
        for actor in actors:
            if actor.get("known_for_department") == "Acting":
                xactor = DomUtils.add_node(doc, root, "actor")
                DomUtils.add_node(doc, xactor, "name", actor.get("name") or "")
                DomUtils.add_node(doc, xactor, "type", "Actor")
                DomUtils.add_node(doc, xactor, "tmdbid", actor.get("id") or "")
                DomUtils.add_node(doc, xactor, "thumb",
                                  f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{actor.get('profile_path')}")
                DomUtils.add_node(doc, xactor, "profile",
                                  f"https://www.themoviedb.org/person/{actor.get('id')}")
        #  Save (a file etc) (computing)文件
        self.__save_nfo(doc, file_path.with_suffix(".nfo"))

    @staticmethod
    @retry(RequestException, logger=logger)
    def __save_image(url: str, file_path: Path):
        """
        Download the image and save it
        """
        if file_path.exists():
            return
        try:
            logger.info(f" Downloading{file_path.stem} Photograph：{url} ...")
            r = RequestUtils().get_res(url=url, raise_exception=True)
            if r:
                file_path.write_bytes(r.content)
                logger.info(f" Picture saved：{file_path}")
            else:
                logger.info(f"{file_path.stem} Image download failed， Please check network connectivity")
        except RequestException as err:
            raise err
        except Exception as err:
            logger.error(f"{file_path.stem} Image download failed：{err}")

    @staticmethod
    def __save_nfo(doc, file_path: Path):
        """
        Save (a file etc) (computing)NFO
        """
        if file_path.exists():
            return
        xml_str = doc.toprettyxml(indent="  ", encoding="utf-8")
        file_path.write_bytes(xml_str)
        logger.info(f"NFO Document saved：{file_path}")
