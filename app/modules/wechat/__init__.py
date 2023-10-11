import xml.dom.minidom
from typing import Optional, Union, List, Tuple, Any, Dict

from app.core.config import settings
from app.core.context import Context, MediaInfo
from app.log import logger
from app.modules import _ModuleBase, checkMessage
from app.modules.wechat.WXBizMsgCrypt3 import WXBizMsgCrypt
from app.modules.wechat.wechat import WeChat
from app.schemas import MessageChannel, CommingMessage, Notification
from app.utils.dom import DomUtils


class WechatModule(_ModuleBase):
    wechat: WeChat = None

    def init_module(self) -> None:
        self.wechat = WeChat()

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "MESSAGER", "wechat"

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
            # URL Parameters
            sVerifyMsgSig = args.get("msg_signature")
            sVerifyTimeStamp = args.get("timestamp")
            sVerifyNonce = args.get("nonce")
            if not sVerifyMsgSig or not sVerifyTimeStamp or not sVerifyNonce:
                logger.debug(f" Wechat request parameter error：{args}")
                return None
            #  Decryption module
            wxcpt = WXBizMsgCrypt(sToken=settings.WECHAT_TOKEN,
                                  sEncodingAESKey=settings.WECHAT_ENCODING_AESKEY,
                                  sReceiveId=settings.WECHAT_CORPID)
            #  Message data
            if not body:
                logger.debug(f" Wechat request data is empty")
                return None
            logger.debug(f" Received wechat request：{body}")
            ret, sMsg = wxcpt.DecryptMsg(sPostData=body,
                                         sMsgSignature=sVerifyMsgSig,
                                         sTimeStamp=sVerifyTimeStamp,
                                         sNonce=sVerifyNonce)
            if ret != 0:
                logger.error(f" Failure to decrypt wechat messages DecryptMsg ret = {ret}")
                return None
            #  AnalyzeXML Telegram
            """
            1、 Message format：
            <xml>
               <ToUserName><![CDATA[toUser]]></ToUserName>
               <FromUserName><![CDATA[fromUser]]></FromUserName> 
               <CreateTime>1348831860</CreateTime>
               <MsgType><![CDATA[text]]></MsgType>
               <Content><![CDATA[this is a test]]></Content>
               <MsgId>1234567890123456</MsgId>
               <AgentID>1</AgentID>
            </xml>
            2、 Event format：
            <xml>
                <ToUserName><![CDATA[toUser]]></ToUserName>
                <FromUserName><![CDATA[UserID]]></FromUserName>
                <CreateTime>1348831860</CreateTime>
                <MsgType><![CDATA[event]]></MsgType>
                <Event><![CDATA[subscribe]]></Event>
                <AgentID>1</AgentID>
            </xml>            
            """
            dom_tree = xml.dom.minidom.parseString(sMsg.decode('UTF-8'))
            root_node = dom_tree.documentElement
            #  Message type
            msg_type = DomUtils.tag_value(root_node, "MsgType")
            # Event event The event is onlyclick Only then will it work,enter_agent Null
            event = DomUtils.tag_value(root_node, "Event")
            #  SubscribersID
            user_id = DomUtils.tag_value(root_node, "FromUserName")
            #  No message types and usersID The message don't
            if not msg_type or not user_id:
                logger.warn(f" Failure to parse message type and userID")
                return None
            #  Parsing message content
            if msg_type == "event" and event == "click":
                #  Verify that the user has permission to execute interactive commands
                if settings.WECHAT_ADMINS:
                    wechat_admins = settings.WECHAT_ADMINS.split(',')
                    if wechat_admins and not any(
                            user_id == admin_user for admin_user in wechat_admins):
                        self.wechat.send_msg(title=" Users do not have permission to execute menu commands", userid=user_id)
                        return None
                #  According toEventKey Execute a command
                content = DomUtils.tag_value(root_node, "EventKey")
                logger.info(f" Incidents of receipt of microsoft messages：userid={user_id}, event={content}")
            elif msg_type == "text":
                #  Text message
                content = DomUtils.tag_value(root_node, "Content", default="")
                logger.info(f" Received a wechat message：userid={user_id}, text={content}")
            else:
                return None

            if content:
                #  Processing message content
                return CommingMessage(channel=MessageChannel.Wechat,
                                      userid=user_id, username=user_id, text=content)
        except Exception as err:
            logger.error(f" Wechat message processing error occurred：{err}")
        return None

    @checkMessage(MessageChannel.Wechat)
    def post_message(self, message: Notification) -> None:
        """
        Send a message
        :param message:  Message
        :return:  Success or failure
        """
        self.wechat.send_msg(title=message.title, text=message.text,
                             image=message.image, userid=message.userid)

    @checkMessage(MessageChannel.Wechat)
    def post_medias_message(self, message: Notification, medias: List[MediaInfo]) -> Optional[bool]:
        """
        Send media message selection list
        :param message:  Message
        :param medias:  Media list
        :return:  Success or failure
        """
        #  Send the title first
        self.wechat.send_msg(title=message.title, userid=message.userid)
        #  Resend content
        return self.wechat.send_medias_msg(medias=medias, userid=message.userid)

    @checkMessage(MessageChannel.Wechat)
    def post_torrents_message(self, message: Notification, torrents: List[Context]) -> Optional[bool]:
        """
        Send seed message selection list
        :param message:  Message
        :param torrents:  Seed list
        :return:  Success or failure
        """
        return self.wechat.send_torrents_msg(title=message.title, torrents=torrents, userid=message.userid)

    def register_commands(self, commands: Dict[str, dict]):
        """
        Registration command， Implement this function to receive the menu of commands available to the system
        :param commands:  Command dictionary
        """
        self.wechat.create_menus(commands)
