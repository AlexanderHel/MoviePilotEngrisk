import json
import re
from typing import Optional, Union, List, Tuple, Any

from app.core.context import MediaInfo, Context
from app.core.config import settings
from app.log import logger
from app.modules import _ModuleBase, checkMessage
from app.modules.slack.slack import Slack
from app.schemas import MessageChannel, CommingMessage, Notification


class SlackModule(_ModuleBase):
    slack: Slack = None

    def init_module(self) -> None:
        self.slack = Slack()

    def stop(self):
        self.slack.stop()

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "MESSAGER", "slack"

    @staticmethod
    def message_parser(body: Any, form: Any,
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
        #  Messages
        {
            'client_msg_id': '',
            'type': 'message',
            'text': 'hello',
            'user': '',
            'ts': '1670143568.444289',
            'blocks': [{
                'type': 'rich_text',
                'block_id': 'i2j+',
                'elements': [{
                    'type': 'rich_text_section',
                    'elements': [{
                        'type': 'text',
                        'text': 'hello'
                    }]
                }]
            }],
            'team': '',
            'client': '',
            'event_ts': '1670143568.444289',
            'channel_type': 'im'
        }
        #  Command
        {
          "token": "",
          "team_id": "",
          "team_domain": "",
          "channel_id": "",
          "channel_name": "directmessage",
          "user_id": "",
          "user_name": "",
          "command": "/subscribes",
          "text": "",
          "api_app_id": "",
          "is_enterprise_install": "false",
          "response_url": "",
          "trigger_id": ""
        }
        #  (computer) shortcut
        {
          "type": "shortcut",
          "token": "XXXXXXXXXXXXX",
          "action_ts": "1581106241.371594",
          "team": {
            "id": "TXXXXXXXX",
            "domain": "shortcuts-test"
          },
          "user": {
            "id": "UXXXXXXXXX",
            "username": "aman",
            "team_id": "TXXXXXXXX"
          },
          "callback_id": "shortcut_create_task",
          "trigger_id": "944799105734.773906753841.38b5894552bdd4a780554ee59d1f3638"
        }
        #  Button click
        {
          "type": "block_actions",
          "team": {
            "id": "T9TK3CUKW",
            "domain": "example"
          },
          "user": {
            "id": "UA8RXUSPL",
            "username": "jtorrance",
            "team_id": "T9TK3CUKW"
          },
          "api_app_id": "AABA1ABCD",
          "token": "9s8d9as89d8as9d8as989",
          "container": {
            "type": "message_attachment",
            "message_ts": "1548261231.000200",
            "attachment_id": 1,
            "channel_id": "CBR2V3XEX",
            "is_ephemeral": false,
            "is_app_unfurl": false
          },
          "trigger_id": "12321423423.333649436676.d8c1bb837935619ccad0f624c448ffb3",
          "client": {
            "id": "CBR2V3XEX",
            "name": "review-updates"
          },
          "message": {
            "bot_id": "BAH5CA16Z",
            "type": "message",
            "text": "This content can't be displayed.",
            "user": "UAJ2RU415",
            "ts": "1548261231.000200",
            ...
          },
          "response_url": "https://hooks.slack.com/actions/AABA1ABCD/1232321423432/D09sSasdasdAS9091209",
          "actions": [
            {
              "action_id": "WaXA",
              "block_id": "=qXel",
              "text": {
                "type": "plain_text",
                "text": "View",
                "emoji": true
              },
              "value": "click_me_123",
              "type": "button",
              "action_ts": "1548426417.840180"
            }
          ]
        }
        """
        #  Calibrationtoken
        token = args.get("token")
        if not token or token != settings.API_TOKEN:
            return None
        try:
            msg_json: dict = json.loads(body)
        except Exception as err:
            logger.debug(f" AnalyzeSlack Message failure：{err}")
            return None
        if msg_json:
            if msg_json.get("type") == "message":
                userid = msg_json.get("user")
                text = msg_json.get("text")
                username = msg_json.get("user")
            elif msg_json.get("type") == "block_actions":
                userid = msg_json.get("user", {}).get("id")
                text = msg_json.get("actions")[0].get("value")
                username = msg_json.get("user", {}).get("name")
            elif msg_json.get("type") == "event_callback":
                userid = msg_json.get('event', {}).get('user')
                text = re.sub(r"<@[0-9A-Z]+>", "", msg_json.get("event", {}).get("text"), flags=re.IGNORECASE).strip()
                username = ""
            elif msg_json.get("type") == "shortcut":
                userid = msg_json.get("user", {}).get("id")
                text = msg_json.get("callback_id")
                username = msg_json.get("user", {}).get("username")
            elif msg_json.get("command"):
                userid = msg_json.get("user_id")
                text = msg_json.get("command")
                username = msg_json.get("user_name")
            else:
                return None
            logger.info(f" ReceivedSlack Messages：userid={userid}, username={username}, text={text}")
            return CommingMessage(channel=MessageChannel.Slack,
                                  userid=userid, username=username, text=text)
        return None

    @checkMessage(MessageChannel.Slack)
    def post_message(self, message: Notification) -> None:
        """
        Send a message
        :param message:  Messages
        :return:  Success or failure
        """
        self.slack.send_msg(title=message.title, text=message.text,
                            image=message.image, userid=message.userid)

    @checkMessage(MessageChannel.Slack)
    def post_medias_message(self, message: Notification, medias: List[MediaInfo]) -> Optional[bool]:
        """
        Send media message selection list
        :param message:  Messages体
        :param medias:  Media information
        :return:  Success or failure
        """
        return self.slack.send_meidas_msg(title=message.title, medias=medias, userid=message.userid)

    @checkMessage(MessageChannel.Slack)
    def post_torrents_message(self, message: Notification, torrents: List[Context]) -> Optional[bool]:
        """
        Send seed message selection list
        :param message:  Messages体
        :param torrents:  Seed information
        :return:  Success or failure
        """
        return self.slack.send_torrents_msg(title=message.title, torrents=torrents,
                                            userid=message.userid)
