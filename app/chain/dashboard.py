from typing import Optional, List

from app import schemas
from app.chain import ChainBase


class DashboardChain(ChainBase):
    """
    Various dashboard statistical processing chains
    """
    def media_statistic(self) -> Optional[List[schemas.Statistic]]:
        """
        Statistics on the number of media
        """
        return self.run_module("media_statistic")

    def downloader_info(self) -> schemas.DownloaderInfo:
        """
        Downloader information
        """
        return self.run_module("downloader_info")
