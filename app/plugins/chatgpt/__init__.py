from typing import Any, List, Dict, Tuple

from app.core.config import settings
from app.core.event import eventmanager
from app.plugins import _PluginBase
from app.plugins.chatgpt.openai import OpenAi
from app.schemas.types import EventType


class ChatGPT(_PluginBase):
    #  Plug-in name
    plugin_name = "ChatGPT"
    #  Plugin description
    plugin_desc = " Message interaction support withChatGPT Dialogues。"
    #  Plug-in icons
    plugin_icon = "chatgpt.png"
    #  Theme color
    plugin_color = "#74AA9C"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "jxxghp"
    #  Author's homepage
    author_url = "https://github.com/jxxghp"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "chatgpt_"
    #  Loading sequence
    plugin_order = 15
    #  Available user levels
    auth_level = 1

    #  Private property
    openai = None
    _enabled = False
    _proxy = False
    _openai_url = None
    _openai_key = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._openai_url = config.get("openai_url")
            self._openai_key = config.get("openai_key")
            self.openai = OpenAi(api_key=self._openai_key, api_url=self._openai_url,
                                 proxy=settings.PROXY if self._proxy else None)

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
                            },
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
                                            'model': 'proxy',
                                            'label': ' Using proxies',
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
                                            'model': 'openai_url',
                                            'label': 'OpenAI API Url',
                                            'placeholder': 'https://api.openai.com',
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
                                            'model': 'openai_key',
                                            'label': 'sk-xxx'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            "proxy": False,
            "openai_url": "https://api.openai.com",
            "openai_key": ""
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.UserMessage)
    def talk(self, event):
        """
        Listening to user messages， GainChatGPT Return (to a previous condition)
        """
        if not self.openai:
            return
        text = event.event_data.get("text")
        userid = event.event_data.get("userid")
        channel = event.event_data.get("channel")
        if not text:
            return
        response = self.openai.get_response(text=text, userid=userid)
        if response:
            self.post_message(channel=channel, title=response, userid=userid)

    def stop_service(self):
        """
        Exit plugin
        """
        pass
