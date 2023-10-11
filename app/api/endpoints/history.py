from pathlib import Path
from typing import List, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.transfer import TransferChain
from app.core.event import eventmanager
from app.core.security import verify_token
from app.db import get_db
from app.db.models.downloadhistory import DownloadHistory
from app.db.models.transferhistory import TransferHistory
from app.schemas import MediaType
from app.schemas.types import EventType

router = APIRouter()


@router.get("/download", summary=" Check download history", response_model=List[schemas.DownloadHistory])
def download_history(page: int = 1,
                     count: int = 30,
                     db: Session = Depends(get_db),
                     _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Check download history
    """
    return DownloadHistory.list_by_page(db, page, count)


@router.delete("/download", summary=" Delete download history", response_model=schemas.Response)
def delete_download_history(history_in: schemas.DownloadHistory,
                            db: Session = Depends(get_db),
                            _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Delete download history
    """
    DownloadHistory.delete(db, history_in.id)
    return schemas.Response(success=True)


@router.get("/transfer", summary=" Query transfer history", response_model=schemas.Response)
def transfer_history(title: str = None,
                     page: int = 1,
                     count: int = 30,
                     db: Session = Depends(get_db),
                     _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Query transfer history
    """
    if title:
        total = TransferHistory.count_by_title(db, title)
        result = TransferHistory.list_by_title(db, title, page, count)
    else:
        result = TransferHistory.list_by_page(db, page, count)
        total = TransferHistory.count(db)

    return schemas.Response(success=True,
                            data={
                                "list": result,
                                "total": total,
                            })


@router.delete("/transfer", summary=" Delete transfer history", response_model=schemas.Response)
def delete_transfer_history(history_in: schemas.TransferHistory,
                            deletesrc: bool = False,
                            deletedest: bool = False,
                            db: Session = Depends(get_db),
                            _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Delete transfer history
    """
    history = TransferHistory.get(db, history_in.id)
    if not history:
        return schemas.Response(success=False, msg=" Record does not exist")
    #  Excluding media library files
    if deletedest and history.dest:
        TransferChain(db).delete_files(Path(history.dest))
    #  Deleting source files
    if deletesrc and history.src:
        TransferChain(db).delete_files(Path(history.src))
        #  Send event
        eventmanager.send_event(
            EventType.DownloadFileDeleted,
            {
                "src": history.src
            }
        )
    #  Deletion of records
    TransferHistory.delete(db, history_in.id)
    return schemas.Response(success=True)


@router.post("/transfer", summary=" History re-transfer", response_model=schemas.Response)
def redo_transfer_history(history_in: schemas.TransferHistory,
                          mtype: str = None,
                          new_tmdbid: int = None,
                          db: Session = Depends(get_db),
                          _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    History re-transfer， Non-input mtype  Cap (a poem) new_tmdbid  Hour， Automatic re-recognition using file names
    """
    if mtype and new_tmdbid:
        state, errmsg = TransferChain(db).re_transfer(logid=history_in.id,
                                                      mtype=MediaType(mtype), tmdbid=new_tmdbid)
    else:
        state, errmsg = TransferChain(db).re_transfer(logid=history_in.id)
    if state:
        return schemas.Response(success=True)
    else:
        return schemas.Response(success=False, message=errmsg)
