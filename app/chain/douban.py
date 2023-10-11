from typing import Optional, List

from app.chain import ChainBase
from app.core.context import Context
from app.core.context import MediaInfo
from app.core.metainfo import MetaInfo
from app.log import logger
from app.schemas import MediaType


class DoubanChain(ChainBase):
    """
    Bean processing chain
    """

    def recognize_by_doubanid(self, doubanid: str) -> Optional[Context]:
        """
        According to doubanID Identify media messages
        """
        logger.info(f' Start recognizing media messages， Douban, prc social networking websiteID：{doubanid} ...')
        #  Check douban information
        doubaninfo = self.douban_info(doubanid=doubanid)
        if not doubaninfo:
            logger.warn(f' No doujinshi information has been found， Douban, prc social networking websiteID：{doubanid}')
            return None
        return self.recognize_by_doubaninfo(doubaninfo)

    def recognize_by_doubaninfo(self, doubaninfo: dict) -> Optional[Context]:
        """
        Identify media information based on beanbag information
        """
        #  Prioritize the use of original title matches
        season_meta = None
        if doubaninfo.get("original_title"):
            meta = MetaInfo(title=doubaninfo.get("original_title"))
            season_meta = MetaInfo(title=doubaninfo.get("title"))
            #  Merger season
            meta.begin_season = season_meta.begin_season
        else:
            meta = MetaInfo(title=doubaninfo.get("title"))
        #  Particular year
        if doubaninfo.get("year"):
            meta.year = doubaninfo.get("year")
        #  Type of treatment
        if isinstance(doubaninfo.get('media_type'), MediaType):
            meta.type = doubaninfo.get('media_type')
        else:
            meta.type = MediaType.MOVIE if doubaninfo.get("type") == "movie" else MediaType.TV
        #  Identify media messages using the original headline
        mediainfo = self.recognize_media(meta=meta, mtype=meta.type)
        if not mediainfo:
            if season_meta and season_meta.name != meta.name:
                #  Identify media messages using the main headline
                mediainfo = self.recognize_media(meta=season_meta, mtype=season_meta.type)
            if not mediainfo:
                logger.warn(f'{meta.name}  Not recognizedTMDB Media information')
                return Context(meta_info=meta, media_info=MediaInfo(douban_info=doubaninfo))
        logger.info(f' Recognition of media messages：{mediainfo.type.value} {mediainfo.title_year} {meta.season}')
        mediainfo.set_douban_info(doubaninfo)
        return Context(meta_info=meta, media_info=mediainfo)

    def movie_top250(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get douban moviesTOP250
        :param page:   Pagination
        :param count:   Quantity per page
        """
        return self.run_module("movie_top250", page=page, count=count)

    def movie_showing(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get movies in theaters
        """
        return self.run_module("movie_showing", page=page, count=count)

    def tv_weekly_chinese(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get this week's top chinese dramas
        """
        return self.run_module("tv_weekly_chinese", page=page, count=count)

    def tv_weekly_global(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get this week's list of global episodes
        """
        return self.run_module("tv_weekly_global", page=page, count=count)

    def douban_discover(self, mtype: MediaType, sort: str, tags: str,
                        page: int = 0, count: int = 30) -> Optional[List[dict]]:
        """
        Discover douban movies、 Episode
        :param mtype:   Media type
        :param sort:   Sort by
        :param tags:   Tab (of a window) (computing)
        :param page:   Pagination
        :param count:   Quantities
        :return:  Media information list
        """
        return self.run_module("douban_discover", mtype=mtype, sort=sort, tags=tags,
                               page=page, count=count)

    def tv_animation(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get animated episodes
        """
        return self.run_module("tv_animation", page=page, count=count)
