from apscheduler.schedulers.background import BackgroundScheduler

from app.chain.download import DownloadChain
from app.chain.media import MediaChain
from app.core.config import settings
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple, Optional, Union
from app.log import logger
from app.schemas import NotificationType, TransferTorrent, DownloadingTorrent
from app.schemas.types import TorrentStatus, MessageChannel
from app.utils.string import StringUtils


class DownloadingMsg(_PluginBase):
    #  Plug-in name
    plugin_name = " Download progress push"
    #  Plugin description
    plugin_desc = " Push the progress of ongoing downloads at regular intervals。"
    #  Plug-in icons
    plugin_icon = "downloadmsg.png"
    #  Theme color
    plugin_color = "#3DE75D"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "thsrite"
    #  Author's homepage
    author_url = "https://github.com/thsrite"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "downloading_"
    #  Loading sequence
    plugin_order = 22
    #  Available user levels
    auth_level = 2

    #  Private property
    _enabled = False
    #  Task execution interval
    _seconds = None
    _type = None
    _adminuser = None
    _downloadhis = None

    #  Timers
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        #  Discontinuation of existing mandates
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._seconds = config.get("seconds") or 300
            self._type = config.get("type") or 'admin'
            self._adminuser = config.get("adminuser")

            #  Load modules
        if self._enabled:
            self._downloadhis = DownloadHistoryOper(self.db)
            #  Time service
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._seconds:
                try:
                    self._scheduler.add_job(func=self.__downloading,
                                            trigger='interval',
                                            seconds=int(self._seconds),
                                            name=" Download progress push")
                except Exception as err:
                    logger.error(f" Timed task configuration error：{err}")

            #  Initiate tasks
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __downloading(self):
        """
        Push the progress of ongoing downloads at regular intervals
        """
        #  Downloading seeds now.
        torrents = DownloadChain(self.db).list_torrents(status=TorrentStatus.DOWNLOADING)
        if not torrents:
            logger.info(" There are currently no tasks being downloaded！")
            return
            #  Push user
        if self._type == "admin" or self._type == "both":
            if not self._adminuser:
                logger.error(" No administrator user configured")
                return

            for userid in str(self._adminuser).split(","):
                self.__send_msg(torrents=torrents, userid=userid)

        if self._type == "user" or self._type == "both":
            user_torrents = {}
            #  Based on the seeds being downloadedhash Get download history
            for torrent in torrents:
                downloadhis = self._downloadhis.get_by_hash(download_hash=torrent.hash)
                if not downloadhis:
                    logger.warn(f" Torrent {torrent.hash}  Not availableMoviePilot Download history， Unable to push download progress")
                    continue
                if not downloadhis.userid:
                    logger.debug(f" Torrent {torrent.hash}  Downloaded user records not captured， Unable to push download progress")
                    continue
                user_torrent = user_torrents.get(downloadhis.userid) or []
                user_torrent.append(torrent)
                user_torrents[downloadhis.userid] = user_torrent

            if not user_torrents or not user_torrents.keys():
                logger.warn(" User download history not captured， Unable to push download progress")
                return

            #  Push user下载任务进度
            for userid in list(user_torrents.keys()):
                if not userid:
                    continue
                #  If the user is an administrator， No need for repeat pushes
                if self._type == "admin" or self._type == "both" and self._adminuser and userid in str(
                        self._adminuser).split(","):
                    logger.debug(" Administrator has pushed")
                    continue

                user_torrent = user_torrents.get(userid)
                if not user_torrent:
                    logger.warn(f" No users acquired {userid}  Download tasks")
                    continue
                self.__send_msg(torrents=user_torrent,
                                userid=userid)

        if self._type == "all":
            self.__send_msg(torrents=torrents)

    def __send_msg(self, torrents: Optional[List[Union[TransferTorrent, DownloadingTorrent]]], userid: str = None):
        """
        Send a message
        """
        title = f" Common {len(torrents)}  Tasks are being downloaded.："
        messages = []
        index = 1
        channel_value = None
        for torrent in torrents:
            year = None
            name = None
            se = None
            ep = None
            #  Check the download history first， No further identification
            downloadhis = self._downloadhis.get_by_hash(download_hash=torrent.hash)
            if downloadhis:
                name = downloadhis.title
                year = downloadhis.year
                se = downloadhis.seasons
                ep = downloadhis.episodes
                if not channel_value:
                    channel_value = downloadhis.channel
            else:
                try:
                    context = MediaChain(self.db).recognize_by_title(title=torrent.title)
                    if not context or not context.media_info:
                        continue
                    media_info = context.media_info
                    year = media_info.year
                    name = media_info.title
                    if media_info.number_of_seasons:
                        se = f"S{str(media_info.number_of_seasons).rjust(2, '0')}"
                    if media_info.number_of_episodes:
                        ep = f"E{str(media_info.number_of_episodes).rjust(2, '0')}"
                except Exception as e:
                    print(str(e))

            #  Assembled title
            if year:
                media_name = "%s (%s) %s%s" % (name, year, se, ep)
            elif name:
                media_name = "%s %s%s" % (name, se, ep)
            else:
                media_name = torrent.title

            messages.append(f"{index}. {media_name}\n"
                            f"{torrent.title} "
                            f"{StringUtils.str_filesize(torrent.size)} "
                            f"{round(torrent.progress, 1)}%")
            index += 1

        #  User messaging channels
        if channel_value:
            channel = next(
                (channel for channel in MessageChannel.__members__.values() if channel.value == channel_value), None)
        else:
            channel = None
        self.post_message(mtype=NotificationType.Download,
                          channel=channel,
                          title=title,
                          text="\n".join(messages),
                          userid=userid)

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
                                           'cols': 12
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
                                           'cols': 12,
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'seconds',
                                                   'label': ' Execution interval',
                                                   'placeholder': ' Work unit (one's workplace)（ Unit of angle or arc equivalent one sixtieth of a degree）'
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'adminuser',
                                                   'label': ' Administrator',
                                                   'placeholder': ' Multi-user, Demerger'
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VSelect',
                                               'props': {
                                                   'model': 'type',
                                                   'label': ' Push type',
                                                   'items': [
                                                       {'title': ' Janitors', 'value': 'admin'},
                                                       {'title': ' Download users', 'value': 'user'},
                                                       {'title': ' Administrators and download users', 'value': 'both'},
                                                       {'title': ' All users', 'value': 'all'}
                                                   ]
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
                   "seconds": 300,
                   "adminuser": "",
                   "type": "admin"
               }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        Exit plugin
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("Exit plugin失败：%s" % str(e))
