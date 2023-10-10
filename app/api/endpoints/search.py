from typing import List, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.douban import DoubanChain
from app.chain.search import SearchChain
from app.core.security import verify_token
from app.db import get_db
from app.schemas.types import MediaType

router = APIRouter()


@router.get("/last", summary=" Query search results", response_model=List[schemas.Context])
async def search_latest(db: Session = Depends(get_db),
                        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query search results
    """
    torrents = SearchChain(db).last_search_results()
    return [torrent.to_dict() for torrent in torrents]


@router.get("/media/{mediaid}", summary=" Precise search of resources", response_model=List[schemas.Context])
def search_by_tmdbid(mediaid: str,
                     mtype: str = None,
                     area: str = "title",
                     db: Session = Depends(get_db),
                     _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According toTMDBID/ Douban, prc social networking websiteID Accurate search of site resources tmdb:/douban:/
    """
    if mediaid.startswith("tmdb:"):
        tmdbid = int(mediaid.replace("tmdb:", ""))
        if mtype:
            mtype = MediaType(mtype)
        torrents = SearchChain(db).search_by_tmdbid(tmdbid=tmdbid, mtype=mtype, area=area)
    elif mediaid.startswith("douban:"):
        doubanid = mediaid.replace("douban:", "")
        #  Recognizing doujinshi information
        context = DoubanChain(db).recognize_by_doubanid(doubanid)
        if not context or not context.media_info or not context.media_info.tmdb_id:
            return []
        torrents = SearchChain(db).search_by_tmdbid(tmdbid=context.media_info.tmdb_id,
                                                    mtype=context.media_info.type,
                                                    area=area)
    else:
        return []
    return [torrent.to_dict() for torrent in torrents]


@router.get("/title", summary=" Fuzzy search resources", response_model=List[schemas.TorrentInfo])
async def search_by_title(keyword: str = None,
                          page: int = 0,
                          site: int = None,
                          db: Session = Depends(get_db),
                          _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Fuzzy search for site resources by name， Pagination support， Empty keywords are back to homepage resources
    """
    torrents = SearchChain(db).search_by_title(title=keyword, page=page, site=site)
    return [torrent.to_dict() for torrent in torrents]
