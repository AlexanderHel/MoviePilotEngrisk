from typing import Optional, Union

from pydantic import BaseModel

from app.schemas.types import NotificationType, MessageChannel


class CommingMessage(BaseModel):
    """
    Foreign news
    """
    #  SubscribersID
    userid: Optional[Union[str, int]] = None
    #  User id
    username: Optional[str] = None
    #  News channel
    channel: Optional[MessageChannel] = None
    #  Message body
    text: Optional[str] = None


class Notification(BaseModel):
    """
    Messages
    """
    #  News channel
    channel: Optional[MessageChannel] = None
    # Messages类型
    mtype: Optional[NotificationType] = None
    #  Caption
    title: Optional[str] = None
    #  Text content
    text: Optional[str] = None
    #  Photograph
    image: Optional[str] = None
    #  Link (on a website)
    link: Optional[str] = None
    #  SubscribersID
    userid: Optional[Union[str, int]] = None


class NotificationSwitch(BaseModel):
    """
    Messages开关
    """
    # Messages类型
    mtype: Optional[str] = None
    #  Wechat switch
    wechat: Optional[bool] = False
    # TG Switchgear
    telegram: Optional[bool] = False
    # Slack Switchgear
    slack: Optional[bool] = False
    # SynologyChat Switchgear
    synologychat: Optional[bool] = False
