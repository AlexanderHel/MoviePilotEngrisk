import json
import threading
from typing import List, Union, Generator

from sqlalchemy.orm import Session

from app import schemas
from app.chain import ChainBase
from app.core.config import settings
from app.db import SessionFactory
from app.db.mediaserver_oper import MediaServerOper
from app.log import logger

lock = threading.Lock()


class MediaServerChain(ChainBase):
    """
    Media server processing chain
    """

    def __init__(self, db: Session = None):
        super().__init__(db)

    def librarys(self, server: str) -> List[schemas.MediaServerLibrary]:
        """
        Get all media libraries of the media server
        """
        return self.run_module("mediaserver_librarys", server=server)

    def items(self, server: str, library_id: Union[str, int]) -> List[schemas.MediaServerItem]:
        """
        Get all items of the media server
        """
        return self.run_module("mediaserver_items", server=server, library_id=library_id)

    def iteminfo(self, server: str, item_id: Union[str, int]) -> schemas.MediaServerItem:
        """
        Getting media server project information
        """
        return self.run_module("mediaserver_iteminfo", server=server, item_id=item_id)

    def episodes(self, server: str, item_id: Union[str, int]) -> List[schemas.MediaServerSeasonInfo]:
        """
        Get media server episode information
        """
        return self.run_module("mediaserver_tv_episodes", server=server, item_id=item_id)

    def sync(self):
        """
        Synchronize all data from the media library to the local database
        """
        with lock:
            #  Media server synchronization using separate sessions
            _db = SessionFactory()
            _dbOper = MediaServerOper(_db)
            #  Summary statistics
            total_count = 0
            #  Empty the register
            _dbOper.empty(server=settings.MEDIASERVER)
            #  Synchronized blacklists
            sync_blacklist = settings.MEDIASERVER_SYNC_BLACKLIST.split(
                ",") if settings.MEDIASERVER_SYNC_BLACKLIST else []
            #  Media server setup
            if not settings.MEDIASERVER:
                return
            mediaservers = settings.MEDIASERVER.split(",")
            #  Traversing the media server
            for mediaserver in mediaservers:
                logger.info(f" Starting to synchronize media libraries {mediaserver}  Data ...")
                for library in self.librarys(mediaserver):
                    #  Synchronized blacklists 跳过
                    if library.name in sync_blacklist:
                        continue
                    logger.info(f" Synchronizing. {mediaserver}  Media library {library.name} ...")
                    library_count = 0
                    for item in self.items(mediaserver, library.id):
                        if not item:
                            continue
                        if not item.item_id:
                            continue
                        #  Reckoning
                        library_count += 1
                        seasoninfo = {}
                        #  Typology
                        item_type = " Dramas" if item.item_type in ['Series', 'show'] else " Cinematic"
                        if item_type == " Dramas":
                            #  Search for episode information
                            espisodes_info = self.episodes(mediaserver, item.item_id) or []
                            for episode in espisodes_info:
                                seasoninfo[episode.season] = episode.episodes
                        #  Insert data
                        item_dict = item.dict()
                        item_dict['seasoninfo'] = json.dumps(seasoninfo)
                        item_dict['item_type'] = item_type
                        _dbOper.add(**item_dict)
                    logger.info(f"{mediaserver}  Media library {library.name}  Synchronized completion， Number of common steps：{library_count}")
                    #  Totals add up
                    total_count += library_count
            #  Close the database connection
            if _db:
                _db.close()
            logger.info("【MediaServer】 Media library data synchronization completed， Number of synchronizations：%s" % total_count)
