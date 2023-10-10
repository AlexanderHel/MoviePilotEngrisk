import re
import traceback
from datetime import datetime, timedelta
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing.pool import ThreadPool
from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import urljoin

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ruamel.yaml import CommentedMap

from app import schemas
from app.core.config import settings
from app.core.event import EventManager, eventmanager, Event
from app.db.models.site import Site
from app.helper.browser import PlaywrightHelper
from app.helper.cloudflare import under_challenge
from app.helper.module import ModuleHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils
from app.utils.string import StringUtils
from app.utils.timer import TimerUtils


class AutoSignIn(_PluginBase):
    #  Plug-in name
    plugin_name = " Automatic site check-in"
    #  Plugin description
    plugin_desc = " Automatic simulation of the login site、 Sign in。"
    #  Plug-in icons
    plugin_icon = "signin.png"
    #  Theme color
    plugin_color = "#4179F4"
    #  Plug-in version
    plugin_version = "1.1"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "autosignin_"
    #  Loading sequence
    plugin_order = 0
    #  Available user levels
    auth_level = 2

    #  Private property
    sites: SitesHelper = None
    #  Event manager
    event: EventManager = None
    #  Timers
    _scheduler: Optional[BackgroundScheduler] = None
    #  Loaded modules
    _site_schema: list = []

    #  Configuration properties
    _enabled: bool = False
    _cron: str = ""
    _onlyonce: bool = False
    _notify: bool = False
    _queue_cnt: int = 5
    _sign_sites: list = []
    _login_sites: list = []
    _retry_keyword = None
    _clean: bool = False
    _start_time: int = None
    _end_time: int = None

    def init_plugin(self, config: dict = None):
        self.sites = SitesHelper()
        self.event = EventManager()

        #  Discontinuation of existing mandates
        self.stop_service()

        #  Configure
        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._queue_cnt = config.get("queue_cnt") or 5
            self._sign_sites = config.get("sign_sites") or []
            self._login_sites = config.get("login_sites") or []
            self._retry_keyword = config.get("retry_keyword")
            self._clean = config.get("clean")

            #  Filter out deleted sites
            all_sites = [site for site in self.sites.get_indexers() if not site.get("public")]
            self._sign_sites = [site.get("id") for site in all_sites if site.get("id") in self._sign_sites]
            self._login_sites = [site.get("id") for site in all_sites if site.get("id") in self._login_sites]
            #  Save configuration
            self.__update_config()

        #  Load modules
        if self._enabled or self._onlyonce:

            self._site_schema = ModuleHelper.load('app.plugins.autosignin.sites',
                                                  filter_func=lambda _, obj: hasattr(obj, 'match'))

            #  Time service
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            #  Run one immediately
            if self._onlyonce:
                logger.info(" Site automated check-in service activated， Run one immediately")
                self._scheduler.add_job(func=self.sign_in, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name=" Automatic site check-in")

                #  Turn off the disposable switch
                self._onlyonce = False
                #  Save configuration
                self.__update_config()

            #  Periodic operation
            if self._enabled:
                if self._cron:
                    try:
                        if str(self._cron).strip().count(" ") == 4:
                            self._scheduler.add_job(func=self.sign_in,
                                                    trigger=CronTrigger.from_crontab(self._cron),
                                                    name=" Automatic site check-in")
                            logger.info(f" Site automated check-in service activated， Implementation period {self._cron}")
                        else:
                            # 2.3/9-23
                            crons = str(self._cron).strip().split("/")
                            if len(crons) == 2:
                                # 2.3
                                cron = crons[0]
                                # 9-23
                                times = crons[1].split("-")
                                if len(times) == 2:
                                    # 9
                                    self._start_time = int(times[0])
                                    # 23
                                    self._end_time = int(times[1])
                                if self._start_time and self._end_time:
                                    self._scheduler.add_job(func=self.sign_in,
                                                            trigger="interval",
                                                            hours=float(str(cron).strip()),
                                                            name=" Automatic site check-in")
                                    logger.info(
                                        f" Site automated check-in service activated， Implementation period {self._start_time} Point (in space or time)-{self._end_time} Point (in space or time)  Each{cron} Performed once an hour")
                                else:
                                    logger.error(" Failure to start site auto check-in service， Periodicity formatting error")
                                    #  Push real-time messages
                                    self.systemmessage.put(f" Execution cycle misconfiguration")
                                    self._cron = ""
                                    self._enabled = False
                                    self.__update_config()
                            else:
                                #  Default (setting)0-24  Follow the cycle
                                self._start_time = 0
                                self._end_time = 24
                                self._scheduler.add_job(func=self.sign_in,
                                                        trigger="interval",
                                                        hours=float(str(self._cron).strip()),
                                                        name=" Automatic site check-in")
                                logger.info(
                                    f" Site automated check-in service activated， Implementation period {self._start_time} Point (in space or time)-{self._end_time} Point (in space or time)  Each{self._cron} Performed once an hour")
                    except Exception as err:
                        logger.error(f" Timed task configuration error：{err}")
                        #  Push real-time messages
                        self.systemmessage.put(f" Execution cycle misconfiguration：{err}")
                        self._cron = ""
                        self._enabled = False
                        self.__update_config()
                else:
                    #  Random period of time
                    triggers = TimerUtils.random_scheduler(num_executions=2,
                                                           begin_hour=9,
                                                           end_hour=23,
                                                           max_interval=12 * 60,
                                                           min_interval=6 * 60)
                    for trigger in triggers:
                        self._scheduler.add_job(self.sign_in, "cron",
                                                hour=trigger.hour, minute=trigger.minute,
                                                name=" Automatic site check-in")

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    def __update_config(self):
        #  Save configuration
        self.update_config(
            {
                "enabled": self._enabled,
                "notify": self._notify,
                "cron": self._cron,
                "onlyonce": self._onlyonce,
                "queue_cnt": self._queue_cnt,
                "sign_sites": self._sign_sites,
                "login_sites": self._login_sites,
                "retry_keyword": self._retry_keyword,
                "clean": self._clean,
            }
        )

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        Defining remote control commands
        :return:  Command keywords、 Event、 Descriptive、 Accompanying data
        """
        return [{
            "cmd": "/site_signin",
            "event": EventType.SiteSignin,
            "desc": " Site check-in",
            "category": " Website",
            "data": {}
        }]

    def get_api(self) -> List[Dict[str, Any]]:
        """
        Get pluginsAPI
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API Clarification"
        }]
        """
        return [{
            "path": "/signin_by_domain",
            "endpoint": self.signin_by_domain,
            "methods": ["GET"],
            "summary": " Site check-in",
            "description": " Signing in to a site using a site domain",
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Assembly plugin configuration page， Two pieces of data need to be returned：1、 Page configuration；2、 Data structure
        """
        #  Options for the site
        site_options = [{"title": site.name, "value": site.id}
                        for site in Site.list_order_by_pri(self.db)]
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
                                    'md': 3
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
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': ' Send notification',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
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
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'clean',
                                            'label': ' Clear the current day's cache',
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': ' Implementation period',
                                            'placeholder': '5 Classifier for honorific peoplecron Displayed formula， Leave blank spaces in writing'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'queue_cnt',
                                            'label': ' Number of queues'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'retry_keyword',
                                            'label': ' Retry keywords',
                                            'placeholder': ' Regular expression support， Only when it's meant to be will you re-sign (idiom); it's fate to re-sign a contract'
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
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'sign_sites',
                                            'label': ' Check-in site',
                                            'items': site_options
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
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'login_sites',
                                            'label': ' Login site',
                                            'items': site_options
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
                                        'component': 'VAlert',
                                        'props': {
                                            'text': ' Implementation cycle support：'
                                                    '1、5 Classifier for honorific peoplecron Displayed formula；'
                                                    '2、 Configuration interval（ Hourly）， As if2.3/9-23（9-23 The points are separated by2.3 Performed once an hour）；'
                                                    '3、 Periodicity is not filled in by default9-23 Point randomized execution2 Substandard。'
                                                    ' First full implementation per day， The rest of the sites that perform hit retry keywords。'
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
            "notify": True,
            "cron": "",
            "onlyonce": False,
            "clean": False,
            "queue_cnt": 5,
            "sign_sites": [],
            "login_sites": [],
            "retry_keyword": " Incorrect| Fail (e.g. experiments)"
        }

    def get_page(self) -> List[dict]:
        """
        Patchwork plug-in detail page， Need to return to page configuration， Also with data
        """
        #  Array of dates for the last two days
        date_list = [(datetime.now() - timedelta(days=i)).date() for i in range(2)]
        #  Last day's check-in data
        current_day = ""
        sign_data = []
        for day in date_list:
            current_day = f"{day.month} Moon{day.day} Date"
            sign_data = self.get_data(current_day)
            if sign_data:
                break
        if sign_data:
            contents = [
                {
                    'component': 'tr',
                    'props': {
                        'class': 'text-sm'
                    },
                    'content': [
                        {
                            'component': 'td',
                            'props': {
                                'class': 'whitespace-nowrap break-keep text-high-emphasis'
                            },
                            'text': current_day
                        },
                        {
                            'component': 'td',
                            'text': data.get("site")
                        },
                        {
                            'component': 'td',
                            'text': data.get("status")
                        }
                    ]
                } for data in sign_data
            ]
        else:
            contents = [
                {
                    'component': 'tr',
                    'props': {
                        'class': 'text-sm'
                    },
                    'content': [
                        {
                            'component': 'td',
                            'props': {
                                'colspan': 3,
                                'class': 'text-center'
                            },
                            'text': ' No data available'
                        }
                    ]
                }
            ]
        return [
            {
                'component': 'VTable',
                'props': {
                    'hover': True
                },
                'content': [
                    {
                        'component': 'thead',
                        'content': [
                            {
                                'component': 'th',
                                'props': {
                                    'class': 'text-start ps-4'
                                },
                                'text': ' Dates'
                            },
                            {
                                'component': 'th',
                                'props': {
                                    'class': 'text-start ps-4'
                                },
                                'text': ' Website'
                            },
                            {
                                'component': 'th',
                                'props': {
                                    'class': 'text-start ps-4'
                                },
                                'text': ' State of affairs'
                            }
                        ]
                    },
                    {
                        'component': 'tbody',
                        'content': contents
                    }
                ]
            }
        ]

    @eventmanager.register(EventType.SiteSignin)
    def sign_in(self, event: Event = None):
        """
        Automatic check-in| Simulated login
        """
        #  Dates
        today = datetime.today()
        if self._start_time and self._end_time:
            if int(datetime.today().hour) < self._start_time or int(datetime.today().hour) > self._end_time:
                logger.error(
                    f" Current time {int(datetime.today().hour)}  (euphemism) pass away {self._start_time}-{self._end_time}  Coverage， Withdrawal of the mandate")
                return
        if event:
            logger.info(" Command received.， Start site check-in ...")
            self.post_message(channel=event.event_data.get("channel"),
                              title=" Start site check-in ...",
                              userid=event.event_data.get("user"))

        if self._sign_sites:
            self.__do(today=today, type=" Sign in", do_sites=self._sign_sites, event=event)
        if self._login_sites:
            self.__do(today=today, type=" Log in", do_sites=self._login_sites, event=event)

    def __do(self, today: datetime, type: str, do_sites: list, event: Event = None):
        """
        Check-in logic
        """
        yesterday = today - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        #  Delete yesterday's history
        self.del_data(key=type + "-" + yesterday_str)
        self.del_data(key=f"{yesterday.month} Moon{yesterday.day} Date")

        #  Check if you have signed in today| Login history
        today = today.strftime('%Y-%m-%d')
        today_history = self.get_data(key=type + "-" + today)

        #  Search all sites
        all_sites = [site for site in self.sites.get_indexers() if not site.get("public")]
        #  Filter out unchecked sites
        if do_sites:
            do_sites = [site for site in all_sites if site.get("id") in do_sites]
        else:
            do_sites = all_sites

        #  No data today.
        if not today_history or self._clean:
            logger.info(f" Today {today}  8th earthly branch: 1-3 p.m., 6th solar month (7th july-6th august){type}， Commencement{type} Selected sites")
            if self._clean:
                #  Turn off the switch.
                self._clean = False
        else:
            #  Need to retry site
            retry_sites = today_history.get("retry") or []
            #  Signed in today| Login site
            already_sites = today_history.get("do") or []

            #  Not signed today| Login site
            no_sites = [site for site in do_sites if
                        site.get("id") not in already_sites or site.get("id") in retry_sites]

            if not no_sites:
                logger.info(f" Today {today}  Afterwards{type}， Recklessly{type} Website， End of current mandate")
                return

            #  Mission site =  Need to retry+ Not todaydo
            do_sites = no_sites
            logger.info(f" Today {today}  Afterwards{type}， Start retrying hit keyword sites")

        if not do_sites:
            logger.info(f" No need.{type} Sites")
            return

        #  Executive check-in
        logger.info(f" Commence{type} Mandates ...")
        if type == " Sign in":
            with ThreadPool(min(len(do_sites), int(self._queue_cnt))) as p:
                status = p.map(self.signin_site, do_sites)
        else:
            with ThreadPool(min(len(do_sites), int(self._queue_cnt))) as p:
                status = p.map(self.login_site, do_sites)

        if status:
            logger.info(f" Website{type} Mission accomplished！")
            #  Get today's date
            key = f"{datetime.now().month} Moon{datetime.now().day} Date"
            today_data = self.get_data(key)
            if today_data:
                if not isinstance(today_data, list):
                    today_data = [today_data]
                for s in status:
                    today_data.append({
                        "site": s[0],
                        "status": s[1]
                    })
            else:
                today_data = [{
                    "site": s[0],
                    "status": s[1]
                } for s in status]
            #  Save data
            self.save_data(key, today_data)

            #  Sites that hit retry wordsid
            retry_sites = []
            #  Site check-in for hit retry wordsmsg
            retry_msg = []
            #  Login successful
            login_success_msg = []
            #  Sign in successfully
            sign_success_msg = []
            #  Signed in
            already_sign_msg = []
            #  Successful simulation check-in
            fz_sign_msg = []
            #  Fail (e.g. experiments)｜ Incorrect
            failed_msg = []

            sites = {site.get('name'): site.get("id") for site in self.sites.get_indexers() if not site.get("public")}
            for s in status:
                site_name = s[0]
                site_id = None
                if site_name:
                    site_id = sites.get(site_name)
                #  Record the sites that hit this retry keyword
                if self._retry_keyword:
                    if site_id:
                        match = re.search(self._retry_keyword, s[1])
                        if match:
                            logger.debug(f" Website {site_name}  Hit retry keywords {self._retry_keyword}")
                            retry_sites.append(site_id)
                            #  Hit sites
                            retry_msg.append(s)
                            continue

                if " Login successful" in s:
                    login_success_msg.append(s)
                elif " Successful simulation check-in" in s:
                    fz_sign_msg.append(s)
                    continue
                elif " Sign in successfully" in s:
                    sign_success_msg.append(s)
                elif ' Signed in' in s:
                    already_sign_msg.append(s)
                else:
                    failed_msg.append(s)

            if not self._retry_keyword:
                #  Retry the selected site if no retry keyword is set.
                retry_sites = self._sign_sites if type == " Sign in" else self._login_sites
            logger.debug(f" Next time{type} Retry site {retry_sites}")

            #  Commit to history (to a higher standard)
            self.save_data(key=type + "-" + today,
                           value={
                               "do": self._sign_sites if type == " Sign in" else self._login_sites,
                               "retry": retry_sites
                           })

            #  Send notification
            if self._notify:
                #  Check-in details  Login successful、 Sign in successfully、 Signed in、 Successful simulation check-in、 Fail (e.g. experiments)-- Retry after a hit
                signin_message = login_success_msg + sign_success_msg + already_sign_msg + fz_sign_msg + failed_msg
                if len(retry_msg) > 0:
                    signin_message += retry_msg

                signin_message = "\n".join([f'【{s[0]}】{s[1]}' for s in signin_message if s])
                self.post_message(title=f"【 Site automation{type}】",
                                  mtype=NotificationType.SiteMessage,
                                  text=f" Full{type} Quantities: {len(self._sign_sites if type == ' Sign in' else self._login_sites)} \n"
                                       f" This time{type} Quantities: {len(do_sites)} \n"
                                       f" Next time{type} Quantities: {len(retry_sites) if self._retry_keyword else 0} \n"
                                       f"{signin_message}"
                                  )
            if event:
                self.post_message(channel=event.event_data.get("channel"),
                                  title=f" Website{type} Fulfillment！", userid=event.event_data.get("user"))
        else:
            logger.error(f" Website{type} Mission failure！")
            if event:
                self.post_message(channel=event.event_data.get("channel"),
                                  title=f" Website{type} Mission failure！", userid=event.event_data.get("user"))
        #  Save configuration
        self.__update_config()

    def __build_class(self, url) -> Any:
        for site_schema in self._site_schema:
            try:
                if site_schema.match(url):
                    return site_schema
            except Exception as e:
                logger.error(" Site module load failure：%s" % str(e))
        return None

    def signin_by_domain(self, url: str) -> schemas.Response:
        """
        Sign in to a site， Transferring entityAPI Call (programming)
        """
        domain = StringUtils.get_url_domain(url)
        site_info = self.sites.get_indexer(domain)
        if not site_info:
            return schemas.Response(
                success=True,
                message=f" Website【{url}】 Non-existent"
            )
        else:
            return schemas.Response(
                success=True,
                message=self.signin_site(site_info)
            )

    def signin_site(self, site_info: CommentedMap) -> Tuple[str, str]:
        """
        Sign in to a site
        """
        site_module = self.__build_class(site_info.get("url"))
        if site_module and hasattr(site_module, "signin"):
            try:
                _, msg = site_module().signin(site_info)
                #  Special sites return check-in information directly， Preventing simulated check-ins、 Simulated logins are ambiguous
                return site_info.get("name"), msg or ""
            except Exception as e:
                traceback.print_exc()
                return site_info.get("name"), f" Failed to sign in：{str(e)}"
        else:
            return site_info.get("name"), self.__signin_base(site_info)

    @staticmethod
    def __signin_base(site_info: CommentedMap) -> str:
        """
        Generic check-in processing
        :param site_info:  Site information
        :return:  Check-in results information
        """
        if not site_info:
            return ""
        site = site_info.get("name")
        site_url = site_info.get("url")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        render = site_info.get("render")
        proxies = settings.PROXY if site_info.get("proxy") else None
        proxy_server = settings.PROXY_SERVER if site_info.get("proxy") else None
        if not site_url or not site_cookie:
            logger.warn(f" Unconfigured {site}  The site address orCookie， Unable to sign in")
            return ""
        #  Analog login
        try:
            #  Access link
            checkin_url = site_url
            if site_url.find("attendance.php") == -1:
                #  Spellbound check-in address
                checkin_url = urljoin(site_url, "attendance.php")
            logger.info(f" Start site check-in：{site}， Address：{checkin_url}...")
            if render:
                page_source = PlaywrightHelper().get_page_source(url=checkin_url,
                                                                 cookies=site_cookie,
                                                                 ua=ua,
                                                                 proxies=proxy_server)
                if not SiteUtils.is_logged_in(page_source):
                    if under_challenge(page_source):
                        return f" Failure to passCloudflare！"
                    return f" Emulation login failure，Cookie Expired！"
                else:
                    #  Determine if you are signed in or not
                    if re.search(r' Signed| Sign in and get it!', page_source, re.IGNORECASE) \
                            or SiteUtils.is_checkin(page_source):
                        return f" Sign in successfully"
                    return " Successful simulation check-in"
            else:
                res = RequestUtils(cookies=site_cookie,
                                   ua=ua,
                                   proxies=proxies
                                   ).get_res(url=checkin_url)
                if not res and site_url != checkin_url:
                    logger.info(f" Start site simulation login：{site}， Address：{site_url}...")
                    res = RequestUtils(cookies=site_cookie,
                                       ua=ua,
                                       proxies=proxies
                                       ).get_res(url=site_url)
                #  Determine login status
                if res and res.status_code in [200, 500, 403]:
                    if not SiteUtils.is_logged_in(res.text):
                        if under_challenge(res.text):
                            msg = " Web site has beenCloudflare Defend， Please open the site browser simulation"
                        elif res.status_code == 200:
                            msg = "Cookie Expired"
                        else:
                            msg = f" Status code：{res.status_code}"
                        logger.warn(f"{site}  Failed to sign in，{msg}")
                        return f" Failed to sign in，{msg}！"
                    else:
                        logger.info(f"{site}  Sign in successfully")
                        return f" Sign in successfully"
                elif res is not None:
                    logger.warn(f"{site}  Failed to sign in， Status code：{res.status_code}")
                    return f" Failed to sign in， Status code：{res.status_code}！"
                else:
                    logger.warn(f"{site}  Failed to sign in， Unable to open website")
                    return f" Failed to sign in， Unable to open website！"
        except Exception as e:
            logger.warn("%s  Failed to sign in：%s" % (site, str(e)))
            traceback.print_exc()
            return f" Failed to sign in：{str(e)}！"

    def login_site(self, site_info: CommentedMap) -> Tuple[str, str]:
        """
        Simulate logging into a site
        """
        return site_info.get("name"), self.__login_base(site_info)

    @staticmethod
    def __login_base(site_info: CommentedMap) -> str:
        """
        Generic processing for analog login
        :param site_info:  Site information
        :return:  Check-in results information
        """
        if not site_info:
            return ""
        site = site_info.get("name")
        site_url = site_info.get("url")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        render = site_info.get("render")
        proxies = settings.PROXY if site_info.get("proxy") else None
        proxy_server = settings.PROXY_SERVER if site_info.get("proxy") else None
        if not site_url or not site_cookie:
            logger.warn(f" Unconfigured {site}  The site address orCookie， Unable to sign in")
            return ""
        #  Analog login
        try:
            #  Access link
            site_url = str(site_url).replace("attendance.php", "")
            logger.info(f" Start site simulation login：{site}， Address：{site_url}...")
            if render:
                page_source = PlaywrightHelper().get_page_source(url=site_url,
                                                                 cookies=site_cookie,
                                                                 ua=ua,
                                                                 proxies=proxy_server)
                if not SiteUtils.is_logged_in(page_source):
                    if under_challenge(page_source):
                        return f" Failure to passCloudflare！"
                    return f" Emulation login failure，Cookie Expired！"
                else:
                    return " Successful simulated login"
            else:
                res = RequestUtils(cookies=site_cookie,
                                   ua=ua,
                                   proxies=proxies
                                   ).get_res(url=site_url)
                #  Determine login status
                if res and res.status_code in [200, 500, 403]:
                    if not SiteUtils.is_logged_in(res.text):
                        if under_challenge(res.text):
                            msg = " Web site has beenCloudflare Defend， Please open the site browser simulation"
                        elif res.status_code == 200:
                            msg = "Cookie Expired"
                        else:
                            msg = f" Status code：{res.status_code}"
                        logger.warn(f"{site}  Simulated login failure，{msg}")
                        return f" Simulated login failure，{msg}！"
                    else:
                        logger.info(f"{site}  Successful simulated login")
                        return f" Successful simulated login"
                elif res is not None:
                    logger.warn(f"{site}  Simulated login failure， Status code：{res.status_code}")
                    return f" Simulated login failure， Status code：{res.status_code}！"
                else:
                    logger.warn(f"{site}  Simulated login failure， Unable to open website")
                    return f" Simulated login failure， Unable to open website！"
        except Exception as e:
            logger.warn("%s  Simulated login failure：%s" % (site, str(e)))
            traceback.print_exc()
            return f" Simulated login failure：{str(e)}！"

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

    @eventmanager.register(EventType.SiteDeleted)
    def site_deleted(self, event):
        """
        Delete the corresponding site selection
        """
        site_id = event.event_data.get("site_id")
        config = self.get_config()
        if config:
            self._sign_sites = self.__remove_site_id(config.get("sign_sites") or [], site_id)
            self._login_sites = self.__remove_site_id(config.get("login_sites") or [], site_id)
            #  Save configuration
            self.__update_config()

    def __remove_site_id(self, do_sites, site_id):
        if do_sites:
            if isinstance(do_sites, str):
                do_sites = [do_sites]

            #  Delete the corresponding site
            if site_id:
                do_sites = [site for site in do_sites if int(site) != int(site_id)]
            else:
                #  Empty
                do_sites = []

            #  If no site， Failing agreement
            if len(do_sites) == 0:
                self._enabled = False

        return do_sites
