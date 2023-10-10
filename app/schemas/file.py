from typing import Optional

from pydantic import BaseModel


class FileItem(BaseModel):
    #  Typology dir/file
    type: Optional[str] = None
    #  File path
    path: Optional[str] = None
    #  Filename
    name: Optional[str] = None
    #  Filename
    basename: Optional[str] = None
    #  File suffix
    extension: Optional[str] = None
    #  File size
    size: Optional[int] = None
    #  Modify time
    modify_time: Optional[float] = None
