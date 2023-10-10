import re
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class TTG(_ISiteSigninHandler):
    """
    TTG Sign in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "totheglory.im"

    #  Signed in
    _sign_regex = ['<b style="color:green;"> Signed in</b>']
    _sign_text = ' In favor of， You have signed in today， Don't be greedy.'

    #  Sign in successfully
    _success_text = ' You have signed in continuously'

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
        html_text = self.get_page_source(url="https://totheglory.im",
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

        #  Determine if you are signed in or not
        sign_status = self.sign_in_result(html_res=html_text,
                                          regexs=self._sign_regex)
        if sign_status:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        #  Get sign-in parameters
        signed_timestamp = re.search('(?<=signed_timestamp: ")\\d{10}', html_text).group()
        signed_token = re.search('(?<=signed_token: ").*(?=")', html_text).group()
        logger.debug(f"signed_timestamp={signed_timestamp} signed_token={signed_token}")

        data = {
            'signed_timestamp': signed_timestamp,
            'signed_token': signed_token
        }
        #  Sign in
        sign_res = RequestUtils(cookies=site_cookie,
                                ua=ua,
                                proxies=settings.PROXY if proxy else None
                                ).post_res(url="https://totheglory.im/signed.php",
                                           data=data)
        if not sign_res or sign_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Check-in interface request failed'

        sign_res.encoding = "utf-8"
        if self._success_text in sign_res.text:
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
        if self._sign_text in sign_res.text:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        logger.error(f"{site}  Failed to sign in， Unknown cause")
        return False, ' Failed to sign in， Unknown cause'
