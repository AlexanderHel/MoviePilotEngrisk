import json
from typing import List, Any

from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app import schemas
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.security import verify_token
from app.db import get_db
from app.db.models.subscribe import Subscribe
from app.db.models.user import User
from app.db.userauth import get_current_active_user
from app.scheduler import Scheduler
from app.schemas.types import MediaType

router = APIRouter()


def start_subscribe_add(db: Session, title: str, year: str,
                        mtype: MediaType, tmdbid: int, season: int, username: str):
    """
    Starting a subscription task
    """
    SubscribeChain(db).add(title=title, year=year,
                           mtype=mtype, tmdbid=tmdbid, season=season, username=username)


@router.get("/", summary=" All subscriptions", response_model=List[schemas.Subscribe])
def read_subscribes(
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Check all subscriptions
    """
    subscribes = Subscribe.list(db)
    for subscribe in subscribes:
        if subscribe.sites:
            subscribe.sites = json.loads(subscribe.sites)
    return subscribes


@router.post("/", summary=" Add subscription", response_model=schemas.Response)
def create_subscribe(
        *,
        subscribe_in: schemas.Subscribe,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Add subscription
    """
    #  Type conversion
    if subscribe_in.type:
        mtype = MediaType(subscribe_in.type)
    else:
        mtype = None
    #  Title conversion
    if subscribe_in.name:
        title = subscribe_in.name
    else:
        title = None
    sid, message = SubscribeChain(db).add(mtype=mtype,
                                          title=title,
                                          year=subscribe_in.year,
                                          tmdbid=subscribe_in.tmdbid,
                                          season=subscribe_in.season,
                                          doubanid=subscribe_in.doubanid,
                                          username=current_user.name,
                                          best_version=subscribe_in.best_version,
                                          exist_ok=True)
    return schemas.Response(success=True if sid else False, message=message, data={
        "id": sid
    })


@router.put("/", summary=" Update subscription", response_model=schemas.Response)
def update_subscribe(
        *,
        subscribe_in: schemas.Subscribe,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    Update subscription information
    """
    subscribe = Subscribe.get(db, subscribe_in.id)
    if not subscribe:
        return schemas.Response(success=False, message=" Subscription does not exist")
    if subscribe_in.sites is not None:
        subscribe_in.sites = json.dumps(subscribe_in.sites)
    #  Avoid updating missing episodes
    subscribe_dict = subscribe_in.dict()
    if not subscribe_in.lack_episode:
        #  When there are no missing episodes， Missing episodes cleared， Avoid updating to0
        subscribe_dict.pop("lack_episode")
    elif subscribe_in.total_episode:
        #  When the total number of episodes increases， The number of missing episodes should also be increased
        if subscribe_in.total_episode > (subscribe.total_episode or 0):
            subscribe_dict["lack_episode"] = (subscribe.lack_episode
                                              + (subscribe_in.total_episode
                                                 - (subscribe.total_episode or 0)))
    subscribe.update(db, subscribe_dict)
    return schemas.Response(success=True)


@router.get("/media/{mediaid}", summary=" Inquiry subscription", response_model=schemas.Subscribe)
def subscribe_mediaid(
        mediaid: str,
        season: int = None,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    According toTMDBID Or doubanID Inquiry subscription tmdb:/douban:
    """
    if mediaid.startswith("tmdb:"):
        tmdbid = mediaid[5:]
        if not tmdbid or not str(tmdbid).isdigit():
            return Subscribe()
        result = Subscribe.exists(db, int(tmdbid), season)
    elif mediaid.startswith("douban:"):
        doubanid = mediaid[7:]
        if not doubanid:
            return Subscribe()
        result = Subscribe.get_by_doubanid(db, doubanid)
    else:
        result = None
    if result and result.sites:
        result.sites = json.loads(result.sites)

    return result if result else Subscribe()


@router.get("/refresh", summary=" Refresh subscription", response_model=schemas.Response)
def refresh_subscribes(
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Refresh all subscriptions
    """
    Scheduler().start("subscribe_refresh")
    return schemas.Response(success=True)


@router.get("/check", summary=" Refresh subscription TMDB  Text", response_model=schemas.Response)
def check_subscribes(
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Refresh subscription TMDB  Text
    """
    Scheduler().start("subscribe_tmdb")
    return schemas.Response(success=True)


@router.get("/search", summary=" Search all subscriptions", response_model=schemas.Response)
def search_subscribes(
        background_tasks: BackgroundTasks,
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Search all subscriptions
    """
    background_tasks.add_task(
        Scheduler().start,
        job_id="subscribe_search",
        sid=None,
        state='R',
        manual=True
    )
    return schemas.Response(success=True)


@router.get("/search/{subscribe_id}", summary=" Search subscriptions", response_model=schemas.Response)
def search_subscribe(
        subscribe_id: int,
        background_tasks: BackgroundTasks,
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Search subscriptions by subscription number
    """
    background_tasks.add_task(
        Scheduler().start,
        job_id="subscribe_search",
        sid=subscribe_id,
        state=None,
        manual=True
    )
    return schemas.Response(success=True)


@router.get("/{subscribe_id}", summary=" Subscription details", response_model=schemas.Subscribe)
def read_subscribe(
        subscribe_id: int,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Search subscription information by subscription number
    """
    subscribe = Subscribe.get(db, subscribe_id)
    if subscribe.sites:
        subscribe.sites = json.loads(subscribe.sites)
    return subscribe


@router.delete("/media/{mediaid}", summary=" Delete subscription", response_model=schemas.Response)
def delete_subscribe_by_mediaid(
        mediaid: str,
        season: int = None,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    According toTMDBID Or doubanID Delete subscription tmdb:/douban:
    """
    if mediaid.startswith("tmdb:"):
        tmdbid = mediaid[5:]
        if not tmdbid or not str(tmdbid).isdigit():
            return schemas.Response(success=False)
        Subscribe().delete_by_tmdbid(db, int(tmdbid), season)
    elif mediaid.startswith("douban:"):
        doubanid = mediaid[7:]
        if not doubanid:
            return schemas.Response(success=False)
        Subscribe().delete_by_doubanid(db, doubanid)

    return schemas.Response(success=True)


@router.delete("/{subscribe_id}", summary=" Delete subscription", response_model=schemas.Response)
def delete_subscribe(
        subscribe_id: int,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    Delete subscription information
    """
    Subscribe.delete(db, subscribe_id)
    return schemas.Response(success=True)


@router.post("/seerr", summary="OverSeerr/JellySeerr Notification subscription", response_model=schemas.Response)
async def seerr_subscribe(request: Request, background_tasks: BackgroundTasks,
                          db: Session = Depends(get_db),
                          authorization: str = Header(None)) -> Any:
    """
    Jellyseerr/Overseerr Subscribe to
    """
    if not authorization or authorization != settings.API_TOKEN:
        raise HTTPException(
            status_code=400,
            detail=" Authorization failure",
        )
    req_json = await request.json()
    if not req_json:
        raise HTTPException(
            status_code=500,
            detail=" The message content is empty",
        )
    notification_type = req_json.get("notification_type")
    if notification_type not in ["MEDIA_APPROVED", "MEDIA_AUTO_APPROVED"]:
        return schemas.Response(success=False, message=" Unsupported notification types")
    subject = req_json.get("subject")
    media_type = MediaType.MOVIE if req_json.get("media", {}).get("media_type") == "movie" else MediaType.TV
    tmdbId = req_json.get("media", {}).get("tmdbId")
    if not media_type or not tmdbId or not subject:
        return schemas.Response(success=False, message=" Incorrect request parameters")
    user_name = req_json.get("request", {}).get("requestedBy_username")
    #  Add subscription
    if media_type == MediaType.MOVIE:
        background_tasks.add_task(start_subscribe_add,
                                  db=db,
                                  mtype=media_type,
                                  tmdbid=tmdbId,
                                  title=subject,
                                  year="",
                                  season=0,
                                  username=user_name)
    else:
        seasons = []
        for extra in req_json.get("extra", []):
            if extra.get("name") == "Requested Seasons":
                seasons = [int(str(sea).strip()) for sea in extra.get("value").split(", ") if str(sea).isdigit()]
                break
        for season in seasons:
            background_tasks.add_task(start_subscribe_add,
                                      db=db,
                                      mtype=media_type,
                                      tmdbid=tmdbId,
                                      title=subject,
                                      year="",
                                      season=season,
                                      username=user_name)

    return schemas.Response(success=True)
