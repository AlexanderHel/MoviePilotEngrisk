import json
from typing import Optional

from sqlalchemy.orm import Session

from app.db import DbOper
from app.db.models.mediaserver import MediaServerItem


class MediaServerOper(DbOper):
    """
    Media server data management
    """

    def __init__(self, db: Session = None):
        super().__init__(db)

    def add(self, **kwargs) -> bool:
        """
        Add media server data
        """
        item = MediaServerItem(**kwargs)
        if not item.get_by_itemid(self._db, kwargs.get("item_id")):
            item.create(self._db)
            return True
        return False

    def empty(self, server: str):
        """
        Empty media server data
        """
        MediaServerItem.empty(self._db, server)

    def exists(self, **kwargs) -> Optional[MediaServerItem]:
        """
        Determine if media server data exists
        """
        if kwargs.get("tmdbid"):
            #  PrioritizationTMDBID Surname zha
            item = MediaServerItem.exist_by_tmdbid(self._db, tmdbid=kwargs.get("tmdbid"),
                                                   mtype=kwargs.get("mtype"))
        else:
            #  By title、 Typology、 Year check
            item = MediaServerItem.exists_by_title(self._db, title=kwargs.get("title"),
                                                   mtype=kwargs.get("mtype"), year=kwargs.get("year"))
        if not item:
            return None

        if kwargs.get("season"):
            #  Determine if the season exists
            if not item.seasoninfo:
                return None
            seasoninfo = json.loads(item.seasoninfo) or {}
            if kwargs.get("season") not in seasoninfo.keys():
                return None
        return item

    def get_item_id(self, **kwargs) -> Optional[str]:
        """
        Getting media server dataID
        """
        item = self.exists(**kwargs)
        if not item:
            return None
        return str(item.item_id)
