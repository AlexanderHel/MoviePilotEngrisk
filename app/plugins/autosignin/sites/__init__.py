# -*- coding: utf-8 -*-
import re
from abc import ABCMeta, abstractmethod
from typing import Tuple

import chardet
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.helper.browser import PlaywrightHelper
from app.log import logger
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class _ISiteSigninHandler(metaclass=ABCMeta):
    """
    Base class that implements site check-in， All site check-in classes need to inherit this class， Realizationmatch Cap (a poem)signin Methodologies
    The implementation class is placed into thesitesignin Directory will automatically load the
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = ""

    @abstractmethod
    def match(self, url: str) -> bool:
        """
        Based on siteUrl Determine if the current site check-in class matches， In most cases it is sufficient to use the default implementation
        :param url:  WebsiteUrl
        :return:  Whether or not it matches， If a match is made then the class'ssignin Methodologies
        """
        return True if StringUtils.url_equal(url, self.site_url) else False

    @abstractmethod
    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """
        Perform check-in operations
        :param site_info:  Site information， Contains siteUrl、 WebsiteCookie、UA And other information
        :return: True|False, Check-in results information
        """
        pass

    @staticmethod
    def get_page_source(url: str, cookie: str, ua: str, proxy: bool, render: bool) -> str:
        """
        Get page source code
        :param url: Url Address
        :param cookie: Cookie
        :param ua: UA
        :param proxy:  Whether to use a proxy
        :param render:  Whether to render
        :return:  Page source code， Error message
        """
        if render:
            return PlaywrightHelper().get_page_source(url=url,
                                                      cookies=cookie,
                                                      ua=ua,
                                                      proxies=settings.PROXY_SERVER if proxy else None)
        else:
            res = RequestUtils(cookies=cookie,
                               ua=ua,
                               proxies=settings.PROXY if proxy else None
                               ).get_res(url=url)
            if res is not None:
                #  Utilizationchardet Detecting character encoding
                raw_data = res.content
                if raw_data:
                    try:
                        result = chardet.detect(raw_data)
                        encoding = result['encoding']
                        #  Decode to string
                        return raw_data.decode(encoding)
                    except Exception as e:
                        logger.error(f"chardet Failed to decode：{e}")
                        return res.text
                else:
                    return res.text
            return ""

    @staticmethod
    def sign_in_result(html_res: str, regexs: list) -> bool:
        """
        Determine if sign-in is successful
        """
        html_text = re.sub(r"#\d+", "", re.sub(r"\d+px", "", html_res))
        for regex in regexs:
            if re.search(str(regex), html_text):
                return True
        return False
