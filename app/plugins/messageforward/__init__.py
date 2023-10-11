import json
import re
from datetime import datetime

from app.core.config import settings
from app.plugins import _PluginBase
from app.core.event import eventmanager
from app.schemas.types import EventType, MessageChannel
from app.utils.http import RequestUtils
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger


class MessageForward(_PluginBase):
    #  Plug-in name
    plugin_name = " Message forwarding"
    #  Plugin description
    plugin_desc = " Forward notifications based on regularity to otherWeChat Appliance。"
    #  Plug-in icons
    plugin_icon = "forward.png"
    #  Theme color
    plugin_color = "#32ABD1"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "messageforward_"
    #  Loading sequence
    plugin_order = 16
    #  Available user levels
    auth_level = 1

    #  Private property
    _enabled = False
    _wechat = None
    _pattern = None
    _pattern_token = {}

    #  Enterprise wechat send messageURL
    _send_msg_url = f"{settings.WECHAT_PROXY}/cgi-bin/message/send?access_token=%s"
    #  Enterprise wechat getTokenURL
    _token_url = f"{settings.WECHAT_PROXY}/cgi-bin/gettoken?corpid=%s&corpsecret=%s"

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._wechat = config.get("wechat")
            self._pattern = config.get("pattern")

            #  Gaintoken Stockpile
            if self._enabled and self._wechat:
                self.__save_wechat_token()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Assembly plugin configuration page， Two pieces of data need to be returned：1、 Page configuration；2、 Data structure
        """
        return [
                   {
                       'component': 'VForm',
                       'content': [
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VSwitch',
                                               'props': {
                                                   'model': 'enabled',
                                                   'label': ' Enable forwarding'
                                               }
                                           }
                                       ]
                                   },
                               ]
                           },
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextarea',
                                               'props': {
                                                   'model': 'wechat',
                                                   'rows': '3',
                                                   'label': ' Application configuration',
                                                   'placeholder': 'appid:corpid:appsecret（ One line, one configuration）'
                                               }
                                           }
                                       ]
                                   }
                               ]
                           },
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextarea',
                                               'props': {
                                                   'model': 'pattern',
                                                   'rows': '3',
                                                   'label': ' Regular configuration',
                                                   'placeholder': ' Corresponds to the application configuration above， One in a row， One-to-one correspondence'
                                               }
                                           }
                                       ]
                                   }
                               ]
                           },
                       ]
                   }
               ], {
                   "enabled": False,
                   "wechat": "",
                   "pattern": ""
               }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event):
        """
        Message forwarding
        """
        if not self._enabled:
            return

        #  Message body
        data = event.event_data
        channel = data['channel']
        if channel and channel != MessageChannel.Wechat:
            return

        title = data['title']
        text = data['text']
        image = data['image']
        userid = data['userid']

        #  Regular match
        patterns = self._pattern.split("\n")
        for index, pattern in enumerate(patterns):
            msg_match = re.search(pattern, title)
            if msg_match:
                access_token, appid = self.__flush_access_token(index)
                if not access_token:
                    logger.error(" No validtoken， Please check the configuration")
                    continue

                #  Send a message
                if image:
                    self.__send_image_message(title, text, image, userid, access_token, appid, index)
                else:
                    self.__send_message(title, text, userid, access_token, appid, index)

    def __save_wechat_token(self):
        """
        Get and storewechat token
        """
        #  Parse configuration
        wechats = self._wechat.split("\n")
        for index, wechat in enumerate(wechats):
            wechat_config = wechat.split(":")
            if len(wechat_config) != 3:
                logger.error(f"{wechat}  Incorrect application configuration")
                continue
            appid = wechat_config[0]
            corpid = wechat_config[1]
            appsecret = wechat_config[2]

            #  Expired， Retrievetoken
            access_token, expires_in, access_token_time = self.__get_access_token(corpid=corpid,
                                                                                  appsecret=appsecret)
            if not access_token:
                #  Hasn'ttoken， Gaintoken
                logger.error(f"wechat Configure appid = {appid}  Gaintoken Fail (e.g. experiments)， Please check the configuration")
                continue

            self._pattern_token[index] = {
                "appid": appid,
                "corpid": corpid,
                "appsecret": appsecret,
                "access_token": access_token,
                "expires_in": expires_in,
                "access_token_time": access_token_time,
            }

    def __flush_access_token(self, index: int, force: bool = False):
        """
        Getting the firsti Configurationwechat token
        """
        wechat_token = self._pattern_token[index]
        if not wechat_token:
            logger.error(f" Failure to acquire the first {index}  The rule corresponding to thewechat Appliancetoken， Please check the configuration")
            return None
        access_token = wechat_token['access_token']
        expires_in = wechat_token['expires_in']
        access_token_time = wechat_token['access_token_time']
        appid = wechat_token['appid']
        corpid = wechat_token['corpid']
        appsecret = wechat_token['appsecret']

        #  Judgementstoken Validity period
        if force or (datetime.now() - access_token_time).seconds >= expires_in:
            #  Retrievetoken
            access_token, expires_in, access_token_time = self.__get_access_token(corpid=corpid,
                                                                                  appsecret=appsecret)
            if not access_token:
                logger.error(f"wechat Configure appid = {appid}  Gaintoken Fail (e.g. experiments)， Please check the configuration")
                return None, None

        self._pattern_token[index] = {
            "appid": appid,
            "corpid": corpid,
            "appsecret": appsecret,
            "access_token": access_token,
            "expires_in": expires_in,
            "access_token_time": access_token_time,
        }
        return access_token, appid

    def __send_message(self, title: str, text: str = None, userid: str = None, access_token: str = None,
                       appid: str = None, index: int = None) -> Optional[bool]:
        """
        Send text message
        :param title:  Message title
        :param text:  Message
        :param userid:  The message sender'sID， If it's empty, send it to everyone.
        :return:  Sender state， Error message
        """
        if text:
            conent = "%s\n%s" % (title, text.replace("\n\n", "\n"))
        else:
            conent = title

        if not userid:
            userid = "@all"
        req_json = {
            "touser": userid,
            "msgtype": "text",
            "agentid": appid,
            "text": {
                "content": conent
            },
            "safe": 0,
            "enable_id_trans": 0,
            "enable_duplicate_check": 0
        }
        return self.__post_request(access_token=access_token, req_json=req_json, index=index, title=title)

    def __send_image_message(self, title: str, text: str, image_url: str, userid: str = None,
                             access_token: str = None, appid: str = None, index: int = None) -> Optional[bool]:
        """
        Send a graphic message
        :param title:  Message title
        :param text:  Message
        :param image_url:  Image address
        :param userid:  The message sender'sID， If it's empty, send it to everyone.
        :return:  Sender state， Error message
        """
        if text:
            text = text.replace("\n\n", "\n")
        if not userid:
            userid = "@all"
        req_json = {
            "touser": userid,
            "msgtype": "news",
            "agentid": appid,
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
        return self.__post_request(access_token=access_token, req_json=req_json, index=index, title=title)

    def __post_request(self, access_token: str, req_json: dict, index: int, title: str, retry: int = 0) -> bool:
        message_url = self._send_msg_url % access_token
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
                    logger.info(f" Forward the message {title}  Successes")
                    return True
                else:
                    if ret_json.get('errcode') == 81013:
                        return False

                    logger.error(f" Forward the message {title}  Fail (e.g. experiments)， Error message：{ret_json}")
                    if ret_json.get('errcode') == 42001 or ret_json.get('errcode') == 40014:
                        logger.info("token Expired， Refreshing.token Retry")
                        #  Retrievetoken
                        access_token, appid = self.__flush_access_token(index=index,
                                                                        force=True)
                        if access_token:
                            retry += 1
                            #  Resend request
                            if retry <= 3:
                                return self.__post_request(access_token=access_token,
                                                           req_json=req_json,
                                                           index=index,
                                                           title=title,
                                                           retry=retry)
                    return False
            elif res is not None:
                logger.error(f" Forward the message {title}  Fail (e.g. experiments)， Error code：{res.status_code}， Cause of error：{res.reason}")
                return False
            else:
                logger.error(f" Forward the message {title}  Fail (e.g. experiments)， Return information not obtained")
                return False
        except Exception as err:
            logger.error(f" Forward the message {title}  Exceptions， Error message：{err}")
            return False

    def __get_access_token(self, corpid: str, appsecret: str):
        """
        Get wechatToken
        :return：  MicrosoftToken
        """
        try:
            token_url = self._token_url % (corpid, appsecret)
            res = RequestUtils().get_res(token_url)
            if res:
                ret_json = res.json()
                if ret_json.get('errcode') == 0:
                    access_token = ret_json.get('access_token')
                    expires_in = ret_json.get('expires_in')
                    access_token_time = datetime.now()

                    return access_token, expires_in, access_token_time
                else:
                    logger.error(f"{ret_json.get('errmsg')}")
                    return None, None, None
            else:
                logger.error(f"{corpid} {appsecret}  Gaintoken Fail (e.g. experiments)")
                return None, None, None
        except Exception as e:
            logger.error(f" Get wechataccess_token Fail (e.g. experiments)， Error message：{e}")
            return None, None, None

    def stop_service(self):
        """
        Exit plugin
        """
        pass
