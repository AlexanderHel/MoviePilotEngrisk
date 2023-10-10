import json
from typing import Tuple

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class HDChina(_ISiteSigninHandler):
    """
    Porcelain check-in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "hdchina.org"

    #  Signed in
    _sign_regex = ['<a class="label label-default" href="#"> Signed in</a>']

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

        #  Trying to solve porcelaincookie Expires after daily check-in, Retain onlyhdchina= Portion
        cookie = ""
        #  String splitting by semicolon
        sub_strs = site_cookie.split(";")
        #  Iterate over each substring
        for sub_str in sub_strs:
            if "hdchina=" in sub_str:
                #  If the substring contains"hdchina="， Then the substring is retained
                cookie += sub_str + ";"

        if "hdchina=" not in cookie:
            logger.error(f"{site}  Failed to sign in，Cookie Lose effectiveness")
            return False, ' Failed to sign in，Cookie Lose effectiveness'

        site_cookie = cookie
        #  Get pagehtml
        html_res = RequestUtils(cookies=site_cookie,
                                ua=ua,
                                proxies=proxies
                                ).get_res(url="https://hdchina.org/index.php")
        if not html_res or html_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'

        if "login.php" in html_res.text or " Blocking page" in html_res.text:
            logger.error(f"{site}  Failed to sign in，Cookie Lose effectiveness")
            return False, ' Failed to sign in，Cookie Lose effectiveness'

        #  Get the newly returnedcookie Check-in
        site_cookie = ';'.join(['{}={}'.format(k, v) for k, v in html_res.cookies.get_dict().items()])

        #  Determine if you are signed in or not
        html_res.encoding = "utf-8"
        sign_status = self.sign_in_result(html_res=html_res.text,
                                          regexs=self._sign_regex)
        if sign_status:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        #  Parsing without signing inhtml
        html = etree.HTML(html_res.text)

        if not html:
            return False, ' Failed to sign in'

        # x_csrf
        x_csrf = html.xpath("//meta[@name='x-csrf']/@content")[0]
        if not x_csrf:
            logger.error("{site}  Failed to sign in， Gainx-csrf Fail (e.g. experiments)")
            return False, ' Failed to sign in'
        logger.debug(f" Getx-csrf {x_csrf}")

        #  Sign in
        data = {
            'csrf': x_csrf
        }
        sign_res = RequestUtils(cookies=site_cookie,
                                ua=ua,
                                proxies=proxies
                                ).post_res(url="https://hdchina.org/plugin_sign-in.php?cmd=signin", data=data)
        if not sign_res or sign_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Check-in interface request failed'

        sign_dict = json.loads(sign_res.text)
        logger.debug(f" Check-in returns results {sign_dict}")
        if sign_dict['state']:
            # {'state': 'success', 'signindays': 10, 'integral': 20}
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
        else:
            # {'state': False, 'msg': ' ErroneousCSRF / Incorrect CSRF token'}
            logger.error(f"{site}  Failed to sign in， ErroneousCSRF / Incorrect CSRF token")
            return False, ' Failed to sign in'
