from typing import Generator, Optional

from app.core.config import settings
from app.helper.module import ModuleHelper
from app.log import logger
from app.utils.object import ObjectUtils
from app.utils.singleton import Singleton


class ModuleManager(metaclass=Singleton):
    """
    Module manager
    """

    #  Module list
    _modules: dict = {}
    #  List of runtime modules
    _running_modules: dict = {}

    def __init__(self):
        self.load_modules()

    def load_modules(self):
        """
        Load all modules
        """
        #  Scanning module catalog
        modules = ModuleHelper.load(
            "app.modules",
            filter_func=lambda _, obj: hasattr(obj, 'init_module') and hasattr(obj, 'init_setting')
        )
        self._running_modules = {}
        self._modules = {}
        for module in modules:
            module_id = module.__name__
            self._modules[module_id] = module
            #  Generating examples
            _module = module()
            #  Initialization module
            if self.check_setting(_module.init_setting()):
                #  Load control via template switches
                _module.init_module()
                self._running_modules[module_id] = _module
                logger.info(f"Moudle Loaded：{module_id}")

    def stop(self):
        """
        Stop all modules
        """
        for _, module in self._running_modules.items():
            if hasattr(module, "stop"):
                module.stop()

    @staticmethod
    def check_setting(setting: Optional[tuple]) -> bool:
        """
        Check that the switch is turned on.， Switch use, Separate multiple values， Matching one of these means it's on.
        """
        if not setting:
            return True
        switch, value = setting
        if getattr(settings, switch) and value is True:
            return True
        if value in getattr(settings, switch):
            return True
        return False

    def get_modules(self, method: str) -> Generator:
        """
        Get a list of modules that implement the same method
        """
        if not self._running_modules:
            return []
        for _, module in self._running_modules.items():
            if hasattr(module, method) \
                    and ObjectUtils.check_method(getattr(module, method)):
                yield module
