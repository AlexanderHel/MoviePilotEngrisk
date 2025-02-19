from typing import Any, List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.media import MediaChain
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.metainfo import MetaInfo
from app.db import get_db
from app.db.models.subscribe import Subscribe
from app.schemas import RadarrMovie, SonarrSeries
from app.schemas.types import MediaType
from version import APP_VERSION

arr_router = APIRouter(tags=['servarr'])


@arr_router.get("/system/status", summary=" System status")
def arr_system_status(apikey: str) -> Any:
    """
    Analog (device, as opposed digital)Radarr、Sonarr System status
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    return {
        "appName": "MoviePilot",
        "instanceName": "moviepilot",
        "version": APP_VERSION,
        "buildTime": "",
        "isDebug": False,
        "isProduction": True,
        "isAdmin": True,
        "isUserInteractive": True,
        "startupPath": "/app",
        "appData": "/config",
        "osName": "debian",
        "osVersion": "",
        "isNetCore": True,
        "isLinux": True,
        "isOsx": False,
        "isWindows": False,
        "isDocker": True,
        "mode": "console",
        "branch": "main",
        "databaseType": "sqLite",
        "databaseVersion": {
            "major": 0,
            "minor": 0,
            "build": 0,
            "revision": 0,
            "majorRevision": 0,
            "minorRevision": 0
        },
        "authentication": "none",
        "migrationVersion": 0,
        "urlBase": "",
        "runtimeVersion": {
            "major": 0,
            "minor": 0,
            "build": 0,
            "revision": 0,
            "majorRevision": 0,
            "minorRevision": 0
        },
        "runtimeName": "",
        "startTime": "",
        "packageVersion": "",
        "packageAuthor": "jxxghp",
        "packageUpdateMechanism": "builtIn",
        "packageUpdateMechanismMessage": ""
    }


@arr_router.get("/qualityProfile", summary=" Quality configuration")
def arr_qualityProfile(apikey: str) -> Any:
    """
    Analog (device, as opposed digital)Radarr、Sonarr Quality configuration
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    return [
        {
            "id": 1,
            "name": " Default (setting)",
            "upgradeAllowed": True,
            "cutoff": 0,
            "items": [
                {
                    "id": 0,
                    "name": " Default (setting)",
                    "quality": {
                        "id": 0,
                        "name": " Default (setting)",
                        "source": "0",
                        "resolution": 0
                    },
                    "items": [
                        "string"
                    ],
                    "allowed": True
                }
            ],
            "minFormatScore": 0,
            "cutoffFormatScore": 0,
            "formatItems": [
                {
                    "id": 0,
                    "format": 0,
                    "name": " Default (setting)",
                    "score": 0
                }
            ]
        }
    ]


@arr_router.get("/rootfolder", summary=" Root directory")
def arr_rootfolder(apikey: str) -> Any:
    """
    Analog (device, as opposed digital)Radarr、Sonarr Root directory
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    return [
        {
            "id": 1,
            "path": "/" if not settings.LIBRARY_PATHS else str(settings.LIBRARY_PATHS[0]),
            "accessible": True,
            "freeSpace": 0,
            "unmappedFolders": []
        }
    ]


@arr_router.get("/tag", summary=" Tab (of a window) (computing)")
def arr_tag(apikey: str) -> Any:
    """
    Analog (device, as opposed digital)Radarr、Sonarr Tab (of a window) (computing)
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    return [
        {
            "id": 1,
            "label": " Default (setting)"
        }
    ]


@arr_router.get("/languageprofile", summary=" Multilingualism")
def arr_languageprofile(apikey: str) -> Any:
    """
    Analog (device, as opposed digital)Radarr、Sonarr Multilingualism
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    return [{
        "id": 1,
        "name": " Default (setting)",
        "upgradeAllowed": True,
        "cutoff": {
            "id": 1,
            "name": " Default (setting)"
        },
        "languages": [
            {
                "id": 1,
                "language": {
                    "id": 1,
                    "name": " Default (setting)"
                },
                "allowed": True
            }
        ]
    }]


@arr_router.get("/movie", summary=" All subscription movies", response_model=List[schemas.RadarrMovie])
def arr_movies(apikey: str, db: Session = Depends(get_db)) -> Any:
    """
    Consult (a document etc)Rardar Cinematic
    """
    """
    [
      {
        "id": 0,
        "title": "string",
        "originalTitle": "string",
        "originalLanguage": {
          "id": 0,
          "name": "string"
        },
        "secondaryYear": 0,
        "secondaryYearSourceId": 0,
        "sortTitle": "string",
        "sizeOnDisk": 0,
        "status": "tba",
        "overview": "string",
        "inCinemas": "2023-06-13T09:23:41.494Z",
        "physicalRelease": "2023-06-13T09:23:41.494Z",
        "digitalRelease": "2023-06-13T09:23:41.494Z",
        "physicalReleaseNote": "string",
        "images": [
          {
            "coverType": "unknown",
            "url": "string",
            "remoteUrl": "string"
          }
        ],
        "website": "string",
        "remotePoster": "string",
        "year": 0,
        "hasFile": true,
        "youTubeTrailerId": "string",
        "studio": "string",
        "path": "string",
        "qualityProfileId": 0,
        "monitored": true,
        "minimumAvailability": "tba",
        "isAvailable": true,
        "folderName": "string",
        "runtime": 0,
        "cleanTitle": "string",
        "imdbId": "string",
        "tmdbId": 0,
        "titleSlug": "string",
        "rootFolderPath": "string",
        "folder": "string",
        "certification": "string",
        "genres": [
          "string"
        ],
        "tags": [
          0
        ],
        "added": "2023-06-13T09:23:41.494Z",
        "addOptions": {
          "ignoreEpisodesWithFiles": true,
          "ignoreEpisodesWithoutFiles": true,
          "monitor": "movieOnly",
          "searchForMovie": true,
          "addMethod": "manual"
        },
        "popularity": 0
      }
    ]
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    #  Check all movie subscriptions
    result = []
    subscribes = Subscribe.list(db)
    for subscribe in subscribes:
        if subscribe.type != MediaType.MOVIE.value:
            continue
        result.append(RadarrMovie(
            id=subscribe.id,
            title=subscribe.name,
            year=subscribe.year,
            isAvailable=True,
            monitored=True,
            tmdbId=subscribe.tmdbid,
            imdbId=subscribe.imdbid,
            profileId=1,
            qualityProfileId=1,
            hasFile=False
        ))
    return result


@arr_router.get("/movie/lookup", summary=" Search for movies", response_model=List[schemas.RadarrMovie])
def arr_movie_lookup(apikey: str, term: str, db: Session = Depends(get_db)) -> Any:
    """
    Consult (a document etc)Rardar Cinematic term: `tmdb:${id}`
    Neither existence nor non-existence can return an error
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    tmdbid = term.replace("tmdb:", "")
    #  Search for media information
    mediainfo = MediaChain(db).recognize_media(mtype=MediaType.MOVIE, tmdbid=int(tmdbid))
    if not mediainfo:
        return [RadarrMovie()]
    #  Check if it already exists
    exists = MediaChain(db).media_exists(mediainfo=mediainfo)
    if not exists:
        #  File does not exist
        hasfile = False
    else:
        #  Documentation exists
        hasfile = True
    #  Check if you are subscribed
    subscribes = Subscribe.get_by_tmdbid(db, int(tmdbid))
    if subscribes:
        #  Subscribe toID
        subid = subscribes[0].id
        #  Subscribed
        monitored = True
    else:
        subid = None
        monitored = False

    return [RadarrMovie(
        id=subid,
        title=mediainfo.title,
        year=mediainfo.year,
        isAvailable=True,
        monitored=monitored,
        tmdbId=mediainfo.tmdb_id,
        imdbId=mediainfo.imdb_id,
        titleSlug=mediainfo.original_title,
        folderName=mediainfo.title_year,
        profileId=1,
        qualityProfileId=1,
        hasFile=hasfile
    )]


@arr_router.get("/movie/{mid}", summary=" Movie subscription details", response_model=schemas.RadarrMovie)
def arr_movie(apikey: str, mid: int, db: Session = Depends(get_db)) -> Any:
    """
    Consult (a document etc)Rardar Cinematic订阅
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    subscribe = Subscribe.get(db, mid)
    if subscribe:
        return RadarrMovie(
            id=subscribe.id,
            title=subscribe.name,
            year=subscribe.year,
            isAvailable=True,
            monitored=True,
            tmdbId=subscribe.tmdbid,
            imdbId=subscribe.imdbid,
            profileId=1,
            qualityProfileId=1,
            hasFile=False
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=" Movie not found！"
        )


@arr_router.post("/movie", summary=" Add movie subscription")
def arr_add_movie(apikey: str,
                  movie: RadarrMovie,
                  db: Session = Depends(get_db),
                  ) -> Any:
    """
    AdditionalRardar Movie subscription
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    #  Check if the subscription already exists
    subscribe = Subscribe.get_by_tmdbid(db, movie.tmdbId)
    if subscribe:
        return {
            "id": subscribe.id
        }
    #  Add subscription
    sid, message = SubscribeChain(db).add(title=movie.title,
                                          year=movie.year,
                                          mtype=MediaType.MOVIE,
                                          tmdbid=movie.tmdbId,
                                          userid="Seerr")
    if sid:
        return {
            "id": sid
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f" Failed to add subscription：{message}"
        )


@arr_router.delete("/movie/{mid}", summary=" Delete movie subscription", response_model=schemas.Response)
def arr_remove_movie(apikey: str, mid: int, db: Session = Depends(get_db)) -> Any:
    """
    RemovingRardar Movie subscription
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    subscribe = Subscribe.get(db, mid)
    if subscribe:
        subscribe.delete(db, mid)
        return schemas.Response(success=True)
    else:
        raise HTTPException(
            status_code=404,
            detail=" Movie not found！"
        )


@arr_router.get("/series", summary=" All episodes", response_model=List[schemas.SonarrSeries])
def arr_series(apikey: str, db: Session = Depends(get_db)) -> Any:
    """
    Consult (a document etc)Sonarr Episode
    """
    """
    [
      {
        "id": 0,
        "title": "string",
        "sortTitle": "string",
        "status": "continuing",
        "ended": true,
        "profileName": "string",
        "overview": "string",
        "nextAiring": "2023-06-13T09:08:17.624Z",
        "previousAiring": "2023-06-13T09:08:17.624Z",
        "network": "string",
        "airTime": "string",
        "images": [
          {
            "coverType": "unknown",
            "url": "string",
            "remoteUrl": "string"
          }
        ],
        "originalLanguage": {
          "id": 0,
          "name": "string"
        },
        "remotePoster": "string",
        "seasons": [
          {
            "seasonNumber": 0,
            "monitored": true,
            "statistics": {
              "nextAiring": "2023-06-13T09:08:17.624Z",
              "previousAiring": "2023-06-13T09:08:17.624Z",
              "episodeFileCount": 0,
              "episodeCount": 0,
              "totalEpisodeCount": 0,
              "sizeOnDisk": 0,
              "releaseGroups": [
                "string"
              ],
              "percentOfEpisodes": 0
            },
            "images": [
              {
                "coverType": "unknown",
                "url": "string",
                "remoteUrl": "string"
              }
            ]
          }
        ],
        "year": 0,
        "path": "string",
        "qualityProfileId": 0,
        "seasonFolder": true,
        "monitored": true,
        "useSceneNumbering": true,
        "runtime": 0,
        "tvdbId": 0,
        "tvRageId": 0,
        "tvMazeId": 0,
        "firstAired": "2023-06-13T09:08:17.624Z",
        "seriesType": "standard",
        "cleanTitle": "string",
        "imdbId": "string",
        "titleSlug": "string",
        "rootFolderPath": "string",
        "folder": "string",
        "certification": "string",
        "genres": [
          "string"
        ],
        "tags": [
          0
        ],
        "added": "2023-06-13T09:08:17.624Z",
        "addOptions": {
          "ignoreEpisodesWithFiles": true,
          "ignoreEpisodesWithoutFiles": true,
          "monitor": "unknown",
          "searchForMissingEpisodes": true,
          "searchForCutoffUnmetEpisodes": true
        },
        "ratings": {
          "votes": 0,
          "value": 0
        },
        "statistics": {
          "seasonCount": 0,
          "episodeFileCount": 0,
          "episodeCount": 0,
          "totalEpisodeCount": 0,
          "sizeOnDisk": 0,
          "releaseGroups": [
            "string"
          ],
          "percentOfEpisodes": 0
        },
        "episodesChanged": true
      }
    ]
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    #  Check all tv series subscriptions
    result = []
    subscribes = Subscribe.list(db)
    for subscribe in subscribes:
        if subscribe.type != MediaType.TV.value:
            continue
        result.append(SonarrSeries(
            id=subscribe.id,
            title=subscribe.name,
            seasonCount=1,
            seasons=[{
                "seasonNumber": subscribe.season,
                "monitored": True,
            }],
            remotePoster=subscribe.poster,
            year=subscribe.year,
            tmdbId=subscribe.tmdbid,
            tvdbId=subscribe.tvdbid,
            imdbId=subscribe.imdbid,
            profileId=1,
            languageProfileId=1,
            qualityProfileId=1,
            isAvailable=True,
            monitored=True,
            hasFile=False
        ))
    return result


@arr_router.get("/series/lookup", summary=" Search for episodes")
def arr_series_lookup(apikey: str, term: str, db: Session = Depends(get_db)) -> Any:
    """
    Consult (a document etc)Sonarr Episode term: `tvdb:${id}` title
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )

    #  GainTVDBID
    if not term.startswith("tvdb:"):
        mediainfo = MediaChain(db).recognize_media(meta=MetaInfo(term),
                                                   mtype=MediaType.TV)
        if not mediainfo:
            return [SonarrSeries()]
        tvdbid = mediainfo.tvdb_id
        if not tvdbid:
            return [SonarrSeries()]
    else:
        mediainfo = None
        tvdbid = int(term.replace("tvdb:", ""))

    #  Consult (a document etc)TVDB Text
    tvdbinfo = MediaChain(db).tvdb_info(tvdbid=tvdbid)
    if not tvdbinfo:
        return [SonarrSeries()]

    #  Quarterly information
    seas: List[int] = []
    sea_num = tvdbinfo.get('season')
    if sea_num:
        seas = list(range(1, int(sea_num) + 1))

    #  According toTVDB Search for media information
    if not mediainfo:
        mediainfo = MediaChain(db).recognize_media(meta=MetaInfo(tvdbinfo.get('seriesName')),
                                                   mtype=MediaType.TV)

    #  Query the existence of
    exists = MediaChain(db).media_exists(mediainfo)
    if exists:
        hasfile = True
    else:
        hasfile = False

    #  Check subscription information
    seasons: List[dict] = []
    subscribes = Subscribe.get_by_tmdbid(db, mediainfo.tmdb_id)
    if subscribes:
        #  Monitored
        monitored = True
        #  Monitored季
        sub_seas = [sub.season for sub in subscribes]
        for sea in seas:
            if sea in sub_seas:
                seasons.append({
                    "seasonNumber": sea,
                    "monitored": True,
                })
            else:
                seasons.append({
                    "seasonNumber": sea,
                    "monitored": False,
                })
        subid = subscribes[-1].id
    else:
        subid = None
        monitored = False
        for sea in seas:
            seasons.append({
                "seasonNumber": sea,
                "monitored": False,
            })

    return [SonarrSeries(
        id=subid,
        title=mediainfo.title,
        seasonCount=len(seasons),
        seasons=seasons,
        remotePoster=mediainfo.get_poster_image(),
        year=mediainfo.year,
        tmdbId=mediainfo.tmdb_id,
        tvdbId=mediainfo.tvdb_id,
        imdbId=mediainfo.imdb_id,
        profileId=1,
        languageProfileId=1,
        qualityProfileId=1,
        isAvailable=True,
        monitored=monitored,
        hasFile=hasfile
    )]


@arr_router.get("/series/{tid}", summary=" Episode details")
def arr_serie(apikey: str, tid: int, db: Session = Depends(get_db)) -> Any:
    """
    Consult (a document etc)Sonarr Episode
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    subscribe = Subscribe.get(db, tid)
    if subscribe:
        return SonarrSeries(
            id=subscribe.id,
            title=subscribe.name,
            seasonCount=1,
            seasons=[{
                "seasonNumber": subscribe.season,
                "monitored": True,
            }],
            year=subscribe.year,
            remotePoster=subscribe.poster,
            tmdbId=subscribe.tmdbid,
            tvdbId=subscribe.tvdbid,
            imdbId=subscribe.imdbid,
            profileId=1,
            languageProfileId=1,
            qualityProfileId=1,
            isAvailable=True,
            monitored=True,
            hasFile=False
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=" No tv series found！"
        )


@arr_router.post("/series", summary=" Add episode subscription")
def arr_add_series(apikey: str, tv: schemas.SonarrSeries,
                   db: Session = Depends(get_db)) -> Any:
    """
    AdditionalSonarr Episode subscription
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    #  Check if the subscription exists
    left_seasons = []
    for season in tv.seasons:
        subscribe = Subscribe.get_by_tmdbid(db, tmdbid=tv.tmdbId,
                                            season=season.get("seasonNumber"))
        if subscribe:
            continue
        left_seasons.append(season)
    #  All existing subscriptions
    if not left_seasons:
        return {
            "id": 1
        }
    #  Add subscription for the rest
    sid = 0
    message = ""
    for season in left_seasons:
        if not season.get("monitored"):
            continue
        sid, message = SubscribeChain(db).add(title=tv.title,
                                              year=tv.year,
                                              season=season.get("seasonNumber"),
                                              tmdbid=tv.tmdbId,
                                              mtype=MediaType.TV,
                                              userid="Seerr")

    if sid:
        return {
            "id": sid
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f" Failed to add subscription：{message}"
        )


@arr_router.delete("/series/{tid}", summary=" Delete episode subscription")
def arr_remove_series(apikey: str, tid: int, db: Session = Depends(get_db)) -> Any:
    """
    RemovingSonarr Episode subscription
    """
    if not apikey or apikey != settings.API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=" Authentication failure！",
        )
    subscribe = Subscribe.get(db, tid)
    if subscribe:
        subscribe.delete(db, tid)
        return schemas.Response(success=True)
    else:
        raise HTTPException(
            status_code=404,
            detail=" No tv series found！"
        )
