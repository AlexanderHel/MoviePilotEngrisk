import base64
from typing import Tuple, Optional
from urllib.parse import urljoin

from lxml import etree
from sqlalchemy.orm import Session

from app.chain import ChainBase
from app.chain.site import SiteChain
from app.core.config import settings
from app.db.site_oper import SiteOper
from app.db.siteicon_oper import SiteIconOper
from app.helper.cloudflare import under_challenge
from app.helper.cookiecloud import CookieCloudHelper
from app.helper.message import MessageHelper
from app.helper.rss import RssHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils


class CookieCloudChain(ChainBase):
    """
    CookieCloud Process chain
    """

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.siteoper = SiteOper(self._db)
        self.siteiconoper = SiteIconOper(self._db)
        self.siteshelper = SitesHelper()
        self.rsshelper = RssHelper()
        self.sitechain = SiteChain(self._db)
        self.message = MessageHelper()
        self.cookiecloud = CookieCloudHelper(
            server=settings.COOKIECLOUD_HOST,
            key=settings.COOKIECLOUD_KEY,
            password=settings.COOKIECLOUD_PASSWORD
        )

    def process(self, manual=False) -> Tuple[bool, str]:
        """
        Pass (a bill or inspection etc)CookieCloud Synchronization siteCookie
        """
        logger.info(" Start synchronizationCookieCloud Website ...")
        cookies, msg = self.cookiecloud.download()
        if not cookies:
            logger.error(f"CookieCloud Synchronization failure：{msg}")
            if manual:
                self.message.put(f"CookieCloud Synchronization failure： {msg}")
            return False, msg
        #  Save (a file etc) (computing)Cookie Or add a new site
        _update_count = 0
        _add_count = 0
        _fail_count = 0
        for domain, cookie in cookies.items():
            #  Get site information
            indexer = self.siteshelper.get_indexer(domain)
            site_info = self.siteoper.get_by_domain(domain)
            if site_info:
                #  Check site connectivity
                status, msg = self.sitechain.test(domain)
                #  Updating the siteCookie
                if status:
                    logger.info(f" Website【{site_info.name}】 Connectivity is normal， AsynchronousCookieCloud Digital")
                    #  Updating the siterss Address
                    if not site_info.public and not site_info.rss:
                        #  Automatic generationrss Address
                        rss_url, errmsg = self.rsshelper.get_rss_link(
                            url=site_info.url,
                            cookie=cookie,
                            ua=settings.USER_AGENT,
                            proxy=True if site_info.proxy else False
                        )
                        if rss_url:
                            logger.info(f" Updating the site {domain} RSS Address ...")
                            self.siteoper.update_rss(domain=domain, rss=rss_url)
                        else:
                            logger.warn(errmsg)
                    continue
                #  Updating the siteCookie
                logger.info(f" Updating the site {domain} Cookie ...")
                self.siteoper.update_cookie(domain=domain, cookies=cookie)
                _update_count += 1
            elif indexer:
                #  New sites
                res = RequestUtils(cookies=cookie,
                                   ua=settings.USER_AGENT
                                   ).get_res(url=indexer.get("domain"))
                if res and res.status_code in [200, 500, 403]:
                    if not indexer.get("public") and not SiteUtils.is_logged_in(res.text):
                        _fail_count += 1
                        if under_challenge(res.text):
                            logger.warn(f" Website {indexer.get('name')}  (indicates passive-voice clauses)Cloudflare Defend， Unable to log in， Unable to add site")
                            continue
                        logger.warn(
                            f" Website {indexer.get('name')}  Login failure， No account on the site orCookie Expired， Unable to add site")
                        continue
                elif res is not None:
                    _fail_count += 1
                    logger.warn(f" Website {indexer.get('name')}  Connection status code：{res.status_code}， Unable to add site")
                    continue
                else:
                    _fail_count += 1
                    logger.warn(f" Website {indexer.get('name')}  Connection failure， Unable to add site")
                    continue
                #  Gainrss Address
                rss_url = None
                if not indexer.get("public") and indexer.get("domain"):
                    #  Automatic generationrss Address
                    rss_url, errmsg = self.rsshelper.get_rss_link(url=indexer.get("domain"),
                                                                  cookie=cookie,
                                                                  ua=settings.USER_AGENT)
                    if errmsg:
                        logger.warn(errmsg)
                #  Insertion into the database
                logger.info(f" New sites {indexer.get('name')} ...")
                self.siteoper.add(name=indexer.get("name"),
                                  url=indexer.get("domain"),
                                  domain=domain,
                                  cookie=cookie,
                                  rss=rss_url,
                                  public=1 if indexer.get("public") else 0)
                _add_count += 1

            #  Save site icon
            if indexer:
                site_icon = self.siteiconoper.get_by_domain(domain)
                if not site_icon or not site_icon.base64:
                    logger.info(f" Start caching site {indexer.get('name')}  Icon (computing) ...")
                    icon_url, icon_base64 = self.__parse_favicon(url=indexer.get("domain"),
                                                                 cookie=cookie,
                                                                 ua=settings.USER_AGENT)
                    if icon_url:
                        self.siteiconoper.update_icon(name=indexer.get("name"),
                                                      domain=domain,
                                                      icon_url=icon_url,
                                                      icon_base64=icon_base64)
                        logger.info(f" Cache site {indexer.get('name')}  Icon success")
                    else:
                        logger.warn(f" Cache site {indexer.get('name')}  Icon failure")
        #  Processing completed
        ret_msg = f" Updated.{_update_count} Stations， Added{_add_count} Stations"
        if _fail_count > 0:
            ret_msg += f"，{_fail_count} Failed to add a site， Will be retried the next time it is synchronized， It can also be added manually"
        if manual:
            self.message.put(f"CookieCloud Synchronization successful, {ret_msg}")
        logger.info(f"CookieCloud Synchronization successful：{ret_msg}")
        return True, ret_msg

    @staticmethod
    def __parse_favicon(url: str, cookie: str, ua: str) -> Tuple[str, Optional[str]]:
        """
        Parse sitefavicon, Come (or go) backbase64 fav Icon (computing)
        :param url:  Site address
        :param cookie: Cookie
        :param ua: User-Agent
        :return:
        """
        favicon_url = urljoin(url, "favicon.ico")
        res = RequestUtils(cookies=cookie, timeout=60, ua=ua).get_res(url=url)
        if res:
            html_text = res.text
        else:
            logger.error(f" Failed to get site page：{url}")
            return favicon_url, None
        html = etree.HTML(html_text)
        if html:
            fav_link = html.xpath('//head/link[contains(@rel, "icon")]/@href')
            if fav_link:
                favicon_url = urljoin(url, fav_link[0])

        res = RequestUtils(cookies=cookie, timeout=20, ua=ua).get_res(url=favicon_url)
        if res:
            return favicon_url, base64.b64encode(res.content).decode()
        else:
            logger.error(f" Failed to get site icon：{favicon_url}")
        return favicon_url, None
