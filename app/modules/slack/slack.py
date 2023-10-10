import re
from threading import Lock
from typing import List, Optional

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

from app.core.config import settings
from app.core.context import MediaInfo, Context
from app.core.metainfo import MetaInfo
from app.log import logger
from app.utils.string import StringUtils


lock = Lock()


class Slack:

    _client: WebClient = None
    _service: SocketModeHandler = None

    _ds_url = f"http://127.0.0.1:{settings.PORT}/api/v1/message?token={settings.API_TOKEN}"

    def __init__(self):

        if not settings.SLACK_OAUTH_TOKEN or not settings.SLACK_APP_TOKEN:
            return
        
        try:
            slack_app = App(token=settings.SLACK_OAUTH_TOKEN,
                            ssl_check_enabled=False,
                            url_verification_enabled=False)
        except Exception as err:
            logger.error(f"Slack Initialization failure: {err}")
            return
        self._client = slack_app.client

        #  Registering a message response
        @slack_app.event("message")
        def slack_message(message):
            local_res = requests.post(self._ds_url, json=message, timeout=10)
            logger.debug("message: %s processed, response is: %s" % (message, local_res.text))

        @slack_app.action(re.compile(r"actionId-\d+"))
        def slack_action(ack, body):
            ack()
            local_res = requests.post(self._ds_url, json=body, timeout=60)
            logger.debug("message: %s processed, response is: %s" % (body, local_res.text))

        @slack_app.event("app_mention")
        def slack_mention(say, body):
            say(f" Received， Please wait.... <@{body.get('event', {}).get('user')}>")
            local_res = requests.post(self._ds_url, json=body, timeout=10)
            logger.debug("message: %s processed, response is: %s" % (body, local_res.text))

        @slack_app.shortcut(re.compile(r"/*"))
        def slack_shortcut(ack, body):
            ack()
            local_res = requests.post(self._ds_url, json=body, timeout=10)
            logger.debug("message: %s processed, response is: %s" % (body, local_res.text))

        @slack_app.command(re.compile(r"/*"))
        def slack_command(ack, body):
            ack()
            local_res = requests.post(self._ds_url, json=body, timeout=10)
            logger.debug("message: %s processed, response is: %s" % (body, local_res.text))

        #  Starting services
        try:
            self._service = SocketModeHandler(
                slack_app,
                settings.SLACK_APP_TOKEN
            )
            self._service.connect()
            logger.info("Slack Message acceptance service startup")
        except Exception as err:
            logger.error("Slack Failed to start the message receiving service: %s" % str(err))

    def stop(self):
        if self._service:
            try:
                self._service.close()
                logger.info("Slack The message receiving service has been discontinued")
            except Exception as err:
                logger.error("Slack Message receiving service stop failure: %s" % str(err))

    def send_msg(self, title: str, text: str = "", image: str = "", url: str = "", userid: str = ""):
        """
        DispatchTelegram Messages
        :param title:  Message title
        :param text:  Message
        :param image:  Message image address
        :param url:  Click on the message spinningURL
        :param userid:  SubscribersID， If so, send a message to that user only
        :user_id:  The target user to whom the message is sentID， If empty, send to administrator
        """
        if not self._client:
            return False, " Message client not ready"
        if not title and not text:
            return False, " Title and content cannot be empty at the same time"
        try:
            if userid:
                channel = userid
            else:
                #  Message broadcasting
                channel = self.__find_public_channel()
            #  Message text
            message_text = ""
            #  Constructor
            blocks = []
            if not image:
                message_text = f"{title}\n{text or ''}"
            else:
                #  Message pictures
                if image:
                    #  Assembly message content
                    blocks.append({"type": "section", "text": {
                        "type": "mrkdwn",
                        "text": f"*{title}*\n{text or ''}"
                    }, 'accessory': {
                        "type": "image",
                        "image_url": f"{image}",
                        "alt_text": f"{title}"
                    }})
                #  Link (on a website)
                if url:
                    blocks.append({
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": " View details",
                                    "emoji": True
                                },
                                "value": "click_me_url",
                                "url": f"{url}",
                                "action_id": "actionId-url"
                            }
                        ]
                    })
            #  Dispatch
            result = self._client.chat_postMessage(
                channel=channel,
                text=message_text[:1000],
                blocks=blocks,
                mrkdwn=True
            )
            return True, result
        except Exception as msg_e:
            logger.error(f"Slack Failed to send message: {msg_e}")
            return False, str(msg_e)

    def send_meidas_msg(self, medias: List[MediaInfo], userid: str = "", title: str = "") -> Optional[bool]:
        """
        Sending list class messages
        """
        if not self._client:
            return False
        if not medias:
            return False
        try:
            if userid:
                channel = userid
            else:
                #  Message broadcasting
                channel = self.__find_public_channel()
            #  Message body
            title_section = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*"
                }
            }
            blocks = [title_section]
            #  Listings
            if medias:
                blocks.append({
                    "type": "divider"
                })
                index = 1
                for media in medias:
                    if media.get_poster_image():
                        if media.vote_star:
                            text = f"{index}. *<{media.detail_link}|{media.title_year}>*" \
                                   f"\n Typology：{media.type.value}" \
                                   f"\n{media.vote_star}" \
                                   f"\n{media.get_overview_string(50)}"
                        else:
                            text = f"{index}. *<{media.detail_link}|{media.title_year}>*" \
                                   f"\n Typology：{media.type.value}" \
                                   f"\n{media.get_overview_string(50)}"
                        blocks.append(
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": text
                                },
                                "accessory": {
                                    "type": "image",
                                    "image_url": f"{media.get_poster_image()}",
                                    "alt_text": f"{media.title_year}"
                                }
                            }
                        )
                        blocks.append(
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": " Option",
                                            "emoji": True
                                        },
                                        "value": f"{index}",
                                        "action_id": f"actionId-{index}"
                                    }
                                ]
                            }
                        )
                        index += 1
            #  Dispatch
            result = self._client.chat_postMessage(
                channel=channel,
                text=title,
                blocks=blocks
            )
            return True if result else False
        except Exception as msg_e:
            logger.error(f"Slack Failed to send message: {msg_e}")
            return False

    def send_torrents_msg(self, torrents: List[Context],
                          userid: str = "", title: str = "") -> Optional[bool]:
        """
        Send a list message
        """
        if not self._client:
            return None

        try:
            if userid:
                channel = userid
            else:
                #  Message broadcasting
                channel = self.__find_public_channel()
            #  Message body
            title_section = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*"
                }
            }
            blocks = [title_section, {
                "type": "divider"
            }]
            #  Listings
            index = 1
            for context in torrents:
                torrent = context.torrent_info
                site_name = torrent.site_name
                meta = MetaInfo(torrent.title, torrent.description)
                link = torrent.page_url
                title = f"{meta.season_episode} " \
                        f"{meta.resource_term} " \
                        f"{meta.video_term} " \
                        f"{meta.release_group}"
                title = re.sub(r"\s+", " ", title).strip()
                free = torrent.volume_factor
                seeder = f"{torrent.seeders}↑"
                description = torrent.description
                text = f"{index}. 【{site_name}】<{link}|{title}> " \
                       f"{StringUtils.str_filesize(torrent.size)} {free} {seeder}\n" \
                       f"{description}"
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text
                        }
                    }
                )
                blocks.append(
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": " Option",
                                    "emoji": True
                                },
                                "value": f"{index}",
                                "action_id": f"actionId-{index}"
                            }
                        ]
                    }
                )
                index += 1
            #  Dispatch
            result = self._client.chat_postMessage(
                channel=channel,
                text=title,
                blocks=blocks
            )
            return True if result else False
        except Exception as msg_e:
            logger.error(f"Slack Failed to send message: {msg_e}")
            return False

    def __find_public_channel(self):
        """
        Find a public channel
        """
        if not self._client:
            return ""
        conversation_id = ""
        try:
            for result in self._client.conversations_list():
                if conversation_id:
                    break
                for channel in result["channels"]:
                    if channel.get("name") == (settings.SLACK_CHANNEL or " Blanket"):
                        conversation_id = channel.get("id")
                        break
        except Exception as e:
            logger.error(f" FindSlack Public channel failure: {e}")
        return conversation_id
