import re
import threading
from pathlib import Path
from threading import Event
from typing import Optional, List, Dict

import telebot
from telebot import apihelper
from telebot.types import InputFile

from app.core.config import settings
from app.core.context import MediaInfo, Context
from app.core.metainfo import MetaInfo
from app.log import logger
from app.utils.http import RequestUtils
from app.utils.singleton import Singleton
from app.utils.string import StringUtils

apihelper.proxy = settings.PROXY


class Telegram(metaclass=Singleton):
    _ds_url = f"http://127.0.0.1:{settings.PORT}/api/v1/message?token={settings.API_TOKEN}"
    _event = Event()
    _bot: telebot.TeleBot = None

    def __init__(self):
        """
        Initialization parameters
        """
        # Token
        self._telegram_token = settings.TELEGRAM_TOKEN
        # Chat Id
        self._telegram_chat_id = settings.TELEGRAM_CHAT_ID
        #  Initializing the robot
        if self._telegram_token and self._telegram_chat_id:
            # bot
            _bot = telebot.TeleBot(self._telegram_token, parse_mode="Markdown")
            #  Record handle
            self._bot = _bot

            @_bot.message_handler(commands=['start', 'help'])
            def send_welcome(message):
                _bot.reply_to(message, " Hint： Send the name directly or` Subscribe to`+ Name (of a thing)， Search or subscribe to movies、 Dramas")

            @_bot.message_handler(func=lambda message: True)
            def echo_all(message):
                RequestUtils(timeout=5).post_res(self._ds_url, json=message.json)

            def run_polling():
                """
                Define threaded functions to run infinity_polling
                """
                try:
                    _bot.infinity_polling(long_polling_timeout=30, logger_level=None)
                except Exception as err:
                    logger.error(f"Telegram Message receiving service exception：{err}")

            #  Start a thread to run infinity_polling
            self._polling_thread = threading.Thread(target=run_polling)
            self._polling_thread.start()
            logger.info("Telegram Message acceptance service startup")

    def send_msg(self, title: str, text: str = "", image: str = "", userid: str = "") -> Optional[bool]:
        """
        DispatchTelegram Messages
        :param title:  Message title
        :param text:  Message
        :param image:  Message image address
        :param userid:  SubscribersID， If so, send a message to that user only
        :userid:  The target user to whom the message is sentID， If empty, send to administrator
        """
        if not self._telegram_token or not self._telegram_chat_id:
            return None

        if not title and not text:
            logger.warn(" Title and content cannot be empty at the same time")
            return False

        try:
            if text:
                caption = f"*{title}*\n{text}"
            else:
                caption = f"*{title}*"

            if userid:
                chat_id = userid
            else:
                chat_id = self._telegram_chat_id

            return self.__send_request(userid=chat_id, image=image, caption=caption)

        except Exception as msg_e:
            logger.error(f" Failed to send message：{msg_e}")
            return False

    def send_meidas_msg(self, medias: List[MediaInfo], userid: str = "", title: str = "") -> Optional[bool]:
        """
        Send media list message
        """
        if not self._telegram_token or not self._telegram_chat_id:
            return None

        try:
            index, image, caption = 1, "", "*%s*" % title
            for media in medias:
                if not image:
                    image = media.get_message_image()
                if media.vote_average:
                    caption = "%s\n%s. [%s](%s)\n_%s，%s_" % (caption,
                                                             index,
                                                             media.title_year,
                                                             media.detail_link,
                                                             f" Typology：{media.type.value}",
                                                             f" Score (of student's work)：{media.vote_average}")
                else:
                    caption = "%s\n%s. [%s](%s)\n_%s_" % (caption,
                                                          index,
                                                          media.title_year,
                                                          media.detail_link,
                                                          f" Typology：{media.type.value}")
                index += 1

            if userid:
                chat_id = userid
            else:
                chat_id = self._telegram_chat_id

            return self.__send_request(userid=chat_id, image=image, caption=caption)

        except Exception as msg_e:
            logger.error(f" Failed to send message：{msg_e}")
            return False

    def send_torrents_msg(self, torrents: List[Context],
                          userid: str = "", title: str = "") -> Optional[bool]:
        """
        Send a list message
        """
        if not self._telegram_token or not self._telegram_chat_id:
            return None

        if not torrents:
            return False

        try:
            index, caption = 1, "*%s*" % title
            mediainfo = torrents[0].media_info
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
                caption = f"{caption}\n{index}.【{site_name}】[{title}]({link}) " \
                          f"{StringUtils.str_filesize(torrent.size)} {free} {seeder}"
                index += 1

            if userid:
                chat_id = userid
            else:
                chat_id = self._telegram_chat_id

            return self.__send_request(userid=chat_id, caption=caption,
                                       image=mediainfo.get_message_image())

        except Exception as msg_e:
            logger.error(f" Failed to send message：{msg_e}")
            return False

    def __send_request(self, userid: str = None, image="", caption="") -> bool:
        """
        TowardTelegram Sending message
        """

        if image:
            req = RequestUtils(proxies=settings.PROXY).get_res(image)
            if req and req.content:
                image_file = Path(settings.TEMP_PATH) / Path(image).name
                image_file.write_bytes(req.content)
                photo = InputFile(image_file)
                ret = self._bot.send_photo(chat_id=userid or self._telegram_chat_id,
                                           photo=photo,
                                           caption=caption,
                                           parse_mode="Markdown")
                if ret:
                    return True
        ret = self._bot.send_message(chat_id=userid or self._telegram_chat_id,
                                     text=caption,
                                     parse_mode="Markdown")

        return True if ret else False

    def register_commands(self, commands: Dict[str, dict]):
        """
        Registration menu commands
        """
        if not self._bot:
            return
        #  Set upbot Command
        if commands:
            self._bot.delete_my_commands()
            self._bot.set_my_commands(
                commands=[
                    telebot.types.BotCommand(cmd[1:], str(desc.get("description"))) for cmd, desc in
                    commands.items()
                ]
            )

    def stop(self):
        """
        CessationTelegram Message acceptance service
        """
        if self._bot:
            self._bot.stop_polling()
            self._polling_thread.join()
            logger.info("Telegram The message receiving service has been discontinued")
