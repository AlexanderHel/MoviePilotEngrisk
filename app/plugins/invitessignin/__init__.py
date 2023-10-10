import json
import re
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger
from app.schemas import NotificationType
from app.utils.http import RequestUtils


class InvitesSignin(_PluginBase):
    #  Plug-in name
    plugin_name = " Pills to sign in"
    #  Plugin description
    plugin_desc = " Pill forum sign in。"
    #  Plug-in icons
    plugin_icon = "invites.png"
    #  Theme color
    plugin_color = "#FFFFFF"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "invitessignin"
    #  Loading sequence
    plugin_order = 24
    #  Available user levels
    auth_level = 2

    #  Private property
    _enabled = False
    #  Task execution interval
    _cron = None
    _cookie = None
    _onlyonce = False
    _notify = False

    #  Timers
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        #  Discontinuation of existing mandates
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._cookie = config.get("cookie")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")

            #  Load modules
        if self._enabled:
            #  Time service
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._cron:
                try:
                    self._scheduler.add_job(func=self.__signin,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Pills to sign in")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")

            if self._onlyonce:
                logger.info(f" Pill check-in service launched， Run one immediately")
                self._scheduler.add_job(func=self.__signin, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name=" Pills to sign in")
                #  Turn off the disposable switch
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "cron": self._cron,
                    "enabled": self._enabled,
                    "cookie": self._cookie,
                    "notify": self._notify,
                })

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __signin(self):
        """
        Pills to sign in
        """
        res = RequestUtils(cookies=self._cookie).get_res(url="https://invites.fun")
        if not res or res.status_code != 200:
            logger.error(" Request pill error")
            return

        #  GaincsrfToken
        pattern = r'"csrfToken":"(.*?)"'
        csrfToken = re.findall(pattern, res.text)
        if not csrfToken:
            logger.error(" RequestingcsrfToken Fail (e.g. experiments)")
            return

        csrfToken = csrfToken[0]
        logger.info(f" GaincsrfToken Successes {csrfToken}")

        #  Gainuserid
        pattern = r'"userId":(\d+)'
        match = re.search(pattern, res.text)

        if match:
            userId = match.group(1)
            logger.info(f" Gainuserid Successes {userId}")
        else:
            logger.error(" Not founduserId")
            return

        headers = {
            "X-Csrf-Token": csrfToken,
            "X-Http-Method-Override": "PATCH",
            "Cookie": self._cookie
        }

        data = {
            "data": {
                "type": "users",
                "attributes": {
                    "canCheckin": False,
                    "totalContinuousCheckIn": 2
                },
                "id": userId
            }
        }

        #  Start checking in.
        res = RequestUtils(headers=headers).post_res(url=f"https://invites.fun/api/users/{userId}", json=data)

        if not res or res.status_code != 200:
            logger.error("Pills to sign in失败")
            return

        sign_dict = json.loads(res.text)
        money = sign_dict['data']['attributes']['money']
        totalContinuousCheckIn = sign_dict['data']['attributes']['totalContinuousCheckIn']

        #  Send notification
        if self._notify:
            self.post_message(
                mtype=NotificationType.SiteMessage,
                title="【Pills to sign in任务完成】",
                text=f" Cumulative sign-in {totalContinuousCheckIn} \n"
                     f" Surplus pills {money}")

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
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VSwitch',
                                               'props': {
                                                   'model': 'enabled',
                                                   'label': ' Enabling plug-ins',
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VSwitch',
                                               'props': {
                                                   'model': 'notify',
                                                   'label': ' Open notification',
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VSwitch',
                                               'props': {
                                                   'model': 'onlyonce',
                                                   'label': ' Run one immediately',
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
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'cron',
                                                   'label': ' Check-in period'
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'cookie',
                                                   'label': ' Boluscookie'
                                               }
                                           }
                                       ]
                                   }
                               ]
                           }
                       ]
                   }
               ], {
                   "enabled": False,
                   "onlyonce": False,
                   "notify": False,
                   "cookie": "",
                   "cron": "0 9 * * *"
               }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        Exit plugin
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("Exit plugin失败：%s" % str(e))
