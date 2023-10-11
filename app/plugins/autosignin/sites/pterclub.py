import json
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.string import StringUtils


class PTerClub(_ISiteSigninHandler):
    """
    Cat check-in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "pterclub.com"

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

        #  Sign in
        html_text = self.get_page_source(url='https://pterclub.com/attendance-ajax.php',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)
        if not html_text:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Please checkcookie Whether or not it has expired'
        try:
            sign_dict = json.loads(html_text)
        except Exception as e:
            logger.error(f"{site}  Failed to sign in， Check-in interface return data exception， Error message：{e}")
            return False, ' Failed to sign in， Check-in interface return data exception'
        if sign_dict['status'] == '1':
            # {"status":"1","data":" ( Check-in has been successful300)","message":"<p> This is your first<b>237</b> Secondary check-in，
            #  Signed in continuously<b>237</b> Sky。</p><p> This check-in gets<b>300</b> Grams of cat food。</p>"}
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
        else:
            # {"status":"0","data":" Pardon me","message":" You've already signed in today.， Please do not refresh repeatedly。"}
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'
