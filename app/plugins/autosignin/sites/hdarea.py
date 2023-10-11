from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class HDArea(_ISiteSigninHandler):
    """
    That's a big sign.
    """

    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "hdarea.club"

    #  Sign in successfully
    _success_text = " At this check-in you get"
    _repeat_text = " Please don't double check in!"

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
        proxies = settings.PROXY if site_info.get("proxy") else None

        #  Get pagehtml
        data = {
            'action': 'sign_in'
        }
        html_res = RequestUtils(cookies=site_cookie,
                                ua=ua,
                                proxies=proxies
                                ).post_res(url="https://www.hdarea.club/sign_in.php", data=data)
        if not html_res or html_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'

        if "login.php" in html_res.text:
            logger.error(f"{site}  Failed to sign in，Cookie Lose effectiveness")
            return False, ' Failed to sign in，Cookie Lose effectiveness'

        #  Determine if you are signed in or not
        # ' Signed in continuously278 Sky， With this check-in you get100 Magic bonus!'
        if self._success_text in html_res.text:
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
        if self._repeat_text in html_res.text:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'
        logger.error(f"{site}  Failed to sign in， Check-in interface returns {html_res.text}")
        return False, ' Failed to sign in'
