from typing import List, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import schemas
from app.chain.douban import DoubanChain
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.security import verify_token
from app.db import get_db
from app.schemas import MediaType
from app.utils.http import RequestUtils

router = APIRouter()


@router.get("/img/{imgurl:path}", summary=" Douban photo agency")
def douban_img(imgurl: str) -> Any:
    """
    Douban photo agency
    """
    if not imgurl:
        return None
    response = RequestUtils(headers={
        'Referer': "https://movie.douban.com/"
    }, ua=settings.USER_AGENT).get_res(url=imgurl)
    if response:
        return Response(content=response.content, media_type="image/jpeg")
    return None


@router.get("/recognize/{doubanid}", summary=" Douban, prc social networking websiteID Recognize", response_model=schemas.Context)
def recognize_doubanid(doubanid: str,
                       db: Session = Depends(get_db),
                       _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According to doubanID Identify media messages
    """
    #  Identify media messages
    context = DoubanChain(db).recognize_by_doubanid(doubanid=doubanid)
    if context:
        return context.to_dict()
    else:
        return schemas.Context()


@router.get("/showing", summary=" Douban is now in theaters", response_model=List[schemas.MediaInfo])
def movie_showing(page: int = 1,
                  count: int = 30,
                  db: Session = Depends(get_db),
                  _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Browse douban in theaters
    """
    movies = DoubanChain(db).movie_showing(page=page, count=count)
    if not movies:
        return []
    medias = [MediaInfo(douban_info=movie) for movie in movies]
    return [media.to_dict() for media in medias]


@router.get("/movies", summary=" Douban movie", response_model=List[schemas.MediaInfo])
def douban_movies(sort: str = "R",
                  tags: str = "",
                  page: int = 1,
                  count: int = 30,
                  db: Session = Depends(get_db),
                  _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Browse douban movie information
    """
    movies = DoubanChain(db).douban_discover(mtype=MediaType.MOVIE,
                                             sort=sort, tags=tags, page=page, count=count)
    if not movies:
        return []
    medias = [MediaInfo(douban_info=movie) for movie in movies]
    return [media.to_dict() for media in medias
            if media.poster_path
            and "movie_large.jpg" not in media.poster_path
            and "tv_normal.png" not in media.poster_path]


@router.get("/tvs", summary=" Douban episodes", response_model=List[schemas.MediaInfo])
def douban_tvs(sort: str = "R",
               tags: str = "",
               page: int = 1,
               count: int = 30,
               db: Session = Depends(get_db),
               _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Browse douban episode information
    """
    tvs = DoubanChain(db).douban_discover(mtype=MediaType.TV,
                                          sort=sort, tags=tags, page=page, count=count)
    if not tvs:
        return []
    medias = [MediaInfo(douban_info=tv) for tv in tvs]
    return [media.to_dict() for media in medias
            if media.poster_path
            and "movie_large.jpg" not in media.poster_path
            and "tv_normal.jpg" not in media.poster_path
            and "tv_large.jpg" not in media.poster_path]


@router.get("/movie_top250", summary=" Douban movieTOP250", response_model=List[schemas.MediaInfo])
def movie_top250(page: int = 1,
                 count: int = 30,
                 db: Session = Depends(get_db),
                 _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Browse douban episode information
    """
    movies = DoubanChain(db).movie_top250(page=page, count=count)
    return [MediaInfo(douban_info=movie).to_dict() for movie in movies]


@router.get("/tv_weekly_chinese", summary=" Douban weekly list of domestic dramas", response_model=List[schemas.MediaInfo])
def tv_weekly_chinese(page: int = 1,
                      count: int = 30,
                      db: Session = Depends(get_db),
                      _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    China weekly drama word of mouth ranking
    """
    tvs = DoubanChain(db).tv_weekly_chinese(page=page, count=count)
    return [MediaInfo(douban_info=tv).to_dict() for tv in tvs]


@router.get("/tv_weekly_global", summary=" Douban global drama weekly list", response_model=List[schemas.MediaInfo])
def tv_weekly_global(page: int = 1,
                     count: int = 30,
                     db: Session = Depends(get_db),
                     _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Global weekly drama word of mouth
    """
    tvs = DoubanChain(db).tv_weekly_global(page=page, count=count)
    return [MediaInfo(douban_info=tv).to_dict() for tv in tvs]


@router.get("/tv_animation", summary="Douban animation series", response_model=List[schemas.MediaInfo])
def tv_animation(page: int = 1,
                 count: int = 30,
                 db: Session = Depends(get_db),
                 _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Popular animated series
    """
    tvs = DoubanChain(db).tv_animation(page=page, count=count)
    return [MediaInfo(douban_info=tv).to_dict() for tv in tvs]


@router.get("/{doubanid}", summary=" Check douban details", response_model=schemas.MediaInfo)
def douban_info(doubanid: str,
                db: Session = Depends(get_db),
                _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According to doubanID Check douban media information
    """
    doubaninfo = DoubanChain(db).douban_info(doubanid=doubanid)
    if doubaninfo:
        return MediaInfo(douban_info=doubaninfo).to_dict()
    else:
        return schemas.MediaInfo()
