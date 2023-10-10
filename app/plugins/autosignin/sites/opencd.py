import json
import time
from typing import Tuple

from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.helper.ocr import OcrHelper
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class Opencd(_ISiteSigninHandler):
    """
    Queensocr Sign in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "open.cd"

    #  Signed in
    _repeat_text = "/plugin_sign-in.php?cmd=show-log"

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
        html_text = self.get_page_source(url='https://www.open.cd',
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

        if self._repeat_text in html_text:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        #  Get sign-in parameters
        html_text = self.get_page_source(url='https://www.open.cd/plugin_sign-in.php',
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)
        if not html_text:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'

        #  Parsing without signing inhtml
        html = etree.HTML(html_text)
        if not html:
            return False, ' Failed to sign in'

        #  Check-in parameters
        img_url = html.xpath('//form[@id="frmSignin"]//img/@src')[0]
        img_hash = html.xpath('//form[@id="frmSignin"]//input[@name="imagehash"]/@value')[0]
        if not img_url or not img_hash:
            logger.error(f"{site}  Failed to sign in， Failed to get sign-in parameters")
            return False, ' Failed to sign in， Failed to get sign-in parameters'

        #  Full captchaurl
        img_get_url = 'https://www.open.cd/%s' % img_url
        logger.debug(f"{site}  Get{site} Captcha link {img_get_url}")

        # ocr Recognize multiple times， Gain6 Captcha, a type of challenge-response test (computing)
        times = 0
        ocr_result = None
        #  Recognize a few times
        while times <= 3:
            # ocr Qr code recognition
            ocr_result = OcrHelper().get_captcha_text(image_url=img_get_url,
                                                      cookie=site_cookie,
                                                      ua=ua)
            logger.debug(f"ocr Recognize{site} Captcha, a type of challenge-response test (computing) {ocr_result}")
            if ocr_result:
                if len(ocr_result) == 6:
                    logger.info(f"ocr Recognize{site} Captcha success {ocr_result}")
                    break
            times += 1
            logger.debug(f"ocr Recognize{site} Captcha failure， Retrying.， Current number of retries {times}")
            time.sleep(1)

        if ocr_result:
            #  Assembly request parameters
            data = {
                'imagehash': img_hash,
                'imagestring': ocr_result
            }
            #  Visit the sign-in link
            sign_res = RequestUtils(cookies=site_cookie,
                                    ua=ua,
                                    proxies=settings.PROXY if proxy else None
                                    ).post_res(url='https://www.open.cd/plugin_sign-in.php?cmd=signin', data=data)
            if sign_res and sign_res.status_code == 200:
                logger.debug(f"sign_res Come (or go) back {sign_res.text}")
                # sign_res.text = '{"state":"success","signindays":"0","integral":"10"}'
                sign_dict = json.loads(sign_res.text)
                if sign_dict['state']:
                    logger.info(f"{site}  Sign in successfully")
                    return True, ' Sign in successfully'
                else:
                    logger.error(f"{site}  Failed to sign in， Check-in interface returns {sign_dict}")
                    return False, ' Failed to sign in'

        logger.error(f'{site}  Failed to sign in： Verification code not obtained')
        return False, ' Failed to sign in： Verification code not obtained'
