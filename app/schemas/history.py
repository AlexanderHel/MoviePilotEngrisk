from typing import Optional

from pydantic import BaseModel


class DownloadHistory(BaseModel):
    # ID
    id: int
    #  Preservation of distance
    path: Optional[str] = None
    #  Typology： Cinematic、 Dramas
    type: Optional[str] = None
    #  Caption
    title: Optional[str] = None
    #  Particular year
    year: Optional[str] = None
    # TMDBID
    tmdbid: Optional[int] = None
    # IMDBID
    imdbid: Optional[str] = None
    # TVDBID
    tvdbid: Optional[int] = None
    #  Douban, prc social networking websiteID
    doubanid: Optional[str] = None
    #  Classifier for seasonal crop yield or seasons of a tv seriesSxx
    seasons: Optional[str] = None
    #  Classifier for sections of a tv series e.g. episodeExx
    episodes: Optional[str] = None
    #  Playbill
    image: Optional[str] = None
    #  DownloaderHash
    download_hash: Optional[str] = None
    #  Seed name
    torrent_name: Optional[str] = None
    #  Seed description
    torrent_description: Optional[str] = None
    #  Website
    torrent_site: Optional[str] = None
    #  Download users
    userid: Optional[str] = None
    #  Download channels
    channel: Optional[str] = None
    #  Creation time
    date: Optional[str] = None
    #  Note
    note: Optional[str] = None

    class Config:
        orm_mode = True


class TransferHistory(BaseModel):
    # ID
    id: int
    #  Source catalog
    src: Optional[str] = None
    #  Destination catalog
    dest: Optional[str] = None
    #  Transfer mode
    mode: Optional[str] = None
    #  Typology： Cinematic、 Dramas
    type: Optional[str] = None
    #  Secondary classification
    category: Optional[str] = None
    #  Caption
    title: Optional[str] = None
    #  Particular year
    year: Optional[str] = None
    # TMDBID
    tmdbid: Optional[int] = None
    # IMDBID
    imdbid: Optional[str] = None
    # TVDBID
    tvdbid: Optional[int] = None
    #  Douban, prc social networking websiteID
    doubanid: Optional[str] = None
    #  Classifier for seasonal crop yield or seasons of a tv seriesSxx
    seasons: Optional[str] = None
    #  Classifier for sections of a tv series e.g. episodeExx
    episodes: Optional[str] = None
    #  Playbill
    image: Optional[str] = None
    #  DownloaderHash
    download_hash: Optional[str] = None
    #  State of affairs 1- Successes，0- Fail (e.g. experiments)
    status: bool = True
    #  Reasons for failure
    errmsg: Optional[str] = None
    #  Dates
    date: Optional[str] = None

    class Config:
        orm_mode = True
