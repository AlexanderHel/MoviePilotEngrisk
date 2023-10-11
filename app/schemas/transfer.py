from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class TransferTorrent(BaseModel):
    """
    Information on tasks to be transferred
    """
    title: Optional[str] = None
    path: Optional[Path] = None
    hash: Optional[str] = None
    tags: Optional[str] = None


class DownloadingTorrent(BaseModel):
    """
    Task information in the download
    """
    hash: Optional[str] = None
    title: Optional[str] = None
    name: Optional[str] = None
    year: Optional[str] = None
    season_episode: Optional[str] = None
    size: Optional[float] = 0
    progress: Optional[float] = 0
    state: Optional[str] = 'downloading'
    upspeed: Optional[str] = None
    dlspeed: Optional[str] = None
    media: Optional[dict] = {}


class TransferInfo(BaseModel):
    """
    File transfer result information
    """
    #  Success flag
    success: bool = True
    #  Divert or distract (attention etc)⼁ Trails
    path: Optional[Path] = None
    #  Post-transfer path
    target_path: Optional[Path] = None
    #  Whether or not the original blu-ray disc
    is_bluray: Optional[bool] = False
    #  Number of documents processed
    file_count: Optional[int] = 0
    #  List of documents processed
    file_list: Optional[list] = []
    #  List of target documents
    file_list_new: Optional[list] = []
    #  Total document size
    total_size: Optional[float] = 0
    #  List of failures
    fail_list: Optional[list] = []
    #  Error message
    message: Optional[str] = None

    def to_dict(self):
        """
        Return to dictionary
        """
        dicts = vars(self).copy()  #  Create a copy of the dictionary to avoid modifying the original data
        dicts["path"] = str(self.path) if self.path else None
        dicts["target_path"] = str(self.target_path) if self.target_path else None
        return dicts


class EpisodeFormat(BaseModel):
    """
    Episode custom recognition format
    """
    format: Optional[str] = None
    detail: Optional[str] = None
    part: Optional[str] = None
    offset: Optional[int] = None
