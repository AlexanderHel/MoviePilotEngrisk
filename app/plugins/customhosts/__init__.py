from typing import List, Tuple, Dict, Any

from python_hosts import Hosts, HostsEntry

from app.core.event import eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType
from app.utils.ip import IpUtils
from app.utils.system import SystemUtils


class CustomHosts(_PluginBase):
    #  Plug-in name
    plugin_name = " CustomizableHosts"
    #  Plugin description
    plugin_desc = " Modify the systemhosts File， Accelerated network access。"
    #  Plug-in icons
    plugin_icon = "hosts.png"
    #  Theme color
    plugin_color = "#02C4E0"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "customhosts_"
    #  Loading sequence
    plugin_order = 10
    #  Available user levels
    auth_level = 1

    #  Private property
    _hosts = []
    _enabled = False

    def init_plugin(self, config: dict = None):
        #  Read configuration
        if config:
            self._enabled = config.get("enabled")
            self._hosts = config.get("hosts")
            if isinstance(self._hosts, str):
                self._hosts = str(self._hosts).split('\n')
            if self._enabled and self._hosts:
                #  Freehost
                new_hosts = []
                for host in self._hosts:
                    if host and host != '\n':
                        new_hosts.append(host.replace("\n", "") + "\n")
                self._hosts = new_hosts

                #  Add to system
                error_flag, error_hosts = self.__add_hosts_to_system(self._hosts)
                self._enabled = self._enabled and not error_flag

                #  Update errorHosts
                self.update_config({
                    "hosts": ''.join(self._hosts),
                    "err_hosts": error_hosts,
                    "enabled": self._enabled
                })

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
                                           'cols': 12
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextarea',
                                               'props': {
                                                   'model': 'hosts',
                                                   'label': ' Customizablehosts',
                                                   'rows': 10,
                                                   'placeholder': ' One configuration per line， Format：ip host1 host2 ...'
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
                                           'cols': 12
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextarea',
                                               'props': {
                                                   'model': 'err_hosts',
                                                   'readonly': True,
                                                   'label': ' Incorrecthosts',
                                                   'rows': 2,
                                                   'placeholder': ' Craphosts The configuration is displayed here， Please modify the abovehosts Resubmission（ Craphosts Does not write to the systemhosts File）'
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
                   "hosts": "",
                   "err_hosts": ""
               }

    def get_page(self) -> List[dict]:
        pass

    @staticmethod
    def __read_system_hosts():
        """
        Retrieval systemhosts Boyfriend
        """
        #  Get localhosts Trails
        if SystemUtils.is_windows():
            hosts_path = r"c:\windows\system32\drivers\etc\hosts"
        else:
            hosts_path = '/etc/hosts'
        #  Retrieval systemhosts
        return Hosts(path=hosts_path)

    def __add_hosts_to_system(self, hosts):
        """
        Increasehosts To the system
        """
        #  Systemshosts Boyfriend
        system_hosts = self.__read_system_hosts()
        #  Filter out plugin-addedhosts
        orgin_entries = []
        for entry in system_hosts.entries:
            if entry.entry_type == "comment" and entry.comment == "# CustomHostsPlugin":
                break
            orgin_entries.append(entry)
        system_hosts.entries = orgin_entries
        #  New effectivehosts
        new_entrys = []
        #  New and wronghosts
        err_hosts = []
        err_flag = False
        for host in hosts:
            if not host:
                continue
            host_arr = str(host).split()
            try:
                host_entry = HostsEntry(entry_type='ipv4' if IpUtils.is_ipv4(str(host_arr[0])) else 'ipv6',
                                        address=host_arr[0],
                                        names=host_arr[1:])
                new_entrys.append(host_entry)
            except Exception as err:
                err_hosts.append(host + "\n")
                logger.error(f"[HOST]  Format conversion error：{str(err)}")
                #  Push real-time messages
                self.systemmessage.put(f"[HOST]  Format conversion error：{str(err)}")

        #  Write systemhosts
        if new_entrys:
            try:
                #  Add separation marker
                system_hosts.add([HostsEntry(entry_type='comment', comment="# CustomHostsPlugin")])
                #  Add newHosts
                system_hosts.add(new_entrys)
                system_hosts.write()
                logger.info("Update system hosts file successfully (Note: Container hosts are updated when the container is running!)")
            except Exception as err:
                err_flag = True
                logger.error(f" Updating the systemhosts File failure：{str(err) or ' Please check the permissions'}")
                #  Push real-time messages
                self.systemmessage.put(f" Updating the systemhosts File failure：{str(err) or ' Please check the permissions'}")
        return err_flag, err_hosts

    def stop_service(self):
        """
        Exit plugin
        """
        pass

    @eventmanager.register(EventType.PluginReload)
    def reload(self, event):
        """
        Responding to plugin reload events
        """
        plugin_id = event.event_data.get("plugin_id")
        if not plugin_id:
            return
        if plugin_id != self.__class__.__name__:
            return
        return self.init_plugin(self.get_config())
