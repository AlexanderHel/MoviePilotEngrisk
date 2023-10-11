from typing import Optional

from pydantic import BaseModel


# Shared properties
class UserBase(BaseModel):
    #  User id
    name: str
    #  Inbox， Not yet activated
    email: Optional[str] = None
    #  State of affairs
    is_active: Optional[bool] = True
    #  Super-administrator
    is_superuser: bool = False
    #  Avatar
    avatar: Optional[str] = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    name: str
    email: Optional[str] = None
    password: Optional[str] = None


# Properties to receive via API on update
class UserUpdate(UserBase):
    name: str
    password: Optional[str] = None


class UserInDBBase(UserBase):
    id: Optional[int] = None

    class Config:
        orm_mode = True


# Additional properties to return via API
class User(UserInDBBase):
    name: str
    email: Optional[str] = None


# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str
