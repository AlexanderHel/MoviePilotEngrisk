from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import schemas
from app.chain.tmdb import TmdbChain
from app.chain.user import UserChain
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.db import get_db
from app.db.models.user import User
from app.log import logger
from app.utils.web import WebUtils

router = APIRouter()


@router.post("/access-token", summary=" Gaintoken", response_model=schemas.Token)
async def login_access_token(
        db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Get certifiedToken
    """
    #  Checking the database
    user = User.authenticate(
        db=db,
        name=form_data.username,
        password=form_data.password
    )
    if not user:
        #  Request for assistance with accreditation
        logger.warn(" Login user local mismatch， Attempted assisted authentication ...")
        token = UserChain(db).user_authenticate(form_data.username, form_data.password)
        if not token:
            raise HTTPException(status_code=401, detail=" Incorrect username or password")
        else:
            logger.info(f" Assisted certification success， User information: {token}")
            #  Add user information sheet
            user = User.get_by_name(db=db, name=form_data.username)
            if not user:
                logger.info(f" The user does not exist， Create user: {form_data.username}")
                user = User(name=form_data.username, is_active=True,
                            is_superuser=False, hashed_password=get_password_hash(token))
                user.create(db)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail=" User not enabled")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return schemas.Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        token_type="bearer",
        super_user=user.is_superuser,
        user_name=user.name,
        avatar=user.avatar
    )


@router.get("/bing", summary="Bing Daily wallpaper", response_model=schemas.Response)
def bing_wallpaper() -> Any:
    """
    GainBing Daily wallpaper
    """
    url = WebUtils.get_bing_wallpaper()
    if url:
        return schemas.Response(success=False,
                                message=url)
    return schemas.Response(success=False)


@router.get("/tmdb", summary="TMDB Movie poster", response_model=schemas.Response)
def tmdb_wallpaper(db: Session = Depends(get_db)) -> Any:
    """
    GainTMDB Movie poster
    """
    wallpager = TmdbChain(db).get_random_wallpager()
    if wallpager:
        return schemas.Response(
            success=True,
            message=wallpager
        )
    return schemas.Response(success=False)
