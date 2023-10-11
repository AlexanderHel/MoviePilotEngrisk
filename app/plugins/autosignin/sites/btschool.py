from typing import Tuple

from ruamel.yaml import CommentedMap

from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.string import StringUtils


class BTSchool(_ISiteSigninHandler):
    """
    School check-in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "pt.btschool.club"

    #  Signed in
    _sign_text = ' Daily sign-in'

    @classmethod
    def match(cls, url) -> bool:
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
        render = site_info.get("render")
        proxy = site_info.get("proxy")

        logger.info(f"{site}  Start checking in.")
        #  Determine if you have signed in today
        html_text = self.get_page_source(url='https://pt.btschool.club',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)

        if not html_text:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'

        if "login.php" in html_text:
            logger.error(f"{site}  Failed to sign in，Cookie Lose effectiveness")
            return False, ' Failed to sign in，Cookie Lose effectiveness'

        #  Signed in
        if self._sign_text not in html_text:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        html_text = self.get_page_source(url='https://pt.btschool.club/index.php?action=addbonus',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)

        if not html_text:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Check-in interface request failed'

        #  Sign in successfully
        if self._sign_text not in html_text:
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
