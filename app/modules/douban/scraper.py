import time
from pathlib import Path
from xml.dom import minidom

from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.log import logger
from app.schemas.types import MediaType
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils


class DoubanScraper:

    def gen_scraper_files(self, meta: MetaBase, mediainfo: MediaInfo, file_path: Path):
        """
        Generate scraping files
        :param meta:  Metadata
        :param mediainfo:  Media information
        :param file_path:  File path or directory path
        """

        try:
            #  Cinematic
            if mediainfo.type == MediaType.MOVIE:
                #  Mandatory or dealt with when it no longer exists
                if not file_path.with_name("movie.nfo").exists() \
                        and not file_path.with_suffix(".nfo").exists():
                    #   Generate movie description file
                    self.__gen_movie_nfo_file(mediainfo=mediainfo,
                                              file_path=file_path)
                #  Generate movie images
                self.__save_image(url=mediainfo.poster_path,
                                  file_path=file_path.with_name(f"poster{Path(mediainfo.poster_path).suffix}"))
            #  Dramas
            else:
                #  Handle when it doesn't exist
                if not file_path.parent.with_name("tvshow.nfo").exists():
                    #  Root directory description file
                    self.__gen_tv_nfo_file(mediainfo=mediainfo,
                                           dir_path=file_path.parents[1])
                #  Generate root directory image
                self.__save_image(url=mediainfo.poster_path,
                                  file_path=file_path.with_name(f"poster{Path(mediainfo.poster_path).suffix}"))
                #  Quarterly catalogNFO
                if not file_path.with_name("season.nfo").exists():
                    self.__gen_tv_season_nfo_file(mediainfo=mediainfo,
                                                  season=meta.begin_season,
                                                  season_path=file_path.parent)
        except Exception as e:
            logger.error(f"{file_path}  Scraping failure：{e}")

    @staticmethod
    def __gen_common_nfo(mediainfo: MediaInfo, doc, root):
        #  Add time
        DomUtils.add_node(doc, root, "dateadded",
                          time.strftime('%Y-%m-%d %H:%M:%S',
                                        time.localtime(time.time())))
        #  Synopsis
        xplot = DomUtils.add_node(doc, root, "plot")
        xplot.appendChild(doc.createCDATASection(mediainfo.overview or ""))
        xoutline = DomUtils.add_node(doc, root, "outline")
        xoutline.appendChild(doc.createCDATASection(mediainfo.overview or ""))
        #  Director (film etc)
        for director in mediainfo.directors:
            DomUtils.add_node(doc, root, "director", director.get("name") or "")
        #  Actor or actress
        for actor in mediainfo.actors:
            xactor = DomUtils.add_node(doc, root, "actor")
            DomUtils.add_node(doc, xactor, "name", actor.get("name") or "")
            DomUtils.add_node(doc, xactor, "type", "Actor")
            DomUtils.add_node(doc, xactor, "role", actor.get("character") or actor.get("role") or "")
            DomUtils.add_node(doc, xactor, "thumb", actor.get('avatar', {}).get('normal'))
            DomUtils.add_node(doc, xactor, "profile", actor.get('url'))
        #  Score (of student's work)
        DomUtils.add_node(doc, root, "rating", mediainfo.vote_average or "0")

        return doc

    def __gen_movie_nfo_file(self,
                             mediainfo: MediaInfo,
                             file_path: Path):
        """
        Movie-generatingNFO Description file
        :param mediainfo:  Douban information
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
        #  Particular year
        DomUtils.add_node(doc, root, "year", mediainfo.year or "")
        DomUtils.add_node(doc, root, "season", "-1")
        DomUtils.add_node(doc, root, "episode", "-1")
        #  Save (a file etc) (computing)
        self.__save_nfo(doc, dir_path.joinpath("tvshow.nfo"))

    def __gen_tv_season_nfo_file(self, mediainfo: MediaInfo, season: int, season_path: Path):
        """
        Generate tv season'sNFO Description file
        :param mediainfo:  Media information
        :param season:  Quarter
        :param season_path:  Catalog of the tv season
        """
        logger.info(f" Season in progressNFO File：{season_path.name}")
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "season")
        #  Add time
        DomUtils.add_node(doc, root, "dateadded", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        #  Synopsis
        xplot = DomUtils.add_node(doc, root, "plot")
        xplot.appendChild(doc.createCDATASection(mediainfo.overview or ""))
        xoutline = DomUtils.add_node(doc, root, "outline")
        xoutline.appendChild(doc.createCDATASection(mediainfo.overview or ""))
        #  Caption
        DomUtils.add_node(doc, root, "title", " Classifier for seasonal crop yield or seasons of a tv series %s" % season)
        #  Issue date
        DomUtils.add_node(doc, root, "premiered", mediainfo.release_date or "")
        DomUtils.add_node(doc, root, "releasedate", mediainfo.release_date or "")
        #  Year of issue
        DomUtils.add_node(doc, root, "year", mediainfo.release_date[:4] if mediainfo.release_date else "")
        # seasonnumber
        DomUtils.add_node(doc, root, "seasonnumber", str(season))
        #  Save (a file etc) (computing)
        self.__save_nfo(doc, season_path.joinpath("season.nfo"))

    @staticmethod
    def __save_image(url: str, file_path: Path):
        """
        Download the image and save it
        """
        if file_path.exists():
            return
        try:
            logger.info(f" Downloading{file_path.stem} Photograph：{url} ...")
            r = RequestUtils().get_res(url=url)
            if r:
                file_path.write_bytes(r.content)
                logger.info(f" Picture saved：{file_path}")
            else:
                logger.info(f"{file_path.stem} Image download failed， Please check network connectivity")
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
