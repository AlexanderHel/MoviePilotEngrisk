import base64
from typing import Tuple, Optional

from lxml import etree
from playwright.sync_api import Page

from app.helper.browser import PlaywrightHelper
from app.helper.ocr import OcrHelper
from app.log import logger
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils
from app.utils.string import StringUtils


class CookieHelper:
    #  Site login interface elementsXPATH
    _SITE_LOGIN_XPATH = {
        "username": [
            '//input[@name="username"]',
            '//input[@id="form_item_username"]',
            '//input[@id="username"]'
        ],
        "password": [
            '//input[@name="password"]',
            '//input[@id="form_item_password"]',
            '//input[@id="password"]',
            '//input[@type="password"]'
        ],
        "captcha": [
            '//input[@name="imagestring"]',
            '//input[@name="captcha"]',
            '//input[@id="form_item_captcha"]',
            '//input[@placeholder=" Verification code"]'
        ],
        "captcha_img": [
            '//img[@alt="captcha"]/@src',
            '//img[@alt="CAPTCHA"]/@src',
            '//img[@alt="SECURITY CODE"]/@src',
            '//img[@id="LAY-user-get-vercode"]/@src',
            '//img[contains(@src,"/api/getCaptcha")]/@src'
        ],
        "submit": [
            '//input[@type="submit"]',
            '//button[@type="submit"]',
            '//button[@lay-filter="login"]',
            '//button[@lay-filter="formLogin"]',
            '//input[@type="button"][@value=" Log in"]'
        ],
        "error": [
            "//table[@class='main']//td[@class='text']/text()"
        ],
        "twostep": [
            '//input[@name="two_step_code"]',
            '//input[@name="2fa_secret"]'
        ]
    }

    @staticmethod
    def parse_cookies(cookies: list) -> str:
        """
        Returns the browser'scookies Convert to string
        """
        if not cookies:
            return ""
        cookie_str = ""
        for cookie in cookies:
            cookie_str += f"{cookie['name']}={cookie['value']}; "
        return cookie_str

    def get_site_cookie_ua(self,
                           url: str,
                           username: str,
                           password: str,
                           proxies: dict = None) -> Tuple[Optional[str], Optional[str], str]:
        """
        Get sitecookie Cap (a poem)ua
        :param url:  Site address
        :param username:  User id
        :param password:  Cryptographic
        :param proxies:  Act on behalf of sb. in a responsible position
        :return: cookie、ua、message
        """

        def __page_handler(page: Page) -> Tuple[Optional[str], Optional[str], str]:
            """
            Page processing
            :return: Cookie Cap (a poem)UA
            """
            #  Login page code
            html_text = page.content()
            if not html_text:
                return None, None, " Failed to get source code"
            #  Find user name input box
            html = etree.HTML(html_text)
            username_xpath = None
            for xpath in self._SITE_LOGIN_XPATH.get("username"):
                if html.xpath(xpath):
                    username_xpath = xpath
                    break
            if not username_xpath:
                return None, None, " User name input box not found"
            #  Find password input box
            password_xpath = None
            for xpath in self._SITE_LOGIN_XPATH.get("password"):
                if html.xpath(xpath):
                    password_xpath = xpath
                    break
            if not password_xpath:
                return None, None, " Password input box not found"
            #  Find captcha input box
            captcha_xpath = None
            for xpath in self._SITE_LOGIN_XPATH.get("captcha"):
                if html.xpath(xpath):
                    captcha_xpath = xpath
                    break
            #  Find captcha images
            captcha_img_url = None
            if captcha_xpath:
                for xpath in self._SITE_LOGIN_XPATH.get("captcha_img"):
                    if html.xpath(xpath):
                        captcha_img_url = html.xpath(xpath)[0]
                        break
                if not captcha_img_url:
                    return None, None, " Captcha image not found"
            #  Find login button
            submit_xpath = None
            for xpath in self._SITE_LOGIN_XPATH.get("submit"):
                if html.xpath(xpath):
                    submit_xpath = xpath
                    break
            if not submit_xpath:
                return None, None, " Login button not found"
            #  Click on the login button
            try:
                #  Wait for the login button to be ready
                page.wait_for_selector(submit_xpath)
                #  Enter user name
                page.fill(username_xpath, username)
                #  Enter a password
                page.fill(password_xpath, password)
                #  Captcha recognition
                if captcha_xpath and captcha_img_url:
                    captcha_element = page.query_selector(captcha_xpath)
                    if captcha_element.is_visible():
                        #  Captcha image address
                        code_url = self.__get_captcha_url(url, captcha_img_url)
                        #  Get the currentcookie Cap (a poem)ua
                        cookie = self.parse_cookies(page.context.cookies())
                        ua = page.evaluate("() => window.navigator.userAgent")
                        #  AutomationOCR Captcha recognition
                        captcha = self.__get_captcha_text(cookie=cookie, ua=ua, code_url=code_url)
                        if captcha:
                            logger.info(" The captcha address is：%s， Identification results：%s" % (code_url, captcha))
                        else:
                            return None, None, " Captcha recognition failure"
                        #  Enter the verification code
                        captcha_element.fill(captcha)
                    else:
                        #  Invisible elements are not processed
                        pass
                #  Click on the login button
                page.click(submit_xpath)
                page.wait_for_load_state("networkidle", timeout=30 * 1000)
            except Exception as e:
                logger.error(f" Emulation login failure：{e}")
                return None, None, f" Emulation login failure：{e}"
            #  Source code after login
            html_text = page.content()
            if not html_text:
                return None, None, " Failed to get web page source code"
            if SiteUtils.is_logged_in(html_text):
                return self.parse_cookies(page.context.cookies()), \
                    page.evaluate("() => window.navigator.userAgent"), ""
            else:
                #  Read error message
                error_xpath = None
                for xpath in self._SITE_LOGIN_XPATH.get("error"):
                    if html.xpath(xpath):
                        error_xpath = xpath
                        break
                if not error_xpath:
                    return None, None, " Login failure"
                else:
                    error_msg = html.xpath(error_xpath)[0]
                    return None, None, error_msg

        if not url or not username or not password:
            return None, None, " Parameter error"

        return PlaywrightHelper().action(url=url,
                                         callback=__page_handler,
                                         proxies=proxies)

    @staticmethod
    def __get_captcha_text(cookie: str, ua: str, code_url: str) -> str:
        """
        Recognize the content of captcha images
        """
        if not code_url:
            return ""
        ret = RequestUtils(ua=ua, cookies=cookie).get_res(code_url)
        if ret:
            if not ret.content:
                return ""
            return OcrHelper().get_captcha_text(
                image_b64=base64.b64encode(ret.content).decode()
            )
        else:
            return ""

    @staticmethod
    def __get_captcha_url(siteurl: str, imageurl: str) -> str:
        """
        Get captcha image ofURL
        """
        if not siteurl or not imageurl:
            return ""
        if imageurl.startswith("/"):
            imageurl = imageurl[1:]
        return "%s/%s" % (StringUtils.get_base_url(siteurl), imageurl)
