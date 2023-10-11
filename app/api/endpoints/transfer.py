from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.transfer import TransferChain
from app.core.security import verify_token
from app.db import get_db
from app.schemas import MediaType

router = APIRouter()


@router.post("/manual", summary=" Manual transfer", response_model=schemas.Response)
def manual_transfer(path: str,
                    target: str = None,
                    tmdbid: int = None,
                    type_name: str = None,
                    season: int = None,
                    transfer_type: str = None,
                    episode_format: str = None,
                    episode_detail: str = None,
                    episode_part: str = None,
                    episode_offset: int = 0,
                    min_filesize: int = 0,
                    db: Session = Depends(get_db),
                    _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    Manual transfer， Support customized episode recognition format
    :param path:  Transfer path or file
    :param target:  Target path
    :param type_name:  Media type、 Cinematic/ Dramas
    :param tmdbid: tmdbid
    :param season:  Episode number
    :param transfer_type:  Type of transfer，move/copy
    :param episode_format:  Episode recognition format
    :param episode_detail:  Episode identification details
    :param episode_part:  Episode identification subplot information
    :param episode_offset:  Episode identification offset
    :param min_filesize:  Minimum file size(MB)
    :param db:  Comprehensive database
    :param _: Token Calibration
    """
    in_path = Path(path)
    if target:
        target = Path(target)
        if not target.exists():
            return schemas.Response(success=False, message=f" Target path does not exist")
    #  Typology
    mtype = MediaType(type_name) if type_name else None
    #  Custom formatting
    epformat = None
    if episode_offset or episode_part or episode_detail or episode_format:
        epformat = schemas.EpisodeFormat(
            format=episode_format,
            detail=episode_detail,
            part=episode_part,
            offset=episode_offset,
        )
    #  Commencement of transfer
    state, errormsg = TransferChain(db).manual_transfer(
        in_path=in_path,
        target=target,
        tmdbid=tmdbid,
        mtype=mtype,
        season=season,
        transfer_type=transfer_type,
        epformat=epformat,
        min_filesize=min_filesize
    )
    #  Fail (e.g. experiments)
    if not state:
        if isinstance(errormsg, list):
            errormsg = f" Finishing，{len(errormsg)}  Failed transfer of documents！"
        return schemas.Response(success=False, message=errormsg)
    #  Successes
    return schemas.Response(success=True)
