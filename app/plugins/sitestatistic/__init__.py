import re
import warnings
from datetime import datetime, timedelta
from multiprocessing.dummy import Pool as ThreadPool
from threading import Lock
from typing import Optional, Any, List, Dict, Tuple

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ruamel.yaml import CommentedMap

from app import schemas
from app.core.config import settings
from app.core.event import Event
from app.core.event import eventmanager
from app.db.models.site import Site
from app.helper.browser import PlaywrightHelper
from app.helper.module import ModuleHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.plugins.sitestatistic.siteuserinfo import ISiteUserInfo
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils
from app.utils.string import StringUtils
from app.utils.timer import TimerUtils

warnings.filterwarnings("ignore", category=FutureWarning)

lock = Lock()


class SiteStatistic(_PluginBase):
    #  Plug-in name
    plugin_name = " Site statistics"
    #  Plugin description
    plugin_desc = " Automatic statistics and presentation of site data。"
    #  Plug-in icons
    plugin_icon = "statistic.png"
    #  Theme color
    plugin_color = "#324A5E"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "lightolly"
    #  Author's homepage
    author_url = "https://github.com/lightolly"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "sitestatistic_"
    #  Loading sequence
    plugin_order = 1
    #  Available user levels
    auth_level = 2

    #  Private property
    sites = None
    _scheduler: Optional[BackgroundScheduler] = None
    _last_update_time: Optional[datetime] = None
    _sites_data: dict = {}
    _site_schema: List[ISiteUserInfo] = None

    #  Configuration properties
    _enabled: bool = False
    _onlyonce: bool = False
    _cron: str = ""
    _notify: bool = False
    _queue_cnt: int = 5
    _statistic_type: str = None
    _statistic_sites: list = []

    def init_plugin(self, config: dict = None):
        self.sites = SitesHelper()
        #  Discontinuation of existing mandates
        self.stop_service()

        #  Configure
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._queue_cnt = config.get("queue_cnt")
            self._statistic_type = config.get("statistic_type") or "all"
            self._statistic_sites = config.get("statistic_sites") or []

            #  Filter out deleted sites
            self._statistic_sites = [site.get("id") for site in self.sites.get_indexers() if
                                     not site.get("public") and site.get("id") in self._statistic_sites]
            self.__update_config()

        if self._enabled or self._onlyonce:
            #  Load modules
            self._site_schema = ModuleHelper.load('app.plugins.sitestatistic.siteuserinfo',
                                                  filter_func=lambda _, obj: hasattr(obj, 'schema'))

            #  Time service
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            self._site_schema.sort(key=lambda x: x.order)
            #  Site last updated
            self._last_update_time = None
            #  Site data
            self._sites_data = {}

            #  Run one immediately
            if self._onlyonce:
                logger.info(f" Site data statistics service launched， Run one immediately")
                self._scheduler.add_job(self.refresh_all_site_data, 'date',
                                        run_date=datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3)
                                        )
                #  Turn off the disposable switch
                self._onlyonce = False

                #  Save configuration
                self.__update_config()

            #  Periodic operation
            if self._enabled and self._cron:
                try:
                    self._scheduler.add_job(func=self.refresh_all_site_data,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Site statistics")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")
                    #  Push real-time messages
                    self.systemmessage.put(f" Execution cycle misconfiguration：{err}")
            else:
                triggers = TimerUtils.random_scheduler(num_executions=1,
                                                       begin_hour=0,
                                                       end_hour=1,
                                                       min_interval=1,
                                                       max_interval=60)
                for trigger in triggers:
                    self._scheduler.add_job(self.refresh_all_site_data, "cron",
                                            hour=trigger.hour, minute=trigger.minute,
                                            name=" Site statistics")

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        Defining remote control commands
        :return:  Command keywords、 Event、 Descriptive、 Accompanying data
        """
        return [{
            "cmd": "/site_statistic",
            "event": EventType.SiteStatistic,
            "desc": " Site statistics",
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
            "path": "/refresh_by_domain",
            "endpoint": self.refresh_by_domain,
            "methods": ["GET"],
            "summary": " Refresh site data",
            "description": " Refresh site data for the corresponding domain",
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
                                            'label': ' Send notification',
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'statistic_type',
                                            'label': ' Type of statistics',
                                            'items': [
                                                {'title': ' Full complement', 'value': 'all'},
                                                {'title': ' Incremental', 'value': 'add'}
                                            ]
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
                                            'model': 'statistic_sites',
                                            'label': ' Statistical sites',
                                            'items': site_options
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
            "notify": True,
            "cron": "5 1 * * *",
            "queue_cnt": 5,
            "statistic_type": "all",
            "statistic_sites": []
        }

    def get_page(self) -> List[dict]:
        """
        Patchwork plug-in detail page， Need to return to page configuration， Also with data
        """
        #
        #  Array of dates for the last two days
        date_list = [(datetime.now() - timedelta(days=i)).date() for i in range(2)]
        #  Last day's check-in data
        stattistic_data: Dict[str, Dict[str, Any]] = {}
        for day in date_list:
            current_day = day.strftime("%Y-%m-%d")
            stattistic_data = self.get_data(current_day)
            if stattistic_data:
                break
        if not stattistic_data:
            return [
                {
                    'component': 'div',
                    'text': ' No data available',
                    'props': {
                        'class': 'text-center',
                    }
                }
            ]
        #  Data is sorted in descending chronological order
        stattistic_data = dict(sorted(stattistic_data.items(),
                                      key=lambda item: item[1].get('upload') or 0,
                                      reverse=True))
        #  Total uploads
        total_upload = sum([data.get("upload")
                            for data in stattistic_data.values() if data.get("upload")])
        #  Total downloads
        total_download = sum([data.get("download")
                              for data in stattistic_data.values() if data.get("download")])
        #  Total number of species
        total_seed = sum([data.get("seeding")
                          for data in stattistic_data.values() if data.get("seeding")])
        #  Total seeding volume
        total_seed_size = sum([data.get("seeding_size")
                               for data in stattistic_data.values() if data.get("seeding_size")])

        #  Site data明细
        site_trs = [
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
                        'text': site
                    },
                    {
                        'component': 'td',
                        'text': data.get("username")
                    },
                    {
                        'component': 'td',
                        'text': data.get("user_level")
                    },
                    {
                        'component': 'td',
                        'props': {
                            'class': 'text-success'
                        },
                        'text': StringUtils.str_filesize(data.get("upload"))
                    },
                    {
                        'component': 'td',
                        'props': {
                            'class': 'text-error'
                        },
                        'text': StringUtils.str_filesize(data.get("download"))
                    },
                    {
                        'component': 'td',
                        'text': data.get('ratio')
                    },
                    {
                        'component': 'td',
                        'text': '{:,.1f}'.format(data.get('bonus') or 0)
                    },
                    {
                        'component': 'td',
                        'text': data.get('seeding')
                    },
                    {
                        'component': 'td',
                        'text': StringUtils.str_filesize(data.get('seeding_size'))
                    }
                ]
            } for site, data in stattistic_data.items() if not data.get("err_msg")
        ]

        #  Assembly page
        return [
            {
                'component': 'VRow',
                'content': [
                    #  Total uploads
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin/upload.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Total uploads'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': StringUtils.str_filesize(total_upload)
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                        ]
                    },
                    #  Total downloads
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin/download.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Total downloads'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': StringUtils.str_filesize(total_download)
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                        ]
                    },
                    #  Total number of species
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin/seed.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Total number of species'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': f'{"{:,}".format(total_seed)}'
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                        ]
                    },
                    #  Total seeding volume
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 3,
                            'sm': 6
                        },
                        'content': [
                            {
                                'component': 'VCard',
                                'props': {
                                    'variant': 'tonal',
                                },
                                'content': [
                                    {
                                        'component': 'VCardText',
                                        'props': {
                                            'class': 'd-flex align-center',
                                        },
                                        'content': [
                                            {
                                                'component': 'VAvatar',
                                                'props': {
                                                    'rounded': True,
                                                    'variant': 'text',
                                                    'class': 'me-3'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VImg',
                                                        'props': {
                                                            'src': '/plugin/database.png'
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'div',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-caption'
                                                        },
                                                        'text': ' Total seeding volume'
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {
                                                            'class': 'd-flex align-center flex-wrap'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'span',
                                                                'props': {
                                                                    'class': 'text-h6'
                                                                },
                                                                'text': StringUtils.str_filesize(total_seed_size)
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    #  Breakdown of data by site
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                        },
                        'content': [
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
                                                'text': ' Website'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' User id'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' User level'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Upload volume'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Downloads'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Sharing rate'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Magic power level'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Determinant (math.)'
                                            },
                                            {
                                                'component': 'th',
                                                'props': {
                                                    'class': 'text-start ps-4'
                                                },
                                                'text': ' Seeding volume'
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'tbody',
                                        'content': site_trs
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

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

    def __build_class(self, html_text: str) -> Any:
        for site_schema in self._site_schema:
            try:
                if site_schema.match(html_text):
                    return site_schema
            except Exception as e:
                logger.error(f" Site match failure {e}")
        return None

    def build(self, site_info: CommentedMap) -> Optional[ISiteUserInfo]:
        """
        Build site information
        """
        site_cookie = site_info.get("cookie")
        if not site_cookie:
            return None
        site_name = site_info.get("name")
        url = site_info.get("url")
        proxy = site_info.get("proxy")
        ua = site_info.get("ua")
        #  Session management
        with requests.Session() as session:
            proxies = settings.PROXY if proxy else None
            proxy_server = settings.PROXY_SERVER if proxy else None
            render = site_info.get("render")

            logger.debug(f" Website {site_name} url={url} site_cookie={site_cookie} ua={ua}")
            if render:
                #  Evolutionary pattern
                html_text = PlaywrightHelper().get_page_source(url=url,
                                                               cookies=site_cookie,
                                                               ua=ua,
                                                               proxies=proxy_server)
            else:
                #  Normal mode
                res = RequestUtils(cookies=site_cookie,
                                   session=session,
                                   ua=ua,
                                   proxies=proxies
                                   ).get_res(url=url)
                if res and res.status_code == 200:
                    if re.search(r"charset=\"?utf-8\"?", res.text, re.IGNORECASE):
                        res.encoding = "utf-8"
                    else:
                        res.encoding = res.apparent_encoding
                    html_text = res.text
                    #  First login anti-climbing
                    if html_text.find("title") == -1:
                        i = html_text.find("window.location")
                        if i == -1:
                            return None
                        tmp_url = url + html_text[i:html_text.find(";")] \
                            .replace("\"", "") \
                            .replace("+", "") \
                            .replace(" ", "") \
                            .replace("window.location=", "")
                        res = RequestUtils(cookies=site_cookie,
                                           session=session,
                                           ua=ua,
                                           proxies=proxies
                                           ).get_res(url=tmp_url)
                        if res and res.status_code == 200:
                            if "charset=utf-8" in res.text or "charset=UTF-8" in res.text:
                                res.encoding = "UTF-8"
                            else:
                                res.encoding = res.apparent_encoding
                            html_text = res.text
                            if not html_text:
                                return None
                        else:
                            logger.error(" Website %s  Anti-climbing restriction：%s,  Status code：%s" % (site_name, url, res.status_code))
                            return None

                    #  Compatible fake home page situation， Fake homepages usually don't have <link rel="search"  Causality
                    if '"search"' not in html_text and '"csrf-token"' not in html_text:
                        res = RequestUtils(cookies=site_cookie,
                                           session=session,
                                           ua=ua,
                                           proxies=proxies
                                           ).get_res(url=url + "/index.php")
                        if res and res.status_code == 200:
                            if re.search(r"charset=\"?utf-8\"?", res.text, re.IGNORECASE):
                                res.encoding = "utf-8"
                            else:
                                res.encoding = res.apparent_encoding
                            html_text = res.text
                            if not html_text:
                                return None
                elif res is not None:
                    logger.error(f" Website {site_name}  Connection failure， Status code：{res.status_code}")
                    return None
                else:
                    logger.error(f" Website {site_name}  Inaccessible：{url}")
                    return None
            #  Parsing site types
            if html_text:
                site_schema = self.__build_class(html_text)
                if not site_schema:
                    logger.error(" Website %s  Unable to recognize site type" % site_name)
                    return None
                return site_schema(site_name, url, site_cookie, html_text, session=session, ua=ua, proxy=proxy)
            return None

    def refresh_by_domain(self, domain: str) -> schemas.Response:
        """
        Refresh a site's data， Transferring entityAPI Call (programming)
        """
        site_info = self.sites.get_indexer(domain)
        if site_info:
            site_data = self.__refresh_site_data(site_info)
            if site_data:
                return schemas.Response(
                    success=True,
                    message=f" Website {domain}  Refresh successful",
                    data=site_data.to_dict()
                )
            return schemas.Response(
                success=False,
                message=f" Website {domain}  Failed to refresh data， Data not captured"
            )
        return schemas.Response(
            success=False,
            message=f" Website {domain}  Non-existent"
        )

    def __refresh_site_data(self, site_info: CommentedMap) -> Optional[ISiteUserInfo]:
        """
        Updating a singlesite  Data message
        :param site_info:
        :return:
        """
        site_name = site_info.get('name')
        site_url = site_info.get('url')
        if not site_url:
            return None
        unread_msg_notify = True
        try:
            site_user_info: ISiteUserInfo = self.build(site_info=site_info)
            if site_user_info:
                logger.debug(f" Website {site_name}  Beginning with {site_user_info.site_schema()}  Model resolution")
                #  Start parsing
                site_user_info.parse()
                logger.debug(f" Website {site_name}  Parse completion")

                #  When data is not available， Returns only error messages， No historical data updates
                if site_user_info.err_msg:
                    self._sites_data.update({site_name: {"err_msg": site_user_info.err_msg}})
                    return None

                #  Send notification， There are unread messages
                self.__notify_unread_msg(site_name, site_user_info, unread_msg_notify)

                #  The sharing rate is close to1 Hour， Send a message alert
                if site_user_info.ratio and float(site_user_info.ratio) < 1:
                    self.post_message(mtype=NotificationType.SiteMessage,
                                      title=f"【 Low site share rate warning】",
                                      text=f" Website {site_user_info.site_name}  Sharing rate {site_user_info.ratio}， Please note！")

                self._sites_data.update(
                    {
                        site_name: {
                            "upload": site_user_info.upload,
                            "username": site_user_info.username,
                            "user_level": site_user_info.user_level,
                            "join_at": site_user_info.join_at,
                            "download": site_user_info.download,
                            "ratio": site_user_info.ratio,
                            "seeding": site_user_info.seeding,
                            "seeding_size": site_user_info.seeding_size,
                            "leeching": site_user_info.leeching,
                            "bonus": site_user_info.bonus,
                            "url": site_url,
                            "err_msg": site_user_info.err_msg,
                            "message_unread": site_user_info.message_unread
                        }
                    })
                return site_user_info

        except Exception as e:
            logger.error(f" Website {site_name}  Failed to get traffic data：{str(e)}")
        return None

    def __notify_unread_msg(self, site_name: str, site_user_info: ISiteUserInfo, unread_msg_notify: bool):
        if site_user_info.message_unread <= 0:
            return
        if self._sites_data.get(site_name, {}).get('message_unread') == site_user_info.message_unread:
            return
        if not unread_msg_notify:
            return

        #  Parse out the content， Then send the content
        if len(site_user_info.message_unread_contents) > 0:
            for head, date, content in site_user_info.message_unread_contents:
                msg_title = f"【 Website {site_user_info.site_name}  Messages】"
                msg_text = f" Timing：{date}\n Caption：{head}\n Element：\n{content}"
                self.post_message(mtype=NotificationType.SiteMessage, title=msg_title, text=msg_text)
        else:
            self.post_message(mtype=NotificationType.SiteMessage,
                              title=f" Website {site_user_info.site_name}  Received "
                                    f"{site_user_info.message_unread}  A new message.， Please login to view")

    @eventmanager.register(EventType.SiteStatistic)
    def refresh(self, event: Event):
        """
        Refresh site data
        """
        if event:
            logger.info("收到命令，开始Refresh site data ...")
            self.post_message(channel=event.event_data.get("channel"),
                              title="开始Refresh site data ...",
                              userid=event.event_data.get("user"))
        self.refresh_all_site_data()
        if event:
            self.post_message(channel=event.event_data.get("channel"),
                              title=" Site data refresh complete！", userid=event.event_data.get("user"))

    def refresh_all_site_data(self):
        """
        Multi-threaded refresh of site download uploads， Default interval6 Hourly
        """
        if not self.sites.get_indexers():
            return

        logger.info("开始Refresh site data ...")

        with lock:

            #  No site specified， Use all sites by default
            if not self._statistic_sites:
                refresh_sites = [site for site in self.sites.get_indexers() if not site.get("public")]
            else:
                refresh_sites = [site for site in self.sites.get_indexers() if
                                 site.get("id") in self._statistic_sites]
            if not refresh_sites:
                return

            #  Concurrent refresh
            with ThreadPool(min(len(refresh_sites), int(self._queue_cnt or 5))) as p:
                p.map(self.__refresh_site_data, refresh_sites)

            #  Notification refresh complete
            if self._notify:
                yesterday_sites_data = {}
                #  Incremental data
                if self._statistic_type == "add":
                    last_update_time = self.get_data("last_update_time")
                    if last_update_time:
                        yesterday_sites_data = self.get_data(last_update_time) or {}

                messages = []
                #  Sort by uploads in descending order
                sites = self._sites_data.keys()
                uploads = [self._sites_data[site].get("upload") or 0 if not yesterday_sites_data.get(site) else
                           (self._sites_data[site].get("upload") or 0) - (
                                   yesterday_sites_data[site].get("upload") or 0) for site in sites]
                downloads = [self._sites_data[site].get("download") or 0 if not yesterday_sites_data.get(site) else
                             (self._sites_data[site].get("download") or 0) - (
                                     yesterday_sites_data[site].get("download") or 0) for site in sites]
                data_list = sorted(list(zip(sites, uploads, downloads)),
                                   key=lambda x: x[1],
                                   reverse=True)
                #  Total uploads
                incUploads = 0
                #  Total downloads
                incDownloads = 0
                for data in data_list:
                    site = data[0]
                    upload = int(data[1])
                    download = int(data[2])
                    if upload > 0 or download > 0:
                        incUploads += int(upload)
                        incDownloads += int(download)
                        messages.append(f"【{site}】\n"
                                        f" Upload volume：{StringUtils.str_filesize(upload)}\n"
                                        f" Downloads：{StringUtils.str_filesize(download)}\n"
                                        f"————————————")

                if incDownloads or incUploads:
                    messages.insert(0, f"【 Aggregate】\n"
                                       f" Total uploads：{StringUtils.str_filesize(incUploads)}\n"
                                       f" Total downloads：{StringUtils.str_filesize(incDownloads)}\n"
                                       f"————————————")
                    self.post_message(mtype=NotificationType.SiteMessage,
                                      title=" Site statistics", text="\n".join(messages))

            #  Get today's date
            key = datetime.now().strftime('%Y-%m-%d')
            #  Save data
            self.save_data(key, self._sites_data)

            #  Update time
            self.save_data("last_update_time", key)
            logger.info(" Site data refresh complete")

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "cron": self._cron,
            "notify": self._notify,
            "queue_cnt": self._queue_cnt,
            "statistic_type": self._statistic_type,
            "statistic_sites": self._statistic_sites,
        })

    @eventmanager.register(EventType.SiteDeleted)
    def site_deleted(self, event):
        """
        Delete the corresponding site selection
        """
        site_id = event.event_data.get("site_id")
        config = self.get_config()
        if config:
            statistic_sites = config.get("statistic_sites")
            if statistic_sites:
                if isinstance(statistic_sites, str):
                    statistic_sites = [statistic_sites]

                #  Delete the corresponding site
                if site_id:
                    statistic_sites = [site for site in statistic_sites if int(site) != int(site_id)]
                else:
                    #  Empty
                    statistic_sites = []

                #  If no site， Failing agreement
                if len(statistic_sites) == 0:
                    self._enabled = False

                self._statistic_sites = statistic_sites
                #  Save configuration
                self.__update_config()
