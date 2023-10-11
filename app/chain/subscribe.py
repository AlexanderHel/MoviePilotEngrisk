import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple

from sqlalchemy.orm import Session

from app.chain import ChainBase
from app.chain.download import DownloadChain
from app.chain.search import SearchChain
from app.chain.torrents import TorrentsChain
from app.core.context import TorrentInfo, Context, MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.db.models.subscribe import Subscribe
from app.db.subscribe_oper import SubscribeOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.message import MessageHelper
from app.log import logger
from app.schemas import NotExistMediaInfo, Notification
from app.schemas.types import MediaType, SystemConfigKey, MessageChannel, NotificationType


class SubscribeChain(ChainBase):
    """
    Subscription management processing chain
    """

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.downloadchain = DownloadChain(self._db)
        self.searchchain = SearchChain(self._db)
        self.subscribeoper = SubscribeOper(self._db)
        self.torrentschain = TorrentsChain()
        self.message = MessageHelper()
        self.systemconfig = SystemConfigOper()

    def add(self, title: str, year: str,
            mtype: MediaType = None,
            tmdbid: int = None,
            doubanid: str = None,
            season: int = None,
            channel: MessageChannel = None,
            userid: str = None,
            username: str = None,
            message: bool = True,
            exist_ok: bool = False,
            **kwargs) -> Tuple[Optional[int], str]:
        """
        Recognize media messages and add subscriptions
        """
        logger.info(f' Start adding subscriptions， Caption：{title} ...')
        #  Identifying metadata
        metainfo = MetaInfo(title)
        if year:
            metainfo.year = year
        if mtype:
            metainfo.type = mtype
        if season:
            metainfo.type = MediaType.TV
            metainfo.begin_season = season
        #  Identify media messages
        mediainfo: MediaInfo = self.recognize_media(meta=metainfo, mtype=mtype, tmdbid=tmdbid)
        if not mediainfo:
            logger.warn(f' No media messages recognized， Caption：{title}，tmdbid：{tmdbid}')
            return None, " No media messages recognized"
        #  Updating media images
        self.obtain_images(mediainfo=mediainfo)
        #  Total episodes
        if mediainfo.type == MediaType.TV:
            if not season:
                season = 1
            #  Total episodes
            if not kwargs.get('total_episode'):
                if not mediainfo.seasons:
                    #  Additional media information
                    mediainfo: MediaInfo = self.recognize_media(mtype=mediainfo.type,
                                                                tmdbid=mediainfo.tmdb_id)
                    if not mediainfo:
                        logger.error(f" Media message recognition failure！")
                        return None, " Media message recognition failure"
                    if not mediainfo.seasons:
                        logger.error(f" Season set information is not available in the media information， Caption：{title}，tmdbid：{tmdbid}")
                        return None, " Season set information is not available in the media information"
                total_episode = len(mediainfo.seasons.get(season) or [])
                if not total_episode:
                    logger.error(f' Total episodes not available， Caption：{title}，tmdbid：{tmdbid}')
                    return None, " Total episodes not available"
                kwargs.update({
                    'total_episode': total_episode
                })
            #  Missing set
            if not kwargs.get('lack_episode'):
                kwargs.update({
                    'lack_episode': kwargs.get('total_episode')
                })
        #  Add subscription
        sid, err_msg = self.subscribeoper.add(mediainfo, doubanid=doubanid,
                                              season=season, username=username, **kwargs)
        if not sid:
            logger.error(f'{mediainfo.title_year} {err_msg}')
            if not exist_ok and message:
                #  Send back to original user
                self.post_message(Notification(channel=channel,
                                               mtype=NotificationType.Subscribe,
                                               title=f"{mediainfo.title_year} {metainfo.season} "
                                                     f" Failed to add subscription！",
                                               text=f"{err_msg}",
                                               image=mediainfo.get_message_image(),
                                               userid=userid))
        elif message:
            logger.info(f'{mediainfo.title_year} {metainfo.season}  Add subscription successfully')
            if username or userid:
                text = f" Score (of student's work)：{mediainfo.vote_average}， From users：{username or userid}"
            else:
                text = f" Score (of student's work)：{mediainfo.vote_average}"
            #  Spread the word
            self.post_message(Notification(channel=channel,
                                           mtype=NotificationType.Subscribe,
                                           title=f"{mediainfo.title_year} {metainfo.season}  Added subscription",
                                           text=text,
                                           image=mediainfo.get_message_image()))
        #  Return results
        return sid, ""

    def exists(self, mediainfo: MediaInfo, meta: MetaBase = None):
        """
        Determine if a subscription already exists
        """
        if self.subscribeoper.exists(tmdbid=mediainfo.tmdb_id,
                                     season=meta.begin_season if meta else None):
            return True
        return False

    def search(self, sid: int = None, state: str = 'N', manual: bool = False):
        """
        Subscribe to search
        :param sid:  Subscribe toID， Only process this subscription if there is a value
        :param state:  Subscription status N: Not searched R: Searched
        :param manual:  Whether to search manually
        :return:  Update the subscription status toR Or delete a subscription
        """
        if sid:
            subscribes = [self.subscribeoper.get(sid)]
        else:
            subscribes = self.subscribeoper.list(state)
        #  Iteration subscription
        for subscribe in subscribes:
            #  Check if the current time minus the subscription creation time is more than1 Minutes， Otherwise, skip ahead.， Allow time to edit subscriptions
            if subscribe.date:
                now = datetime.now()
                subscribe_time = datetime.strptime(subscribe.date, '%Y-%m-%d %H:%M:%S')
                if (now - subscribe_time).total_seconds() < 60:
                    logger.debug(f" Subscription title：{subscribe.name}  New less than1 Minutes， No search...")
                    continue
            logger.info(f' Start searching for subscriptions， Caption：{subscribe.name} ...')
            #  If the state isN Then update toR
            if subscribe.state == 'N':
                self.subscribeoper.update(subscribe.id, {'state': 'R'})
            #  Generating metadata
            meta = MetaInfo(subscribe.name)
            meta.year = subscribe.year
            meta.begin_season = subscribe.season or None
            meta.type = MediaType(subscribe.type)
            #  Identify media messages
            mediainfo: MediaInfo = self.recognize_media(meta=meta, mtype=meta.type, tmdbid=subscribe.tmdbid)
            if not mediainfo:
                logger.warn(f' No media messages recognized， Caption：{subscribe.name}，tmdbid：{subscribe.tmdbid}')
                continue

            #  Unwashed state
            if not subscribe.best_version:
                #  Total episodes per season
                totals = {}
                if subscribe.season and subscribe.total_episode:
                    totals = {
                        subscribe.season: subscribe.total_episode
                    }
                #  Querying missing media information
                exist_flag, no_exists = self.downloadchain.get_no_exists_info(
                    meta=meta,
                    mediainfo=mediainfo,
                    totals=totals
                )
                if exist_flag:
                    logger.info(f'{mediainfo.title_year}  Already exists in the media library， Complete the subscription')
                    self.subscribeoper.delete(subscribe.id)
                    #  Send notification
                    self.post_message(Notification(mtype=NotificationType.Subscribe,
                                                   title=f'{mediainfo.title_year} {meta.season}  Completed subscriptions',
                                                   image=mediainfo.get_message_image()))
                    continue
                #  Tv series subscription
                if meta.type == MediaType.TV:
                    #  Replace total episodes and start episodes using subscriptionno_exists
                    no_exists = self.__get_subscribe_no_exits(
                        no_exists=no_exists,
                        tmdb_id=mediainfo.tmdb_id,
                        begin_season=meta.begin_season,
                        total_episode=subscribe.total_episode,
                        start_episode=subscribe.start_episode,

                    )
                    #  Printing missing set information
                    if no_exists and no_exists.get(subscribe.tmdbid):
                        no_exists_info = no_exists.get(subscribe.tmdbid).get(subscribe.season)
                        if no_exists_info:
                            logger.info(f' Subscribe to {mediainfo.title_year} {meta.season}  Missing set：{no_exists_info.episodes}')
            else:
                #  Plate washing state
                if meta.type == MediaType.TV:
                    no_exists = {
                        subscribe.season: NotExistMediaInfo(
                            season=subscribe.season,
                            episodes=[],
                            total_episode=subscribe.total_episode,
                            start_episode=subscribe.start_episode or 1)
                    }
                else:
                    no_exists = {}
            #  Site scope
            if subscribe.sites:
                sites = json.loads(subscribe.sites)
            else:
                sites = None
            #  Priority filtering rules
            if subscribe.best_version:
                priority_rule = self.systemconfig.get(SystemConfigKey.BestVersionFilterRules)
            else:
                priority_rule = self.systemconfig.get(SystemConfigKey.SubscribeFilterRules)
            #  Default filtering rules
            if subscribe.include or subscribe.exclude:
                filter_rule = {
                    "include": subscribe.include,
                    "exclude": subscribe.exclude
                }
            else:
                filter_rule = self.systemconfig.get(SystemConfigKey.DefaultFilterRules)
            #  Look for sth.， Meanwhile tv shows filter out unwanted episodes
            contexts = self.searchchain.process(mediainfo=mediainfo,
                                                keyword=subscribe.keyword,
                                                no_exists=no_exists,
                                                sites=sites,
                                                priority_rule=priority_rule,
                                                filter_rule=filter_rule)
            if not contexts:
                logger.warn(f' Subscribe to {subscribe.keyword or subscribe.name}  No resources searched')
                if meta.type == MediaType.TV:
                    #  No resources searched， However, there may be changes in local absences， Update subscription remaining episodes
                    self.__update_lack_episodes(lefts=no_exists, subscribe=subscribe, mediainfo=mediainfo)
                continue
            #  Filtration
            matched_contexts = []
            for context in contexts:
                torrent_meta = context.meta_info
                torrent_info = context.torrent_info
                torrent_mediainfo = context.media_info
                #  Unwashed
                if not subscribe.best_version:
                    #  If it's a tv show filter out episodes that have already been downloaded
                    if torrent_mediainfo.type == MediaType.TV:
                        if self.__check_subscribe_note(subscribe, torrent_meta.episode_list):
                            logger.info(f'{torrent_info.title}  Corresponding episodes {torrent_meta.episode_list}  Downloaded')
                            continue
                else:
                    #  Plate washing， Not for the whole season
                    if torrent_mediainfo.type == MediaType.TV:
                        if torrent_meta.episode_list:
                            logger.info(f'{subscribe.name}  The plates are being washed.，{torrent_info.title}  Not the whole season.')
                            continue
                    #  Don't prioritize less than the downloaded priority
                    if subscribe.current_priority \
                            and torrent_info.pri_order < subscribe.current_priority:
                        logger.info(f'{subscribe.name}  The plates are being washed.，{torrent_info.title}  Lower priority than downloaded')
                        continue
                matched_contexts.append(context)
            if not matched_contexts:
                logger.warn(f' Subscribe to {subscribe.name}  There are no resources that meet the filter criteria')
                #  Unwashed未搜索到资源，但本地缺失可能有变化，Update subscription remaining episodes
                if meta.type == MediaType.TV and not subscribe.best_version:
                    self.__update_lack_episodes(lefts=no_exists, subscribe=subscribe, mediainfo=mediainfo)
                continue
            #  Automatic download
            downloads, lefts = self.downloadchain.batch_download(contexts=matched_contexts,
                                                                 no_exists=no_exists)
            #  Update downloaded episodes
            if downloads \
                    and meta.type == MediaType.TV \
                    and not subscribe.best_version:
                self.__update_subscribe_note(subscribe=subscribe, downloads=downloads)

            if downloads and not lefts:
                #  Determine if a subscription should be completed
                self.finish_subscribe_or_not(subscribe=subscribe, meta=meta,
                                             mediainfo=mediainfo, downloads=downloads)
            else:
                #  Unfinished downloads
                logger.info(f'{mediainfo.title_year}  Not downloaded in full， Continue subscription ...')
                if meta.type == MediaType.TV and not subscribe.best_version:
                    #  Update subscription remaining episodes and time
                    update_date = True if downloads else False
                    self.__update_lack_episodes(lefts=lefts, subscribe=subscribe,
                                                mediainfo=mediainfo, update_date=update_date)
        #  Send system message when manually triggered
        if manual:
            if sid:
                self.message.put(f' Subscribe to {subscribes[0].name}  Search complete！')
            else:
                self.message.put('所有Subscribe to search完成！')

    def finish_subscribe_or_not(self, subscribe: Subscribe, meta: MetaInfo,
                                mediainfo: MediaInfo, downloads: List[Context]):
        """
        Determine if a subscription should be completed
        """
        if not subscribe.best_version:
            #  All downloads complete
            logger.info(f'{mediainfo.title_year}  Download complete， Complete the subscription')
            self.subscribeoper.delete(subscribe.id)
            #  Send notification
            self.post_message(Notification(mtype=NotificationType.Subscribe,
                                           title=f'{mediainfo.title_year} {meta.season}  Completed subscriptions',
                                           image=mediainfo.get_message_image()))
        else:
            #  Priority of the currently downloaded resource
            priority = max([item.torrent_info.pri_order for item in downloads])
            if priority == 100:
                logger.info(f'{mediainfo.title_year}  Plate washing completed， Delete subscription')
                self.subscribeoper.delete(subscribe.id)
                #  Send notification
                self.post_message(Notification(mtype=NotificationType.Subscribe,
                                               title=f'{mediainfo.title_year} {meta.season}  Washed and finished.',
                                               image=mediainfo.get_message_image()))
            else:
                #  The plates are being washed.， Updated resource prioritization
                logger.info(f'{mediainfo.title_year}  The plates are being washed.， Updated resource prioritization')
                self.subscribeoper.update(subscribe.id, {
                    "current_priority": priority
                })

    def refresh(self):
        """
        Subscription refresh
        """
        #  Trigger refresh site resources， Matching subscriptions from the cache
        sites = self.get_subscribed_sites()
        if sites is None:
            return
        self.match(
            self.torrentschain.refresh(sites=sites)
        )

    def get_subscribed_sites(self) -> Optional[List[int]]:
        """
        Get a list of all sites involved in the subscription（ Economize on resources）
        :return:  Come (or go) back[] Hit on behalf of all sites， Come (or go) backNone Represents no subscription
        """
        #  Check all subscriptions
        subscribes = self.subscribeoper.list('R')
        if not subscribes:
            return None
        ret_sites = []
        #  Refresh the subscription selection of theRss Website
        for subscribe in subscribes:
            #  If there is a subscription with no site selected， Then refresh all subscribed sites
            if not subscribe.sites:
                return []
            #  Refresh selected sites
            sub_sites = json.loads(subscribe.sites)
            if sub_sites:
                ret_sites.extend(sub_sites)
        #  De-emphasize
        if ret_sites:
            ret_sites = list(set(ret_sites))

        return ret_sites

    def match(self, torrents: Dict[str, List[Context]]):
        """
        Matching subscriptions from the cache， And automatically downloads
        """
        if not torrents:
            logger.warn(' No cached resources， Unable to match subscription')
            return
        #  All subscriptions
        subscribes = self.subscribeoper.list('R')
        #  Iteration subscription
        for subscribe in subscribes:
            logger.info(f' Start matching subscriptions， Caption：{subscribe.name} ...')
            #  Generating metadata
            meta = MetaInfo(subscribe.name)
            meta.year = subscribe.year
            meta.begin_season = subscribe.season or None
            meta.type = MediaType(subscribe.type)
            #  Identify media messages
            mediainfo: MediaInfo = self.recognize_media(meta=meta, mtype=meta.type, tmdbid=subscribe.tmdbid)
            if not mediainfo:
                logger.warn(f' No media messages recognized， Caption：{subscribe.name}，tmdbid：{subscribe.tmdbid}')
                continue
            #  Unwashed
            if not subscribe.best_version:
                #  Total episodes per season
                totals = {}
                if subscribe.season and subscribe.total_episode:
                    totals = {
                        subscribe.season: subscribe.total_episode
                    }
                #  Querying missing media information
                exist_flag, no_exists = self.downloadchain.get_no_exists_info(
                    meta=meta,
                    mediainfo=mediainfo,
                    totals=totals
                )
                if exist_flag:
                    logger.info(f'{mediainfo.title_year}  Already exists in the media library， Complete the subscription')
                    self.subscribeoper.delete(subscribe.id)
                    #  Send notification
                    self.post_message(Notification(mtype=NotificationType.Subscribe,
                                                   title=f'{mediainfo.title_year} {meta.season}  Completed subscriptions',
                                                   image=mediainfo.get_message_image()))
                    continue
                #  Tv series subscription
                if meta.type == MediaType.TV:
                    #  Replace total episodes and start episodes using subscriptionno_exists
                    no_exists = self.__get_subscribe_no_exits(
                        no_exists=no_exists,
                        tmdb_id=mediainfo.tmdb_id,
                        begin_season=meta.begin_season,
                        total_episode=subscribe.total_episode,
                        start_episode=subscribe.start_episode,

                    )
                    #  Printing missing set information
                    if no_exists and no_exists.get(subscribe.tmdbid):
                        no_exists_info = no_exists.get(subscribe.tmdbid).get(subscribe.season)
                        if no_exists_info:
                            logger.info(f' Subscribe to {mediainfo.title_year} {meta.season}  Missing set：{no_exists_info.episodes}')
            else:
                #  Typesetting
                if meta.type == MediaType.TV:
                    no_exists = {
                        subscribe.season: NotExistMediaInfo(
                            season=subscribe.season,
                            episodes=[],
                            total_episode=subscribe.total_episode,
                            start_episode=subscribe.start_episode or 1)
                    }
                else:
                    no_exists = {}
            #  Default filtering rules
            default_filter = self.systemconfig.get(SystemConfigKey.DefaultFilterRules) or {}
            include = subscribe.include or default_filter.get("include")
            exclude = subscribe.exclude or default_filter.get("exclude")
            #  Iterate over the cached seeds
            _match_context = []
            for domain, contexts in torrents.items():
                for context in contexts:
                    #  Check for matches
                    torrent_meta = context.meta_info
                    torrent_mediainfo = context.media_info
                    torrent_info = context.torrent_info
                    #  Verify by comparingTMDBID And type
                    if torrent_mediainfo.tmdb_id != mediainfo.tmdb_id \
                            or torrent_mediainfo.type != mediainfo.type:
                        continue
                    #  Priority filtering rules
                    if subscribe.best_version:
                        filter_rule = self.systemconfig.get(SystemConfigKey.BestVersionFilterRules)
                    else:
                        filter_rule = self.systemconfig.get(SystemConfigKey.SubscribeFilterRules)
                    result: List[TorrentInfo] = self.filter_torrents(
                        rule_string=filter_rule,
                        torrent_list=[torrent_info],
                        mediainfo=torrent_mediainfo)
                    if result is not None and not result:
                        #  Does not meet the filtering rules
                        logger.info(f"{torrent_info.title}  Does not match the current filter rule")
                        continue
                    #  Not processed if not within the scope of the subscribing site
                    if subscribe.sites:
                        sub_sites = json.loads(subscribe.sites)
                        if sub_sites and torrent_info.site not in sub_sites:
                            logger.info(f"{torrent_info.title}  Falling short (of expectations) {torrent_mediainfo.title_year}  Subscription site requirements")
                            continue
                    #  If it's a tv show.
                    if torrent_mediainfo.type == MediaType.TV:
                        #  Don't have multiple seasons.
                        if len(torrent_meta.season_list) > 1:
                            logger.info(f'{torrent_info.title}  Multi-season， Not dealt with')
                            continue
                        #  Season of comparison
                        if torrent_meta.begin_season:
                            if meta.begin_season != torrent_meta.begin_season:
                                logger.info(f'{torrent_info.title}  Mismatch')
                                continue
                        elif meta.begin_season != 1:
                            logger.info(f'{torrent_info.title}  Mismatch')
                            continue
                        #  Unwashed
                        if not subscribe.best_version:
                            #  Not the missing episodes don't
                            if no_exists and no_exists.get(subscribe.tmdbid):
                                #  Missing set
                                no_exists_info = no_exists.get(subscribe.tmdbid).get(subscribe.season)
                                if no_exists_info:
                                    #  Is there a crossover?
                                    if no_exists_info.episodes and \
                                            torrent_meta.episode_list and \
                                            not set(no_exists_info.episodes).intersection(
                                                set(torrent_meta.episode_list)
                                            ):
                                        logger.info(
                                            f'{torrent_info.title}  Corresponding episodes {torrent_meta.episode_list}  Missing episodes not included')
                                        continue
                            #  Filtration掉已经下载的集数
                            if self.__check_subscribe_note(subscribe, torrent_meta.episode_list):
                                logger.info(f'{torrent_info.title}  Corresponding episodes {torrent_meta.episode_list}  Downloaded')
                                continue
                        else:
                            #  Plate washing， Not for the whole season
                            if meta.type == MediaType.TV:
                                if torrent_meta.episode_list:
                                    logger.info(f'{subscribe.name}  The plates are being washed.，{torrent_info.title}  Not the whole season.')
                                    continue
                    #  Embody
                    if include:
                        if not re.search(r"%s" % include,
                                         f"{torrent_info.title} {torrent_info.description}", re.I):
                            logger.info(f"{torrent_info.title}  Mismatch inclusion rule {include}")
                            continue
                    #  Rule out
                    if exclude:
                        if re.search(r"%s" % exclude,
                                     f"{torrent_info.title} {torrent_info.description}", re.I):
                            logger.info(f"{torrent_info.title}  Match exclusion rules {exclude}")
                            continue
                    #  Match successful
                    logger.info(f'{mediainfo.title_year}  Match successful：{torrent_info.title}')
                    _match_context.append(context)
            #  Start download
            logger.info(f'{mediainfo.title_year}  Matching complete.， Total matches{len(_match_context)} Individual resource')
            if _match_context:
                #  Batch merit-based downloading
                downloads, lefts = self.downloadchain.batch_download(contexts=_match_context, no_exists=no_exists)
                #  Update downloaded episodes
                if downloads and meta.type == MediaType.TV:
                    self.__update_subscribe_note(subscribe=subscribe, downloads=downloads)

                if downloads and not lefts:
                    #  Determine if you want to complete the subscription
                    self.finish_subscribe_or_not(subscribe=subscribe, meta=meta,
                                                 mediainfo=mediainfo, downloads=downloads)
                else:
                    if meta.type == MediaType.TV and not subscribe.best_version:
                        update_date = True if downloads else False
                        #  Unfinished downloads，计算剩余集数
                        self.__update_lack_episodes(lefts=lefts, subscribe=subscribe,
                                                    mediainfo=mediainfo, update_date=update_date)
            else:
                if meta.type == MediaType.TV:
                    #  No resources searched， However, there may be changes in local absences， Update subscription remaining episodes
                    self.__update_lack_episodes(lefts=no_exists, subscribe=subscribe, mediainfo=mediainfo)

    def check(self):
        """
        Timing check subscription， Update subscription information
        """
        #  Check all subscriptions
        subscribes = self.subscribeoper.list()
        if not subscribes:
            #  No subscription does not run
            return
        #  Iteration subscription
        for subscribe in subscribes:
            logger.info(f' Start checking subscriptions：{subscribe.name} ...')
            #  Generating metadata
            meta = MetaInfo(subscribe.name)
            meta.year = subscribe.year
            meta.begin_season = subscribe.season or None
            meta.type = MediaType(subscribe.type)
            #  Identify media messages
            mediainfo: MediaInfo = self.recognize_media(meta=meta, mtype=meta.type, tmdbid=subscribe.tmdbid)
            if not mediainfo:
                logger.warn(f' No media messages recognized， Caption：{subscribe.name}，tmdbid：{subscribe.tmdbid}')
                continue
            #  For tv series， Get the total number of episodes in the current season
            episodes = mediainfo.seasons.get(subscribe.season) or []
            if len(episodes) > (subscribe.total_episode or 0):
                total_episode = len(episodes)
                lack_episode = subscribe.lack_episode + (total_episode - subscribe.total_episode)
                logger.info(
                    f' Subscribe to {subscribe.name}  Change in total number of episodes， The total number of updated episodes is{total_episode}， The number of missing sets is{lack_episode} ...')
            else:
                total_episode = subscribe.total_episode
                lack_episode = subscribe.lack_episode
            #  UpdateTMDB Text
            self.subscribeoper.update(subscribe.id, {
                "name": mediainfo.title,
                "year": mediainfo.year,
                "vote": mediainfo.vote_average,
                "poster": mediainfo.get_poster_image(),
                "backdrop": mediainfo.get_backdrop_image(),
                "description": mediainfo.overview,
                "imdbid": mediainfo.imdb_id,
                "tvdbid": mediainfo.tvdb_id,
                "total_episode": total_episode,
                "lack_episode": lack_episode
            })
            logger.info(f' Subscribe to {subscribe.name}  Updates completed')

    def __update_subscribe_note(self, subscribe: Subscribe, downloads: List[Context]):
        """
        Update downloaded episodes tonote Field
        """
        #  Query existingNote
        if not downloads:
            return
        note = []
        if subscribe.note:
            note = json.loads(subscribe.note)
        for context in downloads:
            meta = context.meta_info
            mediainfo = context.media_info
            if mediainfo.type != MediaType.TV:
                continue
            if mediainfo.tmdb_id != subscribe.tmdbid:
                continue
            episodes = meta.episode_list
            if not episodes:
                continue
            #  Merge downloaded sets
            note = list(set(note).union(set(episodes)))
            #  Update subscription
            self.subscribeoper.update(subscribe.id, {
                "note": json.dumps(note)
            })

    @staticmethod
    def __check_subscribe_note(subscribe: Subscribe, episodes: List[int]) -> bool:
        """
        Check if the current episode has been downloaded
        """
        if not subscribe.note:
            return False
        if not episodes:
            return False
        note = json.loads(subscribe.note)
        if set(episodes).issubset(set(note)):
            return True
        return False

    def __update_lack_episodes(self, lefts: Dict[int, Dict[int, NotExistMediaInfo]],
                               subscribe: Subscribe,
                               mediainfo: MediaInfo,
                               update_date: bool = False):
        """
        Update subscription remaining episodes
        """
        left_seasons = lefts.get(mediainfo.tmdb_id) or {}
        for season_info in left_seasons.values():
            season = season_info.season
            if season == subscribe.season:
                left_episodes = season_info.episodes
                if not left_episodes:
                    lack_episode = season_info.total_episode
                else:
                    lack_episode = len(left_episodes)
                logger.info(f'{mediainfo.title_year}  Classifier for seasonal crop yield or seasons of a tv series {season}  Update the number of missing episodes to{lack_episode} ...')
                if update_date:
                    #  Also update the last time
                    self.subscribeoper.update(subscribe.id, {
                        "lack_episode": lack_episode,
                        "last_update": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                else:
                    self.subscribeoper.update(subscribe.id, {
                        "lack_episode": lack_episode
                    })

    def remote_list(self, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Query subscriptions and send messages
        """
        subscribes = self.subscribeoper.list()
        if not subscribes:
            self.post_message(Notification(channel=channel,
                                           title=' There are no subscriptions！', userid=userid))
            return
        title = f" Have altogether {len(subscribes)}  Subscription， Responding to the corresponding command operation： " \
                f"\n-  Delete subscription：/subscribe_delete [id]" \
                f"\n-  Search subscriptions：/subscribe_search [id]" \
                f"\n-  Refresh subscription：/subscribe_refresh"
        messages = []
        for subscribe in subscribes:
            if subscribe.type == MediaType.MOVIE.value:
                tmdb_link = f"https://www.themoviedb.org/movie/{subscribe.tmdbid}"
                messages.append(f"{subscribe.id}. [{subscribe.name}（{subscribe.year}）]({tmdb_link})")
            else:
                tmdb_link = f"https://www.themoviedb.org/tv/{subscribe.tmdbid}"
                messages.append(f"{subscribe.id}. [{subscribe.name}（{subscribe.year}）]({tmdb_link}) "
                                f" (prefix indicating ordinal number, e.g. first, number two etc){subscribe.season} Classifier for seasonal crop yield or seasons of a tv series "
                                f"_{subscribe.total_episode - (subscribe.lack_episode or subscribe.total_episode)}"
                                f"/{subscribe.total_episode}_")
        #  Distribution list
        self.post_message(Notification(channel=channel,
                                       title=title, text='\n'.join(messages), userid=userid))

    def remote_delete(self, arg_str: str, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Delete subscription
        """
        if not arg_str:
            self.post_message(Notification(channel=channel,
                                           title=" Please enter the correct command format：/subscribe_delete [id]，"
                                                 "[id] Is the subscription number", userid=userid))
            return
        arg_strs = str(arg_str).split()
        for arg_str in arg_strs:
            arg_str = arg_str.strip()
            if not arg_str.isdigit():
                continue
            subscribe_id = int(arg_str)
            subscribe = self.subscribeoper.get(subscribe_id)
            if not subscribe:
                self.post_message(Notification(channel=channel,
                                               title=f" Subscription number {subscribe_id}  Non-existent！", userid=userid))
                return
            # Delete subscription
            self.subscribeoper.delete(subscribe_id)
        #  Resend the message
        self.remote_list(channel, userid)

    @staticmethod
    def __get_subscribe_no_exits(no_exists: Dict[int, Dict[int, NotExistMediaInfo]],
                                 tmdb_id: int,
                                 begin_season: int,
                                 total_episode: int,
                                 start_episode: int):
        """
        Based on subscription start and total episodes， CombiningTMDB The message counts the number of missing episodes for the current subscription
        :param no_exists:  List of missing season episodes
        :param tmdb_id: TMDB ID
        :param begin_season:  Beginning of the season
        :param total_episode:  Subscribe to set the total number of episodes
        :param start_episode:  Subscribe to set the number of episodes to start
        """
        #  Replace total episodes and start episodes using subscriptionno_exists
        if no_exists \
                and no_exists.get(tmdb_id) \
                and (total_episode or start_episode):
            #  Missing information for the season
            no_exist_season = no_exists.get(tmdb_id).get(begin_season)
            if no_exist_season:
                #  Source list
                episode_list = no_exist_season.episodes
                #  Original total number of episodes
                total = no_exist_season.total_episode
                #  Original number of episodes
                start = no_exist_season.start_episode

                #  Updated episode list、 Number of episodes、 Total episodes
                if not episode_list:
                    #  Missing for the whole season
                    episodes = []
                    start_episode = start_episode or start
                    total_episode = total_episode or total
                else:
                    #  Partially missing
                    if not start_episode \
                            and not total_episode:
                        #  No adjustment required
                        return no_exists
                    if not start_episode:
                        #  No custom start set
                        start_episode = start
                    if not total_episode:
                        #  No customization of the total number of episodes
                        total_episode = total
                    #  New set list
                    new_episodes = list(range(max(start_episode, start), total_episode + 1))
                    #  Take the intersection with the original set list
                    episodes = list(set(episode_list).intersection(set(new_episodes)))
                #  Updating the collection
                no_exists[tmdb_id][begin_season] = NotExistMediaInfo(
                    season=begin_season,
                    episodes=episodes,
                    total_episode=total_episode,
                    start_episode=start_episode
                )
        return no_exists
