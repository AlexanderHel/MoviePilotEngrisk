from typing import Optional, Dict, List

from pydantic import BaseModel


class MetaInfo(BaseModel):
    """
    Identifying metadata
    """
    #  Documents processed or not
    isfile: Optional[bool] = False
    #  Original string
    org_string: Optional[str] = None
    #  Original title
    title: Optional[str] = None
    #  Subheading
    subtitle: Optional[str] = None
    #  Typology  Cinematic、 Dramas
    type: Optional[str] = None
    #  Name (of a thing)
    name: Optional[str] = None
    #  Recognized chinese names
    cn_name: Optional[str] = None
    #  Recognizable english names
    en_name: Optional[str] = None
    #  Particular year
    year: Optional[str] = None
    #  Total number of quarters
    total_season: Optional[int] = 0
    #  The beginning of the identification season  Digital (electronics etc)
    begin_season: Optional[int] = None
    #  End of season for identification  Digital (electronics etc)
    end_season: Optional[int] = None
    #  Total episodes
    total_episode: Optional[int] = 0
    #  Identified starting set
    begin_episode: Optional[int] = None
    #  Identified end sets
    end_episode: Optional[int] = None
    # SxxExx
    season_episode: Optional[str] = None
    # Partx Cd Dvd Disk Disc
    part: Optional[str] = None
    #  Types of resources identified
    resource_type: Optional[str] = None
    #  Effectiveness of identification
    resource_effect: Optional[str] = None
    #  Recognized resolution
    resource_pix: Optional[str] = None
    #  Identified production team/ Subtitling team
    resource_team: Optional[str] = None
    #  Video encoding
    video_encode: Optional[str] = None
    #  Audio encoding
    audio_encode: Optional[str] = None
    #  Resource type
    edition: Optional[str] = None
    #  Identifier information for the application
    apply_words: Optional[List[str]] = None


class MediaInfo(BaseModel):
    """
    Identify media messages
    """
    #  Typology  Cinematic、 Dramas
    type: Optional[str] = None
    #  Media title
    title: Optional[str] = None
    #  Particular year
    year: Optional[str] = None
    #  Caption（ Particular year）
    title_year: Optional[str] = None
    #  Classifier for seasonal crop yield or seasons of a tv series
    season: Optional[int] = None
    # TMDB ID
    tmdb_id: Optional[int] = None
    # IMDB ID
    imdb_id: Optional[str] = None
    # TVDB ID
    tvdb_id: Optional[str] = None
    #  Douban, prc social networking websiteID
    douban_id: Optional[str] = None
    #  Original language of the media
    original_language: Optional[str] = None
    #  Original media release title
    original_title: Optional[str] = None
    #  Media release date
    release_date: Optional[str] = None
    #  Background image
    backdrop_path: Optional[str] = None
    #  Poster image
    poster_path: Optional[str] = None
    #  Score (of student's work)
    vote_average: Optional[int] = 0
    #  Descriptive
    overview: Optional[str] = None
    #  Secondary classification
    category: Optional[str] = ""
    #  Classifier for seasonal crop yield or seasons of a tv series季集清单
    seasons: Optional[Dict[int, list]] = {}
    #  Classifier for seasonal crop yield or seasons of a tv series详情
    season_info: Optional[List[dict]] = []
    #  Alias and translation
    names: Optional[list] = []
    #  Actor or actress
    actors: Optional[list] = []
    #  Director (film etc)
    directors: Optional[list] = []
    #  Detailed links
    detail_link: Optional[str] = None
    #  Other thanTMDB Causality
    #  Adult content or not
    adult: Optional[bool] = False
    #  Founder
    created_by: Optional[list] = []
    #  Episode length
    episode_run_time: Optional[list] = []
    #  Hairstyle
    genres: Optional[List[dict]] = []
    #  Premiere date
    first_air_date: Optional[str] = None
    #  Home page (of a website)
    homepage: Optional[str] = None
    #  Language type (in a classification)
    languages: Optional[list] = []
    #  Last release date
    last_air_date: Optional[str] = None
    #  Streaming media platform
    networks: Optional[list] = []
    #  Episode number (of a tv series etc)
    number_of_episodes: Optional[int] = 0
    #  Classifier for seasonal crop yield or seasons of a tv series数
    number_of_seasons: Optional[int] = 0
    #  Country of origin
    origin_country: Optional[list] = []
    #  Original name
    original_name: Optional[str] = None
    #  Production company
    production_companies: Optional[list] = []
    #  Producer
    production_countries: Optional[list] = []
    #  Language type (in a classification)
    spoken_languages: Optional[list] = []
    #  State of affairs
    status: Optional[str] = None
    #  Tab (of a window) (computing)
    tagline: Optional[str] = None
    #  HairstyleID
    genre_ids: Optional[list] = []
    #  Number of evaluations
    vote_count: Optional[int] = 0
    #  Popularity
    popularity: Optional[int] = 0
    #  Length of time
    runtime: Optional[int] = None
    #  Next episode
    next_episode_to_air: Optional[dict] = {}


class TorrentInfo(BaseModel):
    """
    Search for seed information
    """
    #  WebsiteID
    site: Optional[int] = None
    #  Site name
    site_name: Optional[str] = None
    #  WebsiteCookie
    site_cookie: Optional[str] = None
    #  WebsiteUA
    site_ua: Optional[str] = None
    #  Whether the site uses a proxy
    site_proxy: Optional[bool] = False
    #  Site prioritization
    site_order: Optional[int] = 0
    #  Seed name
    title: Optional[str] = None
    #  Seed subtitle
    description: Optional[str] = None
    # IMDB ID
    imdbid: Optional[str] = None
    #  Seed links
    enclosure: Optional[str] = None
    #  Detail page
    page_url: Optional[str] = None
    #  Seed size
    size: Optional[float] = 0
    #  Breeder
    seeders: Optional[int] = 0
    #  Downloader
    peers: Optional[int] = 0
    #  Completer
    grabs: Optional[int] = 0
    #  Release time
    pubdate: Optional[str] = None
    #  Past due
    date_elapsed: Optional[str] = None
    #  Upload factor
    uploadvolumefactor: Optional[float] = None
    #  Download factor
    downloadvolumefactor: Optional[float] = None
    # HR
    hit_and_run: Optional[bool] = False
    #  Seed labels
    labels: Optional[list] = []
    #  Seeding priority
    pri_order: Optional[int] = 0
    #  Promote
    volume_factor: Optional[str] = None


class Context(BaseModel):
    """
    (textual) context
    """
    #  Metadata
    meta_info: Optional[MetaInfo] = None
    #  Media information
    media_info: Optional[MediaInfo] = None
    #  Seed information
    torrent_info: Optional[TorrentInfo] = None
