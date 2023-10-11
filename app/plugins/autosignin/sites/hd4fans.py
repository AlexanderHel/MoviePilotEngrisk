from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class HD4fans(_ISiteSigninHandler):
    """
    Beastly sign-in
    """

    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "pt.hd4fans.org"

    #  Sign in successfully
    _repeat_text = '<span id="checkedin">[ Sign in successfully]</span>'
    _success_text = " Sign in successfully"

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
        html_text = self.get_page_source(url='https://pt.hd4fans.org/index.php',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)
        if not html_text:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'

        if "login.php" in html_text:
            logger.error(f"{site}  Failed to sign in，cookie Lose effectiveness")
            return False, ' Failed to sign in，cookie Lose effectiveness'

        #  Determine if you are signed in or not
        if self._repeat_text in html_text:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        #  Sign in
        data = {
            'action': 'checkin'
        }
        sign_res = RequestUtils(cookies=site_cookie,
                                ua=ua,
                                proxies=settings.PROXY if proxy else None
                                ).post_res(url="https://pt.hd4fans.org/checkin.php", data=data)
        if not sign_res or sign_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'
        # sign_res.text= This check-in magic
        if sign_res.text and sign_res.text.isdigit():
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'

        logger.error(f"{site}  Failed to sign in， Check-in interface returns {sign_res.text}")
        return False, ' Failed to sign in'
