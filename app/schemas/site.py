from typing import Optional

from pydantic import BaseModel


class Site(BaseModel):
    # ID
    id: Optional[int]
    #  Site name
    name: Optional[str]
    #  Primary domain name of the siteKey
    domain: Optional[str]
    #  Site address
    url: Optional[str]
    #  Site prioritization
    pri: Optional[int] = 0
    # RSS Address
    rss: Optional[str] = None
    # Cookie
    cookie: Optional[str] = None
    # User-Agent
    ua: Optional[str] = None
    #  Whether to use a proxy
    proxy: Optional[int] = 0
    #  Filter rules
    filter: Optional[str] = None
    #  Whether or not to act and dye
    render: Optional[int] = 0
    #  Whether or not the site is public
    public: Optional[int] = 0
    #  Note
    note: Optional[str] = None
    #  Flow control unit cycle
    limit_interval: Optional[int] = None
    #  Number of flow controls
    limit_count: Optional[int] = None
    #  Flow control interval
    limit_seconds: Optional[int] = None
    #  Enable or disable
    is_active: Optional[bool] = True

    class Config:
        orm_mode = True
