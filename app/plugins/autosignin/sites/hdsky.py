import json
import time
from typing import Tuple

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.helper.ocr import OcrHelper
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class HDSky(_ISiteSigninHandler):
    """
    Heavensocr Sign in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "hdsky.me"

    #  Signed in
    _sign_regex = [' Signed in']

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
        html_text = self.get_page_source(url='https://hdsky.me',
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

        #  Get captcha request， Failed to obtain considering network problems， Try getting it a few more times.
        res_times = 0
        img_hash = None
        while not img_hash and res_times <= 3:
            image_res = RequestUtils(cookies=site_cookie,
                                     ua=ua,
                                     proxies=settings.PROXY if proxy else None
                                     ).post_res(url='https://hdsky.me/image_code_ajax.php',
                                                data={'action': 'new'})
            if image_res and image_res.status_code == 200:
                image_json = json.loads(image_res.text)
                if image_json["success"]:
                    img_hash = image_json["code"]
                    break
                res_times += 1
                logger.debug(f" Gain{site} Captcha failure， Retrying.， Current number of retries {res_times}")
                time.sleep(1)

        #  Get to the qr codehash
        if img_hash:
            #  Full captchaurl
            img_get_url = 'https://hdsky.me/image.php?action=regimage&imagehash=%s' % img_hash
            logger.debug(f" Get{site} Captcha link {img_get_url}")
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
                    'action': 'showup',
                    'imagehash': img_hash,
                    'imagestring': ocr_result
                }
                #  Visit the sign-in link
                res = RequestUtils(cookies=site_cookie,
                                   ua=ua,
                                   proxies=settings.PROXY if proxy else None
                                   ).post_res(url='https://hdsky.me/showup.php', data=data)
                if res and res.status_code == 200:
                    if json.loads(res.text)["success"]:
                        logger.info(f"{site}  Sign in successfully")
                        return True, ' Sign in successfully'
                    elif str(json.loads(res.text)["message"]) == "date_unmatch":
                        #  Repeat sign-in
                        logger.warn(f"{site}  Repeat success")
                        return True, ' Signed in today'
                    elif str(json.loads(res.text)["message"]) == "invalid_imagehash":
                        #  Captcha error
                        logger.warn(f"{site}  Failed to sign in： Captcha error")
                        return False, ' Failed to sign in： Captcha error'

        logger.error(f'{site}  Failed to sign in： Verification code not obtained')
        return False, ' Failed to sign in： Verification code not obtained'
