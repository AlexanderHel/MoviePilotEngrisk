import pickle
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict
from typing import List, Optional

from sqlalchemy.orm import Session

from app.chain import ChainBase
from app.core.context import Context
from app.core.context import MediaInfo, TorrentInfo
from app.core.metainfo import MetaInfo
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.progress import ProgressHelper
from app.helper.sites import SitesHelper
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.schemas import NotExistMediaInfo
from app.schemas.types import MediaType, ProgressKey, SystemConfigKey
from app.utils.string import StringUtils


class SearchChain(ChainBase):
    """
    Site resource search processing chain
    """

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.siteshelper = SitesHelper()
        self.progress = ProgressHelper()
        self.systemconfig = SystemConfigOper()
        self.torrenthelper = TorrentHelper()

    def search_by_tmdbid(self, tmdbid: int, mtype: MediaType = None, area: str = "title") -> List[Context]:
        """
        According toTMDB ID Search resources， Exact match， But not without filtering locally available resources
        :param tmdbid: TMDB ID
        :param mtype:  Media, esp. news media， Cinematic or  Dramas
        :param area:  Search scope，title or imdbid
        """
        mediainfo = self.recognize_media(tmdbid=tmdbid, mtype=mtype)
        if not mediainfo:
            logger.error(f'{tmdbid}  Media message recognition failure！')
            return []
        results = self.process(mediainfo=mediainfo, area=area)
        #  Saving results
        bytes_results = pickle.dumps(results)
        self.systemconfig.set(SystemConfigKey.SearchResults, bytes_results)
        return results

    def search_by_title(self, title: str, page: int = 0, site: int = None) -> List[TorrentInfo]:
        """
        Search for resources by title， No recognition or filtering， Direct return to site content
        :param title:  Caption， Returns all site home contents when empty
        :param page:  Pagination
        :param site:  WebsiteID
        """
        if title:
            logger.info(f' Start searching for resources， Byword：{title} ...')
        else:
            logger.info(f' Start browsing resources， Website：{site} ...')
        #  Look for sth.
        return self.__search_all_sites(keywords=[title], sites=[site] if site else None, page=page) or []

    def last_search_results(self) -> List[Context]:
        """
        Get last search results
        """
        results = self.systemconfig.get(SystemConfigKey.SearchResults)
        if not results:
            return []
        try:
            return pickle.loads(results)
        except Exception as e:
            print(str(e))
            return []

    def process(self, mediainfo: MediaInfo,
                keyword: str = None,
                no_exists: Dict[int, Dict[int, NotExistMediaInfo]] = None,
                sites: List[int] = None,
                priority_rule: str = None,
                filter_rule: Dict[str, str] = None,
                area: str = "title") -> List[Context]:
        """
        Search for seed resources based on media information， Exact match， Apply filtering rules， At the same time, according tono_exists Filtering resources that already exist locally
        :param mediainfo:  Media information
        :param keyword:  Search keywords
        :param no_exists:  Missing media messages
        :param sites:  WebsiteID Listings， Search all sites when empty
        :param priority_rule:  Priority rules， Use search prioritization rules when empty
        :param filter_rule:  Filter rules， Null is to use the default filtering rules
        :param area:  Search scope，title or imdbid
        """
        logger.info(f' Start searching for resources， Byword：{keyword or mediainfo.title} ...')
        #  Additional media information
        if not mediainfo.names:
            mediainfo: MediaInfo = self.recognize_media(mtype=mediainfo.type,
                                                        tmdbid=mediainfo.tmdb_id)
            if not mediainfo:
                logger.error(f' Media message recognition failure！')
                return []
        #  Missing seasonal episodes
        if no_exists and no_exists.get(mediainfo.tmdb_id):
            #  Filter episodes
            season_episodes = {sea: info.episodes
                               for sea, info in no_exists[mediainfo.tmdb_id].items()}
        else:
            season_episodes = None
        #  Look for sth.关键词
        if keyword:
            keywords = [keyword]
        elif mediainfo.original_title and mediainfo.title != mediainfo.original_title:
            keywords = [mediainfo.title, mediainfo.original_title]
        else:
            keywords = [mediainfo.title]
        #  Perform a search
        torrents: List[TorrentInfo] = self.__search_all_sites(
            mediainfo=mediainfo,
            keywords=keywords,
            sites=sites,
            area=area
        )
        if not torrents:
            logger.warn(f'{keyword or mediainfo.title}  No resources searched')
            return []
        #  Filtering seeds
        if priority_rule is None:
            #  Fetch search prioritization rules
            priority_rule = self.systemconfig.get(SystemConfigKey.SearchFilterRules)
        if priority_rule:
            logger.info(f' Start filtering resources， Current rule：{priority_rule} ...')
            result: List[TorrentInfo] = self.filter_torrents(rule_string=priority_rule,
                                                             torrent_list=torrents,
                                                             season_episodes=season_episodes,
                                                             mediainfo=mediainfo)
            if result is not None:
                torrents = result
            if not torrents:
                logger.warn(f'{keyword or mediainfo.title}  No resources that meet the prioritization rules')
                return []
        #  Filter again using the default filtering rules
        torrents = self.filter_torrents_by_rule(torrents=torrents,
                                                filter_rule=filter_rule)
        if not torrents:
            logger.warn(f'{keyword or mediainfo.title}  No resources matching the filtering rules')
            return []
        #  Matched resource
        _match_torrents = []
        #  Aggregate
        _total = len(torrents)
        #  Number processed
        _count = 0
        if mediainfo:
            self.progress.start(ProgressKey.Search)
            logger.info(f' Start matching， Assemble {_total}  Individual resource ...')
            self.progress.update(value=0, text=f' Start matching， Assemble {_total}  Individual resource ...', key=ProgressKey.Search)
            for torrent in torrents:
                _count += 1
                self.progress.update(value=(_count / _total) * 100,
                                     text=f' Matching. {torrent.site_name}， Done {_count} / {_total} ...',
                                     key=ProgressKey.Search)
                #  Verify by comparingIMDBID
                if torrent.imdbid \
                        and mediainfo.imdb_id \
                        and torrent.imdbid == mediainfo.imdb_id:
                    logger.info(f'{mediainfo.title}  Matching to resources：{torrent.site_name} - {torrent.title}')
                    _match_torrents.append(torrent)
                    continue
                #  Recognize
                torrent_meta = MetaInfo(title=torrent.title, subtitle=torrent.description)
                #  Type of comparison
                if (torrent_meta.type == MediaType.TV and mediainfo.type != MediaType.TV) \
                        or (torrent_meta.type != MediaType.TV and mediainfo.type == MediaType.TV):
                    logger.warn(f'{torrent.site_name} - {torrent.title}  Type mismatch')
                    continue
                #  Year of comparison
                if mediainfo.year:
                    if mediainfo.type == MediaType.TV:
                        #  Year of episode， Years may vary from season to season
                        if torrent_meta.year and torrent_meta.year not in [year for year in
                                                                           mediainfo.season_years.values()]:
                            logger.warn(f'{torrent.site_name} - {torrent.title}  Year mismatch')
                            continue
                    else:
                        #  Year of movie， Float up and down1 Surname nian
                        if torrent_meta.year not in [str(int(mediainfo.year) - 1),
                                                     mediainfo.year,
                                                     str(int(mediainfo.year) + 1)]:
                            logger.warn(f'{torrent.site_name} - {torrent.title}  Year mismatch')
                            continue
                #  Comparison of titles and original language titles
                meta_name = StringUtils.clear_upper(torrent_meta.name)
                if meta_name in [
                    StringUtils.clear_upper(mediainfo.title),
                    StringUtils.clear_upper(mediainfo.original_title)
                ]:
                    logger.info(f'{mediainfo.title}  Matching to resources by title：{torrent.site_name} - {torrent.title}')
                    _match_torrents.append(torrent)
                    continue
                #  Determining the presence of a title in a subtitle with the original language title
                if torrent.description:
                    subtitle = torrent.description.split()
                    if (StringUtils.is_chinese(mediainfo.title)
                        and str(mediainfo.title) in subtitle) \
                            or (StringUtils.is_chinese(mediainfo.original_title)
                                and str(mediainfo.original_title) in subtitle):
                        logger.info(f'{mediainfo.title}  Matching to resources by subheading：{torrent.site_name} - {torrent.title}，'
                                    f' Subheading：{torrent.description}')
                        _match_torrents.append(torrent)
                        continue
                #  Comparing aliases and translations
                for name in mediainfo.names:
                    if StringUtils.clear_upper(name) == meta_name:
                        logger.info(f'{mediainfo.title}  Match to resource by alias or translation：{torrent.site_name} - {torrent.title}')
                        _match_torrents.append(torrent)
                        break
                else:
                    logger.warn(f'{torrent.site_name} - {torrent.title}  Title mismatch')
            self.progress.update(value=100,
                                 text=f' Matching complete.， Total matches {len(_match_torrents)}  Individual resource',
                                 key=ProgressKey.Search)
            self.progress.end(ProgressKey.Search)
        else:
            _match_torrents = torrents
        logger.info(f" Matching complete.， Total matches {len(_match_torrents)}  Individual resource")
        #  Get rid ofmediainfo Redundant data in the
        mediainfo.clear()
        #  Assembly context
        contexts = [Context(meta_info=MetaInfo(title=torrent.title, subtitle=torrent.description),
                            media_info=mediainfo,
                            torrent_info=torrent) for torrent in _match_torrents]
        #  Arrange in order
        contexts = self.torrenthelper.sort_torrents(contexts)
        #  Come (or go) back
        return contexts

    def __search_all_sites(self, keywords: List[str],
                           mediainfo: Optional[MediaInfo] = None,
                           sites: List[int] = None,
                           page: int = 0,
                           area: str = "title") -> Optional[List[TorrentInfo]]:
        """
        Multi-threaded search for multiple sites
        :param mediainfo:   Identified media messages
        :param keywords:   Search keyword list
        :param sites:   Designated siteID Listings， Search only the specified site if available， Otherwise search all sites
        :param page:   Search page
        :param area:   Search area title or imdbid
        :reutrn:  Resource list
        """
        #  Unopened sites are not searched
        indexer_sites = []

        #  Configured indexing sites
        if not sites:
            sites = self.systemconfig.get(SystemConfigKey.IndexerSites) or []

        for indexer in self.siteshelper.get_indexers():
            #  Check site index switch
            if not sites or indexer.get("id") in sites:
                #  Site flow control
                state, msg = self.siteshelper.check(indexer.get("domain"))
                if state:
                    logger.warn(msg)
                    continue
                indexer_sites.append(indexer)
        if not indexer_sites:
            logger.warn(' No active sites are turned on， Unable to search for resources')
            return []

        #  Initiation of progress
        self.progress.start(ProgressKey.Search)
        #  Start counting
        start_time = datetime.now()
        #  Aggregate
        total_num = len(indexer_sites)
        #  Number of completions
        finish_count = 0
        #  Update progress
        self.progress.update(value=0,
                             text=f" Start searching， Common {total_num}  Stations ...",
                             key=ProgressKey.Search)
        #  Multi-threaded
        executor = ThreadPoolExecutor(max_workers=len(indexer_sites))
        all_task = []
        for site in indexer_sites:
            if area == "imdbid":
                #  Look for sth.IMDBID
                task = executor.submit(self.search_torrents, site=site,
                                       keywords=[mediainfo.imdb_id] if mediainfo else None,
                                       mtype=mediainfo.type if mediainfo else None,
                                       page=page)
            else:
                #  Look for sth.标题
                task = executor.submit(self.search_torrents, site=site,
                                       keywords=keywords,
                                       mtype=mediainfo.type if mediainfo else None,
                                       page=page)
            all_task.append(task)
        #  Result set
        results = []
        for future in as_completed(all_task):
            finish_count += 1
            result = future.result()
            if result:
                results.extend(result)
            logger.info(f" Site search progress：{finish_count} / {total_num}")
            self.progress.update(value=finish_count / total_num * 100,
                                 text=f" Searching{keywords or ''}， Done {finish_count} / {total_num}  Stations ...",
                                 key=ProgressKey.Search)
        #  Computational time
        end_time = datetime.now()
        #  Update progress
        self.progress.update(value=100,
                             text=f" Site search complete， Number of effective resources：{len(results)}， Total time consumption {(end_time - start_time).seconds}  Unit of angle or arc equivalent one sixtieth of a degree",
                             key=ProgressKey.Search)
        logger.info(f" Site search complete， Number of effective resources：{len(results)}， Total time consumption {(end_time - start_time).seconds}  Unit of angle or arc equivalent one sixtieth of a degree")
        #  Conclusion of progress
        self.progress.end(ProgressKey.Search)
        #  Come (or go) back
        return results

    def filter_torrents_by_rule(self,
                                torrents: List[TorrentInfo],
                                filter_rule: Dict[str, str] = None
                                ) -> List[TorrentInfo]:
        """
        Filtering seeds using filter rules
        :param torrents:  Seed list
        :param filter_rule:  Filter rules
        """

        #  Takes the default filtering rules
        if not filter_rule:
            filter_rule = self.systemconfig.get(SystemConfigKey.DefaultFilterRules)
        if not filter_rule:
            return torrents
        #  Embody
        include = filter_rule.get("include")
        #  Rule out
        exclude = filter_rule.get("exclude")

        def __filter_torrent(t: TorrentInfo) -> bool:
            """
            Filtering seeds
            """
            #  Embody
            if include:
                if not re.search(r"%s" % include,
                                 f"{t.title} {t.description}", re.I):
                    logger.info(f"{t.title}  Mismatch inclusion rule {include}")
                    return False
            #  Rule out
            if exclude:
                if re.search(r"%s" % exclude,
                             f"{t.title} {t.description}", re.I):
                    logger.info(f"{t.title}  Match exclusion rules {exclude}")
                    return False
            return True

        #  Filter again using the default filtering rules
        return list(filter(lambda t: __filter_torrent(t), torrents))
