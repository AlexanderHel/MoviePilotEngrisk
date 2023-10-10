from pathlib import Path
from typing import Optional, Dict, Union, List

from pydantic import BaseModel

from app.schemas.types import MediaType


class ExistMediaInfo(BaseModel):
    """
    Media information exists on the media server
    """
    #  Typology  Cinematic、 Dramas
    type: Optional[MediaType]
    #  Classifier for seasonal crop yield or seasons of a tv series
    seasons: Optional[Dict[int, list]] = {}
    #  Media server
    server: Optional[str] = None
    #  Media, esp. news mediaID
    itemid: Optional[Union[str, int]] = None


class NotExistMediaInfo(BaseModel):
    """
    No media information exists on the media server
    """
    #  Classifier for seasonal crop yield or seasons of a tv series
    season: Optional[int] = None
    #  Episode list
    episodes: Optional[list] = []
    #  Total episodes
    total_episode: Optional[int] = 0
    #  Initial set
    start_episode: Optional[int] = 0


class RefreshMediaItem(BaseModel):
    """
    Media library refresh information
    """
    #  Caption
    title: Optional[str] = None
    #  Particular year
    year: Optional[str] = None
    #  Typology
    type: Optional[MediaType] = None
    #  Form
    category: Optional[str] = None
    #  Catalogs
    target_path: Optional[Path] = None


class MediaServerLibrary(BaseModel):
    """
    Media server media library information
    """
    #  Server (computer)
    server: Optional[str] = None
    # ID
    id: Optional[Union[str, int]] = None
    #  Name (of a thing)
    name: Optional[str] = None
    #  Trails
    path: Optional[Union[str, list]] = None
    #  Typology
    type: Optional[str] = None
    #  Cover art
    image: Optional[str] = None


class MediaServerItem(BaseModel):
    """
    Media server media information
    """
    # ID
    id: Optional[Union[str, int]] = None
    #  Server (computer)
    server: Optional[str] = None
    #  Media libraryID
    library: Optional[Union[str, int]] = None
    # ID
    item_id: Optional[str] = None
    #  Typology
    item_type: Optional[str] = None
    #  Caption
    title: Optional[str] = None
    #  Original title
    original_title: Optional[str] = None
    #  Particular year
    year: Optional[str] = None
    # TMDBID
    tmdbid: Optional[int] = None
    # IMDBID
    imdbid: Optional[str] = None
    # TVDBID
    tvdbid: Optional[str] = None
    #  Trails
    path: Optional[str] = None
    #  Classifier for seasonal crop yield or seasons of a tv series集
    seasoninfo: Optional[Dict[int, list]] = None
    #  Note
    note: Optional[str] = None
    #  Synchronous time
    lst_mod_date: Optional[str] = None

    class Config:
        orm_mode = True


class MediaServerSeasonInfo(BaseModel):
    """
    Media server media episode information
    """
    season: Optional[int] = None
    episodes: Optional[List[int]] = []


class WebhookEventInfo(BaseModel):
    """
    Webhook Event information
    """
    event: Optional[str] = None
    channel: Optional[str] = None
    item_type: Optional[str] = None
    item_name: Optional[str] = None
    item_id: Optional[str] = None
    item_path: Optional[str] = None
    season_id: Optional[str] = None
    episode_id: Optional[str] = None
    tmdb_id: Optional[str] = None
    overview: Optional[str] = None
    percentage: Optional[float] = None
    ip: Optional[str] = None
    device_name: Optional[str] = None
    client: Optional[str] = None
    user_name: Optional[str] = None
    image_url: Optional[str] = None
    item_favorite: Optional[bool] = None
    save_reason: Optional[str] = None
    item_isvirtual: Optional[bool] = None
