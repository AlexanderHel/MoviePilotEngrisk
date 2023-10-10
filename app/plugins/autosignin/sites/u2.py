import datetime
import random
import re
from typing import Tuple

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class U2(_ISiteSigninHandler):
    """
    U2 Sign in  Randomization
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "u2.dmhy.org"

    #  Signed in
    _sign_regex = ['<a href="showup.php"> Signed in</a>',
                   '<a href="showup.php">Show Up</a>',
                   '<a href="showup.php">Показать</a>',
                   '<a href="showup.php"> Signed</a>',
                   '<a href="showup.php"> Signed</a>']

    #  Sign in successfully
    _success_text = "window.location.href = 'showup.php';</script>"

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

        now = datetime.datetime.now()
        #  Determine if the current time is less than9 Point (in space or time)
        if now.hour < 9:
            logger.error(f"{site}  Failed to sign in，9 Don't sign in before midnight.")
            return False, ' Failed to sign in，9 Don't sign in before midnight.'
        
        #  Get pagehtml
        html_text = self.get_page_source(url="https://u2.dmhy.org/showup.php",
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

        #  Parsing without signing inhtml
        html = etree.HTML(html_text)

        if not html:
            return False, ' Failed to sign in'

        #  Get sign-in parameters
        req = html.xpath("//form//td/input[@name='req']/@value")[0]
        hash_str = html.xpath("//form//td/input[@name='hash']/@value")[0]
        form = html.xpath("//form//td/input[@name='form']/@value")[0]
        submit_name = html.xpath("//form//td/input[@type='submit']/@name")
        submit_value = html.xpath("//form//td/input[@type='submit']/@value")
        if not re or not hash_str or not form or not submit_name or not submit_value:
            logger.error("{site}  Failed to sign in， No relevant check-in parameters were obtained")
            return False, ' Failed to sign in'

        #  Randomize an answer
        answer_num = random.randint(0, 3)
        data = {
            'req': req,
            'hash': hash_str,
            'form': form,
            'message': ' Everything is as it should be~',
            submit_name[answer_num]: submit_value[answer_num]
        }
        #  Sign in
        sign_res = RequestUtils(cookies=site_cookie,
                                ua=ua,
                                proxies=settings.PROXY if proxy else None
                                ).post_res(url="https://u2.dmhy.org/showup.php?action=show",
                                           data=data)
        if not sign_res or sign_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Check-in interface request failed'

        #  Determine if sign-in is successful
        # sign_res.text = "<script type="text/javascript">window.location.href = 'showup.php';</script>"
        if self._success_text in sign_res.text:
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
        else:
            logger.error(f"{site}  Failed to sign in， Unknown cause")
            return False, ' Failed to sign in， Unknown cause'
