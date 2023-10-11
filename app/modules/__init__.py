from abc import abstractmethod, ABCMeta
from typing import Tuple, Union

from app.db.systemconfig_oper import SystemConfigOper
from app.schemas import Notification
from app.schemas.types import SystemConfigKey, MessageChannel


class _ModuleBase(metaclass=ABCMeta):
    """
    Module base class， Implementing the corresponding method， Automatically called when needed， Come (or go) backNone Means that the module is not enabled， Will continue to the next module
    Input parameter consistent with the output parameter， Or no output， Can be re-implemented by multiple modules
    """

    @abstractmethod
    def init_module(self) -> None:
        """
        Module initialization
        """
        pass

    @abstractmethod
    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        """
        Module switch setting， Returns the switch name and switch value， The switch value isTrue When a value is present, it means that the value is turned on.， Not implementing the method or returningNone Represents switch not in use
        Some modules support turning on more than one at the same time， At this point, the setup item starts with, Segregation， Switching value usein Judgements
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        If the module has services that need to be stopped when shutting down， This method needs to be implemented
        :return: None， This method can be processed by multiple modules simultaneously
        """
        pass


def checkMessage(channel_type: MessageChannel):
    """
    Checking message channels and message types， Not processed if not met
    """

    def decorator(func):
        def wrapper(self, message: Notification, *args, **kwargs):
            #  Check the message channel
            if message.channel and message.channel != channel_type:
                return None
            else:
                #  Check message type switch
                if message.mtype:
                    switchs = SystemConfigOper().get(SystemConfigKey.NotificationChannels) or []
                    for switch in switchs:
                        if switch.get("mtype") == message.mtype.value:
                            if channel_type == MessageChannel.Wechat and not switch.get("wechat"):
                                return None
                            if channel_type == MessageChannel.Telegram and not switch.get("telegram"):
                                return None
                            if channel_type == MessageChannel.Slack and not switch.get("slack"):
                                return None
                            if channel_type == MessageChannel.SynologyChat and not switch.get("synologychat"):
                                return None
                return func(self, message, *args, **kwargs)

        return wrapper

    return decorator
