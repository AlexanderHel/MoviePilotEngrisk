import glob
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger
from app.schemas import NotificationType


class AutoBackup(_PluginBase):
    #  Plug-in name
    plugin_name = " Automatic backup"
    #  Plugin description
    plugin_desc = " Automatic backup of data and configuration files。"
    #  Plug-in icons
    plugin_icon = "backup.png"
    #  Theme color
    plugin_color = "#4FB647"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "autobackup_"
    #  Loading sequence
    plugin_order = 17
    #  Available user levels
    auth_level = 1

    #  Private property
    _enabled = False
    #  Task execution interval
    _cron = None
    _cnt = None
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
            self._cnt = config.get("cnt")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")

            #  Load modules
        if self._enabled:
            #  Time service
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._cron:
                try:
                    self._scheduler.add_job(func=self.__backup,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            name=" Automatic backup")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")

            if self._onlyonce:
                logger.info(f" Automatic backup service starts， Run one immediately")
                self._scheduler.add_job(func=self.__backup, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                        name=" Automatic backup")
                #  Turn off the disposable switch
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "cron": self._cron,
                    "enabled": self._enabled,
                    "cnt": self._cnt,
                    "notify": self._notify,
                })

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __backup(self):
        """
        Automatic backup、 Delete backup
        """
        logger.info(f" Current time {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}  Start backup")

        # docker Use the default path
        bk_path = self.get_data_path()

        #  Backing up
        zip_file = self.backup(bk_path=bk_path)

        if zip_file:
            logger.info(f" Backup complete  Backup file {zip_file} ")
        else:
            logger.error(" Failed to create backup")

        #  Clean up your backups
        bk_cnt = 0
        del_cnt = 0
        if self._cnt:
            #  Get all the files under the specified path that start with"bk" Documents beginning with， Sort by creation time from oldest to newest
            files = sorted(glob.glob(f"{bk_path}/bk**"), key=os.path.getctime)
            bk_cnt = len(files)
            #  Calculate the number of files to be deleted
            del_cnt = bk_cnt - int(self._cnt)
            if del_cnt > 0:
                logger.info(
                    f" Get {bk_path}  Number of backup files under path {bk_cnt}  Number of reservations {int(self._cnt)}  Number of backup files to be deleted {del_cnt}")

                #  Iterate through and delete the oldest few backups
                for i in range(del_cnt):
                    os.remove(files[i])
                    logger.debug(f" Deleting backup files {files[i]}  Successes")
            else:
                logger.info(
                    f" Get {bk_path}  Number of backup files under path {bk_cnt}  Number of reservations {int(self._cnt)}  No need to delete")

        #  Send notification
        if self._notify:
            self.post_message(
                mtype=NotificationType.SiteMessage,
                title="【 Automatic backup task completion】",
                text=f" Creating a backup{' Successes' if zip_file else ' Fail (e.g. experiments)'}\n"
                     f" Clean up the number of backups {del_cnt}\n"
                     f" Number of remaining backups {bk_cnt - del_cnt}")

    @staticmethod
    def backup(bk_path: Path = None):
        """
        @param bk_path      Customizing the backup path
        """
        try:
            #  Creating a backup folder
            config_path = Path(settings.CONFIG_PATH)
            backup_file = f"bk_{time.strftime('%Y%m%d%H%M%S')}"
            backup_path = bk_path / backup_file
            backup_path.mkdir(parents=True)
            #  Take existing relevant documents andcopy Backing up
            if settings.LIBRARY_CATEGORY:
                shutil.copy(f'{config_path}/category.yaml', backup_path)
            shutil.copy(f'{config_path}/user.db', backup_path)

            zip_file = str(backup_path) + '.zip'
            if os.path.exists(zip_file):
                zip_file = str(backup_path) + '.zip'
            shutil.make_archive(str(backup_path), 'zip', str(backup_path))
            shutil.rmtree(str(backup_path))
            return zip_file
        except IOError:
            return None

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
                                            'label': ' Backup cycle'
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
                                            'model': 'cnt',
                                            'label': ' Maximum number of retained backups'
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
                                            'text': ' The backup file path defaults to the locally mappedconfig/plugins/AutoBackup。'
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
            "request_method": "POST",
            "webhook_url": ""
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
