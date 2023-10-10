from typing import Union

from app.chain import ChainBase
from app.schemas import Notification, MessageChannel


class SystemChain(ChainBase):
    """
    System level processing chain
    """
    def remote_clear_cache(self, channel: MessageChannel, userid: Union[int, str]):
        """
        Clearing the system cache
        """
        self.clear_cache()
        self.post_message(Notification(channel=channel,
                                       title=f" Cache cleanup complete！", userid=userid))
