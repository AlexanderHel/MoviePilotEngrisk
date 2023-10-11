import json
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class Hares(_ISiteSigninHandler):
    """
    White rabbit signing in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "club.hares.top"

    #  Signed in
    _sign_text = ' Signed in'

    @classmethod
    def match(cls, url: str) -> bool:
        """
        Based on siteUrl Determine if the current site check-in class matches， In most cases it is sufficient to use the default implementation
        :param url:  WebsiteUrl
        :return:  Whether or not it matches， If a match is made then the class'ssignin Methodologies
        """
        return True if StringUtils.url_equal(url, cls.site_url) else False

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """
        Perform check-in operations
        :param site_info:  Site information， Contains siteUrl、 WebsiteCookie、UA And other information
        :return:  Check-in results information
        """
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxy = site_info.get("proxy")
        render = site_info.get("render")

        #  Get pagehtml
        html_text = self.get_page_source(url='https://club.hares.top',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)

        if not html_text:
            logger.error(f"{site}  Simulated access failure， Please check site connectivity")
            return False, ' Simulated access failure， Please check site connectivity'

        if "login.php" in html_text:
            logger.error(f"{site}  Simulated access failure，Cookie Lose effectiveness")
            return False, ' Simulated access failure，Cookie Lose effectiveness'

        # if self._sign_text in html_res.text:
        #     logger.info(f" Signed in today")
        #     return True, ' Signed in today'

        headers = {
            'Accept': 'application/json',
            "User-Agent": ua
        }
        sign_res = RequestUtils(cookies=site_cookie,
                                headers=headers,
                                proxies=settings.PROXY if proxy else None
                                ).get_res(url="https://club.hares.top/attendance.php?action=sign")
        if not sign_res or sign_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Check-in interface request failed'

        # {"code":1,"msg":" You've already signed in today."}
        # {"code":0,"msg":" Sign in successfully"}
        sign_dict = json.loads(sign_res.text)
        if sign_dict['code'] == 0:
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
        else:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'
