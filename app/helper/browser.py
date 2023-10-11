from typing import Callable, Any

from playwright.sync_api import sync_playwright, Page
from cf_clearance import sync_cf_retry, sync_stealth
from app.log import logger


class PlaywrightHelper:
    def __init__(self, browser_type="chromium"):
        self.browser_type = browser_type

    @staticmethod
    def __pass_cloudflare(url: str, page: Page) -> bool:
        """
        Try to skipcloudfare Validate (a theory)
        """
        sync_stealth(page, pure=True)
        page.goto(url)
        return sync_cf_retry(page)

    def action(self, url: str,
               callback: Callable,
               cookies: str = None,
               ua: str = None,
               proxies: dict = None,
               headless: bool = False,
               timeout: int = 30) -> Any:
        """
        Access to the web page， Reception (of transmitted signal)Page Object and execute the operation
        :param url:  Webaddress
        :param callback:  Callback function， Need to receivepage Boyfriend
        :param cookies: cookies
        :param ua: user-agent
        :param proxies:  Act on behalf of sb. in a responsible position
        :param headless:  Headless mode or not
        :param timeout:  Timeout
        """
        try:
            with sync_playwright() as playwright:
                browser = playwright[self.browser_type].launch(headless=headless)
                context = browser.new_context(user_agent=ua, proxy=proxies)
                page = context.new_page()
                if cookies:
                    page.set_extra_http_headers({"cookie": cookies})
                try:
                    if not self.__pass_cloudflare(url, page):
                        logger.warn("cloudflare challenge fail！")
                    page.wait_for_load_state("networkidle", timeout=timeout * 1000)
                    #  Callback function
                    return callback(page)
                except Exception as e:
                    logger.error(f" Web operation failure: {e}")
                finally:
                    browser.close()
        except Exception as e:
            logger.error(f" Web operation failure: {e}")
        return None

    def get_page_source(self, url: str,
                        cookies: str = None,
                        ua: str = None,
                        proxies: dict = None,
                        headless: bool = False,
                        timeout: int = 30) -> str:
        """
        Get the web page source code
        :param url:  Webaddress
        :param cookies: cookies
        :param ua: user-agent
        :param proxies:  Act on behalf of sb. in a responsible position
        :param headless:  Headless mode or not
        :param timeout:  Timeout
        """
        source = ""
        try:
            with sync_playwright() as playwright:
                browser = playwright[self.browser_type].launch(headless=headless)
                context = browser.new_context(user_agent=ua, proxy=proxies)
                page = context.new_page()
                if cookies:
                    page.set_extra_http_headers({"cookie": cookies})
                try:
                    if not self.__pass_cloudflare(url, page):
                        logger.warn("cloudflare challenge fail！")
                    page.wait_for_load_state("networkidle", timeout=timeout * 1000)
                    source = page.content()
                except Exception as e:
                    logger.error(f"Get the web page source code失败: {e}")
                    source = None
                finally:
                    browser.close()
        except Exception as e:
            logger.error(f"Get the web page source code失败: {e}")
        return source


#  Sample usage
if __name__ == "__main__":
    utils = PlaywrightHelper()
    test_url = "https://piggo.me"
    test_cookies = ""
    test_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"
    source_code = utils.get_page_source(test_url, cookies=test_cookies, ua=test_user_agent)
    print(source_code)
