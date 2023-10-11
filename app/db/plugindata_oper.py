import json
from typing import Any

from app.db import DbOper
from app.db.models.plugin import PluginData
from app.utils.object import ObjectUtils


class PluginDataOper(DbOper):
    """
    Plug-in data management
    """

    def save(self, plugin_id: str, key: str, value: Any) -> PluginData:
        """
        Saving plug-in data
        :param plugin_id:  Plug-in (software component)id
        :param key:  Digitalkey
        :param value:  Data value
        """
        if ObjectUtils.is_obj(value):
            value = json.dumps(value)
        plugin = PluginData.get_plugin_data_by_key(self._db, plugin_id, key)
        if plugin:
            plugin.update(self._db, {
                "value": value
            })
            return plugin
        else:
            plugin = PluginData(plugin_id=plugin_id, key=key, value=value)
            return plugin.create(self._db)

    def get_data(self, plugin_id: str, key: str) -> Any:
        """
        Getting plugin data
        :param plugin_id:  Plug-in (software component)id
        :param key:  Digitalkey
        """
        data = PluginData.get_plugin_data_by_key(self._db, plugin_id, key)
        if not data:
            return None
        if ObjectUtils.is_obj(data.value):
            return json.loads(data.value)
        return data.value

    def del_data(self, plugin_id: str, key: str) -> Any:
        """
        Delete plug-in data
        :param plugin_id:  Plug-in (software component)id
        :param key:  Digitalkey
        """
        PluginData.del_plugin_data_by_key(self._db, plugin_id, key)

    def truncate(self):
        """
        Empty plugin data
        """
        PluginData.truncate(self._db)

    def get_data_all(self, plugin_id: str) -> Any:
        """
        Get all the data of the plugin
        :param plugin_id:  Plug-in (software component)id
        """
        return PluginData.get_plugin_data_by_plugin_id(self._db, plugin_id)
