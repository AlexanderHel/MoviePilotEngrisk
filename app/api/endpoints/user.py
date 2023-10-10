import base64
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app import schemas
from app.core.security import get_password_hash
from app.db import get_db
from app.db.models.user import User
from app.db.userauth import get_current_active_superuser, get_current_active_user

router = APIRouter()


@router.get("/", summary=" All users", response_model=List[schemas.User])
def read_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Query user list
    """
    users = current_user.list(db)
    return users


@router.post("/", summary=" New subscriber", response_model=schemas.Response)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: schemas.UserCreate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    New subscriber
    """
    user = current_user.get_by_name(db, name=user_in.name)
    if user:
        return schemas.Response(success=False, message=" User already exists")
    user_info = user_in.dict()
    if user_info.get("password"):
        user_info["hashed_password"] = get_password_hash(user_info["password"])
        user_info.pop("password")
    user = User(**user_info)
    user.create(db)
    return schemas.Response(success=True)


@router.put("/", summary=" Update a user", response_model=schemas.Response)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_in: schemas.UserCreate,
    _: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Update a user
    """
    user_info = user_in.dict()
    if user_info.get("password"):
        user_info["hashed_password"] = get_password_hash(user_info["password"])
        user_info.pop("password")
    user = User.get_by_name(db, name=user_info["name"])
    if not user:
        return schemas.Response(success=False, message=" The user does not exist")
    user.update(db, user_info)
    return schemas.Response(success=True)


@router.get("/current", summary=" Currently logged in user information", response_model=schemas.User)
def read_current_user(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Currently logged in user information
    """
    return current_user


@router.post("/avatar/{user_id}", summary=" Upload user avatar", response_model=schemas.Response)
async def upload_avatar(user_id: int, db: Session = Depends(get_db),
                        file: UploadFile = File(...)):
    """
    Upload user avatar
    """
    #  Convert the file toBase64
    file_base64 = base64.b64encode(file.file.read())
    #  Update to user table
    user = User.get(db, user_id)
    if not user:
        return schemas.Response(success=False, message=" The user does not exist")
    user.update(db, {
        "avatar": f"data:image/ico;base64,{file_base64}"
    })
    return schemas.Response(success=True, message=file.filename)


@router.delete("/{user_name}", summary=" Delete user", response_model=schemas.Response)
def delete_user(
    *,
    db: Session = Depends(get_db),
    user_name: str,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Delete user
    """
    user = current_user.get_by_name(db, name=user_name)
    if not user:
        return schemas.Response(success=False, message=" The user does not exist")
    user.delete_by_name(db, user_name)
    return schemas.Response(success=True)


@router.get("/{user_id}", summary=" User details", response_model=schemas.User)
def read_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check user details
    """
    user = current_user.get(db, rid=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=" The user does not exist",
        )
    if user == current_user:
        return user
    if not user.is_superuser:
        raise HTTPException(
            status_code=400,
            detail=" Insufficient user rights"
        )
    return user
