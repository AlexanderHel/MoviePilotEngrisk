from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Any, List, Dict, Tuple

from app.chain import ChainBase
from app.core.config import settings
from app.core.event import EventManager
from app.db import SessionFactory
from app.db.models import Base
from app.db.plugindata_oper import PluginDataOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.message import MessageHelper
from app.schemas import Notification, NotificationType, MessageChannel


class PluginChian(ChainBase):
    """
    Plug-in processing chain
    """
    pass


class _PluginBase(metaclass=ABCMeta):
    """
    Plugin module base class， Plug-in functionality is implemented by continuing the class
    In addition to the built-in properties， There are also the following methods that can be extended or called：
    - stop_service()  Stop plugin service
    - get_config()  Getting configuration information
    - update_config()  Updating configuration information
    - init_plugin()  Effective configuration information
    - get_data_path()  Get plugin data storage directory
    """
    #  Plug-in name
    plugin_name: str = ""
    #  Plugin description
    plugin_desc: str = ""

    def __init__(self):
        #  Database connection
        self.db = SessionFactory()
        #  Plug-in data
        self.plugindata = PluginDataOper(self.db)
        #  Process chain
        self.chain = PluginChian(self.db)
        #  System configuration
        self.systemconfig = SystemConfigOper()
        #  System message
        self.systemmessage = MessageHelper()
        #  Event manager
        self.eventmanager = EventManager()

    @abstractmethod
    def init_plugin(self, config: dict = None):
        """
        Effective configuration information
        :param config:  Configuration information dictionary
        """
        pass

    @staticmethod
    @abstractmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        Get plugin command
        [{
            "cmd": "/xx",
            "event": EventType.xx,
            "desc": " Name (of a thing)",
            "category": " Categorization， Requires registration toWechat Must be categorized when",
            "data": {}
        }]
        """
        pass

    @abstractmethod
    def get_api(self) -> List[Dict[str, Any]]:
        """
        Get pluginsAPI
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API Name (of a thing)",
            "description": "API Clarification"
        }]
        """
        pass

    @abstractmethod
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Assembly plugin configuration page， Two pieces of data need to be returned：1、 Page configuration；2、 Data structure
        """
        pass

    @abstractmethod
    def get_page(self) -> List[dict]:
        """
        Patchwork plug-in detail page， Need to return to page configuration， Also with data
        """
        pass

    @abstractmethod
    def get_state(self) -> bool:
        """
        Get plugin runtime status
        """
        pass

    @abstractmethod
    def stop_service(self):
        """
        Stop plugins
        """
        pass

    def update_config(self, config: dict, plugin_id: str = None) -> bool:
        """
        Updating configuration information
        :param config:  Configuration information dictionary
        :param plugin_id:  Plug-in (software component)ID
        """
        if not plugin_id:
            plugin_id = self.__class__.__name__
        return self.systemconfig.set(f"plugin.{plugin_id}", config)

    def get_config(self, plugin_id: str = None) -> Any:
        """
        Getting configuration information
        :param plugin_id:  Plug-in (software component)ID
        """
        if not plugin_id:
            plugin_id = self.__class__.__name__
        return self.systemconfig.get(f"plugin.{plugin_id}")

    def get_data_path(self, plugin_id: str = None) -> Path:
        """
        Get plugin data storage directory
        """
        if not plugin_id:
            plugin_id = self.__class__.__name__
        data_path = settings.PLUGIN_DATA_PATH / f"{plugin_id}"
        if not data_path.exists():
            data_path.mkdir(parents=True)
        return data_path

    def save_data(self, key: str, value: Any, plugin_id: str = None) -> Base:
        """
        Saving plug-in data
        :param key:  Digitalkey
        :param value:  Data value
        :param plugin_id:  Plug-in (software component)ID
        """
        if not plugin_id:
            plugin_id = self.__class__.__name__
        return self.plugindata.save(plugin_id, key, value)

    def get_data(self, key: str, plugin_id: str = None) -> Any:
        """
        Getting plugin data
        :param key:  Digitalkey
        :param plugin_id: plugin_id
        """
        if not plugin_id:
            plugin_id = self.__class__.__name__
        return self.plugindata.get_data(plugin_id, key)

    def del_data(self, key: str, plugin_id: str = None) -> Any:
        """
        Delete plug-in data
        :param key:  Digitalkey
        :param plugin_id: plugin_id
        """
        if not plugin_id:
            plugin_id = self.__class__.__name__
        return self.plugindata.del_data(plugin_id, key)

    def post_message(self, channel: MessageChannel = None, mtype: NotificationType = None, title: str = None,
                     text: str = None, image: str = None, link: str = None, userid: str = None):
        """
        Send a message
        """
        self.chain.post_message(Notification(
            channel=channel, mtype=mtype, title=title, text=text,
            image=image, link=link, userid=userid
        ))

    def close(self):
        """
        Close the database connection
        """
        if self.db:
            self.db.close()
