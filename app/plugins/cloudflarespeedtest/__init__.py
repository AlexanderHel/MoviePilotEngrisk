import os
import subprocess
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from python_hosts import Hosts, HostsEntry
from requests import Response

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils
from app.utils.ip import IpUtils
from app.utils.system import SystemUtils


class CloudflareSpeedTest(_PluginBase):
    #  Plug-in name
    plugin_name = "Cloudflare IP Preferred"
    #  Plugin description
    plugin_desc = "🌩  Beta (software) Cloudflare CDN  Latency and speed， Automatic preferencesIP。"
    #  Plug-in icons
    plugin_icon = "cloudflare.jpg"
    #  Theme color
    plugin_color = "#F6821F"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "cloudflarespeedtest_"
    #  Loading sequence
    plugin_order = 12
    #  Available user levels
    auth_level = 1

    #  Private property
    _customhosts = False
    _cf_ip = None
    _scheduler = None
    _cron = None
    _onlyonce = False
    _ipv4 = False
    _ipv6 = False
    _version = None
    _additional_args = None
    _re_install = False
    _notify = False
    _check = False
    _cf_path = None
    _cf_ipv4 = None
    _cf_ipv6 = None
    _result_file = None
    _release_prefix = 'https://github.com/XIU2/CloudflareSpeedTest/releases/download'
    _binary_name = 'CloudflareST'

    def init_plugin(self, config: dict = None):
        #  Discontinuation of existing mandates
        self.stop_service()

        #  Read configuration
        if config:
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._cf_ip = config.get("cf_ip")
            self._version = config.get("version")
            self._ipv4 = config.get("ipv4")
            self._ipv6 = config.get("ipv6")
            self._re_install = config.get("re_install")
            self._additional_args = config.get("additional_args")
            self._notify = config.get("notify")
            self._check = config.get("check")

        if self.get_state() or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            try:
                if self.get_state() and self._cron:
                    logger.info(f"Cloudflare CDN Preferred service activation， Cyclicality：{self._cron}")
                    self._scheduler.add_job(func=self.__cloudflareSpeedTest,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name="Cloudflare Preferred")

                if self._onlyonce:
                    logger.info(f"Cloudflare CDN Preferred service activation， Run one immediately")
                    self._scheduler.add_job(func=self.__cloudflareSpeedTest, trigger='date',
                                            run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                            name="Cloudflare Preferred")
                    #  Turn off the disposable switch
                    self._onlyonce = False
                    self.__update_config()
            except Exception as err:
                logger.error(f"Cloudflare CDN Preferred service error：{str(err)}")
                self.systemmessage.put(f"Cloudflare CDN Preferred service error：{str(err)}")
                return

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __cloudflareSpeedTest(self):
        """
        CloudflareSpeedTest Preferred
        """
        self._cf_path = self.get_data_path()
        self._cf_ipv4 = os.path.join(self._cf_path, "ip.txt")
        self._cf_ipv6 = os.path.join(self._cf_path, "ipv6.txt")
        self._result_file = os.path.join(self._cf_path, "result_hosts.txt")

        #  Get customizedHosts Plug-in (software component)， Stop if no setting
        customHosts = self.get_config("CustomHosts")
        self._customhosts = customHosts and customHosts.get("enabled")
        if self._cf_ip and not customHosts or not customHosts.get("hosts"):
            logger.error(f"Cloudflare CDN Preferably relies on customizationHosts， Please maintain firsthosts")
            return

        if not self._cf_ip:
            logger.error("CloudflareSpeedTest Loaded successfully， First run， Need to configure preferencesip")
            return

        # ipv4 Cap (a poem)ipv6 Either one or the other
        if not self._ipv4 and not self._ipv6:
            self._ipv4 = True
            self.__update_config()
            logger.warn(f"Cloudflare CDN Preferably unspecifiedip Typology， Default (setting)ipv4")

        err_flag, release_version = self.__check_envirment()
        if err_flag and release_version:
            #  New version
            self._version = release_version
            self.__update_config()

        hosts = customHosts.get("hosts")
        if isinstance(hosts, str):
            hosts = str(hosts).split('\n')
        #  Calibration preferencesip
        if self._check:
            self.__check_cf_ip(hosts=hosts)

        #  Start preferences
        if err_flag:
            logger.info(" In progressCLoudflare CDN Preferred， Please be patient.")
            #  Execute the preferred command，-dd No speed limit
            if SystemUtils.is_windows():
                cf_command = f'cd \"{self._cf_path}\" && CloudflareST {self._additional_args} -o \"{self._result_file}\"' + (
                    f' -f \"{self._cf_ipv4}\"' if self._ipv4 else '') + (f' -f \"{self._cf_ipv6}\"' if self._ipv6 else '')
            else:
                cf_command = f'cd {self._cf_path} && chmod a+x {self._binary_name} && ./{self._binary_name} {self._additional_args} -o {self._result_file}' + (
                    f' -f {self._cf_ipv4}' if self._ipv4 else '') + (f' -f {self._cf_ipv6}' if self._ipv6 else '')
            logger.info(f' Preferred commands are being executed {cf_command}')
            if SystemUtils.is_windows():
                process = subprocess.Popen(cf_command, shell=True)
                #  Unable to exit after executing a command  Use asynchronous and set timeout programs
                #  Set the timeout to120 Unit of angle or arc equivalent one sixtieth of a degree
                if cf_command.__contains__("-dd"):
                    time.sleep(120)
                else:
                    time.sleep(600)
                #  If it is not in the120 Finish the task in seconds， Then kill the process.
                if process.poll() is None:
                    os.system('taskkill /F /IM CloudflareST.exe')
            else:
                os.system(cf_command)

            #  Getting the best after the bestip
            if SystemUtils.is_windows():
                powershell_command = f"powershell.exe -Command \"Get-Content \'{self._result_file}\' | Select-Object -Skip 1 -First 1 | Write-Output\""
                logger.info(f' Under implementationpowershell Command {powershell_command}')
                best_ip = SystemUtils.execute(powershell_command)
                best_ip = best_ip.split(',')[0]
            else:
                best_ip = SystemUtils.execute("sed -n '2,1p' " + self._result_file + " | awk -F, '{print $1}'")
            logger.info(f"\n Get the optimumip==>[{best_ip}]")

            #  Replacement customizationHosts Plug-in databasehosts
            if IpUtils.is_ipv4(best_ip) or IpUtils.is_ipv6(best_ip):
                if best_ip == self._cf_ip:
                    logger.info(f"CloudflareSpeedTest CDN Preferredip Unchanged， Leave sth. unprocessed")
                else:
                    #  Replacement preferencesip
                    err_hosts = customHosts.get("err_hosts")

                    #  Deal withip
                    new_hosts = []
                    for host in hosts:
                        if host and host != '\n':
                            host_arr = str(host).split()
                            if host_arr[0] == self._cf_ip:
                                new_hosts.append(host.replace(self._cf_ip, best_ip).replace("\n", "") + "\n")
                            else:
                                new_hosts.append(host.replace("\n", "") + "\n")

                    #  Update customizationHosts
                    self.update_config(
                        {
                            "hosts": ''.join(new_hosts),
                            "err_hosts": err_hosts,
                            "enabled": True
                        }, "CustomHosts"
                    )

                    #  Update preferencesip
                    old_ip = self._cf_ip
                    self._cf_ip = best_ip
                    self.__update_config()
                    logger.info(f"Cloudflare CDN Preferredip [{best_ip}]  Replaced customizationHosts Plug-in (software component)")

                    #  Unwind customizationhosts Plugin reloading
                    logger.info(" NotificationsCustomHosts Plugin reloading ...")
                    self.eventmanager.send_event(EventType.PluginReload,
                                                 {
                                                     "plugin_id": "CustomHosts"
                                                 })
                    if self._notify:
                        self.post_message(
                            mtype=NotificationType.SiteMessage,
                            title="【Cloudflare Preferred task completion】",
                            text=f" Rawip：{old_ip}\n"
                                 f" Meso- (chemistry)ip：{best_ip}"
                        )
        else:
            logger.error(" Get the optimumip Formatting error， Please try again.")
            self._onlyonce = False
            self.__update_config()
            self.stop_service()

    def __check_cf_ip(self, hosts):
        """
        Calibratecf Preferredip
        Preventing special circumstancescf Preferredip And customizationhosts Plug-in (software)ip Incoherence
        """
        #  Statistics for eachIP Number of occurrences of the address
        ip_count = {}
        for host in hosts:
            if host:
                ip = host.split()[0]
                if ip in ip_count:
                    ip_count[ip] += 1
                else:
                    ip_count[ip] = 1

        #  Find the most frequentIP Address
        max_ips = []  #  Saving the most occurrences ofIP Address
        max_count = 0
        for ip, count in ip_count.items():
            if count > max_count:
                max_ips = [ip]  #  UpdatedIP Address
                max_count = count
            elif count == max_count:
                max_ips.append(ip)

        #  If the highest number of occurrences ofip There's more than one.， Shall not be treated as compatible
        if len(max_ips) != 1:
            return

        if max_ips[0] != self._cf_ip:
            self._cf_ip = max_ips[0]
            logger.info(f" Getting to customizehosts Plug-in (software)ip {max_ips[0]}  Highest number of occurrences， Auto-corrected preferredip")

    def __check_envirment(self):
        """
        Environmental inspections
        """
        #  Whether or not signs are installed
        install_flag = False

        #  Whether to reinstall
        if self._re_install:
            install_flag = True
            if SystemUtils.is_windows():
                os.system(f'rd /s /q \"{self._cf_path}\"')
            else:
                os.system(f'rm -rf {self._cf_path}')
            logger.info(f' RemovingCloudflareSpeedTest Catalogs {self._cf_path}， Start re-installation')

        #  Determine if a directory exists
        cf_path = Path(self._cf_path)
        if not cf_path.exists():
            os.mkdir(self._cf_path)

        #  GainCloudflareSpeedTest Latest version
        release_version = self.__get_release_version()
        if not release_version:
            #  If the upgrade fails but there is an executableCloudflareST， Then you can continue to run， And vice versa stops
            if Path(f'{self._cf_path}/{self._binary_name}').exists():
                logger.warn(f" GainCloudflareSpeedTest Versions fail， An executable version exists， Continue to run")
                return True, None
            elif self._version:
                logger.error(f" GainCloudflareSpeedTest Versions fail， Get last run version{self._version}， Start installation")
                install_flag = True
            else:
                release_version = "v2.2.2"
                self._version = release_version
                logger.error(f" GainCloudflareSpeedTest Versions fail， Getting the default version{release_version}， Start installation")
                install_flag = True

        #  Updated
        if not install_flag and release_version != self._version:
            logger.info(f" DetectedCloudflareSpeedTest Versions available[{release_version}] Update， Start installation")
            install_flag = True

        #  Database has version data after reinstallation， But if it's not available locally, reinstall it.
        if not install_flag and release_version == self._version and not Path(
                f'{self._cf_path}/{self._binary_name}').exists() and not Path(
                f'{self._cf_path}/CloudflareST.exe').exists():
            logger.warn(f" Not detectedCloudflareSpeedTest Local version， Reinstallation")
            install_flag = True

        if not install_flag:
            logger.info(f"CloudflareSpeedTest No new version， An executable version exists， Continue to run")
            return True, None

        #  Checking the environment、 Mounting
        if SystemUtils.is_windows():
            # windows
            cf_file_name = 'CloudflareST_windows_amd64.zip'
            download_url = f'{self._release_prefix}/{release_version}/{cf_file_name}'
            return self.__os_install(download_url, cf_file_name, release_version,
                                     f"ditto -V -x -k --sequesterRsrc {self._cf_path}/{cf_file_name} {self._cf_path}")
        elif SystemUtils.is_macos():
            # mac
            uname = SystemUtils.execute('uname -m')
            arch = 'amd64' if uname == 'x86_64' else 'arm64'
            cf_file_name = f'CloudflareST_darwin_{arch}.zip'
            download_url = f'{self._release_prefix}/{release_version}/{cf_file_name}'
            return self.__os_install(download_url, cf_file_name, release_version,
                                     f"ditto -V -x -k --sequesterRsrc {self._cf_path}/{cf_file_name} {self._cf_path}")
        else:
            # docker
            uname = SystemUtils.execute('uname -m')
            arch = 'amd64' if uname == 'x86_64' else 'arm64'
            cf_file_name = f'CloudflareST_linux_{arch}.tar.gz'
            download_url = f'{self._release_prefix}/{release_version}/{cf_file_name}'
            return self.__os_install(download_url, cf_file_name, release_version,
                                     f"tar -zxf {self._cf_path}/{cf_file_name} -C {self._cf_path}")

    def __os_install(self, download_url, cf_file_name, release_version, unzip_command):
        """
        macos docker Mountingcloudflare
        """
        #  After manually downloading the installation package， No need to download here
        if not Path(f'{self._cf_path}/{cf_file_name}').exists():
            #  Download for the first time or download the new version of the zip archive
            proxies = settings.PROXY
            https_proxy = proxies.get("https") if proxies and proxies.get("https") else None
            if https_proxy:
                if SystemUtils.is_windows():
                    self.__get_windows_cloudflarest(download_url, proxies)
                else:
                    os.system(
                        f'wget -P {self._cf_path} --no-check-certificate -e use_proxy=yes -e https_proxy={https_proxy} {download_url}')
            else:
                if SystemUtils.is_windows():
                    self.__get_windows_cloudflarest(download_url, proxies)
                else:
                    os.system(f'wget -P {self._cf_path} https://ghproxy.com/{download_url}')

        #  Determine whether the installation package has been downloaded
        if Path(f'{self._cf_path}/{cf_file_name}').exists():
            try:
                if SystemUtils.is_windows():
                    with zipfile.ZipFile(f'{self._cf_path}/{cf_file_name}', 'r') as zip_ref:
                        #  Decompression (in digital technology)ZIP File to the specified directory
                        zip_ref.extractall(self._cf_path)
                    if Path(f'{self._cf_path}\\CloudflareST.exe').exists():
                        logger.info(f"CloudflareSpeedTest Successful installation， Current version：{release_version}")
                        return True, release_version
                    else:
                        logger.error(f"CloudflareSpeedTest Installation failure， Please check")
                        os.system(f'rd /s /q \"{self._cf_path}\"')
                        return False, None
                #  Decompression (in digital technology)
                os.system(f'{unzip_command}')
                #  Delete zip
                os.system(f'rm -rf {self._cf_path}/{cf_file_name}')
                if Path(f'{self._cf_path}/{self._binary_name}').exists():
                    logger.info(f"CloudflareSpeedTest Successful installation， Current version：{release_version}")
                    return True, release_version
                else:
                    logger.error(f"CloudflareSpeedTest Installation failure， Please check")
                    os.removedirs(self._cf_path)
                    return False, None
            except Exception as err:
                #  If the upgrade fails but there is an executableCloudflareST， Then you can continue to run， And vice versa stops
                if Path(f'{self._cf_path}/{self._binary_name}').exists() or \
                        Path(f'{self._cf_path}\\CloudflareST.exe').exists():
                    logger.error(f"CloudflareSpeedTest Installation failure：{str(err)}， Continue to run with the current version")
                    return True, None
                else:
                    logger.error(f"CloudflareSpeedTest Installation failure：{str(err)}， No available version， Stop running")
                    if SystemUtils.is_windows():
                        os.system(f'rd /s /q \"{self._cf_path}\"')
                    else:
                        os.removedirs(self._cf_path)
                    return False, None
        else:
            #  If the upgrade fails but there is an executableCloudflareST， Then you can continue to run， And vice versa stops
            if Path(f'{self._cf_path}/{self._binary_name}').exists() or \
                    Path(f'{self._cf_path}\\CloudflareST.exe').exists():
                logger.warn(f"CloudflareSpeedTest Installation failure， An executable version exists， Continue to run")
                return True, None
            else:
                logger.error(f"CloudflareSpeedTest Installation failure， No available version， Stop running")
                if SystemUtils.is_windows():
                    os.system(f'rd /s /q \"{self._cf_path}\"')
                else:
                    os.removedirs(self._cf_path)
                return False, None

    def __get_windows_cloudflarest(self, download_url, proxies):
        response = Response()
        try:
            response = requests.get(download_url, stream=True, proxies=proxies if proxies else None)
        except requests.exceptions.RequestException as e:
            logger.error(f"CloudflareSpeedTest Failed to download：{str(e)}")
        if response.status_code == 200:
            with open(f'{self._cf_path}\\CloudflareST_windows_amd64.zip', 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

    @staticmethod
    def __get_release_version():
        """
        GainCloudflareSpeedTest Latest version
        """
        version_res = RequestUtils().get_res(
            "https://api.github.com/repos/XIU2/CloudflareSpeedTest/releases/latest")
        if not version_res:
            version_res = RequestUtils(proxies=settings.PROXY).get_res(
                "https://api.github.com/repos/XIU2/CloudflareSpeedTest/releases/latest")
        if version_res:
            ver_json = version_res.json()
            version = f"{ver_json['tag_name']}"
            return version
        else:
            return None

    def __update_config(self):
        """
        Update preferred plugin configuration
        """
        self.update_config({
            "onlyonce": False,
            "cron": self._cron,
            "cf_ip": self._cf_ip,
            "version": self._version,
            "ipv4": self._ipv4,
            "ipv6": self._ipv6,
            "re_install": self._re_install,
            "additional_args": self._additional_args,
            "notify": self._notify,
            "check": self._check
        })

    def get_state(self) -> bool:
        return True if self._cf_ip and self._cron else False

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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cf_ip',
                                            'label': ' PreferredIP',
                                            'placeholder': '121.121.121.121'
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
                                            'model': 'cron',
                                            'label': ' Preferential cycle',
                                            'placeholder': '0 0 0 ? *'
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
                                            'model': 'version',
                                            'readonly': True,
                                            'label': 'CloudflareSpeedTest Releases',
                                            'placeholder': ' Not yet installed'
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
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'ipv4',
                                            'label': 'IPv4',
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
                                            'model': 'ipv6',
                                            'label': 'IPv6',
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
                                            'model': 'check',
                                            'label': ' Automatic calibration',
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 're_install',
                                            'label': ' Run after reinstallation',
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
                                            'label': ' Run-time notification',
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'additional_args',
                                            'label': ' Advanced parameters',
                                            'placeholder': '-dd'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "cf_ip": "",
            "cron": "",
            "version": "",
            "ipv4": True,
            "ipv6": False,
            "check": False,
            "onlyonce": False,
            "re_install": False,
            "notify": True,
            "additional_args": ""
        }

    def get_page(self) -> List[dict]:
        pass

    @staticmethod
    def __read_system_hosts():
        """
        Retrieval systemhosts Boyfriend
        """
        #  Get localhosts Trails
        if SystemUtils.is_windows():
            hosts_path = r"c:\windows\system32\drivers\etc\hosts"
        else:
            hosts_path = '/etc/hosts'
        #  Retrieval systemhosts
        return Hosts(path=hosts_path)

    def __add_hosts_to_system(self, hosts):
        """
        Increasehosts To the system
        """
        #  Systemshosts Boyfriend
        system_hosts = self.__read_system_hosts()
        #  Filter out plugin-addedhosts
        orgin_entries = []
        for entry in system_hosts.entries:
            if entry.entry_type == "comment" and entry.comment == "# CustomHostsPlugin":
                break
            orgin_entries.append(entry)
        system_hosts.entries = orgin_entries
        #  New effectivehosts
        new_entrys = []
        #  New and wronghosts
        err_hosts = []
        err_flag = False
        for host in hosts:
            if not host:
                continue
            host_arr = str(host).split()
            try:
                host_entry = HostsEntry(entry_type='ipv4' if IpUtils.is_ipv4(str(host_arr[0])) else 'ipv6',
                                        address=host_arr[0],
                                        names=host_arr[1:])
                new_entrys.append(host_entry)
            except Exception as err:
                err_hosts.append(host + "\n")
                logger.error(f"[HOST]  Format conversion error：{str(err)}")
                #  Push real-time messages
                self.systemmessage.put(f"[HOST]  Format conversion error：{str(err)}")

        #  Write systemhosts
        if new_entrys:
            try:
                #  Add separation marker
                system_hosts.add([HostsEntry(entry_type='comment', comment="# CustomHostsPlugin")])
                #  Add newHosts
                system_hosts.add(new_entrys)
                system_hosts.write()
                logger.info(" Updating the systemhosts Documentation success")
            except Exception as err:
                err_flag = True
                logger.error(f" Updating the systemhosts File failure：{str(err) or ' Please check the permissions'}")
                #  Push real-time messages
                self.systemmessage.put(f" Updating the systemhosts File failure：{str(err) or ' Please check the permissions'}")
        return err_flag, err_hosts

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
