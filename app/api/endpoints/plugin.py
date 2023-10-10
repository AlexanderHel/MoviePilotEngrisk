from typing import Any, List

from fastapi import APIRouter, Depends

from app import schemas
from app.core.plugin import PluginManager
from app.core.security import verify_token
from app.db.systemconfig_oper import SystemConfigOper
from app.schemas.types import SystemConfigKey

router = APIRouter()


@router.get("/", summary=" All plug-ins", response_model=List[schemas.Plugin])
def all_plugins(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Check the list of all plug-ins
    """
    return PluginManager().get_plugin_apps()


@router.get("/installed", summary=" Installed plug-ins", response_model=List[str])
def installed_plugins(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query the list of installed plug-ins for a user
    """
    return SystemConfigOper().get(SystemConfigKey.UserInstalledPlugins) or []


@router.get("/install/{plugin_id}", summary=" Installation of plug-ins", response_model=schemas.Response)
def install_plugin(plugin_id: str,
                   _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Installation of plug-ins
    """
    # 已Installation of plug-ins
    install_plugins = SystemConfigOper().get(SystemConfigKey.UserInstalledPlugins) or []
    # Installation of plug-ins
    if plugin_id not in install_plugins:
        install_plugins.append(plugin_id)
        #  Save settings
        SystemConfigOper().set(SystemConfigKey.UserInstalledPlugins, install_plugins)
        #  Reload plugin manager
        PluginManager().init_config()
    return schemas.Response(success=True)


@router.get("/form/{plugin_id}", summary=" Get plugin form page")
def plugin_form(plugin_id: str,
                _: schemas.TokenPayload = Depends(verify_token)) -> dict:
    """
    Depending on the plug-inID Get plugin configuration form
    """
    conf, model = PluginManager().get_plugin_form(plugin_id)
    return {
        "conf": conf,
        "model": model
    }


@router.get("/page/{plugin_id}", summary=" Get plugin data page")
def plugin_page(plugin_id: str, _: schemas.TokenPayload = Depends(verify_token)) -> List[dict]:
    """
    Depending on the plug-inID Getting plugin configuration information
    """
    return PluginManager().get_plugin_page(plugin_id)


@router.get("/{plugin_id}", summary=" Getting plugin configuration")
def plugin_config(plugin_id: str, _: schemas.TokenPayload = Depends(verify_token)) -> dict:
    """
    Depending on the plug-inID Getting plugin configuration information
    """
    return PluginManager().get_plugin_config(plugin_id)


@router.put("/{plugin_id}", summary=" Updating plugin configuration", response_model=schemas.Response)
def set_plugin_config(plugin_id: str, conf: dict,
                      _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Depending on the plug-inID Getting plugin configuration information
    """
    #  Save configuration
    PluginManager().save_plugin_config(plugin_id, conf)
    #  Re-activation plugin
    PluginManager().reload_plugin(plugin_id, conf)
    return schemas.Response(success=True)


@router.delete("/{plugin_id}", summary=" Uninstallation of plug-ins", response_model=schemas.Response)
def uninstall_plugin(plugin_id: str,
                     _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Uninstallation of plug-ins
    """
    #  Deleting installed information
    install_plugins = SystemConfigOper().get(SystemConfigKey.UserInstalledPlugins) or []
    for plugin in install_plugins:
        if plugin == plugin_id:
            install_plugins.remove(plugin)
            break
    #  Save (a file etc) (computing)
    SystemConfigOper().set(SystemConfigKey.UserInstalledPlugins, install_plugins)
    #  Reload plugin manager
    PluginManager().init_config()
    return schemas.Response(success=True)


#  Registration pluginAPI
for api in PluginManager().get_plugin_apis():
    router.add_api_route(**api)
