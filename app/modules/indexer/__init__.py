from datetime import datetime
from typing import List, Optional, Tuple, Union

from ruamel.yaml import CommentedMap

from app.core.context import TorrentInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.indexer.mtorrent import MTorrentSpider
from app.modules.indexer.spider import TorrentSpider
from app.modules.indexer.tnode import TNodeSpider
from app.modules.indexer.torrentleech import TorrentLeech
from app.schemas.types import MediaType
from app.utils.string import StringUtils


class IndexerModule(_ModuleBase):
    """
    Indexing module
    """

    def init_module(self) -> None:
        pass

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "INDEXER", "builtin"

    def search_torrents(self, site: CommentedMap,
                        keywords: List[str] = None,
                        mtype: MediaType = None,
                        page: int = 0) -> List[TorrentInfo]:
        """
        Search a site
        :param site:   Website
        :param keywords:   Search keyword list
        :param mtype:   Media type
        :param page:   Pagination
        :return:  Resource list
        """
        #  Confirm the name of the search
        if not keywords:
            #  View seed page
            keywords = [None]

        #  Start indexing
        result_array = []
        #  Start counting
        start_time = datetime.now()

        #  Search for multiple keywords
        for search_word in keywords:
            #  May be a keyword orttxxxx
            if search_word \
                    and site.get('language') == "en" \
                    and StringUtils.is_chinese(search_word):
                #  No chinese support
                logger.warn(f"{site.get('name')}  Chinese search is not supported")
                continue

            #  Remove special characters from search keywords
            if search_word:
                search_word = StringUtils.clear(search_word, replace_word=" ", allow_space=True)

            try:
                if site.get('parser') == "TNodeSpider":
                    error_flag, result_array = TNodeSpider(site).search(
                        keyword=search_word,
                        page=page
                    )
                elif site.get('parser') == "TorrentLeech":
                    error_flag, result_array = TorrentLeech(site).search(
                        keyword=search_word,
                        page=page
                    )
                elif site.get('parser') == "mTorrent":
                    error_flag, result_array = MTorrentSpider(site).search(
                        keyword=search_word,
                        mtype=mtype,
                        page=page
                    )
                else:
                    error_flag, result_array = self.__spider_search(
                        search_word=search_word,
                        indexer=site,
                        mtype=mtype,
                        page=page
                    )
                #  Stop when results are available
                if result_array:
                    break
            except Exception as err:
                logger.error(f"{site.get('name')}  Search error：{err}")

        #  Time spent indexing
        seconds = round((datetime.now() - start_time).seconds, 1)

        #  Return results
        if not result_array or len(result_array) == 0:
            logger.warn(f"{site.get('name')}  No data searched， Take a period of (x amount of time) {seconds}  Unit of angle or arc equivalent one sixtieth of a degree")
            return []
        else:
            logger.info(f"{site.get('name')}  Search complete， Take a period of (x amount of time) {seconds}  Unit of angle or arc equivalent one sixtieth of a degree， Return data：{len(result_array)}")
            #  Consolidation of site information， In order toTorrentInfo Come (or go) back
            return [TorrentInfo(site=site.get("id"),
                                site_name=site.get("name"),
                                site_cookie=site.get("cookie"),
                                site_ua=site.get("ua"),
                                site_proxy=site.get("proxy"),
                                site_order=site.get("pri"),
                                **result) for result in result_array]

    @staticmethod
    def __spider_search(indexer: CommentedMap,
                        search_word: str = None,
                        mtype: MediaType = None,
                        page: int = 0) -> (bool, List[dict]):
        """
        Search individual sites by keywords
        :param: indexer:  Site configuration
        :param: search_word:  Keywords.
        :param: page:  Pagination
        :param: mtype:  Media type
        :param: timeout:  Timeout
        :return:  Whether an error has occurred,  Seed list
        """
        _spider = TorrentSpider(indexer=indexer,
                                mtype=mtype,
                                keyword=search_word,
                                page=page)

        return _spider.is_error, _spider.get_torrents()

    def refresh_torrents(self, site: CommentedMap) -> Optional[List[TorrentInfo]]:
        """
        Get seeds for the latest page of the site， Multiple sites require multithreading
        :param site:   Website
        :reutrn:  List of seed resources
        """
        return self.search_torrents(site=site)
