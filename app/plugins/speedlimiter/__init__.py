import ipaddress
from typing import List, Tuple, Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.modules.emby import Emby
from app.modules.jellyfin import Jellyfin
from app.modules.plex import Plex
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.schemas import NotificationType, WebhookEventInfo
from app.schemas.types import EventType
from app.utils.ip import IpUtils


class SpeedLimiter(_PluginBase):
    #  Plug-in name
    plugin_name = " Playback speed limit"
    #  Plugin description
    plugin_desc = " When playing media library videos on the extranet， Automatic speed limiting of downloaders。"
    #  Plug-in icons
    plugin_icon = "SpeedLimiter.jpg"
    #  Theme color
    plugin_color = "#183883"
    #  Plug-in version
    plugin_version = "1.0"
    #  Plug-in authors
    plugin_author = "Shurelol"
    #  Author's homepage
    author_url = "https://github.com/Shurelol"
    #  Plug-in configuration itemsID Prefix (linguistics)
    plugin_config_prefix = "speedlimit_"
    #  Loading sequence
    plugin_order = 11
    #  Available user levels
    auth_level = 1

    #  Private property
    _scheduler = None
    _qb = None
    _tr = None
    _enabled: bool = False
    _notify: bool = False
    _interval: int = 60
    _downloader: list = []
    _play_up_speed: float = 0
    _play_down_speed: float = 0
    _noplay_up_speed: float = 0
    _noplay_down_speed: float = 0
    _bandwidth: float = 0
    _allocation_ratio: str = ""
    _auto_limit: bool = False
    _limit_enabled: bool = False
    #  Unlimited address
    _unlimited_ips = {}
    #  Current speed limit status
    _current_state = ""

    def init_plugin(self, config: dict = None):
        #  Read configuration
        if config:
            self._enabled = config.get("enabled")
            self._notify = config.get("notify")
            self._play_up_speed = float(config.get("play_up_speed")) if config.get("play_up_speed") else 0
            self._play_down_speed = float(config.get("play_down_speed")) if config.get("play_down_speed") else 0
            self._noplay_up_speed = float(config.get("noplay_up_speed")) if config.get("noplay_up_speed") else 0
            self._noplay_down_speed = float(config.get("noplay_down_speed")) if config.get("noplay_down_speed") else 0
            self._current_state = f"U:{self._noplay_up_speed},D:{self._noplay_down_speed}"
            try:
                #  Total bandwidth
                self._bandwidth = int(float(config.get("bandwidth") or 0)) * 1000000
                #  Automatic speed limit switch
                if self._bandwidth > 0:
                    self._auto_limit = True
                else:
                    self._auto_limit = False
            except Exception as e:
                logger.error(f" Intelligent speed limit uplink bandwidth setting error：{str(e)}")
                self._bandwidth = 0

            #  Speed limit service switch
            self._limit_enabled = True if (self._play_up_speed
                                           or self._play_down_speed
                                           or self._auto_limit) else False
            self._allocation_ratio = config.get("allocation_ratio") or ""
            #  Unlimited address
            self._unlimited_ips["ipv4"] = config.get("ipv4") or ""
            self._unlimited_ips["ipv6"] = config.get("ipv6") or ""

            self._downloader = config.get("downloader") or []
            if self._downloader:
                if 'qbittorrent' in self._downloader:
                    self._qb = Qbittorrent()
                if 'transmission' in self._downloader:
                    self._tr = Transmission()

        #  There's a mission on the horizon.
        self.stop_service()

        #  Starting a speed limit task
        if self._enabled and self._limit_enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(func=self.check_playing_sessions,
                                    trigger='interval',
                                    seconds=self._interval,
                                    name=" Playback speed limit check")
            self._scheduler.print_jobs()
            self._scheduler.start()
            logger.info(" Playback speed limit checking service starts")

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
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
                                            'model': 'notify',
                                            'label': ' Send notification',
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
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'downloader',
                                            'label': ' Downloader',
                                            'items': [
                                                {'title': 'Qbittorrent', 'value': 'qbittorrent'},
                                                {'title': 'Transmission', 'value': 'transmission'},
                                            ]
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
                                            'model': 'play_up_speed',
                                            'label': ' Playback speed limit（ Upload）',
                                            'placeholder': 'KB/s'
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
                                            'model': 'play_down_speed',
                                            'label': ' Playback speed limit（ Downloading）',
                                            'placeholder': 'KB/s'
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
                                            'model': 'noplay_up_speed',
                                            'label': ' Unplayed speed limit（ Upload）',
                                            'placeholder': 'KB/s'
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
                                            'model': 'noplay_down_speed',
                                            'label': ' Unplayed speed limit（ Downloading）',
                                            'placeholder': 'KB/s'
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
                                            'model': 'bandwidth',
                                            'label': ' Intelligent uplink bandwidth limiting',
                                            'placeholder': 'Mbps'
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'allocation_ratio',
                                            'label': ' Intelligent speed limit allocation ratio',
                                            'items': [
                                                {'title': ' On average', 'value': ''},
                                                {'title': '1：9', 'value': '1:9'},
                                                {'title': '2：8', 'value': '2:8'},
                                                {'title': '3：7', 'value': '3:7'},
                                                {'title': '4：6', 'value': '4:6'},
                                                {'title': '6：4', 'value': '6:4'},
                                                {'title': '7：3', 'value': '7:3'},
                                                {'title': '8：2', 'value': '8:2'},
                                                {'title': '9：1', 'value': '9:1'},
                                            ]
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
                                            'model': 'ipv4',
                                            'label': ' Unlimited address range（ipv4）',
                                            'placeholder': ' Leave the default unlimited speed intranet emptyipv4'
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
                                            'model': 'ipv6',
                                            'label': ' Unlimited address range（ipv6）',
                                            'placeholder': ' Leave the default unlimited speed intranet emptyipv6'
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
            "notify": True,
            "downloader": [],
            "play_up_speed": None,
            "play_down_speed": None,
            "noplay_up_speed": None,
            "noplay_down_speed": None,
            "bandwidth": None,
            "allocation_ratio": "",
            "ipv4": "",
            "ipv6": ""
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.WebhookMessage)
    def check_playing_sessions(self, event: Event = None):
        """
        Check playback sessions
        """
        if not self._qb and not self._tr:
            return
        if not self._enabled:
            return
        if event:
            event_data: WebhookEventInfo = event.event_data
            if event_data.event not in [
                "playback.start",
                "PlaybackStart",
                "media.play",
                "media.stop",
                "PlaybackStop",
                "playback.stop"
            ]:
                return
        #  Total bitrate of current playback
        total_bit_rate = 0
        #  Media server type， Many of, Segregation
        if not settings.MEDIASERVER:
            return
        media_servers = settings.MEDIASERVER.split(',')
        #  Query the status of all media servers
        for media_server in media_servers:
            #  Query playing sessions
            playing_sessions = []
            if media_server == "emby":
                req_url = "[HOST]emby/Sessions?api_key=[APIKEY]"
                try:
                    res = Emby().get_data(req_url)
                    if res and res.status_code == 200:
                        sessions = res.json()
                        for session in sessions:
                            if session.get("NowPlayingItem") and not session.get("PlayState", {}).get("IsPaused"):
                                playing_sessions.append(session)
                except Exception as e:
                    logger.error(f" GainEmby Playback session failed：{str(e)}")
                    continue
                #  Calculating the effective bit rate
                for session in playing_sessions:
                    #  If the unlimited speed range is set, the judgmentsession ip Whether it is within the unlimited speed limit
                    if self._unlimited_ips["ipv4"] or self._unlimited_ips["ipv6"]:
                        if not self.__allow_access(self._unlimited_ips, session.get("RemoteEndPoint")) \
                                and session.get("NowPlayingItem", {}).get("MediaType") == "Video":
                            total_bit_rate += int(session.get("NowPlayingItem", {}).get("Bitrate") or 0)
                    #  No speed limit set， Then the default unlimited speed intranetip
                    elif not IpUtils.is_private_ip(session.get("RemoteEndPoint")) \
                            and session.get("NowPlayingItem", {}).get("MediaType") == "Video":
                        total_bit_rate += int(session.get("NowPlayingItem", {}).get("Bitrate") or 0)
            elif media_server == "jellyfin":
                req_url = "[HOST]Sessions?api_key=[APIKEY]"
                try:
                    res = Jellyfin().get_data(req_url)
                    if res and res.status_code == 200:
                        sessions = res.json()
                        for session in sessions:
                            if session.get("NowPlayingItem") and not session.get("PlayState", {}).get("IsPaused"):
                                playing_sessions.append(session)
                except Exception as e:
                    logger.error(f" GainJellyfin Playback session failed：{str(e)}")
                    continue
                #  Calculating the effective bit rate
                for session in playing_sessions:
                    #  If the unlimited speed range is set, the judgmentsession ip Whether it is within the unlimited speed limit
                    if self._unlimited_ips["ipv4"] or self._unlimited_ips["ipv6"]:
                        if not self.__allow_access(self._unlimited_ips, session.get("RemoteEndPoint")) \
                                and session.get("NowPlayingItem", {}).get("MediaType") == "Video":
                            media_streams = session.get("NowPlayingItem", {}).get("MediaStreams") or []
                            for media_stream in media_streams:
                                total_bit_rate += int(media_stream.get("BitRate") or 0)
                    #  No speed limit set， Then the default unlimited speed intranetip
                    elif not IpUtils.is_private_ip(session.get("RemoteEndPoint")) \
                            and session.get("NowPlayingItem", {}).get("MediaType") == "Video":
                        media_streams = session.get("NowPlayingItem", {}).get("MediaStreams") or []
                        for media_stream in media_streams:
                            total_bit_rate += int(media_stream.get("BitRate") or 0)
            elif media_server == "plex":
                _plex = Plex().get_plex()
                if _plex:
                    sessions = _plex.sessions()
                    for session in sessions:
                        bitrate = sum([m.bitrate or 0 for m in session.media])
                        playing_sessions.append({
                            "type": session.TAG,
                            "bitrate": bitrate,
                            "address": session.player.address
                        })
                    #  Calculating the effective bit rate
                    for session in playing_sessions:
                        #  If the unlimited speed range is set, the judgmentsession ip Whether it is within the unlimited speed limit
                        if self._unlimited_ips["ipv4"] or self._unlimited_ips["ipv6"]:
                            if not self.__allow_access(self._unlimited_ips, session.get("address")) \
                                    and session.get("type") == "Video":
                                total_bit_rate += int(session.get("bitrate") or 0)
                        #  No speed limit set， Then the default unlimited speed intranetip
                        elif not IpUtils.is_private_ip(session.get("address")) \
                                and session.get("type") == "Video":
                            total_bit_rate += int(session.get("bitrate") or 0)

        if total_bit_rate:
            #  Enable smart speed limit to calculate upload speed limit
            if self._auto_limit:
                play_up_speed = self.__calc_limit(total_bit_rate)
            else:
                play_up_speed = self._play_up_speed

            #  Currently playing， Start speed limit
            self.__set_limiter(limit_type=" Playable", upload_limit=play_up_speed,
                               download_limit=self._play_down_speed)
        else:
            #  Currently not playing， Abolish speed limits
            self.__set_limiter(limit_type=" Unplayed", upload_limit=self._noplay_up_speed,
                               download_limit=self._noplay_down_speed)

    def __calc_limit(self, total_bit_rate: float) -> float:
        """
        Calculate intelligent upload speed limits
        """
        if not self._bandwidth:
            return 10
        return round((self._bandwidth - total_bit_rate) / 8 / 1024, 2)

    def __set_limiter(self, limit_type: str, upload_limit: float, download_limit: float):
        """
        Setting speed limit
        """
        if not self._qb and not self._tr:
            return
        state = f"U:{upload_limit},D:{download_limit}"
        if self._current_state == state:
            #  No change in speed limit status
            return
        else:
            self._current_state = state
            
        try:
            cnt = 0
            for download in self._downloader:
                if self._auto_limit and limit_type == " Playable":
                    #  Playback intelligent speed limit is turned on
                    if len(self._downloader) == 1:
                        #  There's only one downloader.
                        upload_limit = int(upload_limit)
                    else:
                        #  Multiple downloaders
                        if not self._allocation_ratio:
                            #  On average
                            upload_limit = int(upload_limit / len(self._downloader))
                        else:
                            #  Sliding scale
                            allocation_count = sum([int(i) for i in self._allocation_ratio.split(":")])
                            upload_limit = int(upload_limit * int(self._allocation_ratio.split(":")[cnt]) / allocation_count)
                            cnt += 1
                if upload_limit:
                    text = f" Upload：{upload_limit} KB/s"
                else:
                    text = f" Upload： Unlimited speed"
                if download_limit:
                    text = f"{text}\n Downloading：{download_limit} KB/s"
                else:
                    text = f"{text}\n Downloading： Unlimited speed"
                if str(download) == 'qbittorrent':
                    if self._qb:
                        self._qb.set_speed_limit(download_limit=download_limit, upload_limit=upload_limit)
                        #  Send notification
                        if self._notify:
                            title = "【 Playback speed limit】"
                            if upload_limit or download_limit:
                                subtitle = f"Qbittorrent  Commencement{limit_type} Speed limit"
                                self.post_message(
                                    mtype=NotificationType.MediaServer,
                                    title=title,
                                    text=f"{subtitle}\n{text}"
                                )
                            else:
                                self.post_message(
                                    mtype=NotificationType.MediaServer,
                                    title=title,
                                    text=f"Qbittorrent  The speed limit has been lifted."
                                )
                else:
                    if self._tr:
                        self._tr.set_speed_limit(download_limit=download_limit, upload_limit=upload_limit)
                        #  Send notification
                        if self._notify:
                            title = "【 Playback speed limit】"
                            if upload_limit or download_limit:
                                subtitle = f"Transmission  Commencement{limit_type} Speed limit"
                                self.post_message(
                                    mtype=NotificationType.MediaServer,
                                    title=title,
                                    text=f"{subtitle}\n{text}"
                                )
                            else:
                                self.post_message(
                                    mtype=NotificationType.MediaServer,
                                    title=title,
                                    text=f"Transmission  The speed limit has been lifted."
                                )
        except Exception as e:
            logger.error(f"Setting speed limit失败：{str(e)}")

    @staticmethod
    def __allow_access(allow_ips: dict, ip: str) -> bool:
        """
        JudgementsIP Legality
        :param allow_ips:  PermissibleIP Realm {"ipv4":, "ipv6":}
        :param ip:  Soundip
        """
        if not allow_ips:
            return True
        try:
            ipaddr = ipaddress.ip_address(ip)
            if ipaddr.version == 4:
                if not allow_ips.get('ipv4'):
                    return True
                allow_ipv4s = allow_ips.get('ipv4').split(",")
                for allow_ipv4 in allow_ipv4s:
                    if ipaddr in ipaddress.ip_network(allow_ipv4, strict=False):
                        return True
            elif ipaddr.ipv4_mapped:
                if not allow_ips.get('ipv4'):
                    return True
                allow_ipv4s = allow_ips.get('ipv4').split(",")
                for allow_ipv4 in allow_ipv4s:
                    if ipaddr.ipv4_mapped in ipaddress.ip_network(allow_ipv4, strict=False):
                        return True
            else:
                if not allow_ips.get('ipv6'):
                    return True
                allow_ipv6s = allow_ips.get('ipv6').split(",")
                for allow_ipv6 in allow_ipv6s:
                    if ipaddr in ipaddress.ip_network(allow_ipv6, strict=False):
                        return True
        except Exception as err:
            print(str(err))
            return False
        return False

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
            print(str(e))
