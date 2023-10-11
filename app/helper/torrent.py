import datetime
import re
from pathlib import Path
from typing import Tuple, Optional, List, Union
from urllib.parse import unquote

from requests import Response
from torrentool.api import Torrent

from app.core.config import settings
from app.core.context import Context
from app.core.metainfo import MetaInfo
from app.db.systemconfig_oper import SystemConfigOper
from app.log import logger
from app.utils.http import RequestUtils
from app.schemas.types import MediaType, SystemConfigKey


class TorrentHelper:
    """
    Seed help category
    """

    def __init__(self):
        self.system_config = SystemConfigOper()

    def download_torrent(self, url: str,
                         cookie: str = None,
                         ua: str = None,
                         referer: str = None,
                         proxy: bool = False) \
            -> Tuple[Optional[Path], Optional[Union[str, bytes]], Optional[str], Optional[list], Optional[str]]:
        """
        Download the seeds locally
        :return:  Seed save path、 Seed content、 Master catalog of seeds、 List of seed documents、 Error message
        """
        if url.startswith("magnet:"):
            return None, url, "", [], f" Magnetic link"
        #  Request for seed files
        req = RequestUtils(
            ua=ua,
            cookies=cookie,
            referer=referer,
            proxies=settings.PROXY if proxy else None
        ).get_res(url=url, allow_redirects=False)
        while req and req.status_code in [301, 302]:
            url = req.headers['Location']
            if url and url.startswith("magnet:"):
                return None, url, "", [], f" Getting to the magnet link"
            req = RequestUtils(
                ua=ua,
                cookies=cookie,
                referer=referer,
                proxies=settings.PROXY if proxy else None
            ).get_res(url=url, allow_redirects=False)
        if req and req.status_code == 200:
            if not req.content:
                return None, None, "", [], " Seed data not downloaded"
            #  Parsing content format
            if req.text and str(req.text).startswith("magnet:"):
                #  Magnetic link
                return None, req.text, "", [], f" Getting to the magnet link"
            elif req.text and " Download seed file" in req.text:
                #  First download tips page
                skip_flag = False
                try:
                    forms = re.findall(r'<form.*?action="(.*?)".*?>(.*?)</form>', req.text, re.S)
                    for form in forms:
                        action = form[0]
                        if action != "?":
                            continue
                        action = url
                        inputs = re.findall(r'<input.*?name="(.*?)".*?value="(.*?)".*?>', form[1], re.S)
                        if inputs:
                            data = {}
                            for item in inputs:
                                data[item[0]] = item[1]
                            #  Rewritereq
                            req = RequestUtils(
                                ua=ua,
                                cookies=cookie,
                                referer=referer,
                                proxies=settings.PROXY if proxy else None
                            ).post_res(url=action, data=data)
                            if req and req.status_code == 200:
                                #  Check if it's a seed file， If an exception is not thrown
                                Torrent.from_string(req.content)
                                #  Skip success
                                logger.info(f" Triggered the site's first seed download， Automatically skipped：{url}")
                                skip_flag = True
                            elif req is not None:
                                logger.warn(f" Triggered the site's first seed download， And cannot be skipped automatically，"
                                            f" Return code：{req.status_code}， Cause of error：{req.reason}")
                            else:
                                logger.warn(f" Triggered the site's first seed download， And cannot be skipped automatically：{url}")
                        break
                except Exception as err:
                    logger.warn(f" Triggered the site's first seed download， Error when trying to auto-skip：{err}， Link (on a website)：{url}")
                if not skip_flag:
                    return None, None, "", [], " Seed data incorrect， Please make sure the link is correct， IfPT The site will have to manually download the seed once at the site"
            #  Seed content
            if req.content:
                #  Check if it's a seed file， If not, the exception is still thrown
                try:
                    #  Read seed file name
                    file_name = self.get_url_filename(req, url)
                    #  Seed file path
                    file_path = Path(settings.TEMP_PATH) / file_name
                    #  Save to file
                    file_path.write_bytes(req.content)
                    #  Get a list of seed directories and files
                    folder_name, file_list = self.get_torrent_info(file_path)
                    #  Success in getting seed data
                    return file_path, req.content, folder_name, file_list, ""
                except Exception as err:
                    logger.error(f" Seed file parsing failure：{err}")
                #  Seed data still incorrect
                return None, None, "", [], " Seed data incorrect， Please make sure the link is correct"
            #  Return failure
            return None, None, "", [], ""
        elif req is None:
            return None, None, "", [], " Unable to open link"
        elif req.status_code == 429:
            return None, None, "", [], " Trigger site flow control， Please try again later."
        else:
            return None, None, "", [], f" Error downloading seeds， Status code：{req.status_code}"

    @staticmethod
    def get_torrent_info(torrent_path: Path) -> Tuple[str, List[str]]:
        """
        Get the folder name and file list of the seed file
        :param torrent_path:  Seed file path
        :return:  Folder name、 List of documents， Single file seeds return empty folder names
        """
        if not torrent_path or not torrent_path.exists():
            return "", []
        try:
            torrentinfo = Torrent.from_file(torrent_path)
            #  Access to the list of documents
            if (not torrentinfo.files
                    or (len(torrentinfo.files) == 1
                        and torrentinfo.files[0].name == torrentinfo.name)):
                #  Single file seed directory name returns null
                folder_name = ""
                #  Single-file seed
                file_list = [torrentinfo.name]
            else:
                #  Catalog name
                folder_name = torrentinfo.name
                #  List of documents， Remove the first level directory if it is the same as the seed name
                file_list = []
                for fileinfo in torrentinfo.files:
                    file_path = Path(fileinfo.name)
                    #  Root path
                    root_path = file_path.parts[0]
                    if root_path == folder_name:
                        file_list.append(str(file_path.relative_to(root_path)))
                    else:
                        file_list.append(fileinfo.name)
            logger.info(f" Parse seed：{torrent_path.name} =>  Catalogs：{folder_name}， List of documents：{file_list}")
            return folder_name, file_list
        except Exception as err:
            logger.error(f" Seed file parsing failure：{err}")
            return "", []

    @staticmethod
    def get_url_filename(req: Response, url: str) -> str:
        """
        Get the seed file name from the download request
        """
        if not req:
            return ""
        disposition = req.headers.get('content-disposition') or ""
        file_name = re.findall(r"filename=\"?(.+)\"?", disposition)
        if file_name:
            file_name = unquote(str(file_name[0].encode('ISO-8859-1').decode()).split(";")[0].strip())
            if file_name.endswith('"'):
                file_name = file_name[:-1]
        elif url and url.endswith(".torrent"):
            file_name = unquote(url.split("/")[-1])
        else:
            file_name = str(datetime.datetime.now())
        return file_name

    def sort_torrents(self, torrent_list: List[Context]) -> List[Context]:
        """
        Sorting seeds against rows
        """
        if not torrent_list:
            return []

        def get_sort_str(_context):
            """
            Sorting function， The larger the value, the higher the priority
            """
            _meta = _context.meta_info
            _torrent = _context.torrent_info
            _media = _context.media_info
            #  Site prioritization
            _site_order = 999 - (_torrent.site_order or 0)
            #  Quarter
            _season_len = str(len(_meta.season_list)).rjust(2, '0')
            #  Episode number (of a tv series etc)
            if not _meta.episode_list:
                #  No episodes at the top of the list.
                _episode_len = "9999"
            else:
                #  Episode number (of a tv series etc)越多的排越前面
                _episode_len = str(len(_meta.episode_list)).rjust(4, '0')
            #  Priority rules
            priority = self.system_config.get(SystemConfigKey.TorrentsPriority)
            if priority != "site":
                #  Arrange in order： Caption、 Resource type、 Breed、 End of a season
                return "%s%s%s%s" % (str(_media.title).ljust(100, ' '),
                                     str(_torrent.pri_order).rjust(3, '0'),
                                     str(_torrent.seeders).rjust(10, '0'),
                                     "%s%s" % (_season_len, _episode_len))
            else:
                #  Arrange in order： Caption、 Resource type、 Website、 Breed、 End of a season
                return "%s%s%s%s%s" % (str(_media.title).ljust(100, ' '),
                                       str(_torrent.pri_order).rjust(3, '0'),
                                       str(_site_order).rjust(3, '0'),
                                       str(_torrent.seeders).rjust(10, '0'),
                                       "%s%s" % (_season_len, _episode_len))

        #  Sorting and grouping of matching resources to select the best one to download
        #  Order by site、 Resource matching order、 Do seed number of downloads in reverse order
        torrent_list = sorted(torrent_list, key=lambda x: get_sort_str(x), reverse=True)

        return torrent_list

    def sort_group_torrents(self, torrent_list: List[Context]) -> List[Context]:
        """
        Sorting media messages、 De-emphasize
        """
        if not torrent_list:
            return []

        #  Arrange in order
        torrent_list = self.sort_torrents(torrent_list)

        #  Weight control
        result = []
        _added = []
        #  Arrange in order后重新加入数组，按真实名称控重，即只取每个名称的第一个
        for context in torrent_list:
            #  Weight control的主链是名称、年份、季、集
            meta = context.meta_info
            media = context.media_info
            if media.type == MediaType.TV:
                media_name = "%s%s" % (media.title_year,
                                       meta.season_episode)
            else:
                media_name = media.title_year
            if media_name not in _added:
                _added.append(media_name)
                result.append(context)

        return result

    @staticmethod
    def get_torrent_episodes(files: list) -> list:
        """
        Get all episodes from the seed's file list
        """
        episodes = []
        for file in files:
            if not file:
                continue
            file_path = Path(file)
            if file_path.suffix not in settings.RMT_MEDIAEXT:
                continue
            #  Use only file name recognition
            meta = MetaInfo(file_path.stem)
            if not meta.begin_episode:
                continue
            episodes = list(set(episodes).union(set(meta.episode_list)))
        return episodes
