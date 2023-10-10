import json
from typing import Optional, Union, List, Tuple, Any, Dict

from app.core.context import MediaInfo, Context
from app.core.config import settings
from app.log import logger
from app.modules import _ModuleBase, checkMessage
from app.modules.telegram.telegram import Telegram
from app.schemas import MessageChannel, CommingMessage, Notification


class TelegramModule(_ModuleBase):
    telegram: Telegram = None

    def init_module(self) -> None:
        self.telegram = Telegram()

    def stop(self):
        self.telegram.stop()

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "MESSAGER", "telegram"

    def message_parser(self, body: Any, form: Any,
                       args: Any) -> Optional[CommingMessage]:
        """
        Parsing message content， Return to dictionary， Note the following convention values：
        userid:  SubscribersID
        username:  User id
        text:  Element
        :param body:  Requestor
        :param form:  Form (document)
        :param args:  Parameters
        :return:  (fig.) channel、 Message body
        """
        """
            {
                'update_id': ,
                'message': {
                    'message_id': ,
                    'from': {
                        'id': ,
                        'is_bot': False,
                        'first_name': '',
                        'username': '',
                        'language_code': 'zh-hans'
                    },
                    'chat': {
                        'id': ,
                        'first_name': '',
                        'username': '',
                        'type': 'private'
                    },
                    'date': ,
                    'text': ''
                }
            }
        """
        #  Calibrationtoken
        token = args.get("token")
        if not token or token != settings.API_TOKEN:
            return None
        try:
            message: dict = json.loads(body)
        except Exception as err:
            logger.debug(f" AnalyzeTelegram Message failure：{err}")
            return None
        if message:
            text = message.get("text")
            user_id = message.get("from", {}).get("id")
            #  Get user name
            user_name = message.get("from", {}).get("username")
            if text:
                logger.info(f" ReceivedTelegram Messages：userid={user_id}, username={user_name}, text={text}")
                #  Checking permissions
                if text.startswith("/"):
                    if settings.TELEGRAM_ADMINS \
                            and str(user_id) not in settings.TELEGRAM_ADMINS.split(',') \
                            and str(user_id) != settings.TELEGRAM_CHAT_ID:
                        self.telegram.send_msg(title=" Only administrators have permission to execute this command", userid=user_id)
                        return None
                else:
                    if settings.TELEGRAM_USERS \
                            and not str(user_id) in settings.TELEGRAM_USERS.split(','):
                        logger.info(f" Subscribers{user_id} Not in the user whitelist， Unable to use this robot")
                        self.telegram.send_msg(title=" You're not on the user whitelist.， Unable to use this robot", userid=user_id)
                        return None
                return CommingMessage(channel=MessageChannel.Telegram,
                                      userid=user_id, username=user_name, text=text)
        return None

    @checkMessage(MessageChannel.Telegram)
    def post_message(self, message: Notification) -> None:
        """
        Send a message
        :param message:  Message body
        :return:  Success or failure
        """
        self.telegram.send_msg(title=message.title, text=message.text,
                               image=message.image, userid=message.userid)

    @checkMessage(MessageChannel.Telegram)
    def post_medias_message(self, message: Notification, medias: List[MediaInfo]) -> Optional[bool]:
        """
        Send media message selection list
        :param message:  Message body
        :param medias:  Media list
        :return:  Success or failure
        """
        return self.telegram.send_meidas_msg(title=message.title, medias=medias,
                                             userid=message.userid)

    @checkMessage(MessageChannel.Telegram)
    def post_torrents_message(self, message: Notification, torrents: List[Context]) -> Optional[bool]:
        """
        Send seed message selection list
        :param message:  Message body
        :param torrents:  Seed list
        :return:  Success or failure
        """
        return self.telegram.send_torrents_msg(title=message.title, torrents=torrents, userid=message.userid)

    def register_commands(self, commands: Dict[str, dict]):
        """
        Registration command， Implement this function to receive the menu of commands available to the system
        :param commands:  Command dictionary
        """
        self.telegram.register_commands(commands)
