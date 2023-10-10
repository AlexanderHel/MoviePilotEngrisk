import traceback
from typing import List, Any, Dict, Tuple

from app.db.systemconfig_oper import SystemConfigOper
from app.helper.module import ModuleHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.schemas.types import SystemConfigKey
from app.utils.object import ObjectUtils
from app.utils.singleton import Singleton


class PluginManager(metaclass=Singleton):
    """
    Plug-in manager
    """
    systemconfig: SystemConfigOper = None

    #  Plugin list
    _plugins: dict = {}
    #  List of runtime state plug-ins
    _running_plugins: dict = {}
    #  ConfigureKey
    _config_key: str = "plugin.%s"

    def __init__(self):
        self.siteshelper = SitesHelper()
        self.init_config()

    def init_config(self):
        #  Configuration management
        self.systemconfig = SystemConfigOper()
        #  Stop existing plug-ins
        self.stop()
        #  Startup plugin
        self.start()

    def start(self):
        """
        Start loading plug-ins
        """

        #  Scanning plugin catalog
        plugins = ModuleHelper.load(
            "app.plugins",
            filter_func=lambda _, obj: hasattr(obj, 'init_plugin')
        )
        #  Installed plug-ins
        installed_plugins = self.systemconfig.get(SystemConfigKey.UserInstalledPlugins) or []
        #  Arrange in order
        plugins.sort(key=lambda x: x.plugin_order if hasattr(x, "plugin_order") else 0)
        self._running_plugins = {}
        self._plugins = {}
        for plugin in plugins:
            plugin_id = plugin.__name__
            try:
                #  StockpileClass
                self._plugins[plugin_id] = plugin
                #  Uninstalled not loaded
                if plugin_id not in installed_plugins:
                    continue
                #  Generating examples
                plugin_obj = plugin()
                #  Effective plugin configuration
                plugin_obj.init_plugin(self.get_plugin_config(plugin_id))
                #  Storing running instances
                self._running_plugins[plugin_id] = plugin_obj
                logger.info(f"Plugin Loaded：{plugin_id}")
            except Exception as err:
                logger.error(f" Loading plug-ins {plugin_id}  Make a mistake：{err} - {traceback.format_exc()}")

    def reload_plugin(self, plugin_id: str, conf: dict):
        """
        Reload the plugin
        """
        if not self._running_plugins.get(plugin_id):
            return
        self._running_plugins[plugin_id].init_plugin(conf)

    def stop(self):
        """
        Cessation
        """
        # Cessation所有插件
        for plugin in self._running_plugins.values():
            #  Closing the database
            if hasattr(plugin, "close"):
                plugin.close()
            #  Close plug-in
            if hasattr(plugin, "stop_service"):
                plugin.stop_service()
        #  Empty the image
        self._plugins = {}
        self._running_plugins = {}

    def get_plugin_config(self, pid: str) -> dict:
        """
        Getting plugin configuration
        """
        if not self._plugins.get(pid):
            return {}
        return self.systemconfig.get(self._config_key % pid) or {}

    def save_plugin_config(self, pid: str, conf: dict) -> bool:
        """
        Save plugin configuration
        """
        if not self._plugins.get(pid):
            return False
        return self.systemconfig.set(self._config_key % pid, conf)

    def get_plugin_form(self, pid: str) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Get plugin form
        """
        if not self._running_plugins.get(pid):
            return [], {}
        if hasattr(self._running_plugins[pid], "get_form"):
            return self._running_plugins[pid].get_form() or ([], {})
        return [], {}

    def get_plugin_page(self, pid: str) -> List[dict]:
        """
        Get plugin page
        """
        if not self._running_plugins.get(pid):
            return []
        if hasattr(self._running_plugins[pid], "get_page"):
            return self._running_plugins[pid].get_page() or []
        return []

    def get_plugin_commands(self) -> List[Dict[str, Any]]:
        """
        Get plugin command
        [{
            "cmd": "/xx",
            "event": EventType.xx,
            "desc": "xxxx",
            "data": {}
        }]
        """
        ret_commands = []
        for _, plugin in self._running_plugins.items():
            if hasattr(plugin, "get_command") \
                    and ObjectUtils.check_method(plugin.get_command):
                ret_commands += plugin.get_command() or []
        return ret_commands

    def get_plugin_apis(self) -> List[Dict[str, Any]]:
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
        ret_apis = []
        for pid, plugin in self._running_plugins.items():
            if hasattr(plugin, "get_api") \
                    and ObjectUtils.check_method(plugin.get_api):
                apis = plugin.get_api() or []
                for api in apis:
                    api["path"] = f"/{pid}{api['path']}"
                ret_apis.extend(apis)
        return ret_apis

    def run_plugin_method(self, pid: str, method: str, *args, **kwargs) -> Any:
        """
        How to run the plug-in
        """
        if not self._running_plugins.get(pid):
            return None
        if not hasattr(self._running_plugins[pid], method):
            return None
        return getattr(self._running_plugins[pid], method)(*args, **kwargs)

    def get_plugin_apps(self) -> List[dict]:
        """
        Get all plugin information
        """
        #  Return value
        all_confs = []
        #  Installed plug-ins
        installed_apps = self.systemconfig.get(SystemConfigKey.UserInstalledPlugins) or []
        for pid, plugin in self._plugins.items():
            #  Runner plug-in
            plugin_obj = self._running_plugins.get(pid)
            #  Basic property
            conf = {}
            # ID
            conf.update({"id": pid})
            #  Installed state
            if pid in installed_apps:
                conf.update({"installed": True})
            else:
                conf.update({"installed": False})
            #  Operational state
            if plugin_obj and hasattr(plugin, "get_state"):
                conf.update({"state": plugin_obj.get_state()})
            else:
                conf.update({"state": False})
            #  Availability of detail pages
            if hasattr(plugin, "get_page"):
                if ObjectUtils.check_method(plugin.get_page):
                    conf.update({"has_page": True})
                else:
                    conf.update({"has_page": False})
            #  Scope of one's jurisdiction
            if hasattr(plugin, "auth_level"):
                if self.siteshelper.auth_level < plugin.auth_level:
                    continue
            #  Name (of a thing)
            if hasattr(plugin, "plugin_name"):
                conf.update({"plugin_name": plugin.plugin_name})
            #  Descriptive
            if hasattr(plugin, "plugin_desc"):
                conf.update({"plugin_desc": plugin.plugin_desc})
            #  Releases
            if hasattr(plugin, "plugin_version"):
                conf.update({"plugin_version": plugin.plugin_version})
            #  Icon (computing)
            if hasattr(plugin, "plugin_icon"):
                conf.update({"plugin_icon": plugin.plugin_icon})
            #  Theme color
            if hasattr(plugin, "plugin_color"):
                conf.update({"plugin_color": plugin.plugin_color})
            #  Author
            if hasattr(plugin, "plugin_author"):
                conf.update({"plugin_author": plugin.plugin_author})
            #  Author链接
            if hasattr(plugin, "author_url"):
                conf.update({"author_url": plugin.author_url})
            #  Aggregate
            all_confs.append(conf)
        return all_confs
