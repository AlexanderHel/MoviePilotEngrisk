import hashlib
import json
import time

from app.utils.http import RequestUtils


class IyuuHelper(object):
    _version = "2.0.0"
    _api_base = "https://api.iyuu.cn/%s"
    _sites = {}
    _token = None

    def __init__(self, token):
        self._token = token
        if self._token:
            self.init_config()

    def init_config(self):
        pass

    def __request_iyuu(self, url, method="get", params=None):
        """
        TowardIYUUApi Send request
        """
        if params:
            if not params.get("sign"):
                params.update({"sign": self._token})
            if not params.get("version"):
                params.update({"version": self._version})
        else:
            params = {"sign": self._token, "version": self._version}
        #  Starting a request
        if method == "get":
            ret = RequestUtils(
                accept_type="application/json"
            ).get_res(f"{url}", params=params)
        else:
            ret = RequestUtils(
                accept_type="application/json"
            ).post_res(f"{url}", data=params)
        if ret:
            result = ret.json()
            if result.get('ret') == 200:
                return result.get('data'), ""
            else:
                return None, f" RequestingIYUU Fail (e.g. experiments)， Status code：{result.get('ret')}， Back to information：{result.get('msg')}"
        elif ret is not None:
            return None, f" RequestingIYUU Fail (e.g. experiments)， Status code：{ret.status_code}， Cause of error：{ret.reason}"
        else:
            return None, f" RequestingIYUU Fail (e.g. experiments)， Return information not obtained"

    def get_torrent_url(self, sid):
        if not sid:
            return None, None
        if not self._sites:
            self._sites = self.__get_sites()
        if not self._sites.get(sid):
            return None, None
        site = self._sites.get(sid)
        return site.get('base_url'), site.get('download_page')

    def __get_sites(self):
        """
        Back to all sites supporting auxiliary species
        :return:  Site list、 Error message
        {
            "ret": 200,
            "data": {
                "sites": [
                    {
                        "id": 1,
                        "site": "keepfrds",
                        "nickname": " Friends",
                        "base_url": "pt.keepfrds.com",
                        "download_page": "download.php?id={}&passkey={passkey}",
                        "reseed_check": "passkey",
                        "is_https": 2
                    },
                ]
            }
        }
        """
        result, msg = self.__request_iyuu(url=self._api_base % 'App.Api.Sites')
        if result:
            ret_sites = {}
            sites = result.get('sites') or []
            for site in sites:
                ret_sites[site.get('id')] = site
            return ret_sites
        else:
            print(msg)
            return {}

    def get_seed_info(self, info_hashs: list):
        """
        Come (or go) backinfo_hash Corresponding siteid、 Torrentid
        {
            "ret": 200,
            "data": [
                {
                    "sid": 3,
                    "torrent_id": 377467,
                    "info_hash": "a444850638e7a6f6220e2efdde94099c53358159"
                },
                {
                    "sid": 7,
                    "torrent_id": 35538,
                    "info_hash": "cf7d88fd656d10fe5130d13567aec27068b96676"
                }
            ],
            "msg": "",
            "version": "1.0.0"
        }
        """
        info_hashs.sort()
        json_data = json.dumps(info_hashs, separators=(',', ':'), ensure_ascii=False)
        sha1 = self.get_sha1(json_data)
        result, msg = self.__request_iyuu(url=self._api_base % 'App.Api.Infohash',
                                          method="post",
                                          params={
                                              "timestamp": time.time(),
                                              "hash": json_data,
                                              "sha1": sha1
                                          })
        return result, msg

    @staticmethod
    def get_sha1(json_str) -> str:
        return hashlib.sha1(json_str.encode('utf-8')).hexdigest()

    def get_auth_sites(self):
        """
        Return to the list of sites that support authentication
        [
            {
                "id": 2,
                "site": "pthome",
                "bind_check": "passkey,uid"
            }
        ]
        """
        result, msg = self.__request_iyuu(url=self._api_base % 'App.Api.GetRecommendSites')
        if result:
            return result.get('recommend') or []
        else:
            print(msg)
            return []

    def bind_site(self, site, passkey, uid):
        """
        Binding site
        :param site:  Site name
        :param passkey: passkey
        :param uid:  Subscribersid
        :return:  Status code、 Error message
        """
        result, msg = self.__request_iyuu(url=self._api_base % 'App.Api.Bind',
                                          method="get",
                                          params={
                                              "token": self._token,
                                              "site": site,
                                              "passkey": self.get_sha1(passkey),
                                              "id": uid
                                          })
        return result, msg
