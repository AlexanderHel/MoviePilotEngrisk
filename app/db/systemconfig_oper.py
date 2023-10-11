import json
from typing import Any, Union

from app.db import DbOper, SessionFactory
from app.db.models.systemconfig import SystemConfig
from app.schemas.types import SystemConfigKey
from app.utils.object import ObjectUtils
from app.utils.singleton import Singleton


class SystemConfigOper(DbOper, metaclass=Singleton):
    #  Configuration objects
    __SYSTEMCONF: dict = {}

    def __init__(self):
        """
        Load configuration into memory
        """
        self._db = SessionFactory()
        super().__init__(self._db)
        for item in SystemConfig.list(self._db):
            if ObjectUtils.is_obj(item.value):
                self.__SYSTEMCONF[item.key] = json.loads(item.value)
            else:
                self.__SYSTEMCONF[item.key] = item.value

    def set(self, key: Union[str, SystemConfigKey], value: Any):
        """
        Setting up system settings
        """
        if isinstance(key, SystemConfigKey):
            key = key.value
        #  Update memory
        self.__SYSTEMCONF[key] = value
        #  Write to database
        if ObjectUtils.is_obj(value):
            value = json.dumps(value)
        elif value is None:
            value = ''
        conf = SystemConfig.get_by_key(self._db, key)
        if conf:
            if value:
                conf.update(self._db, {"value": value})
            else:
                conf.delete(self._db, conf.id)
        else:
            conf = SystemConfig(key=key, value=value)
            conf.create(self._db)

    def get(self, key: Union[str, SystemConfigKey] = None) -> Any:
        """
        Getting system settings
        """
        if isinstance(key, SystemConfigKey):
            key = key.value
        if not key:
            return self.__SYSTEMCONF
        return self.__SYSTEMCONF.get(key)

    def __del__(self):
        if self._db:
            self._db.close()
