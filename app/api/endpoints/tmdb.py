from typing import List, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.tmdb import TmdbChain
from app.core.context import MediaInfo
from app.core.security import verify_token
from app.db import get_db
from app.schemas.types import MediaType

router = APIRouter()


@router.get("/seasons/{tmdbid}", summary="TMDB All seasons", response_model=List[schemas.TmdbSeason])
def tmdb_seasons(tmdbid: int, db: Session = Depends(get_db),
                 _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According toTMDBID Consult (a document etc)themoviedb All season information
    """
    seasons_info = TmdbChain(db).tmdb_seasons(tmdbid=tmdbid)
    if not seasons_info:
        return []
    else:
        return seasons_info


@router.get("/similar/{tmdbid}/{type_name}", summary=" Similar movies/ Dramas", response_model=List[schemas.MediaInfo])
def tmdb_similar(tmdbid: int,
                 type_name: str,
                 db: Session = Depends(get_db),
                 _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According toTMDBID Search for similar movies/ Dramas，type_name:  Cinematic/ Dramas
    """
    mediatype = MediaType(type_name)
    if mediatype == MediaType.MOVIE:
        tmdbinfos = TmdbChain(db).movie_similar(tmdbid=tmdbid)
    elif mediatype == MediaType.TV:
        tmdbinfos = TmdbChain(db).tv_similar(tmdbid=tmdbid)
    else:
        return []
    if not tmdbinfos:
        return []
    else:
        return [MediaInfo(tmdb_info=tmdbinfo).to_dict() for tmdbinfo in tmdbinfos]


@router.get("/recommend/{tmdbid}/{type_name}", summary=" Recommended movies/ Dramas", response_model=List[schemas.MediaInfo])
def tmdb_recommend(tmdbid: int,
                   type_name: str,
                   db: Session = Depends(get_db),
                   _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According toTMDBID Check recommended movies/ Dramas，type_name:  Cinematic/ Dramas
    """
    mediatype = MediaType(type_name)
    if mediatype == MediaType.MOVIE:
        tmdbinfos = TmdbChain(db).movie_recommend(tmdbid=tmdbid)
    elif mediatype == MediaType.TV:
        tmdbinfos = TmdbChain(db).tv_recommend(tmdbid=tmdbid)
    else:
        return []
    if not tmdbinfos:
        return []
    else:
        return [MediaInfo(tmdb_info=tmdbinfo).to_dict() for tmdbinfo in tmdbinfos]


@router.get("/credits/{tmdbid}/{type_name}", summary=" Dramatis personae", response_model=List[schemas.TmdbPerson])
def tmdb_credits(tmdbid: int,
                 type_name: str,
                 page: int = 1,
                 db: Session = Depends(get_db),
                 _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According toTMDBID Check the cast，type_name:  Cinematic/ Dramas
    """
    mediatype = MediaType(type_name)
    if mediatype == MediaType.MOVIE:
        tmdbinfos = TmdbChain(db).movie_credits(tmdbid=tmdbid, page=page)
    elif mediatype == MediaType.TV:
        tmdbinfos = TmdbChain(db).tv_credits(tmdbid=tmdbid, page=page)
    else:
        return []
    if not tmdbinfos:
        return []
    else:
        return [schemas.TmdbPerson(**tmdbinfo) for tmdbinfo in tmdbinfos]


@router.get("/person/{person_id}", summary=" Character details", response_model=schemas.TmdbPerson)
def tmdb_person(person_id: int,
                db: Session = Depends(get_db),
                _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Character-basedID Check character details
    """
    tmdbinfo = TmdbChain(db).person_detail(person_id=person_id)
    if not tmdbinfo:
        return schemas.TmdbPerson()
    else:
        return schemas.TmdbPerson(**tmdbinfo)


@router.get("/person/credits/{person_id}", summary=" Characters", response_model=List[schemas.MediaInfo])
def tmdb_person_credits(person_id: int,
                        page: int = 1,
                        db: Session = Depends(get_db),
                        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Character-basedID Enquire about a person's acting credits
    """
    tmdbinfo = TmdbChain(db).person_credits(person_id=person_id, page=page)
    if not tmdbinfo:
        return []
    else:
        return [MediaInfo(tmdb_info=tmdbinfo).to_dict() for tmdbinfo in tmdbinfo]


@router.get("/movies", summary="TMDB Cinematic", response_model=List[schemas.MediaInfo])
def tmdb_movies(sort_by: str = "popularity.desc",
                with_genres: str = "",
                with_original_language: str = "",
                page: int = 1,
                db: Session = Depends(get_db),
                _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Skim overTMDB Movie information
    """
    movies = TmdbChain(db).tmdb_discover(mtype=MediaType.MOVIE,
                                         sort_by=sort_by,
                                         with_genres=with_genres,
                                         with_original_language=with_original_language,
                                         page=page)
    if not movies:
        return []
    return [MediaInfo(tmdb_info=movie).to_dict() for movie in movies]


@router.get("/tvs", summary="TMDB Episode", response_model=List[schemas.MediaInfo])
def tmdb_tvs(sort_by: str = "popularity.desc",
             with_genres: str = "",
             with_original_language: str = "",
             page: int = 1,
             db: Session = Depends(get_db),
             _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Skim overTMDB Episode information
    """
    tvs = TmdbChain(db).tmdb_discover(mtype=MediaType.TV,
                                      sort_by=sort_by,
                                      with_genres=with_genres,
                                      with_original_language=with_original_language,
                                      page=page)
    if not tvs:
        return []
    return [MediaInfo(tmdb_info=tv).to_dict() for tv in tvs]


@router.get("/trending", summary="TMDB Fashionable trend", response_model=List[schemas.MediaInfo])
def tmdb_trending(page: int = 1,
                  db: Session = Depends(get_db),
                  _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Skim overTMDB Episode information
    """
    infos = TmdbChain(db).tmdb_trending(page=page)
    if not infos:
        return []
    return [MediaInfo(tmdb_info=info).to_dict() for info in infos]


@router.get("/{tmdbid}/{season}", summary="TMDB All episodes of season", response_model=List[schemas.TmdbEpisode])
def tmdb_season_episodes(tmdbid: int, season: int,
                         db: Session = Depends(get_db),
                         _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According toTMDBID Query all letters for a particular season
    """
    episodes_info = TmdbChain(db).tmdb_episodes(tmdbid=tmdbid, season=season)
    if not episodes_info:
        return []
    else:
        return episodes_info
