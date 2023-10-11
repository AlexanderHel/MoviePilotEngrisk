from typing import Optional, Union, List, Tuple, Any

from app.core.context import MediaInfo, Context
from app.log import logger
from app.modules import _ModuleBase, checkMessage
from app.modules.synologychat.synologychat import SynologyChat
from app.schemas import MessageChannel, CommingMessage, Notification


class SynologyChatModule(_ModuleBase):
    synologychat: SynologyChat = None

    def init_module(self) -> None:
        self.synologychat = SynologyChat()

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "MESSAGER", "synologychat"

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
        try:
            message: dict = form
            if not message:
                return None
            #  Calibrationtoken
            token = message.get("token")
            if not token or not self.synologychat.check_token(token):
                return None
            #  Copies
            text = message.get("text")
            #  SubscribersID
            user_id = int(message.get("user_id"))
            #  Get user name
            user_name = message.get("username")
            if text and user_id:
                logger.info(f" ReceivedSynologyChat Messages：userid={user_id}, username={user_name}, text={text}")
                return CommingMessage(channel=MessageChannel.SynologyChat,
                                      userid=user_id, username=user_name, text=text)
        except Exception as err:
            logger.debug(f" AnalyzeSynologyChat Message failure：{err}")
        return None

    @checkMessage(MessageChannel.SynologyChat)
    def post_message(self, message: Notification) -> None:
        """
        Send a message
        :param message:  Message body
        :return:  Success or failure
        """
        self.synologychat.send_msg(title=message.title, text=message.text,
                                   image=message.image, userid=message.userid)

    @checkMessage(MessageChannel.SynologyChat)
    def post_medias_message(self, message: Notification, medias: List[MediaInfo]) -> Optional[bool]:
        """
        Send media message selection list
        :param message:  Message body
        :param medias:  Media list
        :return:  Success or failure
        """
        return self.synologychat.send_meidas_msg(title=message.title, medias=medias,
                                                 userid=message.userid)

    @checkMessage(MessageChannel.SynologyChat)
    def post_torrents_message(self, message: Notification, torrents: List[Context]) -> Optional[bool]:
        """
        Send seed message selection list
        :param message:  Message body
        :param torrents:  Seed list
        :return:  Success or failure
        """
        return self.synologychat.send_torrents_msg(title=message.title, torrents=torrents, userid=message.userid)
