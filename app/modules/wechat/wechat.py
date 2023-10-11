import json
import re
import threading
from datetime import datetime
from typing import Optional, List, Dict

from app.core.config import settings
from app.core.context import MediaInfo, Context
from app.core.metainfo import MetaInfo
from app.log import logger
from app.utils.http import RequestUtils
from app.utils.singleton import Singleton
from app.utils.string import StringUtils

lock = threading.Lock()


class WeChat(metaclass=Singleton):
    #  Enterprise wechatToken
    _access_token = None
    #  Enterprise wechatToken过期时间
    _expires_in: int = None
    #  Enterprise wechatToken获取时间
    _access_token_time: datetime = None
    #  Enterprise wechatCorpID
    _corpid = None
    #  Enterprise wechatAppSecret
    _appsecret = None
    #  Enterprise wechatAppID
    _appid = None

    #  Enterprise wechat send messageURL
    _send_msg_url = f"{settings.WECHAT_PROXY}/cgi-bin/message/send?access_token=%s"
    #  Enterprise wechat getTokenURL
    _token_url = f"{settings.WECHAT_PROXY}/cgi-bin/gettoken?corpid=%s&corpsecret=%s"
    #  Enterprise wechat innovation menuURL
    _create_menu_url = f"{settings.WECHAT_PROXY}/cgi-bin/menu/create?access_token=%s&agentid=%s"

    def __init__(self):
        """
        Initialization
        """
        self._corpid = settings.WECHAT_CORPID
        self._appsecret = settings.WECHAT_APP_SECRET
        self._appid = settings.WECHAT_APP_ID

        if self._corpid and self._appsecret and self._appid:
            self.__get_access_token()

    def __get_access_token(self, force=False):
        """
        Get wechatToken
        :return：  MicrosoftToken
        """
        token_flag = True
        if not self._access_token:
            token_flag = False
        else:
            if (datetime.now() - self._access_token_time).seconds >= self._expires_in:
                token_flag = False

        if not token_flag or force:
            if not self._corpid or not self._appsecret:
                return None
            try:
                token_url = self._token_url % (self._corpid, self._appsecret)
                res = RequestUtils().get_res(token_url)
                if res:
                    ret_json = res.json()
                    if ret_json.get('errcode') == 0:
                        self._access_token = ret_json.get('access_token')
                        self._expires_in = ret_json.get('expires_in')
                        self._access_token_time = datetime.now()
                elif res is not None:
                    logger.error(f" Get wechataccess_token Fail (e.g. experiments)， Error code：{res.status_code}， Cause of error：{res.reason}")
                else:
                    logger.error(f" Get wechataccess_token Fail (e.g. experiments)， Return information not obtained")
            except Exception as e:
                logger.error(f" Get wechataccess_token Fail (e.g. experiments)， Error message：{e}")
                return None
        return self._access_token

    def __send_message(self, title: str, text: str = None, userid: str = None) -> Optional[bool]:
        """
        Send text message
        :param title:  Message title
        :param text:  Message
        :param userid:  The message sender'sID， If it's empty, send it to everyone.
        :return:  Sender state， Error message
        """
        message_url = self._send_msg_url % self.__get_access_token()
        if text:
            conent = "%s\n%s" % (title, text.replace("\n\n", "\n"))
        else:
            conent = title

        if not userid:
            userid = "@all"
        req_json = {
            "touser": userid,
            "msgtype": "text",
            "agentid": self._appid,
            "text": {
                "content": conent
            },
            "safe": 0,
            "enable_id_trans": 0,
            "enable_duplicate_check": 0
        }
        return self.__post_request(message_url, req_json)

    def __send_image_message(self, title: str, text: str, image_url: str, userid: str = None) -> Optional[bool]:
        """
        Send a graphic message
        :param title:  Message title
        :param text:  Message
        :param image_url:  Image address
        :param userid:  The message sender'sID， If it's empty, send it to everyone.
        :return:  Sender state， Error message
        """
        message_url = self._send_msg_url % self.__get_access_token()
        if text:
            text = text.replace("\n\n", "\n")
        if not userid:
            userid = "@all"
        req_json = {
            "touser": userid,
            "msgtype": "news",
            "agentid": self._appid,
            "news": {
                "articles": [
                    {
                        "title": title,
                        "description": text,
                        "picurl": image_url,
                        "url": ''
                    }
                ]
            }
        }
        return self.__post_request(message_url, req_json)

    def send_msg(self, title: str, text: str = "", image: str = "", userid: str = None) -> Optional[bool]:
        """
        Wechat messaging portal， Supported texts、 Photograph、 Link jumping、 Specify who to send it to
        :param title:  Message title
        :param text:  Message
        :param image:  Image address
        :param userid:  The message sender'sID， If it's empty, send it to everyone.
        :return:  Sender state， Error message
        """
        if not self.__get_access_token():
            logger.error(" Get wechataccess_token Fail (e.g. experiments)， Please check the parameter configuration")
            return None

        if image:
            ret_code = self.__send_image_message(title, text, image, userid)
        else:
            ret_code = self.__send_message(title, text, userid)

        return ret_code

    def send_medias_msg(self, medias: List[MediaInfo], userid: str = "") -> Optional[bool]:
        """
        Sending list class messages
        """
        if not self.__get_access_token():
            logger.error(" Get wechataccess_token Fail (e.g. experiments)， Please check the parameter configuration")
            return None

        message_url = self._send_msg_url % self.__get_access_token()
        if not userid:
            userid = "@all"
        articles = []
        index = 1
        for media in medias:
            if media.vote_average:
                title = f"{index}. {media.title_year}\n Typology：{media.type.value}， Score (of student's work)：{media.vote_average}"
            else:
                title = f"{index}. {media.title_year}\n Typology：{media.type.value}"
            articles.append({
                "title": title,
                "description": "",
                "picurl": media.get_message_image() if index == 1 else media.get_poster_image(),
                "url": media.detail_link
            })
            index += 1

        req_json = {
            "touser": userid,
            "msgtype": "news",
            "agentid": self._appid,
            "news": {
                "articles": articles
            }
        }
        return self.__post_request(message_url, req_json)

    def send_torrents_msg(self, torrents: List[Context],
                          userid: str = "", title: str = "") -> Optional[bool]:
        """
        Send a list message
        """
        if not self.__get_access_token():
            logger.error(" Get wechataccess_token Fail (e.g. experiments)， Please check the parameter configuration")
            return None

        #  Send the title first
        if title:
            self.__send_message(title=title, userid=userid)

        #  Distribution list
        message_url = self._send_msg_url % self.__get_access_token()
        if not userid:
            userid = "@all"
        articles = []
        index = 1
        for context in torrents:
            torrent = context.torrent_info
            meta = MetaInfo(title=torrent.title, subtitle=torrent.description)
            mediainfo = context.media_info
            torrent_title = f"{index}.【{torrent.site_name}】" \
                            f"{meta.season_episode} " \
                            f"{meta.resource_term} " \
                            f"{meta.video_term} " \
                            f"{meta.release_group} " \
                            f"{StringUtils.str_filesize(torrent.size)} " \
                            f"{torrent.volume_factor} " \
                            f"{torrent.seeders}↑"
            title = re.sub(r"\s+", " ", title).strip()
            articles.append({
                "title": torrent_title,
                "description": torrent.description if index == 1 else '',
                "picurl": mediainfo.get_message_image() if index == 1 else '',
                "url": torrent.page_url
            })
            index += 1

        req_json = {
            "touser": userid,
            "msgtype": "news",
            "agentid": self._appid,
            "news": {
                "articles": articles
            }
        }
        return self.__post_request(message_url, req_json)

    def __post_request(self, message_url: str, req_json: dict) -> bool:
        """
        Send a request to wechat
        """
        try:
            res = RequestUtils(content_type='application/json').post(
                message_url,
                data=json.dumps(req_json, ensure_ascii=False).encode('utf-8')
            )
            if res and res.status_code == 200:
                ret_json = res.json()
                if ret_json.get('errcode') == 0:
                    return True
                else:
                    if ret_json.get('errcode') == 42001:
                        self.__get_access_token(force=True)
                    logger.error(f" Failed to send request， Error message：{ret_json.get('errmsg')}")
                    return False
            elif res is not None:
                logger.error(f" Failed to send request， Error code：{res.status_code}， Cause of error：{res.reason}")
                return False
            else:
                logger.error(f" Failed to send request， Return information not obtained")
                return False
        except Exception as err:
            logger.error(f" Failed to send request， Error message：{err}")
            return False

    def create_menus(self, commands: Dict[str, dict]):
        """
        Automatic registration of wechat menu
        :param commands:  Command dictionary
        Command dictionary：
        {
            "/cookiecloud": {
                "func": CookieCloudChain(self._db).remote_sync,
                "description": " Synchronization site",
                "category": " Website",
                "data": {}
            }
        }
        Registration message format， The first level menu only has the most3 Clause (of law or treaty)， The submenu has a maximum of5 Clause (of law or treaty)：
        {
           "button":[
               {
                   "type":"click",
                   "name":" Song of the day",
                   "key":"V1001_TODAY_MUSIC"
               },
               {
                   "name":" Menu",
                   "sub_button":[
                       {
                           "type":"view",
                           "name":" Look for sth.",
                           "url":"http://www.soso.com/"
                       },
                       {
                           "type":"click",
                           "name":" Give us a shout out.",
                           "key":"V1001_GOOD"
                       }
                   ]
              }
           ]
        }
        """
        #  RequestingURL
        req_url = self._create_menu_url % (self.__get_access_token(), self._appid)

        #  Treat (sb a certain way)commands Check or refer tocategory Clusters
        category_dict = {}
        for key, value in commands.items():
            category: Dict[str, dict] = value.get("category")
            if category:
                if not category_dict.get(category):
                    category_dict[category] = {}
                category_dict[category][key] = value

        #  Level 1 menu
        buttons = []
        for category, menu in category_dict.items():
            #  Secondary menu
            sub_buttons = []
            for key, value in menu.items():
                sub_buttons.append({
                    "type": "click",
                    "name": value.get("description"),
                    "key": key
                })
            buttons.append({
                "name": category,
                "sub_button": sub_buttons[:5]
            })

        if buttons:
            #  Send request
            self.__post_request(req_url, {
                "button": buttons[:3]
            })
