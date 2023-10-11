import secrets
import sys
from pathlib import Path
from typing import List

from pydantic import BaseSettings

from app.utils.system import SystemUtils


class Settings(BaseSettings):
    #  Project name
    PROJECT_NAME = "MoviePilot"
    # API Trails
    API_V1_STR: str = "/api/v1"
    #  Keys
    SECRET_KEY: str = secrets.token_urlsafe(32)
    #  Allowed domains
    ALLOWED_HOSTS: list = ["*"]
    # TOKEN Expiration date (of document)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    #  Time zones
    TZ: str = "Asia/Shanghai"
    # API Listening address
    HOST: str = "0.0.0.0"
    # API Listening port
    PORT: int = 3001
    #  Front-end listening port
    NGINX_PORT: int = 3000
    #  Debug mode or not
    DEBUG: bool = False
    #  Whether to develop a model
    DEV: bool = False
    #  Configuration file directory
    CONFIG_DIR: str = None
    #  Super-administrator
    SUPERUSER: str = "admin"
    #  Super-administrator初始密码
    SUPERUSER_PASSWORD: str = "password"
    # API Keys， Need to be replaced
    API_TOKEN: str = "moviepilot"
    #  Network agent IP:PORT
    PROXY_HOST: str = None
    #  Media information search sources
    SEARCH_SOURCE: str = "themoviedb"
    #  Scraping incoming media files
    SCRAP_METADATA: bool = True
    #  Add whether or not the deposited media followsTMDB Changes in information
    SCRAP_FOLLOW_TMDB: bool = True
    #  Scraping sources
    SCRAP_SOURCE: str = "themoviedb"
    # TMDB Image address
    TMDB_IMAGE_DOMAIN: str = "image.tmdb.org"
    # TMDB API Address
    TMDB_API_DOMAIN: str = "api.themoviedb.org"
    # TMDB API Key
    TMDB_API_KEY: str = "db55323b8d3e4154498498a75642b381"
    # TVDB API Key
    TVDB_API_KEY: str = "6b481081-10aa-440c-99f2-21d17717ee02"
    # Fanart API Key
    FANART_API_KEY: str = "d2d31f9ecabea050fc7d68aa3146015f"
    #  Supported suffix formats
    RMT_MEDIAEXT: list = ['.mp4', '.mkv', '.ts', '.iso',
                          '.rmvb', '.avi', '.mov', '.mpeg',
                          '.mpg', '.wmv', '.3gp', '.asf',
                          '.m4v', '.flv', '.m2ts', '.strm',
                          '.tp']
    #  Supported subtitle file suffix formats
    RMT_SUBEXT: list = ['.srt', '.ass', '.ssa']
    #  Supported audio track file suffix formats
    RMT_AUDIO_TRACK_EXT: list = ['.mka']
    #  Indexer
    INDEXER: str = "builtin"
    #  Subscription model
    SUBSCRIBE_MODE: str = "spider"
    # RSS Subscription mode refresh interval（ Minutes）
    SUBSCRIBE_RSS_INTERVAL: int = 30
    #  Subscribe to search switch
    SUBSCRIBE_SEARCH: bool = False
    #  User authentication site
    AUTH_SITE: str = ""
    #  Interactive search automatically downloads usersID， Utilization, Demerger
    AUTO_DOWNLOAD_USER: str = None
    #  Message notification channels telegram/wechat/slack， For multiple notification channels, Segregation
    MESSAGER: str = "telegram"
    # WeChat CorporationsID
    WECHAT_CORPID: str = None
    # WeChat ApplianceSecret
    WECHAT_APP_SECRET: str = None
    # WeChat ApplianceID
    WECHAT_APP_ID: str = None
    # WeChat Proxy server
    WECHAT_PROXY: str = "https://qyapi.weixin.qq.com"
    # WeChat Token
    WECHAT_TOKEN: str = None
    # WeChat EncodingAESKey
    WECHAT_ENCODING_AESKEY: str = None
    # WeChat  Janitors
    WECHAT_ADMINS: str = None
    # Telegram Bot Token
    TELEGRAM_TOKEN: str = None
    # Telegram Chat ID
    TELEGRAM_CHAT_ID: str = None
    # Telegram  SubscribersID， Utilization, Segregation
    TELEGRAM_USERS: str = ""
    # Telegram  JanitorsID， Utilization, Segregation
    TELEGRAM_ADMINS: str = ""
    # Slack Bot User OAuth Token
    SLACK_OAUTH_TOKEN: str = ""
    # Slack App-Level Token
    SLACK_APP_TOKEN: str = ""
    # Slack  Channel name
    SLACK_CHANNEL: str = ""
    # SynologyChat Webhook
    SYNOLOGYCHAT_WEBHOOK: str = ""
    # SynologyChat Token
    SYNOLOGYCHAT_TOKEN: str = ""
    #  Downloader qbittorrent/transmission
    DOWNLOADER: str = "qbittorrent"
    #  Downloader monitor switch
    DOWNLOADER_MONITOR: bool = True
    # Qbittorrent Address，IP:PORT
    QB_HOST: str = None
    # Qbittorrent User id
    QB_USER: str = None
    # Qbittorrent Cryptographic
    QB_PASSWORD: str = None
    # Qbittorrent Automatic management of classifications
    QB_CATEGORY: bool = False
    # Transmission Address，IP:PORT
    TR_HOST: str = None
    # Transmission User id
    TR_USER: str = None
    # Transmission Cryptographic
    TR_PASSWORD: str = None
    #  Seed labels
    TORRENT_TAG: str = "MOVIEPILOT"
    #  Download save directory， Mapped paths need to be consistent within containers
    DOWNLOAD_PATH: str = "/downloads"
    #  Movie download save directory， Mapped paths need to be consistent within containers
    DOWNLOAD_MOVIE_PATH: str = None
    #  Tv show download save directory， Mapped paths need to be consistent within containers
    DOWNLOAD_TV_PATH: str = None
    #  Anime download save directory， Mapped paths need to be consistent within containers
    DOWNLOAD_ANIME_PATH: str = None
    #  Download catalog secondary categories
    DOWNLOAD_CATEGORY: bool = False
    #  Download site subtitles
    DOWNLOAD_SUBTITLE: bool = True
    #  Media server emby/jellyfin/plex， Multiple media servers, Demerger
    MEDIASERVER: str = "emby"
    #  Inbound refresh media library
    REFRESH_MEDIASERVER: bool = True
    #  Media server synchronization interval（ Hourly）
    MEDIASERVER_SYNC_INTERVAL: int = 6
    #  Media server synchronization blacklist， Multiple media library names, Demerger
    MEDIASERVER_SYNC_BLACKLIST: str = None
    # EMBY Server address，IP:PORT
    EMBY_HOST: str = None
    # EMBY Api Key
    EMBY_API_KEY: str = None
    # Jellyfin Server address，IP:PORT
    JELLYFIN_HOST: str = None
    # Jellyfin Api Key
    JELLYFIN_API_KEY: str = None
    # Plex Server address，IP:PORT
    PLEX_HOST: str = None
    # Plex Token
    PLEX_TOKEN: str = None
    #  Migration pattern link/copy/move/softlink
    TRANSFER_TYPE: str = "copy"
    # CookieCloud Server address
    COOKIECLOUD_HOST: str = "https://movie-pilot.org/cookiecloud"
    # CookieCloud SubscribersKEY
    COOKIECLOUD_KEY: str = None
    # CookieCloud End-to-end encrypted passwords
    COOKIECLOUD_PASSWORD: str = None
    # CookieCloud Synchronization interval（ Minutes）
    COOKIECLOUD_INTERVAL: int = 60 * 24
    # OCR Server address
    OCR_HOST: str = "https://movie-pilot.org"
    # CookieCloud Corresponding browserUA
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.57"
    #  Media library catalog， Multiple directory use, Segregation
    LIBRARY_PATH: str = None
    #  Movie media library catalog name， Default (setting)" Cinematic"
    LIBRARY_MOVIE_NAME: str = None
    #  Tv series media library catalog name， Default (setting)" Dramas"
    LIBRARY_TV_NAME: str = None
    #  Anime media library catalog name， Default (setting)" Dramas/ Cartoons and comics"
    LIBRARY_ANIME_NAME: str = None
    #  Secondary classification
    LIBRARY_CATEGORY: bool = True
    #  Classification of tv series and animegenre_ids
    ANIME_GENREIDS = [16]
    #  Movie renaming format
    MOVIE_RENAME_FORMAT: str = "{{title}}{% if year %} ({{year}}){% endif %}" \
                               "/{{title}}{% if year %} ({{year}}){% endif %}{% if part %}-{{part}}{% endif %}{% if videoFormat %} - {{videoFormat}}{% endif %}" \
                               "{{fileExt}}"
    #  Tv series renaming format
    TV_RENAME_FORMAT: str = "{{title}}{% if year %} ({{year}}){% endif %}" \
                            "/Season {{season}}" \
                            "/{{title}} - {{season_episode}}{% if part %}-{{part}}{% endif %}{% if episode %} -  (prefix indicating ordinal number, e.g. first, number two etc) {{episode}}  Classifier for sections of a tv series e.g. episode{% endif %}" \
                            "{{fileExt}}"
    #  Large memory mode
    BIG_MEMORY_MODE: bool = False

    @property
    def INNER_CONFIG_PATH(self):
        return self.ROOT_PATH / "config"

    @property
    def CONFIG_PATH(self):
        if self.CONFIG_DIR:
            return Path(self.CONFIG_DIR)
        elif SystemUtils.is_docker():
            return Path("/config")
        elif SystemUtils.is_frozen():
            return Path(sys.executable).parent / "config"
        return self.ROOT_PATH / "config"

    @property
    def TEMP_PATH(self):
        return self.CONFIG_PATH / "temp"

    @property
    def ROOT_PATH(self):
        return Path(__file__).parents[2]

    @property
    def PLUGIN_DATA_PATH(self):
        return self.CONFIG_PATH / "plugins"

    @property
    def LOG_PATH(self):
        return self.CONFIG_PATH / "logs"

    @property
    def CACHE_CONF(self):
        if self.BIG_MEMORY_MODE:
            return {
                "tmdb": 1024,
                "refresh": 50,
                "torrents": 100,
                "douban": 512,
                "fanart": 512,
                "meta": 15 * 24 * 3600
            }
        return {
            "tmdb": 256,
            "refresh": 30,
            "torrents": 50,
            "douban": 256,
            "fanart": 128,
            "meta": 7 * 24 * 3600
        }

    @property
    def PROXY(self):
        if self.PROXY_HOST:
            return {
                "http": self.PROXY_HOST,
                "https": self.PROXY_HOST,
            }
        return None

    @property
    def PROXY_SERVER(self):
        if self.PROXY_HOST:
            return {
                "server": self.PROXY_HOST
            }

    @property
    def LIBRARY_PATHS(self) -> List[Path]:
        if self.LIBRARY_PATH:
            return [Path(path) for path in self.LIBRARY_PATH.split(",")]
        return []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.CONFIG_PATH as p:
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
            if SystemUtils.is_frozen():
                if not (p / "app.env").exists():
                    SystemUtils.copy(self.INNER_CONFIG_PATH / "app.env", p / "app.env")
        with self.TEMP_PATH as p:
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
        with self.LOG_PATH as p:
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)

    class Config:
        case_sensitive = True


settings = Settings(
    _env_file=Settings().CONFIG_PATH / "app.env",
    _env_file_encoding="utf-8"
)
