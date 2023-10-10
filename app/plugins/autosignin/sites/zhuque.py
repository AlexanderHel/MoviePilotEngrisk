import json
from typing import Tuple

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class ZhuQue(_ISiteSigninHandler):
    """
    ZHUQUE Sign in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "zhuque.in"

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
        html_text = self.get_page_source(url="https://zhuque.in",
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)
        if not html_text:
            logger.error(f"{site}  Simulated login failure， Please check site connectivity")
            return False, ' Simulated login failure， Please check site connectivity'

        if "login.php" in html_text:
            logger.error(f"{site}  Simulated login failure，Cookie Lose effectiveness")
            return False, ' Simulated login failure，Cookie Lose effectiveness'

        html = etree.HTML(html_text)

        if not html:
            return False, ' Simulated login failure'

        #  Release a skill
        msg = ' Fail (e.g. experiments)'
        x_csrf_token = html.xpath("//meta[@name='x-csrf-token']/@content")[0]
        if x_csrf_token:
            data = {
                "all": 1,
                "resetModal": "true"
            }
            headers = {
                "x-csrf-token": str(x_csrf_token),
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": ua
            }
            skill_res = RequestUtils(cookies=site_cookie,
                                     headers=headers,
                                     proxies=settings.PROXY if proxy else None
                                     ).post_res(url="https://zhuque.in/api/gaming/fireGenshinCharacterMagic", json=data)
            if not skill_res or skill_res.status_code != 200:
                logger.error(f" Simulated login failure， Failed to release skill")

            # '{"status":200,"data":{"code":"FIRE_GENSHIN_CHARACTER_MAGIC_SUCCESS","bonus":0}}'
            skill_dict = json.loads(skill_res.text)
            if skill_dict['status'] == 200:
                bonus = int(skill_dict['data']['bonus'])
                msg = f' Successes， Attainment{bonus} Magic power'

        logger.info(f'【{site}】 Successful simulated login， Skill release{msg}')
        return True, f' Successful simulated login， Skill release{msg}'
