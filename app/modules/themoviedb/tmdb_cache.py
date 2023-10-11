import pickle
import random
import time
from pathlib import Path
from threading import RLock
from typing import Optional

from app.core.config import settings
from app.core.meta import MetaBase
from app.utils.singleton import Singleton
from app.schemas.types import MediaType

lock = RLock()

CACHE_EXPIRE_TIMESTAMP_STR = "cache_expire_timestamp"
EXPIRE_TIMESTAMP = settings.CACHE_CONF.get('meta')


class TmdbCache(metaclass=Singleton):
    """
    TMDB Cached data
    {
        "id": '',
        "title": '',
        "year": '',
        "type": MediaType
    }
    """
    _meta_data: dict = {}
    #  Cache file path
    _meta_path: Path = None
    # TMDB Cache expiration
    _tmdb_cache_expire: bool = True

    def __init__(self):
        self._meta_path = settings.TEMP_PATH / "__tmdb_cache__"
        self._meta_data = self.__load(self._meta_path)

    def clear(self):
        """
        Empty allTMDB (computing) cache
        """
        with lock:
            self._meta_data = {}

    @staticmethod
    def __get_key(meta: MetaBase) -> str:
        """
        Getting the cacheKEY
        """
        return f"[{meta.type.value if meta.type else ' Uncharted'}]{meta.name}-{meta.year}-{meta.begin_season}"

    def get(self, meta: MetaBase):
        """
        According toKEY Value fetch cache value
        """
        key = self.__get_key(meta)
        with lock:
            info: dict = self._meta_data.get(key)
            if info:
                expire = info.get(CACHE_EXPIRE_TIMESTAMP_STR)
                if not expire or int(time.time()) < expire:
                    info[CACHE_EXPIRE_TIMESTAMP_STR] = int(time.time()) + EXPIRE_TIMESTAMP
                    self._meta_data[key] = info
                elif expire and self._tmdb_cache_expire:
                    self.delete(key)
            return info or {}

    def delete(self, key: str) -> dict:
        """
        Deleting cached information
        @param key:  (computing) cachekey
        @return:  Deleted cache contents
        """
        with lock:
            return self._meta_data.pop(key, None)

    def delete_by_tmdbid(self, tmdbid: int) -> None:
        """
        Empty the correspondingTMDBID All cached records of the， To force an updateTMDB Latest data available in
        """
        for key in list(self._meta_data):
            if self._meta_data.get(key, {}).get("id") == tmdbid:
                with lock:
                    self._meta_data.pop(key)

    def delete_unknown(self) -> None:
        """
        Clear unrecognized cache records， In order to re-searchTMDB
        """
        for key in list(self._meta_data):
            if self._meta_data.get(key, {}).get("id") == 0:
                with lock:
                    self._meta_data.pop(key)

    def modify(self, key: str, title: str) -> dict:
        """
        Deleting cached information
        @param key:  (computing) cachekey
        @param title:  Caption
        @return:  Modified cache contents
        """
        with lock:
            if self._meta_data.get(key):
                self._meta_data[key]['title'] = title
                self._meta_data[key][CACHE_EXPIRE_TIMESTAMP_STR] = int(time.time()) + EXPIRE_TIMESTAMP
            return self._meta_data.get(key)

    @staticmethod
    def __load(path: Path) -> dict:
        """
        Load cache from file
        """
        try:
            if path.exists():
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                return data
            return {}
        except Exception as e:
            print(str(e))
            return {}

    def update(self, meta: MetaBase, info: dict) -> None:
        """
        Add or update cache entries
        """
        with lock:
            if info:
                #  Cache title
                cache_title = info.get("title") \
                    if info.get("media_type") == MediaType.MOVIE else info.get("name")
                #  Cache year
                cache_year = info.get('release_date') \
                    if info.get("media_type") == MediaType.MOVIE else info.get('first_air_date')
                if cache_year:
                    cache_year = cache_year[:4]
                self._meta_data[self.__get_key(meta)] = {
                        "id": info.get("id"),
                        "type": info.get("media_type"),
                        "year": cache_year,
                        "title": cache_title,
                        "poster_path": info.get("poster_path"),
                        "backdrop_path": info.get("backdrop_path"),
                        CACHE_EXPIRE_TIMESTAMP_STR: int(time.time()) + EXPIRE_TIMESTAMP
                    }
            else:
                self._meta_data[self.__get_key(meta)] = {'id': 0}

    def save(self, force: bool = False) -> None:
        """
        Save cached data to file
        """

        meta_data = self.__load(self._meta_path)
        new_meta_data = {k: v for k, v in self._meta_data.items() if v.get("id")}

        if not force \
                and not self._random_sample(new_meta_data) \
                and meta_data.keys() == new_meta_data.keys():
            return

        with open(self._meta_path, 'wb') as f:
            pickle.dump(new_meta_data, f, pickle.HIGHEST_PROTOCOL)

    def _random_sample(self, new_meta_data: dict) -> bool:
        """
        Whether the sampling analysis needs to be preserved
        """
        ret = False
        if len(new_meta_data) < 25:
            keys = list(new_meta_data.keys())
            for k in keys:
                info = new_meta_data.get(k)
                expire = info.get(CACHE_EXPIRE_TIMESTAMP_STR)
                if not expire:
                    ret = True
                    info[CACHE_EXPIRE_TIMESTAMP_STR] = int(time.time()) + EXPIRE_TIMESTAMP
                elif int(time.time()) >= expire:
                    ret = True
                    if self._tmdb_cache_expire:
                        new_meta_data.pop(k)
        else:
            count = 0
            keys = random.sample(sorted(new_meta_data.keys()), 25)
            for k in keys:
                info = new_meta_data.get(k)
                expire = info.get(CACHE_EXPIRE_TIMESTAMP_STR)
                if not expire:
                    ret = True
                    info[CACHE_EXPIRE_TIMESTAMP_STR] = int(time.time()) + EXPIRE_TIMESTAMP
                elif int(time.time()) >= expire:
                    ret = True
                    if self._tmdb_cache_expire:
                        new_meta_data.pop(k)
                        count += 1
            if count >= 5:
                ret |= self._random_sample(new_meta_data)
        return ret

    def get_title(self, key: str) -> Optional[str]:
        """
        Getting cached headers
        """
        cache_media_info = self._meta_data.get(key)
        if not cache_media_info or not cache_media_info.get("id"):
            return None
        return cache_media_info.get("title")

    def set_title(self, key: str, cn_title: str) -> None:
        """
        Reset the cache header
        """
        cache_media_info = self._meta_data.get(key)
        if not cache_media_info:
            return
        self._meta_data[key]['title'] = cn_title
