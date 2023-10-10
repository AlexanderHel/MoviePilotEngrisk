from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.dashboard import DashboardChain
from app.core.config import settings
from app.core.security import verify_token
from app.db import get_db
from app.db.models.transferhistory import TransferHistory
from app.scheduler import Scheduler
from app.utils.system import SystemUtils

router = APIRouter()


@router.get("/statistic", summary=" Statistics on the number of media", response_model=schemas.Statistic)
def statistic(db: Session = Depends(get_db),
              _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Querying statistics on the number of media outlets
    """
    media_statistics: Optional[List[schemas.Statistic]] = DashboardChain(db).media_statistic()
    if media_statistics:
        #  Summarize statistical information for each media library
        ret_statistic = schemas.Statistic()
        for media_statistic in media_statistics:
            ret_statistic.movie_count += media_statistic.movie_count
            ret_statistic.tv_count += media_statistic.tv_count
            ret_statistic.episode_count += media_statistic.episode_count
            ret_statistic.user_count += media_statistic.user_count
        return ret_statistic
    else:
        return schemas.Statistic()


@router.get("/storage", summary=" Storage space", response_model=schemas.Storage)
def storage(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Querying storage space information
    """
    total_storage, free_storage = SystemUtils.space_usage(settings.LIBRARY_PATHS)
    return schemas.Storage(
        total_storage=total_storage,
        used_storage=total_storage - free_storage
    )


@router.get("/processes", summary=" Process information", response_model=List[schemas.ProcessInfo])
def processes(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query process information
    """
    return SystemUtils.processes()


@router.get("/downloader", summary=" Downloader information", response_model=schemas.DownloaderInfo)
def downloader(db: Session = Depends(get_db),
               _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Search for downloader information
    """
    transfer_info = DashboardChain(db).downloader_info()
    free_space = SystemUtils.free_space(Path(settings.DOWNLOAD_PATH))
    if transfer_info:
        return schemas.DownloaderInfo(
            download_speed=transfer_info.download_speed,
            upload_speed=transfer_info.upload_speed,
            download_size=transfer_info.download_size,
            upload_size=transfer_info.upload_size,
            free_space=free_space
        )
    else:
        return schemas.DownloaderInfo()


@router.get("/schedule", summary=" Back-office services", response_model=List[schemas.ScheduleInfo])
def schedule(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query back-office service information
    """
    return Scheduler().list()


@router.get("/transfer", summary=" Documentation statistics", response_model=List[int])
def transfer(days: int = 7, db: Session = Depends(get_db),
             _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query document organization statistics
    """
    transfer_stat = TransferHistory.statistic(db, days)
    return [stat[1] for stat in transfer_stat]


@router.get("/cpu", summary=" Get currentCPU Utilization rate", response_model=int)
def cpu(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Get currentCPU Utilization rate
    """
    return SystemUtils.cpu_usage()


@router.get("/memory", summary=" Get current memory usage and utilization", response_model=List[int])
def memory(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Get current memory utilization
    """
    return SystemUtils.memory_usage()
