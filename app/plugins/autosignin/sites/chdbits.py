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


class CHDBits(_ISiteSigninHandler):
    """
    Rainbow island check-in
    If you fill inopenai key Then callchatgpt Get answers
    Otherwise random
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "ptchdbits.co"

    #  Signed in
    _sign_regex = [' I've already signed in today.']

    #  Sign in successfully， To be supplemented
    _success_regex = ['\\d+ Point of magic power']

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

        #  Determine if you have signed in today
        html_text = self.get_page_source(url='https://ptchdbits.co/bakatest.php',
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

        #  Parsing without signing inhtml
        html = etree.HTML(html_text)

        if not html:
            return False, ' Failed to sign in'

        #  Fetch page issues、 Solution
        questionid = html.xpath("//input[@name='questionid']/@value")[0]
        option_ids = html.xpath("//input[@name='choice[]']/@value")
        question_str = html.xpath("//td[@class='text' and contains(text(),' Excuse me, may i ask...?：')]/text()")[0]

        #  Regular fetch problems
        match = re.search(r' Excuse me, may i ask...?：(.+)', question_str)
        if match:
            question_str = match.group(1)
            logger.debug(f" Getting to the sign-in question {question_str}")
        else:
            logger.error(f" Not getting the sign-in issue")
            return False, f"【{site}】 Failed to sign in， Not getting the sign-in issue"

        #  Correct answer， Default random， In the event thatgpt Returned withgpt Returned answers submitted
        choice = [option_ids[random.randint(0, len(option_ids) - 1)]]

        #  Sign in
        return self.__signin(questionid=questionid,
                             choice=choice,
                             site_cookie=site_cookie,
                             ua=ua,
                             proxy=proxy,
                             site=site)

    def __signin(self, questionid: str,
                 choice: list,
                 site: str,
                 site_cookie: str,
                 ua: str,
                 proxy: bool) -> Tuple[bool, str]:
        """
        Check-in request
        questionid: 450
        choice[]: 8
        choice[]: 4
        usercomment:  Current mood: Not have
        submit:  Submit (a report etc)
        Multiple choice will have more than onechoice[]....
        """
        data = {
            'questionid': questionid,
            'choice[]': choice[0] if len(choice) == 1 else choice,
            'usercomment': ' It's too hard.！',
            'wantskip': ' Will not (act, happen etc)'
        }
        logger.debug(f"Check-in request参数 {data}")

        sign_res = RequestUtils(cookies=site_cookie,
                                ua=ua,
                                proxies=settings.PROXY if proxy else None
                                ).post_res(url='https://ptchdbits.co/bakatest.php', data=data)
        if not sign_res or sign_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Check-in interface request failed'

        #  Determine if sign-in is successful
        sign_status = self.sign_in_result(html_res=sign_res.text,
                                          regexs=self._success_regex)
        if sign_status:
            logger.info(f"{site}  Sign in successfully")
            return True, ' Sign in successfully'
        else:
            sign_status = self.sign_in_result(html_res=sign_res.text,
                                              regexs=self._sign_regex)
            if sign_status:
                logger.info(f"{site}  Signed in today")
                return True, ' Signed in today'

            logger.error(f"{site}  Failed to sign in， Please go to page")
            return False, ' Failed to sign in， Please go to page'
