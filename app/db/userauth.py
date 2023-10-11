from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.core.security import verify_token
from app.db import get_db
from app.db.models.user import User


def get_current_user(
        db: Session = Depends(get_db),
        token_data: schemas.TokenPayload = Depends(verify_token)
) -> User:
    user = User.get(db, rid=token_data.sub)
    if not user:
        raise HTTPException(status_code=403, detail=" The user does not exist")
    return user


def get_current_active_user(
        current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail=" User inactivation")
    return current_user


def get_current_active_superuser(
        current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=400, detail=" Insufficient user rights"
        )
    return current_user
