from typing import Optional, Union

from pydantic import BaseModel


class Response(BaseModel):
    #  State of affairs
    success: bool
    #  Message text
    message: Optional[str] = None
    #  Digital
    data: Optional[Union[dict, list]] = {}
