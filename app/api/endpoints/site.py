from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.background import BackgroundTasks

from app import schemas
from app.chain.site import SiteChain
from app.chain.torrents import TorrentsChain
from app.core.event import EventManager
from app.core.security import verify_token
from app.db import get_db
from app.db.models.site import Site
from app.db.models.siteicon import SiteIcon
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.sites import SitesHelper
from app.scheduler import Scheduler
from app.schemas.types import SystemConfigKey, EventType
from app.utils.string import StringUtils

router = APIRouter()


@router.get("/", summary=" All sites", response_model=List[schemas.Site])
def read_sites(db: Session = Depends(get_db),
               _: schemas.TokenPayload = Depends(verify_token)) -> List[dict]:
    """
    Get site list
    """
    return Site.list_order_by_pri(db)


@router.post("/", summary=" New sites", response_model=schemas.Response)
def add_site(
        *,
        db: Session = Depends(get_db),
        site_in: schemas.Site,
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    New sites
    """
    if not site_in.url:
        return schemas.Response(success=False, message=" Site address cannot be empty")
    domain = StringUtils.get_url_domain(site_in.url)
    site_info = SitesHelper().get_indexer(domain)
    if not site_info:
        return schemas.Response(success=False, message=" This site does not support")
    if Site.get_by_domain(db, domain):
        return schemas.Response(success=False, message=f"{domain}  Site exists")
    #  Save site information
    site_in.domain = domain
    site_in.name = site_info.get("name")
    site_in.id = None
    site = Site(**site_in.dict())
    site.create(db)
    return schemas.Response(success=True)


@router.put("/", summary=" Updating the site", response_model=schemas.Response)
def update_site(
        *,
        db: Session = Depends(get_db),
        site_in: schemas.Site,
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    Update site information
    """
    site = Site.get(db, site_in.id)
    if not site:
        return schemas.Response(success=False, message=" Site does not exist")
    site.update(db, site_in.dict())
    return schemas.Response(success=True)


@router.delete("/{site_id}", summary=" Delete site", response_model=schemas.Response)
def delete_site(
        site_id: int,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    Delete site
    """
    Site.delete(db, site_id)
    #  Plugin site removal
    EventManager().send_event(EventType.SiteDeleted,
                              {
                                  "site_id": site_id
                              })
    return schemas.Response(success=True)


@router.get("/cookiecloud", summary="CookieCloud Synchronization", response_model=schemas.Response)
def cookie_cloud_sync(background_tasks: BackgroundTasks,
                      _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    (of a computer) runCookieCloud Synchronize site information
    """
    background_tasks.add_task(Scheduler().start, job_id="cookiecloud")
    return schemas.Response(success=True, message="CookieCloud Synchronization task started！")


@router.get("/reset", summary=" Reset site", response_model=schemas.Response)
def cookie_cloud_sync(db: Session = Depends(get_db),
                      _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Empty all site data and resynchronizeCookieCloud Site information
    """
    Site.reset(db)
    SystemConfigOper().set(SystemConfigKey.IndexerSites, [])
    SystemConfigOper().set(SystemConfigKey.RssSites, [])
    #  Start timing service
    Scheduler().start("cookiecloud", manual=True)
    #  Plugin site removal
    EventManager().send_event(EventType.SiteDeleted,
                              {
                                  "site_id": None
                              })
    return schemas.Response(success=True, message=" Site has been reset！")


@router.get("/cookie/{site_id}", summary=" Updating the siteCookie&UA", response_model=schemas.Response)
def update_cookie(
        site_id: int,
        username: str,
        password: str,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Updating the site with user passwordsCookie
    """
    #  Search site
    site_info = Site.get(db, site_id)
    if not site_info:
        raise HTTPException(
            status_code=404,
            detail=f" Website {site_id}  Non-existent！",
        )
    #  UpdateCookie
    state, message = SiteChain(db).update_cookie(site_info=site_info,
                                                 username=username,
                                                 password=password)
    return schemas.Response(success=state, message=message)


@router.get("/test/{site_id}", summary=" Connection test", response_model=schemas.Response)
def test_site(site_id: int,
              db: Session = Depends(get_db),
              _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Test site availability
    """
    site = Site.get(db, site_id)
    if not site:
        raise HTTPException(
            status_code=404,
            detail=f" Website {site_id}  Non-existent",
        )
    status, message = SiteChain(db).test(site.domain)
    return schemas.Response(success=status, message=message)


@router.get("/icon/{site_id}", summary=" Site icon", response_model=schemas.Response)
def site_icon(site_id: int,
              db: Session = Depends(get_db),
              _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Get site icon：base64 Orurl
    """
    site = Site.get(db, site_id)
    if not site:
        raise HTTPException(
            status_code=404,
            detail=f" Website {site_id}  Non-existent",
        )
    icon = SiteIcon.get_by_domain(db, site.domain)
    if not icon:
        return schemas.Response(success=False, message=" Site icon does not exist！")
    return schemas.Response(success=True, data={
        "icon": icon.base64 if icon.base64 else icon.url
    })


@router.get("/resource/{site_id}", summary=" Site resources", response_model=List[schemas.TorrentInfo])
def site_resource(site_id: int,
                  db: Session = Depends(get_db),
                  _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Browse site resources
    """
    site = Site.get(db, site_id)
    if not site:
        raise HTTPException(
            status_code=404,
            detail=f" Website {site_id}  Non-existent",
        )
    torrents = TorrentsChain().browse(domain=site.domain)
    if not torrents:
        return []
    return [torrent.to_dict() for torrent in torrents]


@router.get("/domain/{site_url}", summary=" Site details", response_model=schemas.Site)
def read_site_by_domain(
        site_url: str,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    Get site information by domain name
    """
    domain = StringUtils.get_url_domain(site_url)
    site = Site.get_by_domain(db, domain)
    if not site:
        raise HTTPException(
            status_code=404,
            detail=f" Website {domain}  Non-existent",
        )
    return site


@router.get("/rss", summary=" All subscription sites", response_model=List[schemas.Site])
def read_rss_sites(db: Session = Depends(get_db)) -> List[dict]:
    """
    Get site list
    """
    #  Selectedrss Website
    selected_sites = SystemConfigOper().get(SystemConfigKey.RssSites) or []
    #  All sites
    all_site = Site.list_order_by_pri(db)
    if not selected_sites or not all_site:
        return []

    #  Selectedrss Website
    rss_sites = [site for site in all_site if site and site.id in selected_sites]
    return rss_sites


@router.get("/{site_id}", summary=" Site details", response_model=schemas.Site)
def read_site(
        site_id: int,
        db: Session = Depends(get_db),
        _: schemas.TokenPayload = Depends(verify_token)
) -> Any:
    """
    Pass (a bill or inspection etc)ID Get site information
    """
    site = Site.get(db, site_id)
    if not site:
        raise HTTPException(
            status_code=404,
            detail=f" Website {site_id}  Non-existent",
        )
    return site
