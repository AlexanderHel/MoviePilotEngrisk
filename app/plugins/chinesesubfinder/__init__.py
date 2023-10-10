from functools import lru_cache
from pathlib import Path
from typing import List, Tuple, Dict, Any

from app.core.config import settings
from app.core.context import MediaInfo
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import TransferInfo
from app.schemas.types import EventType, MediaType
from app.utils.http import RequestUtils


class ChineseSubFinder(_PluginBase):
    #  Plug-in name
    plugin_name = "ChineseSubFinder"
    #  Plugin description
    plugin_desc = " Notify me when you're ready to organize your inventoryChineseSubFinder Download subtitles。"
    #  Plug-in icons
    plugin_icon = "chinesesubfinder.png"
    #  Theme color
    plugin_color = "#83BE39"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "chinesesubfinder_"
    #  Loading sequence
    plugin_order = 5
    #  Available user levels
    auth_level = 1

    #  Private property
    _save_tmp_path = None
    _enabled = False
    _host = None
    _api_key = None
    _remote_path = None
    _local_path = None

    def init_plugin(self, config: dict = None):
        self._save_tmp_path = settings.TEMP_PATH
        if config:
            self._enabled = config.get("enabled")
            self._api_key = config.get("api_key")
            self._host = config.get('host')
            if self._host:
                if not self._host.startswith('http'):
                    self._host = "http://" + self._host
                if not self._host.endswith('/'):
                    self._host = self._host + "/"
            self._local_path = config.get("local_path")
            self._remote_path = config.get("remote_path")

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
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
                                            'label': ' Enabling plug-ins',
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
                                            'model': 'host',
                                            'label': ' Server (computer)'
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
                                            'model': 'api_key',
                                            'label': 'API Keys'
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
                                            'model': 'local_path',
                                            'label': ' Local path'
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
                                            'model': 'remote_path',
                                            'label': ' Remote path'
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
            "host": "",
            "api_key": "",
            "local_path": "",
            "remote_path": ""
        }

    def get_state(self) -> bool:
        return self._enabled

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        pass

    @eventmanager.register(EventType.TransferComplete)
    def download(self, event: Event):
        """
        Call (programming)ChineseSubFinder Download subtitles
        """
        if not self._enabled or not self._host or not self._api_key:
            return
        item = event.event_data
        if not item:
            return
        #  Request address
        req_url = "%sapi/v1/add-job" % self._host

        #  Media information
        item_media: MediaInfo = item.get("mediainfo")
        #  Transfer information
        item_transfer: TransferInfo = item.get("transferinfo")
        #  Typology
        item_type = item_media.type
        #  Destination path
        item_dest: Path = item_transfer.target_path
        #  Whether or not the original blu-ray disc
        item_bluray = item_transfer.is_bluray
        #  List of documents
        item_file_list = item_transfer.file_list_new

        if item_bluray:
            #  Blu-ray disc virtualization files
            item_file_list = ["%s.mp4" % item_dest / item_dest.name]

        for file_path in item_file_list:
            #  Path replacement
            if self._local_path and self._remote_path and file_path.startswith(self._local_path):
                file_path = file_path.replace(self._local_path, self._remote_path).replace('\\', '/')

            #  Call (programming)CSF Download subtitles
            self.__request_csf(req_url=req_url,
                               file_path=file_path,
                               item_type=0 if item_type == MediaType.MOVIE.value else 1,
                               item_bluray=item_bluray)

    @lru_cache(maxsize=128)
    def __request_csf(self, req_url, file_path, item_type, item_bluray):
        #  Create only one task with one name
        logger.info(" NotificationsChineseSubFinder Download subtitles: %s" % file_path)
        params = {
            "video_type": item_type,
            "physical_video_file_full_path": file_path,
            "task_priority_level": 3,
            "media_server_inside_video_id": "",
            "is_bluray": item_bluray
        }
        try:
            res = RequestUtils(headers={
                "Authorization": "Bearer %s" % self._api_key
            }).post(req_url, json=params)
            if not res or res.status_code != 200:
                logger.error(" Call (programming)ChineseSubFinder API Fail (e.g. experiments)！")
            else:
                #  If the file directory is not recognized by thenfo Metadata，  This interface returns the controller， PresumablyChineseSubFinder Underlying causes
                # emby refresh Asynchronous when metadata
                if res.text:
                    job_id = res.json().get("job_id")
                    message = res.json().get("message")
                    if not job_id:
                        logger.warn("ChineseSubFinder Error downloading subtitles：%s" % message)
                    else:
                        logger.info("ChineseSubFinder Task added successfully：%s" % job_id)
                else:
                    logger.error("%s  Missing catalognfo Metadata" % file_path)
        except Exception as e:
            logger.error(" GroutChineseSubFinder Make a mistake：" + str(e))
