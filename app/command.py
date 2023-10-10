import traceback
from threading import Thread, Event
from typing import Any, Union, Dict

from app.chain import ChainBase
from app.chain.download import DownloadChain
from app.chain.site import SiteChain
from app.chain.subscribe import SubscribeChain
from app.chain.system import SystemChain
from app.chain.transfer import TransferChain
from app.core.event import Event as ManagerEvent
from app.core.event import eventmanager, EventManager
from app.core.plugin import PluginManager
from app.db import SessionFactory
from app.log import logger
from app.scheduler import Scheduler
from app.schemas import Notification
from app.schemas.types import EventType, MessageChannel
from app.utils.object import ObjectUtils
from app.utils.singleton import Singleton
from app.utils.system import SystemUtils


class CommandChian(ChainBase):
    """
    Plug-in processing chain
    """

    def process(self, *args, **kwargs):
        pass


class Command(metaclass=Singleton):
    """
    Global command management， Consumer incident
    """
    #  Built-in command
    _commands = {}

    #  Logout event
    _event = Event()

    def __init__(self):
        #  Database connection
        self._db = SessionFactory()
        #  Event manager
        self.eventmanager = EventManager()
        #  Plug-in manager
        self.pluginmanager = PluginManager()
        #  Process chain
        self.chain = CommandChian(self._db)
        #  Scheduled service management
        self.scheduler = Scheduler()
        #  Built-in command
        self._commands = {
            "/cookiecloud": {
                "id": "cookiecloud",
                "type": "scheduler",
                "description": " Synchronization site",
                "category": " Website"
            },
            "/sites": {
                "func": SiteChain(self._db).remote_list,
                "description": " Search site",
                "category": " Website",
                "data": {}
            },
            "/site_cookie": {
                "func": SiteChain(self._db).remote_cookie,
                "description": " Updating the siteCookie",
                "data": {}
            },
            "/site_enable": {
                "func": SiteChain(self._db).remote_enable,
                "description": " Enabling site",
                "data": {}
            },
            "/site_disable": {
                "func": SiteChain(self._db).remote_disable,
                "description": " Disable site",
                "data": {}
            },
            "/mediaserver_sync": {
                "id": "mediaserver_sync",
                "type": "scheduler",
                "description": " Synchronous media server",
                "category": " Managerial"
            },
            "/subscribes": {
                "func": SubscribeChain(self._db).remote_list,
                "description": " Inquiry subscription",
                "category": " Subscribe to",
                "data": {}
            },
            "/subscribe_refresh": {
                "id": "subscribe_refresh",
                "type": "scheduler",
                "description": " Refresh subscription",
                "category": " Subscribe to"
            },
            "/subscribe_search": {
                "id": "subscribe_search",
                "type": "scheduler",
                "description": " Search subscriptions",
                "category": " Subscribe to"
            },
            "/subscribe_delete": {
                "func": SubscribeChain(self._db).remote_delete,
                "description": " Delete subscription",
                "data": {}
            },
            "/subscribe_tmdb": {
                "id": "subscribe_tmdb",
                "type": "scheduler",
                "description": " Subscribe to metadata updates"
            },
            "/downloading": {
                "func": DownloadChain(self._db).remote_downloading,
                "description": " Downloading",
                "category": " Managerial",
                "data": {}
            },
            "/transfer": {
                "id": "transfer",
                "type": "scheduler",
                "description": " Download file organization",
                "category": " Managerial"
            },
            "/redo": {
                "func": TransferChain(self._db).remote_transfer,
                "description": " Manual collation",
                "data": {}
            },
            "/clear_cache": {
                "func": SystemChain(self._db).remote_clear_cache,
                "description": " Clearing the cache",
                "category": " Managerial",
                "data": {}
            },
            "/restart": {
                "func": SystemUtils.restart,
                "description": " Reboot",
                "category": " Managerial",
                "data": {}
            }
        }
        #  Aggregate plug-in commands
        plugin_commands = self.pluginmanager.get_plugin_commands()
        for command in plugin_commands:
            self.register(
                cmd=command.get('cmd'),
                func=Command.send_plugin_event,
                desc=command.get('desc'),
                category=command.get('category'),
                data={
                    'etype': command.get('event'),
                    'data': command.get('data')
                }
            )
        #  Broadcast registration command menu
        self.chain.register_commands(commands=self.get_commands())
        #  Message processing thread
        self._thread = Thread(target=self.__run)
        #  Starting an event processing thread
        self._thread.start()

    def __run(self):
        """
        Event processing thread
        """
        while not self._event.is_set():
            event, handlers = self.eventmanager.get_event()
            if event:
                logger.info(f" Handling of incidents：{event.event_type} - {handlers}")
                for handler in handlers:
                    try:
                        names = handler.__qualname__.split(".")
                        if names[0] == "Command":
                            self.command_event(event)
                        else:
                            self.pluginmanager.run_plugin_method(names[0], names[1], event)
                    except Exception as e:
                        logger.error(f" Event handling error：{str(e)} - {traceback.format_exc()}")

    def __run_command(self, command: Dict[str, any],
                      data_str: str = "",
                      channel: MessageChannel = None, userid: Union[str, int] = None):
        """
        Running the timing service
        """
        if command.get("type") == "scheduler":
            #  Time service
            if userid:
                self.chain.post_message(
                    Notification(
                        channel=channel,
                        title=f" Commence {command.get('description')} ...",
                        userid=userid
                    )
                )

            #  Perform timed tasks
            self.scheduler.start(job_id=command.get("id"))

            if userid:
                self.chain.post_message(
                    Notification(
                        channel=channel,
                        title=f"{command.get('description')}  Implementation completed",
                        userid=userid
                    )
                )
        else:
            #  Command
            cmd_data = command['data'] if command.get('data') else {}
            args_num = ObjectUtils.arguments(command['func'])
            if args_num > 0:
                if cmd_data:
                    #  Use the built-in parameters directly if they are available
                    data = cmd_data.get("data") or {}
                    data['channel'] = channel
                    data['user'] = userid
                    cmd_data['data'] = data
                    command['func'](**cmd_data)
                elif args_num == 2:
                    #  No input parameters， Enter only channels and usersID
                    command['func'](channel, userid)
                elif args_num > 2:
                    #  Multiple input parameters： User input、 SubscribersID
                    command['func'](data_str, channel, userid)
            else:
                #  No parameters
                command['func']()

    def stop(self):
        """
        停止Event processing thread
        """
        self._event.set()
        self._thread.join()
        if self._db:
            self._db.close()

    def get_commands(self):
        """
        Getting a list of commands
        """
        return self._commands

    def register(self, cmd: str, func: Any, data: dict = None,
                 desc: str = None, category: str = None) -> None:
        """
        Registration command
        """
        self._commands[cmd] = {
            "func": func,
            "description": desc,
            "category": category,
            "data": data or {}
        }

    def get(self, cmd: str) -> Any:
        """
        Get command
        """
        return self._commands.get(cmd, {})

    def execute(self, cmd: str, data_str: str = "",
                channel: MessageChannel = None, userid: Union[str, int] = None) -> None:
        """
        Execute a command
        """
        command = self.get(cmd)
        if command:
            try:
                if userid:
                    logger.info(f" Subscribers {userid}  Commence：{command.get('description')} ...")
                else:
                    logger.info(f" Commence：{command.get('description')} ...")

                # Execute a command
                self.__run_command(command, data_str=data_str,
                                   channel=channel, userid=userid)

                if userid:
                    logger.info(f" Subscribers {userid} {command.get('description')}  Implementation completed")
                else:
                    logger.info(f"{command.get('description')}  Implementation completed")
            except Exception as err:
                logger.error(f"Execute a command {cmd} 出错：{str(err)}")
                traceback.print_exc()

    @staticmethod
    def send_plugin_event(etype: EventType, data: dict) -> None:
        """
        Send plugin command
        """
        EventManager().send_event(etype, data)

    @eventmanager.register(EventType.CommandExcute)
    def command_event(self, event: ManagerEvent) -> None:
        """
        Registration command执行事件
        event_data: {
            "cmd": "/xxx args"
        }
        """
        #  Command参数
        event_str = event.event_data.get('cmd')
        #  News channel
        event_channel = event.event_data.get('channel')
        #  Message user
        event_user = event.event_data.get('user')
        if event_str:
            cmd = event_str.split()[0]
            args = " ".join(event_str.split()[1:])
            if self.get(cmd):
                self.execute(cmd, args, event_channel, event_user)
