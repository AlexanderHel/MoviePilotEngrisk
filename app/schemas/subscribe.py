from typing import Optional, List

from pydantic import BaseModel


class Subscribe(BaseModel):
    id: Optional[int] = None
    #  Subscription name
    name: Optional[str] = None
    #  Year of subscription
    year: Optional[str] = None
    #  Subscription type  Cinematic/ Dramas
    type: Optional[str] = None
    #  Search keywords
    keyword: Optional[str] = None
    tmdbid: Optional[int] = None
    doubanid: Optional[str] = None
    #  Quarter
    season: Optional[int] = None
    #  Playbill
    poster: Optional[str] = None
    #  Background image
    backdrop: Optional[str] = None
    #  Score (of student's work)
    vote: Optional[int] = 0
    #  Descriptive
    description: Optional[str] = None
    #  Filter rules
    filter: Optional[str] = None
    #  Embody
    include: Optional[str] = None
    #  Rule out
    exclude: Optional[str] = None
    #  Total episodes
    total_episode: Optional[int] = 0
    #  Number of episodes
    start_episode: Optional[int] = 0
    #  Missing episodes
    lack_episode: Optional[int] = 0
    #  Additional information
    note: Optional[str] = None
    #  State of affairs：N- Newly built， R- Subscription
    state: Optional[str] = None
    #  Last updated
    last_update: Optional[str] = None
    #  Subscriber
    username: Optional[str] = None
    #  Subscribe to the site
    sites: Optional[List[int]] = None
    #  Whether or not to wash the plate
    best_version: Optional[int] = 0
    #  Current priority
    current_priority: Optional[int] = None

    class Config:
        orm_mode = True
