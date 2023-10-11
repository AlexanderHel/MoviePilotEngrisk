# -*- coding: utf-8 -*-
import importlib
import pkgutil


class ModuleHelper:
    """
    Dynamic loading of modules
    """

    @classmethod
    def load(cls, package_path, filter_func=lambda name, obj: True):
        """
        Import submodule
        :param package_path:  Parent package name
        :param filter_func:  Submodule filter functions， The input parameters are the module name and the module object， Come (or go) backTrue Failing agreement， Otherwise not imported
        :return:
        """

        submodules: list = []
        packages = importlib.import_module(package_path)
        for importer, package_name, _ in pkgutil.iter_modules(packages.__path__):
            if package_name.startswith('_'):
                continue
            full_package_name = f'{package_path}.{package_name}'
            module = importlib.import_module(full_package_name)
            for name, obj in module.__dict__.items():
                if name.startswith('_'):
                    continue
                if isinstance(obj, type) and filter_func(name, obj):
                    submodules.append(obj)

        return submodules
