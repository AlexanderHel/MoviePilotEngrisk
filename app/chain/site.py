import re
from typing import Union, Tuple

from sqlalchemy.orm import Session

from app.chain import ChainBase
from app.core.config import settings
from app.db.models.site import Site
from app.db.site_oper import SiteOper
from app.helper.browser import PlaywrightHelper
from app.helper.cloudflare import under_challenge
from app.helper.cookie import CookieHelper
from app.helper.message import MessageHelper
from app.log import logger
from app.schemas import MessageChannel, Notification
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils
from app.utils.string import StringUtils


class SiteChain(ChainBase):
    """
    Site management processing chain
    """

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.siteoper = SiteOper(self._db)
        self.cookiehelper = CookieHelper()
        self.message = MessageHelper()

        #  Special site login authentication
        self.special_site_test = {
            "zhuque.in": self.__zhuque_test,
            # "m-team.io": self.__mteam_test,
        }

    @staticmethod
    def __zhuque_test(site: Site) -> Tuple[bool, str]:
        """
        Determine if the site is logged in：zhuique
        """
        #  Gaintoken
        token = None
        res = RequestUtils(
            ua=site.ua,
            cookies=site.cookie,
            proxies=settings.PROXY if site.proxy else None,
            timeout=15
        ).get_res(url=site.url)
        if res and res.status_code == 200:
            csrf_token = re.search(r'<meta name="x-csrf-token" content="(.+?)">', res.text)
            if csrf_token:
                token = csrf_token.group(1)
        if not token:
            return False, " UnavailableToken"
        #  Calling the query user information interface
        user_res = RequestUtils(
            headers={
                'X-CSRF-TOKEN': token,
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": f"{site.ua}"
            },
            cookies=site.cookie,
            proxies=settings.PROXY if site.proxy else None,
            timeout=15
        ).get_res(url=f"{site.url}api/user/getInfo")
        if user_res and user_res.status_code == 200:
            user_info = user_res.json()
            if user_info and user_info.get("data"):
                return True, " Connection successful"
        return False, "Cookie Expired"

    @staticmethod
    def __mteam_test(site: Site) -> Tuple[bool, str]:
        """
        Determine if the site is logged in：m-team
        """
        url = f"{site.url}api/member/profile"
        res = RequestUtils(
            ua=site.ua,
            cookies=site.cookie,
            proxies=settings.PROXY if site.proxy else None,
            timeout=15
        ).post_res(url=url)
        if res and res.status_code == 200:
            user_info = res.json()
            if user_info and user_info.get("data"):
                return True, " Connection successful"
        return False, "Cookie Expired"

    def test(self, url: str) -> Tuple[bool, str]:
        """
        Test site availability
        :param url:  Site domain name
        :return: ( Availability,  Error message)
        """
        #  Check if the domain name is available
        domain = StringUtils.get_url_domain(url)
        site_info = self.siteoper.get_by_domain(domain)
        if not site_info:
            return False, f" Website【{url}】 Non-existent"

        #  Special site testing
        if self.special_site_test.get(domain):
            return self.special_site_test[domain](site_info)

        #  Generic site testing
        site_url = site_info.url
        site_cookie = site_info.cookie
        ua = site_info.ua
        render = site_info.render
        public = site_info.public
        proxies = settings.PROXY if site_info.proxy else None
        proxy_server = settings.PROXY_SERVER if site_info.proxy else None
        #  Analog login
        try:
            #  Access link
            if render:
                page_source = PlaywrightHelper().get_page_source(url=site_url,
                                                                 cookies=site_cookie,
                                                                 ua=ua,
                                                                 proxies=proxy_server)
                if not public and not SiteUtils.is_logged_in(page_source):
                    if under_challenge(page_source):
                        return False, f" Failure to passCloudflare！"
                    return False, f" Emulation login failure，Cookie Expired！"
            else:
                res = RequestUtils(cookies=site_cookie,
                                   ua=ua,
                                   proxies=proxies
                                   ).get_res(url=site_url)
                #  Determine login status
                if res and res.status_code in [200, 500, 403]:
                    if not public and not SiteUtils.is_logged_in(res.text):
                        if under_challenge(res.text):
                            msg = " Web site has beenCloudflare Defend， Please open the site browser simulation"
                        elif res.status_code == 200:
                            msg = "Cookie Expired"
                        else:
                            msg = f" Status code：{res.status_code}"
                        return False, f"{msg}！"
                    elif public and res.status_code != 200:
                        return False, f" Status code：{res.status_code}！"
                elif res is not None:
                    return False, f" Status code：{res.status_code}！"
                else:
                    return False, f" Unable to open website！"
        except Exception as e:
            return False, f"{str(e)}！"
        return True, " Connection successful"

    def remote_list(self, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Search all sites， Send a message
        """
        site_list = self.siteoper.list()
        if not site_list:
            self.post_message(Notification(
                channel=channel,
                title=" No site information is maintained！",
                userid=userid))
        title = f" Have altogether {len(site_list)}  Stations， Responding to the corresponding command operation：" \
                f"\n-  Disable site：/site_disable [id]" \
                f"\n-  Enabling site：/site_enable [id]" \
                f"\n-  Updating the siteCookie：/site_cookie [id] [username] [password]"
        messages = []
        for site in site_list:
            if site.render:
                render_str = "🧭"
            else:
                render_str = ""
            if site.is_active:
                messages.append(f"{site.id}. [{site.name}]({site.url}){render_str}")
            else:
                messages.append(f"{site.id}. {site.name}")
        #  Distribution list
        self.post_message(Notification(
            channel=channel,
            title=title, text="\n".join(messages), userid=userid))

    def remote_disable(self, arg_str, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Disable site
        """
        if not arg_str:
            return
        arg_str = str(arg_str).strip()
        if not arg_str.isdigit():
            return
        site_id = int(arg_str)
        site = self.siteoper.get(site_id)
        if not site:
            self.post_message(Notification(
                channel=channel,
                title=f" Site number {site_id}  Non-existent！",
                userid=userid))
            return
        # Disable site
        self.siteoper.update(site_id, {
            "is_active": False
        })
        #  Resend the message
        self.remote_list(channel, userid)

    def remote_enable(self, arg_str, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Enabling site
        """
        if not arg_str:
            return
        arg_strs = str(arg_str).split()
        for arg_str in arg_strs:
            arg_str = arg_str.strip()
            if not arg_str.isdigit():
                continue
            site_id = int(arg_str)
            site = self.siteoper.get(site_id)
            if not site:
                self.post_message(Notification(
                    channel=channel,
                    title=f" Site number {site_id}  Non-existent！", userid=userid))
                return
            # Disable site
            self.siteoper.update(site_id, {
                "is_active": True
            })
        #  Resend the message
        self.remote_list(channel, userid)

    def update_cookie(self, site_info: Site,
                      username: str, password: str) -> Tuple[bool, str]:
        """
        Update site based on username and passwordCookie
        :param site_info:  Site information
        :param username:  User id
        :param password:  Cryptographic
        :return: ( Success or failure,  Error message)
        """
        #  Updating the siteCookie
        result = self.cookiehelper.get_site_cookie_ua(
            url=site_info.url,
            username=username,
            password=password,
            proxies=settings.PROXY_HOST if site_info.proxy else None
        )
        if result:
            cookie, ua, msg = result
            if not cookie:
                return False, msg
            self.siteoper.update(site_info.id, {
                "cookie": cookie,
                "ua": ua
            })
            return True, msg
        return False, " Unknown error"

    def remote_cookie(self, arg_str: str, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Updating the site with a username and passwordCookie
        """
        err_title = " Please enter the correct command format：/site_cookie [id] [username] [password]，" \
                    "[id] Is the site number，[uername] Is the site username，[password] Is the site password"
        if not arg_str:
            self.post_message(Notification(
                channel=channel,
                title=err_title, userid=userid))
            return
        arg_str = str(arg_str).strip()
        args = arg_str.split()
        if len(args) != 3:
            self.post_message(Notification(
                channel=channel,
                title=err_title, userid=userid))
            return
        site_id = args[0]
        if not site_id.isdigit():
            self.post_message(Notification(
                channel=channel,
                title=err_title, userid=userid))
            return
        #  WebsiteID
        site_id = int(site_id)
        #  Site information
        site_info = self.siteoper.get(site_id)
        if not site_info:
            self.post_message(Notification(
                channel=channel,
                title=f" Site number {site_id}  Non-existent！", userid=userid))
            return
        self.post_message(Notification(
            channel=channel,
            title=f" Start updating【{site_info.name}】Cookie&UA ...", userid=userid))
        #  User id
        username = args[1]
        #  Cryptographic
        password = args[2]
        #  UpdateCookie
        status, msg = self.update_cookie(site_info=site_info,
                                         username=username,
                                         password=password)
        if not status:
            logger.error(msg)
            self.post_message(Notification(
                channel=channel,
                title=f"【{site_info.name}】 Cookie&UA Update failure！",
                text=f" Cause of the error：{msg}",
                userid=userid))
        else:
            self.post_message(Notification(
                channel=channel,
                title=f"【{site_info.name}】 Cookie&UA Successful update",
                userid=userid))
