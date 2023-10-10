import shutil
from pathlib import Path

import ruamel.yaml

from app.core.config import settings
from app.log import logger
from app.utils.singleton import Singleton


class CategoryHelper(metaclass=Singleton):
    """
    Secondary classification
    """
    _categorys = {}
    _movie_categorys = {}
    _tv_categorys = {}

    def __init__(self):
        self._category_path: Path = settings.CONFIG_PATH / "category.yaml"
        # Secondary classification策略关闭
        if not settings.LIBRARY_CATEGORY:
            return
        try:
            if not self._category_path.exists():
                shutil.copy(settings.INNER_CONFIG_PATH / "category.yaml", self._category_path)
            with open(self._category_path, mode='r', encoding='utf-8') as f:
                try:
                    yaml = ruamel.yaml.YAML()
                    self._categorys = yaml.load(f)
                except Exception as e:
                    logger.warn(f"Secondary classification策略配置文件格式出现严重错误！请检查：{str(e)}")
                    self._categorys = {}
        except Exception as err:
            logger.warn(f"Secondary classification策略配置文件加载出错：{err}")

        if self._categorys:
            self._movie_categorys = self._categorys.get('movie')
            self._tv_categorys = self._categorys.get('tv')
        logger.info(f"已加载Secondary classification策略 category.yaml")

    @property
    def is_movie_category(self) -> bool:
        """
        Get movie category flags
        """
        if self._movie_categorys:
            return True
        return False

    @property
    def is_tv_category(self) -> bool:
        """
        Get tv series category flags
        """
        if self._tv_categorys:
            return True
        return False

    @property
    def movie_categorys(self) -> list:
        """
        Get a list of movie categories
        """
        if not self._movie_categorys:
            return []
        return self._movie_categorys.keys()

    @property
    def tv_categorys(self) -> list:
        """
        Get a categorized list of tv series
        """
        if not self._tv_categorys:
            return []
        return self._tv_categorys.keys()

    def get_movie_category(self, tmdb_info) -> str:
        """
        Judging the classification of a movie
        :param tmdb_info:  IdentifiableTMDB Information contained in
        :return: Secondary classification的名称
        """
        return self.get_category(self._movie_categorys, tmdb_info)

    def get_tv_category(self, tmdb_info) -> str:
        """
        Judging the classification of tv series
        :param tmdb_info:  IdentifiableTMDB Information contained in
        :return: Secondary classification的名称
        """
        return self.get_category(self._tv_categorys, tmdb_info)

    @staticmethod
    def get_category(categorys: dict, tmdb_info: dict) -> str:
        """
        According to TMDB Compare information with categorized profiles， Determine the classification to which it belongs
        :param categorys:  Categorized configurations
        :param tmdb_info: TMDB Text
        :return:  Name of the classification
        """
        if not tmdb_info:
            return ""
        if not categorys:
            return ""
        for key, item in categorys.items():
            if not item:
                return key
            match_flag = True
            for attr, value in item.items():
                if not value:
                    continue
                info_value = tmdb_info.get(attr)
                if not info_value:
                    match_flag = False
                    continue
                elif attr == "production_countries":
                    info_values = [str(val.get("iso_3166_1")).upper() for val in info_value]
                else:
                    if isinstance(info_value, list):
                        info_values = [str(val).upper() for val in info_value]
                    else:
                        info_values = [str(info_value).upper()]

                if value.find(",") != -1:
                    values = [str(val).upper() for val in value.split(",")]
                else:
                    values = [str(value).upper()]

                if not set(values).intersection(set(info_values)):
                    match_flag = False
            if match_flag:
                return key
        return ""
