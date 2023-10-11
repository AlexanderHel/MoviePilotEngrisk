from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.chain.douban import DoubanChain
from app.chain.download import DownloadChain
from app.chain.media import MediaChain
from app.core.context import MediaInfo, Context, TorrentInfo
from app.core.metainfo import MetaInfo
from app.core.security import verify_token
from app.db import get_db
from app.schemas import NotExistMediaInfo, MediaType

router = APIRouter()


@router.get("/", summary=" Downloading", response_model=List[schemas.DownloadingTorrent])
def read_downloading(
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query tasks being downloaded
    """
    return DownloadChain(db).downloading()


@router.post("/", summary=" Add download", response_model=schemas.Response)
def add_downloading(
        media_in: schemas.MediaInfo,
        torrent_in: schemas.TorrentInfo,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Add download tasks
    """
    #  Metadata
    metainfo = MetaInfo(title=torrent_in.title, subtitle=torrent_in.description)
    #  Media information
    mediainfo = MediaInfo()
    mediainfo.from_dict(media_in.dict())
    #  Seed information
    torrentinfo = TorrentInfo()
    torrentinfo.from_dict(torrent_in.dict())
    #  (textual) context
    context = Context(
        meta_info=metainfo,
        media_info=mediainfo,
        torrent_info=torrentinfo
    )
    did = DownloadChain(db).download_single(context=context)
    return schemas.Response(success=True if did else False, data={
        "download_id": did
    })


@router.post("/notexists", summary=" Query missing media information", response_model=List[NotExistMediaInfo])
def exists(media_in: schemas.MediaInfo,
           db: Session = Depends(get_db),
           _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query missing media information
    """
    #  Media information
    mediainfo = MediaInfo()
    meta = MetaInfo(title=media_in.title)
    if media_in.tmdb_id:
        mediainfo.from_dict(media_in.dict())
    elif media_in.douban_id:
        context = DoubanChain(db).recognize_by_doubanid(doubanid=media_in.douban_id)
        if context:
            mediainfo = context.media_info
            meta = context.meta_info
    else:
        context = MediaChain(db).recognize_by_title(title=f"{media_in.title} {media_in.year}")
        if context:
            mediainfo = context.media_info
            meta = context.meta_info
    #  Query missing information
    if not mediainfo or not mediainfo.tmdb_id:
        raise HTTPException(status_code=404, detail=" Media messages do not exist")
    exist_flag, no_exists = DownloadChain(db).get_no_exists_info(meta=meta, mediainfo=mediainfo)
    if mediainfo.type == MediaType.MOVIE:
        #  Return to empty list when movie already exists， Returns an empty list of images when present
        return [] if exist_flag else [NotExistMediaInfo()]
    elif no_exists and no_exists.get(mediainfo.tmdb_id):
        #  Tv series returns missing episodes
        return list(no_exists.get(mediainfo.tmdb_id).values())
    return []


@router.get("/start/{hashString}", summary=" Commencement of mission", response_model=schemas.Response)
def start_downloading(
        hashString: str,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Keru download tasks
    """
    ret = DownloadChain(db).set_downloading(hashString, "start")
    return schemas.Response(success=True if ret else False)


@router.get("/stop/{hashString}", summary=" Suspension of the mandate", response_model=schemas.Response)
def stop_downloading(
        hashString: str,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Controlling download tasks
    """
    ret = DownloadChain(db).set_downloading(hashString, "stop")
    return schemas.Response(success=True if ret else False)


@router.delete("/{hashString}", summary=" Delete download tasks", response_model=schemas.Response)
def remove_downloading(
        hashString: str,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Controlling download tasks
    """
    ret = DownloadChain(db).remove_downloading(hashString)
    return schemas.Response(success=True if ret else False)
