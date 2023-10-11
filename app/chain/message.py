from typing import Any

from app.chain.download import *
from app.chain.media import MediaChain
from app.chain.search import SearchChain
from app.chain.subscribe import SubscribeChain
from app.core.context import MediaInfo
from app.core.event import EventManager
from app.log import logger
from app.schemas import Notification
from app.schemas.types import EventType, MessageChannel

#  Current page
_current_page: int = 0
#  Current metadata
_current_meta: Optional[MetaBase] = None
#  Current media information
_current_media: Optional[MediaInfo] = None


class MessageChain(ChainBase):
    """
    Foreign message processing chain
    """
    #  Cached user data {userid: {type: str, items: list}}
    _cache_file = "__user_messages__"
    #  Amount of data per page
    _page_size: int = 8

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.downloadchain = DownloadChain(self._db)
        self.subscribechain = SubscribeChain(self._db)
        self.searchchain = SearchChain(self._db)
        self.medtachain = MediaChain(self._db)
        self.torrent = TorrentHelper()
        self.eventmanager = EventManager()
        self.torrenthelper = TorrentHelper()

    def process(self, body: Any, form: Any, args: Any) -> None:
        """
        Identify message content， Executable operation
        """
        #  Declare global variables
        global _current_page, _current_meta, _current_media
        #  Get message content
        info = self.message_parser(body=body, form=form, args=args)
        if not info:
            return
        #  (fig.) channel
        channel = info.channel
        #  SubscribersID
        userid = info.userid
        #  User id
        username = info.username
        if not userid:
            logger.debug(f' No user recognizedID：{body}{form}{args}')
            return
        #  Message
        text = str(info.text).strip() if info.text else None
        if not text:
            logger.debug(f' Message content not recognized：：{body}{form}{args}')
            return
        #  Load cache
        user_cache: Dict[str, dict] = self.load_cache(self._cache_file) or {}
        #  Processing messages
        logger.info(f' Receive user message content， Subscribers：{userid}， Element：{text}')
        if text.startswith('/'):
            #  Execute a command
            self.eventmanager.send_event(
                EventType.CommandExcute,
                {
                    "cmd": text,
                    "user": userid,
                    "channel": channel
                }
            )

        elif text.isdigit():
            #  (computing) cache
            cache_data: dict = user_cache.get(userid)
            #  Select project
            if not cache_data \
                    or not cache_data.get('items') \
                    or len(cache_data.get('items')) < int(text):
                #  Send a message
                self.post_message(Notification(channel=channel, title=" Input error！", userid=userid))
                return
            #  (computing) cache类型
            cache_type: str = cache_data.get('type')
            #  (computing) cache列表
            cache_list: list = cache_data.get('items')
            #  Option
            if cache_type == "Search":
                mediainfo: MediaInfo = cache_list[int(text) + _current_page * self._page_size - 1]
                _current_media = mediainfo
                #  Querying missing media information
                exist_flag, no_exists = self.downloadchain.get_no_exists_info(meta=_current_meta,
                                                                              mediainfo=_current_media)
                if exist_flag:
                    self.post_message(
                        Notification(channel=channel,
                                     title=f"{_current_media.title_year}"
                                           f"{_current_meta.sea}  Already exists in the media library",
                                     userid=userid))
                    return
                #  Send missing media messages
                if no_exists:
                    #  Send a message
                    messages = [
                        f" (prefix indicating ordinal number, e.g. first, number two etc) {sea}  Seasonal shortage {StringUtils.str_series(no_exist.episodes) if no_exist.episodes else no_exist.total_episode}  Classifier for sections of a tv series e.g. episode"
                        for sea, no_exist in no_exists.get(mediainfo.tmdb_id).items()]
                    self.post_message(Notification(channel=channel,
                                                   title=f"{mediainfo.title_year}：\n" + "\n".join(messages)))
                #  Search for seeds， Filter out unwanted episodes， Facilitate the selection
                logger.info(f"{mediainfo.title_year}  Not available in the media library， Start searching ...")
                self.post_message(
                    Notification(channel=channel,
                                 title=f" Start searching {mediainfo.type.value} {mediainfo.title_year} ...",
                                 userid=userid))
                #  Start searching
                contexts = self.searchchain.process(mediainfo=mediainfo,
                                                    no_exists=no_exists)
                if not contexts:
                    #  No data
                    self.post_message(Notification(
                        channel=channel, title=f"{mediainfo.title}"
                                               f"{_current_meta.sea}  Required resources not searched！",
                        userid=userid))
                    return
                #  Sort search results
                contexts = self.torrenthelper.sort_torrents(contexts)
                #  Determine whether to set up automatic download
                auto_download_user = settings.AUTO_DOWNLOAD_USER
                #  Match to automatically download users
                if auto_download_user and any(userid == user for user in auto_download_user.split(",")):
                    logger.info(f" Subscribers {userid}  Among the users of automatic downloads， Starting automatic merit-based downloads")
                    #  Automatic selection of downloads
                    self.__auto_download(channel=channel,
                                         cache_list=contexts,
                                         userid=userid,
                                         username=username)
                else:
                    #  Updating the cache
                    user_cache[userid] = {
                        "type": "Torrent",
                        "items": contexts
                    }
                    #  Send seed data
                    logger.info(f" Search to {len(contexts)}  Data entry， Start sending selection messages ...")
                    self.__post_torrents_message(channel=channel,
                                                 title=mediainfo.title,
                                                 items=contexts[:self._page_size],
                                                 userid=userid,
                                                 total=len(contexts))

            elif cache_type == "Subscribe":
                #  Subscribe to media
                mediainfo: MediaInfo = cache_list[int(text) - 1]
                #  Querying missing media information
                exist_flag, _ = self.downloadchain.get_no_exists_info(meta=_current_meta,
                                                                      mediainfo=mediainfo)
                if exist_flag:
                    self.post_message(Notification(
                        channel=channel,
                        title=f"{mediainfo.title_year}"
                              f"{_current_meta.sea}  Already exists in the media library",
                        userid=userid))
                    return
                #  Add subscription， Be in a state ofN
                self.subscribechain.add(title=mediainfo.title,
                                        year=mediainfo.year,
                                        mtype=mediainfo.type,
                                        tmdbid=mediainfo.tmdb_id,
                                        season=_current_meta.begin_season,
                                        channel=channel,
                                        userid=userid,
                                        username=username)
            elif cache_type == "Torrent":
                if int(text) == 0:
                    #  Automatic selection of downloads
                    self.__auto_download(channel=channel,
                                         cache_list=cache_list,
                                         userid=userid,
                                         username=username)
                else:
                    #  Download seeds
                    context: Context = cache_list[int(text) - 1]
                    #  Downloading
                    self.downloadchain.download_single(context, userid=userid, channel=channel)

        elif text.lower() == "p":
            #  Preceding page
            cache_data: dict = user_cache.get(userid)
            if not cache_data:
                #  No cache
                self.post_message(Notification(
                    channel=channel, title=" Input error！", userid=userid))
                return

            if _current_page == 0:
                #  First page
                self.post_message(Notification(
                    channel=channel, title=" It's already on the first page.！", userid=userid))
                return
            cache_type: str = cache_data.get('type')
            cache_list: list = cache_data.get('items')
            #  One page down
            _current_page -= 1
            if _current_page == 0:
                start = 0
                end = self._page_size
            else:
                start = _current_page * self._page_size
                end = start + self._page_size
            if cache_type == "Torrent":
                #  Updating the cache
                user_cache[userid] = {
                    "type": "Torrent",
                    "items": cache_list[start:end]
                }
                #  Send seed data
                self.__post_torrents_message(channel=channel,
                                             title=_current_media.title,
                                             items=cache_list[start:end],
                                             userid=userid,
                                             total=len(cache_list))
            else:
                #  Send media data
                self.__post_medias_message(channel=channel,
                                           title=_current_meta.name,
                                           items=cache_list[start:end],
                                           userid=userid,
                                           total=len(cache_list))

        elif text.lower() == "n":
            #  Next page
            cache_data: dict = user_cache.get(userid)
            if not cache_data:
                #  No cache
                self.post_message(Notification(
                    channel=channel, title=" Input error！", userid=userid))
                return
            cache_type: str = cache_data.get('type')
            cache_list: list = cache_data.get('items')
            total = len(cache_list)
            #  Add a page
            cache_list = cache_list[
                         (_current_page + 1) * self._page_size:(_current_page + 2) * self._page_size]
            if not cache_list:
                #  No data
                self.post_message(Notification(
                    channel=channel, title=" It's the last page.！", userid=userid))
                return
            else:
                #  Add a page
                _current_page += 1
                if cache_type == "Torrent":
                    #  Updating the cache
                    user_cache[userid] = {
                        "type": "Torrent",
                        "items": cache_list
                    }
                    #  Send seed data
                    self.__post_torrents_message(channel=channel,
                                                 title=_current_media.title,
                                                 items=cache_list, userid=userid, total=total)
                else:
                    #  Send media data
                    self.__post_medias_message(channel=channel,
                                               title=_current_meta.name,
                                               items=cache_list, userid=userid, total=total)

        else:
            #  Search or subscribe
            if text.startswith(" Subscribe to"):
                #  Subscribe to
                content = re.sub(r" Subscribe to[:：\s]*", "", text)
                action = "Subscribe"
            elif text.startswith("#") \
                    or re.search(r"^ Treat (to a meal etc)[ Asking for help]", text) \
                    or re.search(r"[?？]$", text) \
                    or StringUtils.count_words(text) > 10 \
                    or text.find(" Proceed with") != -1:
                #  Chats
                content = text
                action = "chat"
            else:
                #  Look for sth.
                content = re.sub(r"( Look for sth.| Downloading)[:：\s]*", "", text)
                action = "Search"

            if action in ["Subscribe", "Search"]:
                #  Look for sth.
                meta, medias = self.medtachain.search(content)
                #  Recognize
                if not meta.name:
                    self.post_message(Notification(
                        channel=channel, title=" Input content not recognized！", userid=userid))
                    return
                #  Start searching
                if not medias:
                    self.post_message(Notification(
                        channel=channel, title=f"{meta.name}  No corresponding media information was found！", userid=userid))
                    return
                logger.info(f" Search to {len(medias)}  Relevant media information")
                #  Record the current state
                _current_meta = meta
                user_cache[userid] = {
                    'type': action,
                    'items': medias
                }
                _current_page = 0
                _current_media = None
                #  Send media list
                self.__post_medias_message(channel=channel,
                                           title=meta.name,
                                           items=medias[:self._page_size],
                                           userid=userid, total=len(medias))
            else:
                #  Broadcasting incident
                self.eventmanager.send_event(
                    EventType.UserMessage,
                    {
                        "text": content,
                        "userid": userid,
                        "channel": channel
                    }
                )

        #  Save cache
        self.save_cache(user_cache, self._cache_file)

    def __auto_download(self, channel, cache_list, userid, username):
        """
        Automatic merit-based downloading
        """
        #  Querying missing media information
        exist_flag, no_exists = self.downloadchain.get_no_exists_info(meta=_current_meta,
                                                                      mediainfo=_current_media)
        if exist_flag:
            self.post_message(Notification(
                channel=channel,
                title=f"{_current_media.title_year}"
                      f"{_current_meta.sea}  Already exists in the media library",
                userid=userid))
            return
        #  Batch download
        downloads, lefts = self.downloadchain.batch_download(contexts=cache_list,
                                                             no_exists=no_exists,
                                                             channel=channel,
                                                             userid=userid)
        if downloads and not lefts:
            #  All downloads complete
            logger.info(f'{_current_media.title_year}  Download complete')
        else:
            #  Unfinished downloads
            logger.info(f'{_current_media.title_year}  Not downloaded not complete， Add subscription ...')
            #  Add subscription， Be in a state ofR
            self.subscribechain.add(title=_current_media.title,
                                    year=_current_media.year,
                                    mtype=_current_media.type,
                                    tmdbid=_current_media.tmdb_id,
                                    season=_current_meta.begin_season,
                                    channel=channel,
                                    userid=userid,
                                    username=username,
                                    state="R")

    def __post_medias_message(self, channel: MessageChannel,
                              title: str, items: list, userid: str, total: int):
        """
        Send media list message
        """
        if total > self._page_size:
            title = f"【{title}】 Total found{total} Related information， Please reply with the corresponding number to select（p:  Preceding page n:  Next page）"
        else:
            title = f"【{title}】 Total found{total} Related information， Please reply with the corresponding number to select"
        self.post_medias_message(Notification(
            channel=channel,
            title=title,
            userid=userid
        ), medias=items)

    def __post_torrents_message(self, channel: MessageChannel, title: str, items: list,
                                userid: str, total: int):
        """
        Send seed list message
        """
        if total > self._page_size:
            title = f"【{title}】 Total found{total} Article related resources， Please reply with the corresponding number to download（0:  Automatic selection p:  Preceding page n:  Next page）"
        else:
            title = f"【{title}】 Total found{total} Article related resources， Please reply with the corresponding number to download（0:  Automatic selection）"
        self.post_torrents_message(Notification(
            channel=channel,
            title=title,
            userid=userid
        ), torrents=items)
