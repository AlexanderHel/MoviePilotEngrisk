import shutil
import time
from pathlib import Path
from typing import Tuple, Union

from lxml import etree

from app.core.config import settings
from app.core.context import Context
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.modules import _ModuleBase
from app.utils.http import RequestUtils
from app.utils.string import StringUtils
from app.utils.system import SystemUtils


class SubtitleModule(_ModuleBase):
    """
    Subtitle download module
    """

    #  Recognition of subtitle download links on site details pageXPATH
    _SITE_SUBTITLE_XPATH = [
        '//td[@class="rowhead"][text()=" Subtitling"]/following-sibling::td//a/@href',
    ]

    def init_module(self) -> None:
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

    def stop(self) -> None:
        pass

    def download_added(self, context: Context, download_dir: Path, torrent_path: Path = None) -> None:
        """
        After adding a successful download task， Download subtitles from the site， Save to download directory
        :param context:   (textual) context， Includes identifying information、 Media information、 Seed information
        :param download_dir:   Download catalog
        :param torrent_path:   Seed file address
        :return: None， This method can be processed by multiple modules simultaneously
        """
        if not settings.DOWNLOAD_SUBTITLE:
            return None

        #  No seed files are not processed
        if not torrent_path:
            return

        #  No detail page not processed
        torrent = context.torrent_info
        if not torrent.page_url:
            return
        #  Subtitle download catalog
        logger.info(" Start downloading subtitles from the site：%s" % torrent.page_url)
        #  Getting seed information
        folder_name, _ = TorrentHelper.get_torrent_info(torrent_path)
        #  File save directory， If the seed is a single file， Imitatefolder_name Emptiness， At this point, the file save directory is the download directory
        download_dir = download_dir / folder_name
        #  Wait for the catalog to exist
        for _ in range(30):
            if download_dir.exists():
                break
            time.sleep(1)
        #  Catalog still doesn't exist， And has a folder name， Then create the directory
        if not download_dir.exists() and folder_name:
            download_dir.mkdir(parents=True, exist_ok=True)
        #  Read website code
        request = RequestUtils(cookies=torrent.site_cookie, ua=torrent.site_ua)
        res = request.get_res(torrent.page_url)
        if res and res.status_code == 200:
            if not res.text:
                logger.warn(f" Failed to read page code：{torrent.page_url}")
                return
            html = etree.HTML(res.text)
            sublink_list = []
            for xpath in self._SITE_SUBTITLE_XPATH:
                sublinks = html.xpath(xpath)
                if sublinks:
                    for sublink in sublinks:
                        if not sublink:
                            continue
                        if not sublink.startswith("http"):
                            base_url = StringUtils.get_base_url(torrent.page_url)
                            if sublink.startswith("/"):
                                sublink = "%s%s" % (base_url, sublink)
                            else:
                                sublink = "%s/%s" % (base_url, sublink)
                        sublink_list.append(sublink)
            #  Download all subtitle files
            for sublink in sublink_list:
                logger.info(f" Find subtitle download links：{sublink}， Start download...")
                #  Downloading
                ret = request.get_res(sublink)
                if ret and ret.status_code == 200:
                    #  Save (a file etc) (computing)ZIP
                    file_name = TorrentHelper.get_url_filename(ret, sublink)
                    if not file_name:
                        logger.warn(f" The link is not a subtitle file.：{sublink}")
                        continue
                    if file_name.lower().endswith(".zip"):
                        # ZIP Contract (to or for)
                        zip_file = settings.TEMP_PATH / file_name
                        #  Save (a file etc) (computing)
                        zip_file.write_bytes(ret.content)
                        #  Unzip path
                        zip_path = zip_file.with_name(zip_file.stem)
                        #  Unzip the file
                        shutil.unpack_archive(zip_file, zip_path, format='zip')
                        #  Traversing the transfer file
                        for sub_file in SystemUtils.list_files(zip_path, settings.RMT_SUBEXT):
                            target_sub_file = download_dir / sub_file.name
                            if target_sub_file.exists():
                                logger.info(f" Subtitle file already exists：{target_sub_file}")
                                continue
                            logger.info(f" Subtitle transfer {sub_file}  Until (a time) {target_sub_file} ...")
                            SystemUtils.copy(sub_file, target_sub_file)
                        #  Deletion of temporary files
                        try:
                            shutil.rmtree(zip_path)
                            zip_file.unlink()
                        except Exception as err:
                            logger.error(f" Failure to delete temporary files：{err}")
                    else:
                        sub_file = settings.TEMP_PATH / file_name
                        #  Save (a file etc) (computing)
                        sub_file.write_bytes(ret.content)
                        target_sub_file = download_dir / sub_file.name
                        logger.info(f" Subtitle transfer {sub_file}  Until (a time) {target_sub_file}")
                        SystemUtils.copy(sub_file, target_sub_file)
                else:
                    logger.error(f" Failed to download subtitle file：{sublink}")
                    continue
            if sublink_list:
                logger.info(f"{torrent.page_url}  Page subtitle download complete")
            else:
                logger.warn(f"{torrent.page_url}  Subtitle download link not found on page")
        elif res is not None:
            logger.warn(f" Grout {torrent.page_url}  Fail (e.g. experiments)， Status code：{res.status_code}")
        else:
            logger.warn(f" Unable to open link：{torrent.page_url}")
