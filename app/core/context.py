import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Tuple

from app.core.config import settings
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.schemas.types import MediaType


@dataclass
class TorrentInfo:
    #  WebsiteID
    site: int = None
    #  Site name
    site_name: str = None
    #  WebsiteCookie
    site_cookie: str = None
    #  WebsiteUA
    site_ua: str = None
    #  Whether the site uses a proxy
    site_proxy: bool = False
    #  Site prioritization
    site_order: int = 0
    #  Seed name
    title: str = None
    #  Seed subtitle
    description: str = None
    # IMDB ID
    imdbid: str = None
    #  Seed links
    enclosure: str = None
    #  Detail page
    page_url: str = None
    #  Seed size
    size: float = 0
    #  Breeder
    seeders: int = 0
    #  Downloader
    peers: int = 0
    #  Completer
    grabs: int = 0
    #  Release time
    pubdate: str = None
    #  Past due
    date_elapsed: str = None
    #  Upload factor
    uploadvolumefactor: float = None
    #  Download factor
    downloadvolumefactor: float = None
    # HR
    hit_and_run: bool = False
    #  Seed labels
    labels: list = field(default_factory=list)
    #  Seeding priority
    pri_order: int = 0

    def __setattr__(self, name: str, value: Any):
        self.__dict__[name] = value

    def __get_properties(self):
        """
        Getting a list of properties
        """
        property_names = []
        for member_name in dir(self.__class__):
            member = getattr(self.__class__, member_name)
            if isinstance(member, property):
                property_names.append(member_name)
        return property_names

    def from_dict(self, data: dict):
        """
        Initialize from dictionary
        """
        properties = self.__get_properties()
        for key, value in data.items():
            if key in properties:
                continue
            setattr(self, key, value)

    @staticmethod
    def get_free_string(upload_volume_factor: float, download_volume_factor: float) -> str:
        """
        Calculate the type of promotion
        """
        if upload_volume_factor is None or download_volume_factor is None:
            return " Uncharted"
        free_strs = {
            "1.0 1.0": " Ordinary",
            "1.0 0.0": " Free (of charge)",
            "2.0 1.0": "2X",
            "2.0 0.0": "2X Free (of charge)",
            "1.0 0.5": "50%",
            "2.0 0.5": "2X 50%",
            "1.0 0.7": "70%",
            "1.0 0.3": "30%"
        }
        return free_strs.get('%.1f %.1f' % (upload_volume_factor, download_volume_factor), " Uncharted")

    @property
    def volume_factor(self):
        """
        Back to promotions
        """
        return self.get_free_string(self.uploadvolumefactor, self.downloadvolumefactor)

    def to_dict(self):
        """
        Return to dictionary
        """
        dicts = asdict(self)
        dicts["volume_factor"] = self.volume_factor
        return dicts


@dataclass
class MediaInfo:
    #  Typology  Cinematic、 Dramas
    type: MediaType = None
    #  Media title
    title: str = None
    #  Particular year
    year: str = None
    #  Classifier for seasonal crop yield or seasons of a tv series
    season: int = None
    # TMDB ID
    tmdb_id: int = None
    # IMDB ID
    imdb_id: str = None
    # TVDB ID
    tvdb_id: int = None
    #  Douban, prc social networking websiteID
    douban_id: str = None
    #  Original language of the media
    original_language: str = None
    #  Original media release title
    original_title: str = None
    #  Media release date
    release_date: str = None
    #  Background image
    backdrop_path: str = None
    #  Poster image
    poster_path: str = None
    # LOGO
    logo_path: str = None
    #  Score (of student's work)
    vote_average: int = 0
    #  Descriptive
    overview: str = None
    #  HairstyleID
    genre_ids: list = field(default_factory=list)
    #  All aliases and translations
    names: list = field(default_factory=list)
    #  Episode list information for each season
    seasons: Dict[int, list] = field(default_factory=dict)
    #  Seasonal details
    season_info: List[dict] = field(default_factory=list)
    #  Year of each season
    season_years: dict = field(default_factory=dict)
    #  Secondary classification
    category: str = ""
    # TMDB INFO
    tmdb_info: dict = field(default_factory=dict)
    #  Douban, prc social networking website INFO
    douban_info: dict = field(default_factory=dict)
    #  Director (film etc)
    directors: List[dict] = field(default_factory=list)
    #  Actor or actress
    actors: List[dict] = field(default_factory=list)
    #  Adult content or not
    adult: bool = False
    #  Founder
    created_by: list = field(default_factory=list)
    #  Episode length
    episode_run_time: list = field(default_factory=list)
    #  Hairstyle
    genres: List[dict] = field(default_factory=list)
    #  Premiere date
    first_air_date: str = None
    #  Home page (of a website)
    homepage: str = None
    #  Language type (in a classification)
    languages: list = field(default_factory=list)
    #  Last release date
    last_air_date: str = None
    #  Streaming media platform
    networks: list = field(default_factory=list)
    #  Episode number (of a tv series etc)
    number_of_episodes: int = 0
    #  Classifier for seasonal crop yield or seasons of a tv series数
    number_of_seasons: int = 0
    #  Country of origin
    origin_country: list = field(default_factory=list)
    #  Original name
    original_name: str = None
    #  Production company
    production_companies: list = field(default_factory=list)
    #  Producer
    production_countries: list = field(default_factory=list)
    #  Language type (in a classification)
    spoken_languages: list = field(default_factory=list)
    #  State of affairs
    status: str = None
    #  Tab (of a window) (computing)
    tagline: str = None
    #  Number of evaluations
    vote_count: int = 0
    #  Popularity
    popularity: int = 0
    #  Length of time
    runtime: int = None
    #  Next episode
    next_episode_to_air: dict = field(default_factory=dict)

    def __post_init__(self):
        #  Setting up media information
        if self.tmdb_info:
            self.set_tmdb_info(self.tmdb_info)
        if self.douban_info:
            self.set_douban_info(self.douban_info)

    def __setattr__(self, name: str, value: Any):
        self.__dict__[name] = value

    def __get_properties(self):
        """
        Getting a list of properties
        """
        property_names = []
        for member_name in dir(self.__class__):
            member = getattr(self.__class__, member_name)
            if isinstance(member, property):
                property_names.append(member_name)
        return property_names

    def from_dict(self, data: dict):
        """
        Initialize from dictionary
        """
        properties = self.__get_properties()
        for key, value in data.items():
            if key in properties:
                continue
            setattr(self, key, value)
        if isinstance(self.type, str):
            self.type = MediaType(self.type)

    def set_image(self, name: str, image: str):
        """
        Setting the image address
        """
        setattr(self, f"{name}_path", image)

    def get_image(self, name: str):
        """
        Get image address
        """
        try:
            return getattr(self, f"{name}_path")
        except AttributeError:
            return None

    def set_category(self, cat: str):
        """
        Setting up secondary categorization
        """
        self.category = cat or ""

    def set_tmdb_info(self, info: dict):
        """
        Initialize matchmaker information
        """

        def __directors_actors(tmdbinfo: dict) -> Tuple[List[dict], List[dict]]:
            """
            Search for directors and actors
            :param tmdbinfo: TMDB Metadata
            :return:  Director's list， Cast list
            """
            """
            "cast": [
              {
                "adult": false,
                "gender": 2,
                "id": 3131,
                "known_for_department": "Acting",
                "name": "Antonio Banderas",
                "original_name": "Antonio Banderas",
                "popularity": 60.896,
                "profile_path": "/iWIUEwgn2KW50MssR7tdPeFoRGW.jpg",
                "cast_id": 2,
                "character": "Puss in Boots (voice)",
                "credit_id": "6052480e197de4006bb47b9a",
                "order": 0
              }
            ],
            "crew": [
              {
                "adult": false,
                "gender": 2,
                "id": 5524,
                "known_for_department": "Production",
                "name": "Andrew Adamson",
                "original_name": "Andrew Adamson",
                "popularity": 9.322,
                "profile_path": "/qqIAVKAe5LHRbPyZUlptsqlo4Kb.jpg",
                "credit_id": "63b86b2224b33300a0585bf1",
                "department": "Production",
                "job": "Executive Producer"
              }
            ]
            """
            if not tmdbinfo:
                return [], []
            _credits = tmdbinfo.get("credits")
            if not _credits:
                return [], []
            directors = []
            actors = []
            for cast in _credits.get("cast"):
                if cast.get("known_for_department") == "Acting":
                    actors.append(cast)
            for crew in _credits.get("crew"):
                if crew.get("job") in ["Director", "Writer", "Editor", "Producer"]:
                    directors.append(crew)
            return directors, actors

        if not info:
            return
        #  Noumenon (object of purely intellectual perception according kant)
        self.tmdb_info = info
        #  Typology
        if isinstance(info.get('media_type'), MediaType):
            self.type = info.get('media_type')
        elif info.get('media_type'):
            self.type = MediaType.MOVIE if info.get("media_type") == "movie" else MediaType.TV
        else:
            self.type = MediaType.MOVIE if info.get("title") else MediaType.TV
        # TMDBID
        self.tmdb_id = info.get('id')
        if not self.tmdb_id:
            return
        #  AddedID
        if info.get("external_ids"):
            self.tvdb_id = info.get("external_ids", {}).get("tvdb_id")
            self.imdb_id = info.get("external_ids", {}).get("imdb_id")
        #  Score (of student's work)
        self.vote_average = round(float(info.get('vote_average')), 1) if info.get('vote_average') else 0
        #  Descriptive
        self.overview = info.get('overview')
        #  Hairstyle
        self.genre_ids = info.get('genre_ids') or []
        #  Original language
        self.original_language = info.get('original_language')
        if self.type == MediaType.MOVIE:
            #  Caption
            self.title = info.get('title')
            #  Original title
            self.original_title = info.get('original_title')
            #  Issue date
            self.release_date = info.get('release_date')
            if self.release_date:
                #  Particular year
                self.year = self.release_date[:4]
        else:
            #  Dramas
            self.title = info.get('name')
            #  Original title
            self.original_title = info.get('original_name')
            #  Issue date
            self.release_date = info.get('first_air_date')
            if self.release_date:
                #  Particular year
                self.year = self.release_date[:4]
            #  Classifier for seasonal crop yield or seasons of a tv series集信息
            if info.get('seasons'):
                self.season_info = info.get('seasons')
                for seainfo in info.get('seasons'):
                    #  Classifier for seasonal crop yield or seasons of a tv series
                    season = seainfo.get("season_number")
                    if not season:
                        continue
                    #  Classifier for sections of a tv series e.g. episode
                    episode_count = seainfo.get("episode_count")
                    self.seasons[season] = list(range(1, episode_count + 1))
                    #  Particular year
                    air_date = seainfo.get("air_date")
                    if air_date:
                        self.season_years[season] = air_date[:4]
        #  Playbill
        if info.get('poster_path'):
            self.poster_path = f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{info.get('poster_path')}"
        #  Contexts
        if info.get('backdrop_path'):
            self.backdrop_path = f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/original{info.get('backdrop_path')}"
        #  Director (film etc)和演员
        self.directors, self.actors = __directors_actors(info)
        #  Alias and translation
        self.names = info.get('names') or []
        #  Remaining attribute assignments
        for key, value in info.items():
            if hasattr(self, key) and not getattr(self, key):
                setattr(self, key, value)

    def set_douban_info(self, info: dict):
        """
        Initialize bean information
        """
        if not info:
            return
        #  Noumenon (object of purely intellectual perception according kant)
        self.douban_info = info
        #  Douban, prc social networking websiteID
        self.douban_id = str(info.get("id"))
        #  Typology

        if not self.type:
            if isinstance(info.get('media_type'), MediaType):
                self.type = info.get('media_type')
            else:
                self.type = MediaType.MOVIE if info.get("type") == "movie" else MediaType.TV
        #  Caption
        if not self.title:
            self.title = info.get("title")
            #  Identify the season in the title
            meta = MetaInfo(self.title)
            self.season = meta.begin_season
        #  Original language标题
        if not self.original_title:
            self.original_title = info.get("original_title")
        #  Particular year
        if not self.year:
            self.year = info.get("year")[:4] if info.get("year") else None
        #  Score (of student's work)
        if not self.vote_average:
            rating = info.get("rating")
            if rating:
                vote_average = float(rating.get("value"))
            else:
                vote_average = 0
            self.vote_average = vote_average
        #  Issue date
        if not self.release_date:
            if info.get("release_date"):
                self.release_date = info.get("release_date")
            elif info.get("pubdate") and isinstance(info.get("pubdate"), list):
                release_date = info.get("pubdate")[0]
                if release_date:
                    match = re.search(r'\d{4}-\d{2}-\d{2}', release_date)
                    if match:
                        self.release_date = match.group()
        #  Playbill
        if not self.poster_path:
            self.poster_path = info.get("pic", {}).get("large")
            if not self.poster_path and info.get("cover_url"):
                self.poster_path = info.get("cover_url")
            if not self.poster_path and info.get("cover"):
                self.poster_path = info.get("cover").get("url")
        #  Synopsis
        if not self.overview:
            self.overview = info.get("intro") or info.get("card_subtitle") or ""
        #  Extracting years from profiles
        if self.overview and not self.year:
            match = re.search(r'\d{4}', self.overview)
            if match:
                self.year = match.group()
        #  Director (film etc)和演员
        if not self.directors:
            self.directors = info.get("directors") or []
        if not self.actors:
            self.actors = info.get("actors") or []
        #  Nickname
        if not self.names:
            self.names = info.get("aka") or []
        #  Episode
        if self.type == MediaType.TV and not self.seasons:
            meta = MetaInfo(info.get("title"))
            if meta.begin_season:
                episodes_count = info.get("episodes_count")
                if episodes_count:
                    self.seasons[meta.begin_season] = list(range(1, episodes_count + 1))
        #  Remaining attribute assignments
        for key, value in info.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    @property
    def title_year(self):
        if self.title:
            return "%s (%s)" % (self.title, self.year) if self.year else self.title
        return ""

    @property
    def detail_link(self):
        """
        TMDB Media detail page address
        """
        if self.tmdb_id:
            if self.type == MediaType.MOVIE:
                return "https://www.themoviedb.org/movie/%s" % self.tmdb_id
            else:
                return "https://www.themoviedb.org/tv/%s" % self.tmdb_id
        elif self.douban_id:
            return "https://movie.douban.com/subject/%s" % self.douban_id
        return ""

    @property
    def stars(self):
        """
        Returns the number of stars in the rating
        """
        if not self.vote_average:
            return ""
        return "".rjust(int(self.vote_average), "★")

    @property
    def vote_star(self):
        if self.vote_average:
            return " Score (of student's work)：%s" % self.stars
        return ""

    def get_backdrop_image(self, default: bool = False):
        """
        Returns the address of the background image
        """
        if self.backdrop_path:
            return self.backdrop_path.replace("original", "w500")
        return default or ""

    def get_message_image(self, default: bool = None):
        """
        Returns the address of the message image
        """
        if self.backdrop_path:
            return self.backdrop_path.replace("original", "w500")
        return self.get_poster_image(default=default)

    def get_poster_image(self, default: bool = None):
        """
        Return to poster image address
        """
        if self.poster_path:
            return self.poster_path.replace("original", "w500")
        return default or ""

    def get_overview_string(self, max_len: int = 140):
        """
        Returns the profile information with a limited length
        :param max_len:  Content length
        :return:
        """
        overview = str(self.overview).strip()
        placeholder = ' ...'
        max_len = max(len(placeholder), max_len - len(placeholder))
        overview = (overview[:max_len] + placeholder) if len(overview) > max_len else overview
        return overview

    def to_dict(self):
        """
        Return to dictionary
        """
        dicts = asdict(self)
        dicts["type"] = self.type.value if self.type else None
        dicts["detail_link"] = self.detail_link
        dicts["title_year"] = self.title_year
        return dicts

    def clear(self):
        """
        Remove redundant data， Bulk reduction
        """
        self.tmdb_info = {}
        self.douban_info = {}
        self.seasons = {}
        self.genres = []
        self.season_info = []
        self.names = []
        self.actors = []
        self.directors = []
        self.production_companies = []
        self.production_countries = []
        self.spoken_languages = []
        self.networks = []
        self.next_episode_to_air = {}


@dataclass
class Context:
    """
    Context object (computing)
    """

    #  Identifying information
    meta_info: MetaBase = None
    #  Media information
    media_info: MediaInfo = None
    #  Seed information
    torrent_info: TorrentInfo = None

    def to_dict(self):
        """
        Convert to dictionary
        """
        return {
            "meta_info": self.meta_info.to_dict() if self.meta_info else None,
            "torrent_info": self.torrent_info.to_dict() if self.torrent_info else None,
            "media_info": self.media_info.to_dict() if self.media_info else None
        }
