from pathlib import Path
from typing import Optional, List, Tuple

from app.chain import ChainBase
from app.core.context import Context, MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo, MetaInfoPath
from app.log import logger
from app.utils.string import StringUtils


class MediaChain(ChainBase):
    """
    Media information processing chain
    """

    def recognize_by_title(self, title: str, subtitle: str = None) -> Optional[Context]:
        """
        Identify media messages based on main and subheadings
        """
        logger.info(f' Start recognizing media messages， Caption：{title}， Subheading：{subtitle} ...')
        #  Identifying metadata
        metainfo = MetaInfo(title, subtitle)
        #  Identify media messages
        mediainfo: MediaInfo = self.recognize_media(meta=metainfo)
        if not mediainfo:
            logger.warn(f'{title}  No media messages recognized')
            return Context(meta_info=metainfo)
        logger.info(f'{title}  Recognition of media messages：{mediainfo.type.value} {mediainfo.title_year}')
        #  Updating media images
        self.obtain_images(mediainfo=mediainfo)
        #  Return context
        return Context(meta_info=metainfo, media_info=mediainfo)

    def recognize_by_path(self, path: str) -> Optional[Context]:
        """
        Identify media information based on file paths
        """
        logger.info(f' Start recognizing media messages， File：{path} ...')
        file_path = Path(path)
        #  Metadata
        file_meta = MetaInfoPath(file_path)
        #  Identify media messages
        mediainfo = self.recognize_media(meta=file_meta)
        if not mediainfo:
            logger.warn(f'{path}  No media messages recognized')
            return Context(meta_info=file_meta)
        logger.info(f'{path}  Recognition of media messages：{mediainfo.type.value} {mediainfo.title_year}')
        #  Updating media images
        self.obtain_images(mediainfo=mediainfo)
        #  Return context
        return Context(meta_info=file_meta, media_info=mediainfo)

    def search(self, title: str) -> Tuple[MetaBase, List[MediaInfo]]:
        """
        Search for media information
        :param title:  Search content
        :return:  Identifying metadata， Media information list
        """
        #  Elements of extraction
        mtype, key_word, season_num, episode_num, year, content = StringUtils.get_keyword(title)
        #  Recognize
        meta = MetaInfo(content)
        if not meta.name:
            logger.warn(f'{title}  No metadata recognized！')
            return meta, []
        #  Consolidated information
        if mtype:
            meta.type = mtype
        if season_num:
            meta.begin_season = season_num
        if episode_num:
            meta.begin_episode = episode_num
        if year:
            meta.year = year
        #  Start searching
        logger.info(f"开始Search for media information：{meta.name}")
        medias: Optional[List[MediaInfo]] = self.search_medias(meta=meta)
        if not medias:
            logger.warn(f"{meta.name}  No corresponding media information was found！")
            return meta, []
        logger.info(f"{content}  Search to {len(medias)}  Relevant media information")
        #  Recognize的元数据，媒体信息列表
        return meta, medias
