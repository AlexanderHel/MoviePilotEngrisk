from typing import Optional

from pydantic import BaseModel


class Plugin(BaseModel):
    """
    Plugin information
    """
    id: str = None
    #  Plug-in name
    plugin_name: Optional[str] = None
    #  Plugin description
    plugin_desc: Optional[str] = None
    #  Plug-in icons
    plugin_icon: Optional[str] = None
    #  Theme color
    plugin_color: Optional[str] = None
    #  Plug-in version
    plugin_version: Optional[str] = None
    #  Plug-in authors
    plugin_author: Optional[str] = None
    #  Author's homepage
    author_url: Optional[str] = None
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix: Optional[str] = None
    #  Loading sequence
    plugin_order: Optional[int] = 0
    #  Available user levels
    auth_level: Optional[int] = 0
    #  Installed or not
    installed: Optional[bool] = False
    #  Operational state
    state: Optional[bool] = False
    #  Availability of detail pages
    has_page: Optional[bool] = False
