from typing import Tuple, Optional

from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class CookieCloudHelper:

    _ignore_cookies: list = ["CookieAutoDeleteBrowsingDataCleanup", "CookieAutoDeleteCleaningDiscarded"]

    def __init__(self, server, key, password):
        self._server = server
        self._key = key
        self._password = password
        self._req = RequestUtils(content_type="application/json")

    def download(self) -> Tuple[Optional[dict], str]:
        """
        Through (a gap)CookieCloud Download data
        :return: Cookie Digital、 Error message
        """
        if not self._server or not self._key or not self._password:
            return None, "CookieCloud Parameter error"
        req_url = "%s/get/%s" % (self._server, self._key)
        ret = self._req.post_res(url=req_url, json={"password": self._password})
        if ret and ret.status_code == 200:
            result = ret.json()
            if not result:
                return {}, " No data downloaded"
            if result.get("cookie_data"):
                contents = result.get("cookie_data")
            else:
                contents = result
            #  Organize data, Utilizationdomain The last two levels of the domain name are used as the basis for grouping
            domain_groups = {}
            for site, cookies in contents.items():
                for cookie in cookies:
                    domain_key = StringUtils.get_url_domain(cookie.get("domain"))
                    if not domain_groups.get(domain_key):
                        domain_groups[domain_key] = [cookie]
                    else:
                        domain_groups[domain_key].append(cookie)
            #  Return error
            ret_cookies = {}
            #  Indexer
            for domain, content_list in domain_groups.items():
                if not content_list:
                    continue
                #  Only ifcf (used form a nominal expression)cookie Filter out
                cloudflare_cookie = True
                for content in content_list:
                    if content["name"] != "cf_clearance":
                        cloudflare_cookie = False
                        break
                if cloudflare_cookie:
                    continue
                #  WebsiteCookie
                cookie_str = ";".join(
                    [f"{content.get('name')}={content.get('value')}"
                     for content in content_list
                     if content.get("name") and content.get("name") not in self._ignore_cookies]
                )
                ret_cookies[domain] = cookie_str
            return ret_cookies, ""
        elif ret:
            return None, f" SynchronizationCookieCloud Fail (e.g. experiments)， Error code：{ret.status_code}"
        else:
            return None, "CookieCloud Request failed， Please check the server address、 SubscribersKEY And whether the encryption password is correct"
