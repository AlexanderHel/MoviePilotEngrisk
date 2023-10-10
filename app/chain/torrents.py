import re
from typing import Dict, List, Union

from cachetools import cached, TTLCache

from app.chain import ChainBase
from app.core.config import settings
from app.core.context import TorrentInfo, Context, MediaInfo
from app.core.metainfo import MetaInfo
from app.db import SessionFactory
from app.db.site_oper import SiteOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.rss import RssHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.schemas import Notification
from app.schemas.types import SystemConfigKey, MessageChannel, NotificationType
from app.utils.singleton import Singleton
from app.utils.string import StringUtils


class TorrentsChain(ChainBase, metaclass=Singleton):
    """
    The home page of the site orRSS Seed treatment chain， Serving subscriptions、 Brush flow, etc.
    """

    _spider_file = "__torrents_cache__"
    _rss_file = "__rss_cache__"

    def __init__(self):
        self._db = SessionFactory()
        super().__init__(self._db)
        self.siteshelper = SitesHelper()
        self.siteoper = SiteOper(self._db)
        self.rsshelper = RssHelper()
        self.systemconfig = SystemConfigOper()

    def remote_refresh(self, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Remote refresh subscription， Send a message
        """
        self.post_message(Notification(channel=channel,
                                       title=f" Start refreshing seeds ...", userid=userid))
        self.refresh()
        self.post_message(Notification(channel=channel,
                                       title=f" Seed refresh complete！", userid=userid))

    def get_torrents(self, stype: str = None) -> Dict[str, List[Context]]:
        """
        Get the current cached seed
        :param stype:  Forcing the cache type to be specified，spider: Crawler cache，rss:rss (computing) cache
        """

        if not stype:
            stype = settings.SUBSCRIBE_MODE

        #  Read cache
        if stype == 'spider':
            return self.load_cache(self._spider_file) or {}
        else:
            return self.load_cache(self._rss_file) or {}

    @cached(cache=TTLCache(maxsize=128 if settings.BIG_MEMORY_MODE else 1, ttl=600))
    def browse(self, domain: str) -> List[TorrentInfo]:
        """
        Browse the content of the site's home page， Return to seed list，TTL (computing) cache10 Minutes
        :param domain:  Site domain name
        """
        logger.info(f' Start acquiring sites {domain}  Latest seeds ...')
        site = self.siteshelper.get_indexer(domain)
        if not site:
            logger.error(f' Website {domain}  Non-existent！')
            return []
        return self.refresh_torrents(site=site)

    @cached(cache=TTLCache(maxsize=128 if settings.BIG_MEMORY_MODE else 1, ttl=300))
    def rss(self, domain: str) -> List[TorrentInfo]:
        """
        Get siteRSS Element， Return to seed list，TTL (computing) cache5 Minutes
        :param domain:  Site domain name
        """
        logger.info(f' Start acquiring sites {domain} RSS ...')
        site = self.siteshelper.get_indexer(domain)
        if not site:
            logger.error(f' Website {domain}  Non-existent！')
            return []
        if not site.get("rss"):
            logger.error(f' Website {domain}  UnconfiguredRSS Address！')
            return []
        rss_items = self.rsshelper.parse(site.get("rss"), True if site.get("proxy") else False)
        if rss_items is None:
            # rss Expire (as in expiration date)， Try to keep the original configuration to generate a newrss
            self.__renew_rss_url(domain=domain, site=site)
            return []
        if not rss_items:
            logger.error(f' Website {domain}  Not availableRSS Digital！')
            return []
        #  Assembled seeds
        ret_torrents: List[TorrentInfo] = []
        for item in rss_items:
            if not item.get("title"):
                continue
            torrentinfo = TorrentInfo(
                site=site.get("id"),
                site_name=site.get("name"),
                site_cookie=site.get("cookie"),
                site_ua=site.get("ua") or settings.USER_AGENT,
                site_proxy=site.get("proxy"),
                site_order=site.get("pri"),
                title=item.get("title"),
                enclosure=item.get("enclosure"),
                page_url=item.get("link"),
                size=item.get("size"),
                pubdate=item["pubdate"].strftime("%Y-%m-%d %H:%M:%S") if item.get("pubdate") else None,
            )
            ret_torrents.append(torrentinfo)

        return ret_torrents

    def refresh(self, stype: str = None, sites: List[int] = None) -> Dict[str, List[Context]]:
        """
        Refresh the site with the latest resources， Recognize and cache it
        :param stype:  Forcing the cache type to be specified，spider: Crawler cache，rss:rss (computing) cache
        :param sites:  Mandatory site designationID Listings， Null reads the set subscription site
        """
        #  Refresh type
        if not stype:
            stype = settings.SUBSCRIBE_MODE

        #  Refresh site
        if not sites:
            sites = self.systemconfig.get(SystemConfigKey.RssSites) or []

        #  Read cache
        torrents_cache = self.get_torrents()

        #  All sites index
        indexers = self.siteshelper.get_indexers()
        #  Traversing site cache resources
        for indexer in indexers:
            #  Sites not turned on do not refresh
            if sites and indexer.get("id") not in sites:
                continue
            domain = StringUtils.get_url_domain(indexer.get("domain"))
            if stype == "spider":
                #  Refresh home seeds
                torrents: List[TorrentInfo] = self.browse(domain=domain)
            else:
                #  Refresh (computer window)RSS Torrent
                torrents: List[TorrentInfo] = self.rss(domain=domain)
            #  Check or refer topubdate Descending order
            torrents.sort(key=lambda x: x.pubdate or '', reverse=True)
            #  Choose an antecedentN Clause (of law or treaty)
            torrents = torrents[:settings.CACHE_CONF.get('refresh')]
            if torrents:
                #  Filtering out untreated seeds
                torrents = [torrent for torrent in torrents
                            if f'{torrent.title}{torrent.description}'
                            not in [f'{t.torrent_info.title}{t.torrent_info.description}'
                                    for t in torrents_cache.get(domain) or []]]
                if torrents:
                    logger.info(f'{indexer.get("name")}  There are {len(torrents)}  New seed')
                else:
                    logger.info(f'{indexer.get("name")}  No new seeds.')
                    continue
                for torrent in torrents:
                    logger.info(f' Processing resources：{torrent.title} ...')
                    #  Recognize
                    meta = MetaInfo(title=torrent.title, subtitle=torrent.description)
                    #  Recognize媒体信息
                    mediainfo: MediaInfo = self.recognize_media(meta=meta)
                    if not mediainfo:
                        logger.warn(f' No media messages recognized， Caption：{torrent.title}')
                        #  Storing empty media messages
                        mediainfo = MediaInfo()
                    #  Cleaning up redundant data
                    mediainfo.clear()
                    #  (textual) context
                    context = Context(meta_info=meta, media_info=mediainfo, torrent_info=torrent)
                    #  Add to cache
                    if not torrents_cache.get(domain):
                        torrents_cache[domain] = [context]
                    else:
                        torrents_cache[domain].append(context)
                    #  If the limit is exceeded, remove the preceding
                    if len(torrents_cache[domain]) > settings.CACHE_CONF.get('torrents'):
                        torrents_cache[domain] = torrents_cache[domain][-settings.CACHE_CONF.get('torrents'):]
                #  Recycling resources
                del torrents
            else:
                logger.info(f'{indexer.get("name")}  No access to seeds')

        #  Save cache locally
        if stype == "spider":
            self.save_cache(torrents_cache, self._spider_file)
        else:
            self.save_cache(torrents_cache, self._rss_file)

        #  Come (or go) back
        return torrents_cache

    def __renew_rss_url(self, domain: str, site: dict):
        """
        Keep the original configuration to generate a newrss Address
        """
        try:
            # RSS Expired links
            logger.error(f" Website {domain} RSS Link has expired， Trying to get it automatically！")
            #  Automatic generationrss Address
            rss_url, errmsg = self.rsshelper.get_rss_link(
                url=site.get("url"),
                cookie=site.get("cookie"),
                ua=site.get("ua") or settings.USER_AGENT,
                proxy=True if site.get("proxy") else False
            )
            if rss_url:
                #  Get the new date of thepasskey
                match = re.search(r'passkey=([a-zA-Z0-9]+)', rss_url)
                if match:
                    new_passkey = match.group(1)
                    #  Get expiredrss Apart frompasskey Portion
                    new_rss = re.sub(r'&passkey=([a-zA-Z0-9]+)', f'&passkey={new_passkey}', site.get("rss"))
                    logger.info(f" Updating the site {domain} RSS Address ...")
                    self.siteoper.update_rss(domain=domain, rss=new_rss)
                else:
                    #  Send a message
                    self.post_message(
                        Notification(mtype=NotificationType.SiteMessage, title=f" Website {domain} RSS Link has expired"))
            else:
                self.post_message(
                    Notification(mtype=NotificationType.SiteMessage, title=f" Website {domain} RSS Link has expired"))
        except Exception as e:
            print(str(e))
            self.post_message(Notification(mtype=NotificationType.SiteMessage, title=f" Website {domain} RSS Link has expired"))
