from typing import Optional

from pydantic import BaseModel


class Statistic(BaseModel):
    #  Cinematic
    movie_count: Optional[int] = 0
    #  Number of tv series
    tv_count: Optional[int] = 0
    #  Episode number (of a tv series etc)
    episode_count: Optional[int] = 0
    #  Number of users
    user_count: Optional[int] = 0


class Storage(BaseModel):
    #  Total storage space
    total_storage: Optional[float] = 0
    #  Used space
    used_storage: Optional[float] = 0


class ProcessInfo(BaseModel):
    #  StepID
    pid: Optional[int] = 0
    #  Process name
    name: Optional[str] = None
    #  Process state
    status: Optional[str] = None
    #  Process occupancyCPU
    cpu: Optional[float] = 0.0
    #  Process memory usage MB
    memory: Optional[float] = 0.0
    #  Process creation time
    create_time: Optional[float] = 0.0
    #  Process runtime  Unit of angle or arc equivalent one sixtieth of a degree
    run_time: Optional[float] = 0.0


class DownloaderInfo(BaseModel):
    #  Download speed
    download_speed: Optional[float] = 0.0
    #  Upload speed
    upload_speed: Optional[float] = 0.0
    #  Downloads
    download_size: Optional[float] = 0.0
    #  Upload volume
    upload_size: Optional[float] = 0.0
    #  Headroom
    free_space: Optional[float] = 0.0


class ScheduleInfo(BaseModel):
    # ID
    id: Optional[str] = None
    #  Name (of a thing)
    name: Optional[str] = None
    #  State of affairs
    status: Optional[str] = None
    #  Next execution time
    next_run: Optional[str] = None
