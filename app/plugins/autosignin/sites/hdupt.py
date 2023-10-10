import re
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.string import StringUtils


class HDUpt(_ISiteSigninHandler):
    """
    hdu Sign in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "pt.hdupt.com"

    #  Signed in
    _sign_regex = ['<span id="yiqiandao">']

    #  Sign in successfully
    _success_text = ' Get charms for this check-in'

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
        html_text = self.get_page_source(url='https://pt.hdupt.com',
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

        sign_status = self.sign_in_result(html_res=html_text,
                                          regexs=self._sign_regex)
        if sign_status:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        #  Sign in
        html_text = self.get_page_source(url='https://pt.hdupt.com/added.php?action=qiandao',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)
        if not html_text:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'

        logger.debug(f"{site}  Check-in interface returns {html_text}")
        #  Determine if you are signed in or not sign_res.text = ".23"
        if len(list(map(int, re.findall(r"\d+", html_text)))) > 0:
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'

        logger.error(f"{site}  Failed to sign in， Check-in interface returns {html_text}")
        return False, ' Failed to sign in'
