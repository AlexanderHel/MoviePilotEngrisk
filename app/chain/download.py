import base64
import json
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple, Set, Dict, Union

from sqlalchemy.orm import Session

from app.chain import ChainBase
from app.core.config import settings
from app.core.context import MediaInfo, TorrentInfo, Context
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.mediaserver_oper import MediaServerOper
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.schemas import ExistMediaInfo, NotExistMediaInfo, DownloadingTorrent, Notification
from app.schemas.types import MediaType, TorrentStatus, EventType, MessageChannel, NotificationType
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class DownloadChain(ChainBase):
    """
    Download processing chain
    """

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.torrent = TorrentHelper()
        self.downloadhis = DownloadHistoryOper(self._db)
        self.mediaserver = MediaServerOper(self._db)

    def post_download_message(self, meta: MetaBase, mediainfo: MediaInfo, torrent: TorrentInfo,
                              channel: MessageChannel = None,
                              userid: str = None):
        """
        Send message to add download
        """
        msg_text = ""
        if userid:
            msg_text = f" Subscribers：{userid}"
        if torrent.site_name:
            msg_text = f"{msg_text}\n Website：{torrent.site_name}"
        if meta.resource_term:
            msg_text = f"{msg_text}\n Mass (in physics)：{meta.resource_term}"
        if torrent.size:
            if str(torrent.size).replace(".", "").isdigit():
                size = StringUtils.str_filesize(torrent.size)
            else:
                size = torrent.size
            msg_text = f"{msg_text}\n Adults and children：{size}"
        if torrent.title:
            msg_text = f"{msg_text}\n Torrent：{torrent.title}"
        if torrent.pubdate:
            msg_text = f"{msg_text}\n Release time：{torrent.pubdate}"
        if torrent.seeders:
            msg_text = f"{msg_text}\n Determinant (math.)：{torrent.seeders}"
        if torrent.uploadvolumefactor and torrent.downloadvolumefactor:
            msg_text = f"{msg_text}\n Promote：{torrent.volume_factor}"
        if torrent.hit_and_run:
            msg_text = f"{msg_text}\nHit&Run： Be"
        if torrent.description:
            html_re = re.compile(r'<[^>]+>', re.S)
            description = html_re.sub('', torrent.description)
            torrent.description = re.sub(r'<[^>]+>', '', description)
            msg_text = f"{msg_text}\n Descriptive：{torrent.description}"

        self.post_message(Notification(
            channel=channel,
            mtype=NotificationType.Download,
            title=f"{mediainfo.title_year} "
                  f"{meta.season_episode}  Start download",
            text=msg_text,
            image=mediainfo.get_message_image()))

    def download_torrent(self, torrent: TorrentInfo,
                         channel: MessageChannel = None,
                         userid: Union[str, int] = None
                         ) -> Tuple[Optional[Union[Path, str]], str, list]:
        """
        Download seed file， If it's a magnetic chain， Will return to the magnet link itself
        :return:  Seed path， Seed catalog name， List of seed documents
        """

        def __get_redict_url(url: str, ua: str = None, cookie: str = None) -> Optional[str]:
            """
            Get the download link， url Specification：[base64]url
            """
            #  Gain[] Hit the nail on the head
            m = re.search(r"\[(.*)](.*)", url)
            if m:
                #  Parameters
                base64_str = m.group(1)
                # URL
                url = m.group(2)
                if not base64_str:
                    return url
                #  Decoding parameter
                req_str = base64.b64decode(base64_str.encode('utf-8')).decode('utf-8')
                req_params: Dict[str, dict] = json.loads(req_str)
                if req_params.get('method') == 'get':
                    # GET Requesting
                    res = RequestUtils(
                        ua=ua,
                        cookies=cookie
                    ).get_res(url, params=req_params.get('params'))
                else:
                    # POST Requesting
                    res = RequestUtils(
                        ua=ua,
                        cookies=cookie
                    ).post_res(url, params=req_params.get('params'))
                if not res:
                    return None
                if not req_params.get('result'):
                    return res.text
                else:
                    data = res.json()
                    for key in str(req_params.get('result')).split("."):
                        data = data.get(key)
                        if not data:
                            return None
                    logger.info(f" Get the download address：{data}")
                    return data
            return None

        #  Get the download link
        if not torrent.enclosure:
            return None, "", []
        if torrent.enclosure.startswith("magnet:"):
            return torrent.enclosure, "", []

        if torrent.enclosure.startswith("["):
            #  Need to decode to get the download address
            torrent_url = __get_redict_url(url=torrent.enclosure,
                                           ua=torrent.site_ua,
                                           cookie=torrent.site_cookie)
        else:
            torrent_url = torrent.enclosure
        if not torrent_url:
            logger.error(f"{torrent.title}  Unable to get the download address：{torrent.enclosure}！")
            return None, "", []
        #  Download seed file
        torrent_file, content, download_folder, files, error_msg = self.torrent.download_torrent(
            url=torrent_url,
            cookie=torrent.site_cookie,
            ua=torrent.site_ua,
            proxy=torrent.site_proxy)

        if isinstance(content, str):
            #  Magnetic link
            return content, "", []

        if not torrent_file:
            logger.error(f" Failed to download seed file：{torrent.title} - {torrent_url}")
            self.post_message(Notification(
                channel=channel,
                mtype=NotificationType.Manual,
                title=f"{torrent.title}  Seed download failed！",
                text=f" Error message：{error_msg}\n Website：{torrent.site_name}",
                userid=userid))
            return None, "", []

        #  Come (or go) back  Seed file path， Seed catalog name， List of seed documents
        return torrent_file, download_folder, files

    def download_single(self, context: Context, torrent_file: Path = None,
                        episodes: Set[int] = None,
                        channel: MessageChannel = None,
                        save_path: str = None,
                        userid: Union[str, int] = None) -> Optional[str]:
        """
        Download & send notification
        :param context:  Resource context
        :param torrent_file:  Seed file path
        :param episodes:  Number of episodes to download
        :param channel:  Notification channels
        :param save_path:  Save path
        :param userid:  SubscribersID
        """
        _torrent = context.torrent_info
        _media = context.media_info
        _meta = context.meta_info
        _folder_name = ""
        if not torrent_file:
            #  Download seed file，得到的可能是文件也可能是磁力链
            content, _folder_name, _file_list = self.download_torrent(_torrent,
                                                                      channel=channel,
                                                                      userid=userid)
            if not content:
                return
        else:
            content = torrent_file
            #  Get the folder name and file list of the seed file
            _folder_name, _file_list = self.torrent.get_torrent_info(torrent_file)

        #  Download catalog
        if not save_path:
            if settings.DOWNLOAD_CATEGORY and _media and _media.category:
                #  Enable download secondary catalog
                if _media.type == MediaType.MOVIE:
                    #  Cinematic
                    download_dir = Path(settings.DOWNLOAD_MOVIE_PATH or settings.DOWNLOAD_PATH) / _media.category
                else:
                    if settings.DOWNLOAD_ANIME_PATH \
                            and _media.genre_ids \
                            and set(_media.genre_ids).intersection(set(settings.ANIME_GENREIDS)):
                        #  Cartoons and comics
                        download_dir = Path(settings.DOWNLOAD_ANIME_PATH)
                    else:
                        #  Dramas
                        download_dir = Path(settings.DOWNLOAD_TV_PATH or settings.DOWNLOAD_PATH) / _media.category
            elif _media:
                #  Downloading secondary directories is not enabled
                if _media.type == MediaType.MOVIE:
                    #  Cinematic
                    download_dir = Path(settings.DOWNLOAD_MOVIE_PATH or settings.DOWNLOAD_PATH)
                else:
                    if settings.DOWNLOAD_ANIME_PATH \
                            and _media.genre_ids \
                            and set(_media.genre_ids).intersection(set(settings.ANIME_GENREIDS)):
                        #  Cartoons and comics
                        download_dir = Path(settings.DOWNLOAD_ANIME_PATH)
                    else:
                        #  Dramas
                        download_dir = Path(settings.DOWNLOAD_TV_PATH or settings.DOWNLOAD_PATH)
            else:
                #  Unidentified
                download_dir = Path(settings.DOWNLOAD_PATH)
        else:
            #  Customize the download directory
            download_dir = Path(save_path)

        #  Add download
        result: Optional[tuple] = self.download(content=content,
                                                cookie=_torrent.site_cookie,
                                                episodes=episodes,
                                                download_dir=download_dir,
                                                category=_media.category)
        if result:
            _hash, error_msg = result
        else:
            _hash, error_msg = None, " Unknown error"

        if _hash:
            #  Download file path
            if _folder_name:
                download_path = download_dir / _folder_name
            else:
                download_path = download_dir / _file_list[0] if _file_list else download_dir

            #  Register to download records
            self.downloadhis.add(
                path=str(download_path),
                type=_media.type.value,
                title=_media.title,
                year=_media.year,
                tmdbid=_media.tmdb_id,
                imdbid=_media.imdb_id,
                tvdbid=_media.tvdb_id,
                doubanid=_media.douban_id,
                seasons=_meta.season,
                episodes=_meta.episode,
                image=_media.get_backdrop_image(),
                download_hash=_hash,
                torrent_name=_torrent.title,
                torrent_description=_torrent.description,
                torrent_site=_torrent.site_name,
                userid=userid,
                channel=channel.value if channel else None,
                date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            )

            #  Register to download files
            files_to_add = []
            for file in _file_list:
                if episodes:
                    #  Identify the set of documents
                    file_meta = MetaInfo(Path(file).stem)
                    if not file_meta.begin_episode \
                            or file_meta.begin_episode not in episodes:
                        continue
                files_to_add.append({
                    "download_hash": _hash,
                    "downloader": settings.DOWNLOADER,
                    "fullpath": str(download_dir / _folder_name / file),
                    "savepath": str(download_dir / _folder_name),
                    "filepath": file,
                    "torrentname": _meta.org_string,
                })
            if files_to_add:
                self.downloadhis.add_files(files_to_add)

            #  Send a message
            self.post_download_message(meta=_meta, mediainfo=_media, torrent=_torrent, channel=channel, userid=userid)
            #  Processing after successful download
            self.download_added(context=context, download_dir=download_dir, torrent_path=torrent_file)
            #  Broadcasting incident
            self.eventmanager.send_event(EventType.DownloadAdded, {
                "hash": _hash,
                "context": context
            })
        else:
            #  Failed to download
            logger.error(f"{_media.title_year}  Failed to add download task："
                         f"{_torrent.title} - {_torrent.enclosure}，{error_msg}")
            self.post_message(Notification(
                channel=channel,
                mtype=NotificationType.Manual,
                title=" Failed to add download task：%s %s"
                      % (_media.title_year, _meta.season_episode),
                text=f" Website：{_torrent.site_name}\n"
                     f" Seed name：{_meta.org_string}\n"
                     f" Error message：{error_msg}",
                image=_media.get_message_image(),
                userid=userid))
        return _hash

    def batch_download(self,
                       contexts: List[Context],
                       no_exists: Dict[int, Dict[int, NotExistMediaInfo]] = None,
                       save_path: str = None,
                       channel: MessageChannel = None,
                       userid: str = None) -> Tuple[List[Context], Dict[int, Dict[int, NotExistMediaInfo]]]:
        """
        Based on missing data， Combination of auto-seeded lists for optimal download
        :param contexts:   Resource context list
        :param no_exists:   Missing episode information
        :param save_path:   Save path
        :param channel:   Notification channels
        :param userid:   SubscribersID
        :return:  List of downloaded resources、 Remaining episodes not yet downloaded no_exists[tmdb_id] = {season: NotExistMediaInfo}
        """
        #  Downloaded items
        downloaded_list: List[Context] = []

        def __update_seasons(_tmdbid: int, _need: list, _current: list) -> list:
            """
            Updateneed_tvs Quarter， Return to remaining quarters
            :param _tmdbid: TMDBID
            :param _need:  Number of seasons to download
            :param _current:  Seasons downloaded
            """
            #  Number of seasons remaining
            need = list(set(_need).difference(set(_current)))
            #  Clear downloaded season information
            for _sea in list(no_exists.get(_tmdbid)):
                if _sea not in need:
                    no_exists[_tmdbid].pop(_sea)
                if not no_exists.get(_tmdbid) and no_exists.get(_tmdbid) is not None:
                    no_exists.pop(_tmdbid)
            return need

        def __update_episodes(_tmdbid: int, _sea: int, _need: list, _current: set) -> list:
            """
            Updateneed_tvs Episode number (of a tv series etc)， Returns the number of remaining episodes
            :param _tmdbid: TMDBID
            :param _sea:  Quarter
            :param _need:  Number of episodes to download
            :param _current:  Episodes downloaded
            """
            #  Remaining number of episodes
            need = list(set(_need).difference(set(_current)))
            if need:
                not_exist = no_exists[_tmdbid][_sea]
                no_exists[_tmdbid][_sea] = NotExistMediaInfo(
                    season=not_exist.season,
                    episodes=need,
                    total_episode=not_exist.total_episode,
                    start_episode=not_exist.start_episode
                )
            else:
                no_exists[_tmdbid].pop(_sea)
                if not no_exists.get(_tmdbid) and no_exists.get(_tmdbid) is not None:
                    no_exists.pop(_tmdbid)
            return need

        def __get_season_episodes(tmdbid: int, season: int) -> int:
            """
            Get the number of episodes for the desired season
            """
            if not no_exists.get(tmdbid):
                return 9999
            no_exist = no_exists.get(tmdbid)
            if not no_exist.get(season):
                return 9999
            return no_exist[season].total_episode

        #  Grouping and sorting
        contexts = TorrentHelper().sort_group_torrents(contexts)

        #  If it's a movie.， Direct download
        for context in contexts:
            if context.media_info.type == MediaType.MOVIE:
                if self.download_single(context, save_path=save_path,
                                        channel=channel, userid=userid):
                    #  Download successfully
                    downloaded_list.append(context)

        #  Dramas整季匹配
        if no_exists:
            #  Let's take out the missing ones for the whole season， See if there happens to be a seed that satisfies all the seasons {tmdbid: [seasons]}
            need_seasons: Dict[int, list] = {}
            for need_tmdbid, need_tv in no_exists.items():
                for tv in need_tv.values():
                    if not tv:
                        continue
                    #  Quarterly lists are empty， Representing a full-season absence
                    if not tv.episodes:
                        if not need_seasons.get(need_tmdbid):
                            need_seasons[need_tmdbid] = []
                        need_seasons[need_tmdbid].append(tv.season or 1)
            #  Find seeds contained throughout the season， Process only seeds that have no episodes in the entire season or have more than one episode in the season
            for need_tmdbid, need_season in need_seasons.items():
                #  Seed cycling
                for context in contexts:
                    #  Media information
                    media = context.media_info
                    #  Identifying metadata
                    meta = context.meta_info
                    #  Seed information
                    torrent = context.torrent_info
                    #  Exclusion of tv series
                    if media.type != MediaType.TV:
                        continue
                    #  Seasonal list of seeds
                    torrent_season = meta.season_list
                    #  Don't seed it with a set.
                    if meta.episode_list:
                        continue
                    #  MatchTMDBID
                    if need_tmdbid == media.tmdb_id:
                        #  Seed seasons are needed for seasons or subsets
                        if set(torrent_season).issubset(set(need_season)):
                            if len(torrent_season) == 1:
                                #  Only one season could be a misnomer， Seeds need to be opened for identification， Download only if the actual number of episodes is greater than or equal to the total number of episodes.
                                content, _, torrent_files = self.download_torrent(torrent)
                                if not content:
                                    continue
                                if isinstance(content, str):
                                    logger.warn(f"{meta.org_string}  The download address is a magnet link， Unable to determine the number of seed file episodes")
                                    continue
                                torrent_episodes = self.torrent.get_torrent_episodes(torrent_files)
                                logger.info(f"{meta.org_string}  The number of parsed file sets is {torrent_episodes}")
                                if not torrent_episodes:
                                    continue
                                #  Total episodes
                                need_total = __get_season_episodes(need_tmdbid, torrent_season[0])
                                if len(torrent_episodes) < need_total:
                                    #  Updated episode range
                                    begin_ep = min(torrent_episodes)
                                    end_ep = max(torrent_episodes)
                                    meta.set_episodes(begin=begin_ep, end=end_ep)
                                    logger.info(
                                        f"{meta.org_string}  Parsing the number of file episodes reveals that it is not a complete collection")
                                    continue
                                else:
                                    #  Downloading
                                    download_id = self.download_single(
                                        context=context,
                                        torrent_file=content if isinstance(content, Path) else None,
                                        save_path=save_path,
                                        channel=channel,
                                        userid=userid
                                    )
                            else:
                                #  Downloading
                                download_id = self.download_single(context, save_path=save_path,
                                                                   channel=channel, userid=userid)

                            if download_id:
                                #  Download successfully
                                downloaded_list.append(context)
                                #  Updates still need seasonal episodes
                                need_season = __update_seasons(_tmdbid=need_tmdbid,
                                                               _need=need_season,
                                                               _current=torrent_season)
        #  Dramas季内的集匹配
        if no_exists:
            # TMDBID Listings
            need_tv_list = list(no_exists)
            for need_tmdbid in need_tv_list:
                # dict[season, [NotExistMediaInfo]]
                need_tv = no_exists.get(need_tmdbid)
                if not need_tv:
                    continue
                #  Cycle through each season
                for sea, tv in need_tv.items():
                    #  Current needs season
                    need_season = sea
                    #  Current needs set
                    need_episodes = tv.episodes
                    # TMDB Total episodes
                    total_episode = tv.total_episode
                    #  Need to start the set
                    start_episode = tv.start_episode or 1
                    #  Missing whole seasons are converted to missing sets for comparison
                    if not need_episodes:
                        need_episodes = list(range(start_episode, total_episode))
                    #  Seed cycling
                    for context in contexts:
                        #  Media information
                        media = context.media_info
                        #  Identifying metadata
                        meta = context.meta_info
                        #  Non-episodes not processed
                        if media.type != MediaType.TV:
                            continue
                        #  MatchTMDB
                        if media.tmdb_id == need_tmdbid:
                            #  No duplicate additions
                            if context in downloaded_list:
                                continue
                            #  Seed season
                            torrent_season = meta.season_list
                            #  Only single-season seeds containing aggregates are treated
                            if len(torrent_season) != 1 or torrent_season[0] != need_season:
                                continue
                            #  Seed set list
                            torrent_episodes = set(meta.episode_list)
                            #  No treatment for the whole season
                            if not torrent_episodes:
                                continue
                            #  Is a subset of the required set then download
                            if torrent_episodes.issubset(set(need_episodes)):
                                #  Downloading
                                download_id = self.download_single(context, save_path=save_path,
                                                                   channel=channel, userid=userid)
                                if download_id:
                                    #  Download successfully
                                    downloaded_list.append(context)
                                    #  Update still needs episodes
                                    need_episodes = __update_episodes(_tmdbid=need_tmdbid,
                                                                      _need=need_episodes,
                                                                      _sea=need_season,
                                                                      _current=torrent_episodes)

        #  Episodes still missing， Select the desired episode file to download from the entire season， Support onlyQB Cap (a poem)TR
        if no_exists:
            # TMDBID Listings
            no_exists_list = list(no_exists)
            for need_tmdbid in no_exists_list:
                # dict[season, [NotExistMediaInfo]]
                need_tv = no_exists.get(need_tmdbid)
                if not need_tv:
                    continue
                #  Need season listings
                need_tv_list = list(need_tv)
                #  Cycling requires seasons
                for sea in need_tv_list:
                    # NotExistMediaInfo
                    tv = need_tv.get(sea)
                    #  Current needs season
                    need_season = sea
                    #  Current needs set
                    need_episodes = tv.episodes
                    #  No set is not processed
                    if not need_episodes:
                        continue
                    #  Seed cycling
                    for context in contexts:
                        #  Media information
                        media = context.media_info
                        #  Identifying metadata
                        meta = context.meta_info
                        #  Seed information
                        torrent = context.torrent_info
                        #  Non-episodes not processed
                        if media.type != MediaType.TV:
                            continue
                        #  No duplicate additions
                        if context in downloaded_list:
                            continue
                        #  Exit when no set is needed
                        if not need_episodes:
                            break
                        #  Select a single full season or a single season that includes all the episodes needed for the
                        if media.tmdb_id == need_tmdbid \
                                and (not meta.episode_list
                                     or set(meta.episode_list).intersection(set(need_episodes))) \
                                and len(meta.season_list) == 1 \
                                and meta.season_list[0] == need_season:
                            #  Check the seeds to see if there are any needed sets
                            content, _, torrent_files = self.download_torrent(torrent)
                            if not content:
                                continue
                            if isinstance(content, str):
                                logger.warn(f"{meta.org_string}  The download address is a magnet link， Unable to parse seed file episodes")
                                continue
                            #  Seeds all sets
                            torrent_episodes = self.torrent.get_torrent_episodes(torrent_files)
                            logger.info(f"{torrent.site_name} - {meta.org_string}  Number of parsed file sets：{torrent_episodes}")
                            #  Selected set
                            selected_episodes = set(torrent_episodes).intersection(set(need_episodes))
                            if not selected_episodes:
                                logger.info(f"{torrent.site_name} - {torrent.title}  There are no required sets， Skip over...")
                                continue
                            logger.info(f"{torrent.site_name} - {torrent.title}  Number of selected episodes：{selected_episodes}")
                            #  Add download
                            download_id = self.download_single(
                                context=context,
                                torrent_file=content if isinstance(content, Path) else None,
                                episodes=selected_episodes,
                                save_path=save_path,
                                channel=channel,
                                userid=userid
                            )
                            if not download_id:
                                continue
                            #  Update recognized sets to the context
                            context.meta_info.begin_episode = min(selected_episodes)
                            context.meta_info.end_episode = max(selected_episodes)
                            #  Download successfully
                            downloaded_list.append(context)
                            #  Update still needs episodes
                            need_episodes = __update_episodes(_tmdbid=need_tmdbid,
                                                              _need=need_episodes,
                                                              _sea=need_season,
                                                              _current=selected_episodes)

        #  Return to downloaded resources， That's all that's left.
        return downloaded_list, no_exists

    def get_no_exists_info(self, meta: MetaBase,
                           mediainfo: MediaInfo,
                           no_exists: Dict[int, Dict[int, NotExistMediaInfo]] = None,
                           totals: Dict[int, int] = None
                           ) -> Tuple[bool, Dict[int, Dict[int, NotExistMediaInfo]]]:
        """
        Check the media library， Query the existence of， For episodes that also return non-existent seasonal episode information
        :param meta:  Metadata
        :param mediainfo:  Identified media information
        :param no_exists:  Non-existing seasonal set information that has been stored prior to calling this method， When passed in, the function searches for content that will be overlaid on the output
        :param totals:  Total number of episodes per season of a tv series
        :return:  Is the current media missing， Total seasonal episodes and missing seasonal episodes for each title
        """

        def __append_no_exists(_season: int, _episodes: list, _total: int, _start: int):
            """
            Adding non-existent season set information
            {tmdbid: [
                "season": int,
                "episodes": list,
                "total_episode": int,
                "start_episode": int
            ]}
            """
            if not no_exists.get(mediainfo.tmdb_id):
                no_exists[mediainfo.tmdb_id] = {
                    _season: NotExistMediaInfo(
                        season=_season,
                        episodes=_episodes,
                        total_episode=_total,
                        start_episode=_start
                    )
                }
            else:
                no_exists[mediainfo.tmdb_id][_season] = NotExistMediaInfo(
                    season=_season,
                    episodes=_episodes,
                    total_episode=_total,
                    start_episode=_start
                )

        if not no_exists:
            no_exists = {}

        if not totals:
            totals = {}

        if mediainfo.type == MediaType.MOVIE:
            #  Cinematic
            itemid = self.mediaserver.get_item_id(mtype=mediainfo.type.value,
                                                  tmdbid=mediainfo.tmdb_id)
            exists_movies: Optional[ExistMediaInfo] = self.media_exists(mediainfo=mediainfo, itemid=itemid)
            if exists_movies:
                logger.info(f" Movies already in the media library：{mediainfo.title_year}")
                return True, {}
            return False, {}
        else:
            if not mediainfo.seasons:
                #  Additional media information
                mediainfo: MediaInfo = self.recognize_media(mtype=mediainfo.type,
                                                            tmdbid=mediainfo.tmdb_id)
                if not mediainfo:
                    logger.error(f" Media message recognition failure！")
                    return False, {}
                if not mediainfo.seasons:
                    logger.error(f" Season set information is not available in the media information：{mediainfo.title_year}")
                    return False, {}
            #  Dramas
            itemid = self.mediaserver.get_item_id(mtype=mediainfo.type.value,
                                                  tmdbid=mediainfo.tmdb_id,
                                                  season=mediainfo.season)
            #  Episodes already in the media library
            exists_tvs: Optional[ExistMediaInfo] = self.media_exists(mediainfo=mediainfo, itemid=itemid)
            if not exists_tvs:
                #  All seasons are missing
                for season, episodes in mediainfo.seasons.items():
                    if not episodes:
                        continue
                    #  All seasons don't exist.
                    if meta.season_list \
                            and season not in meta.season_list:
                        continue
                    #  Total episodes
                    total_ep = totals.get(season) or len(episodes)
                    __append_no_exists(_season=season, _episodes=[],
                                       _total=total_ep, _start=min(episodes))
                return False, no_exists
            else:
                #  There are a number of， Check for missing seasonal episodes for each season
                for season, episodes in mediainfo.seasons.items():
                    if meta.begin_season \
                            and season not in meta.season_list:
                        continue
                    if not episodes:
                        continue
                    #  Total episodes for the season
                    season_total = totals.get(season) or len(episodes)
                    #  The season's pre-existing episodes
                    exist_episodes = exists_tvs.seasons.get(season)
                    if exist_episodes:
                        #  Already exists to take the difference set
                        if totals.get(season):
                            #  Missing episodes by total episodes（ The starting set isTMDB The smallest set in the）
                            lack_episodes = list(set(range(min(episodes),
                                                           season_total + min(episodes))
                                                     ).difference(set(exist_episodes)))
                        else:
                            #  Check or refer toTMDB Set counting missing sets
                            lack_episodes = list(set(episodes).difference(set(exist_episodes)))
                        if not lack_episodes:
                            #  Full set exists
                            continue
                        # Adding non-existent season set information
                        __append_no_exists(_season=season, _episodes=lack_episodes,
                                           _total=season_total, _start=min(lack_episodes))
                    else:
                        #  All seasons don't exist.
                        __append_no_exists(_season=season, _episodes=[],
                                           _total=season_total, _start=min(episodes))
            #  Existence of incomplete episodes
            if no_exists:
                logger.debug(f" Selected episodes already exist in the media library， Deficiencies：{no_exists}")
                return False, no_exists
            #  Fully present
            return True, no_exists

    def remote_downloading(self, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Query tasks being downloaded， And send a message
        """
        torrents = self.list_torrents(status=TorrentStatus.DOWNLOADING)
        if not torrents:
            self.post_message(Notification(
                channel=channel,
                mtype=NotificationType.Download,
                title=" No tasks being downloaded！",
                userid=userid))
            return
        #  Send a message
        title = f" Common {len(torrents)}  Tasks are being downloaded.："
        messages = []
        index = 1
        for torrent in torrents:
            messages.append(f"{index}. {torrent.title} "
                            f"{StringUtils.str_filesize(torrent.size)} "
                            f"{round(torrent.progress, 1)}%")
            index += 1
        self.post_message(Notification(
            channel=channel, mtype=NotificationType.Download,
            title=title, text="\n".join(messages), userid=userid))

    def downloading(self) -> List[DownloadingTorrent]:
        """
        Query tasks being downloaded
        """
        torrents = self.list_torrents(status=TorrentStatus.DOWNLOADING)
        if not torrents:
            return []
        ret_torrents = []
        for torrent in torrents:
            history = self.downloadhis.get_by_hash(torrent.hash)
            if history:
                torrent.media = {
                    "tmdbid": history.tmdbid,
                    "type": history.type,
                    "title": history.title,
                    "season": history.seasons,
                    "episode": history.episodes,
                    "image": history.image,
                }
            ret_torrents.append(torrent)
        return ret_torrents

    def set_downloading(self, hash_str, oper: str) -> bool:
        """
        Controlling download tasks start/stop
        """
        if oper == "start":
            return self.start_torrents(hashs=[hash_str])
        elif oper == "stop":
            return self.stop_torrents(hashs=[hash_str])
        return False

    def remove_downloading(self, hash_str: str) -> bool:
        """
        Delete download tasks
        """
        return self.remove_torrents(hashs=[hash_str])
