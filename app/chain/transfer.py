import glob
import re
import shutil
import threading
from pathlib import Path
from typing import List, Optional, Tuple, Union, Dict

from sqlalchemy.orm import Session

from app.chain import ChainBase
from app.chain.media import MediaChain
from app.chain.tmdb import TmdbChain
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfoPath
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.models.downloadhistory import DownloadHistory
from app.db.models.transferhistory import TransferHistory
from app.db.systemconfig_oper import SystemConfigOper
from app.db.transferhistory_oper import TransferHistoryOper
from app.helper.format import FormatParser
from app.helper.progress import ProgressHelper
from app.log import logger
from app.schemas import TransferInfo, TransferTorrent, Notification, EpisodeFormat
from app.schemas.types import TorrentStatus, EventType, MediaType, ProgressKey, NotificationType, MessageChannel, \
    SystemConfigKey
from app.utils.string import StringUtils
from app.utils.system import SystemUtils

lock = threading.Lock()


class TransferChain(ChainBase):
    """
    Document transfer processing chain
    """

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.downloadhis = DownloadHistoryOper(self._db)
        self.transferhis = TransferHistoryOper(self._db)
        self.progress = ProgressHelper()
        self.mediachain = MediaChain(self._db)
        self.tmdbchain = TmdbChain(self._db)
        self.systemconfig = SystemConfigOper()

    def process(self) -> bool:
        """
        Get the list of seeds in the downloader， And execute the transfer
        """

        #  Global lock， Avoiding duplication of processing
        with lock:
            logger.info(" Begin executing downloader file transfers ...")
            #  Get seed list from downloader
            torrents: Optional[List[TransferTorrent]] = self.list_torrents(status=TorrentStatus.TRANSFER)
            if not torrents:
                logger.info(" Completed downloads not fetched")
                return False

            logger.info(f" Get {len(torrents)}  Completed downloads")

            for torrent in torrents:
                #  Query download record recognition
                downloadhis: DownloadHistory = self.downloadhis.get_by_hash(torrent.hash)
                if downloadhis:
                    #  Typology
                    mtype = MediaType(downloadhis.type)
                    #  Check or refer toTMDBID Recognize
                    mediainfo = self.recognize_media(mtype=mtype,
                                                     tmdbid=downloadhis.tmdbid)
                else:
                    #  In-MoviePilot Downloaded tasks， Identification by document
                    mediainfo = None

                #  Execution transfer
                self.do_transfer(path=torrent.path, mediainfo=mediainfo,
                                 download_hash=torrent.hash)

                #  Setting the status of a download task
                self.transfer_completed(hashs=torrent.hash, path=torrent.path)
            #  Close
            logger.info(" Downloader file transfer execution complete")
            return True

    def do_transfer(self, path: Path, meta: MetaBase = None,
                    mediainfo: MediaInfo = None, download_hash: str = None,
                    target: Path = None, transfer_type: str = None,
                    season: int = None, epformat: EpisodeFormat = None,
                    min_filesize: int = 0, force: bool = False) -> Tuple[bool, str]:
        """
        Perform a complex directory transfer operation
        :param path:  Directories or files to be transferred
        :param meta:  Metadata
        :param mediainfo:  Media information
        :param download_hash:  Download recordhash
        :param target:  Target path
        :param transfer_type:  Type of transfer
        :param season:  Classifier for seasonal crop yield or seasons of a tv series
        :param epformat:  Episode format
        :param min_filesize:  Minimum file size(MB)
        :param force:  Compulsory transfer or not
        Come (or go) back： Success story， Error message
        """
        if not transfer_type:
            transfer_type = settings.TRANSFER_TYPE

        #  Obtaining a list of routes to be transferred
        trans_paths = self.__get_trans_paths(path)
        if not trans_paths:
            logger.warn(f"{path.name}  No transferable media files found")
            return False, f"{path.name}  No transferable media files found"

        #  There are sets of customized formats
        formaterHandler = FormatParser(eformat=epformat.format,
                                       details=epformat.detail,
                                       part=epformat.part,
                                       offset=epformat.offset) if epformat else None

        #  Initiation of progress
        self.progress.start(ProgressKey.FileTransfer)
        #  List of all documents in the catalog
        transfer_files = SystemUtils.list_files(directory=path,
                                                extensions=settings.RMT_MEDIAEXT,
                                                min_filesize=min_filesize)
        if formaterHandler:
            #  There are sets of customized formats，过滤文件
            transfer_files = [f for f in transfer_files if formaterHandler.match(f.name)]

        #  Aggregate error messages
        err_msgs: List[str] = []
        #  Total number of documents
        total_num = len(transfer_files)
        #  Number processed
        processed_num = 0
        #  Number of failures
        fail_num = 0
        #  Skip count
        skip_num = 0
        self.progress.update(value=0,
                             text=f" Commencement of transfer {path}， Common {total_num}  File ...",
                             key=ProgressKey.FileTransfer)

        #  Organize blocked words
        transfer_exclude_words = self.systemconfig.get(SystemConfigKey.TransferExcludeWords)

        #  Process all directories or files to be transferred， By default a transfer path or file has only one media message
        for trans_path in trans_paths:
            #  List of summary seasonal episodes
            season_episodes: Dict[Tuple, List[int]] = {}
            #  Aggregated metadata
            metas: Dict[Tuple, MetaBase] = {}
            #  Aggregated media information
            medias: Dict[Tuple, MediaInfo] = {}
            #  Aggregate transfer information
            transfers: Dict[Tuple, TransferInfo] = {}

            #  If it is a catalog and not⼀ Blu-ray disk， Get all files and transfer
            if (not trans_path.is_file()
                    and not SystemUtils.is_bluray_dir(trans_path)):
                #  Iterate over all files in the download directory
                file_paths = SystemUtils.list_files(directory=trans_path,
                                                    extensions=settings.RMT_MEDIAEXT,
                                                    min_filesize=min_filesize)
            else:
                file_paths = [trans_path]

            if formaterHandler:
                #  There are sets of customized formats，过滤文件
                file_paths = [f for f in file_paths if formaterHandler.match(f.name)]

            #  Transfer of all documents
            for file_path in file_paths:
                #  Recycle bin and hidden files not handled
                file_path_str = str(file_path)
                if file_path_str.find('/@Recycle/') != -1 \
                        or file_path_str.find('/#recycle/') != -1 \
                        or file_path_str.find('/.') != -1 \
                        or file_path_str.find('/@eaDir') != -1:
                    logger.debug(f"{file_path_str}  It's the recycle bin or hidden files")
                    #  Reckoning
                    processed_num += 1
                    skip_num += 1
                    continue

                #  Organize blocked words不处理
                is_blocked = False
                if transfer_exclude_words:
                    for keyword in transfer_exclude_words:
                        if not keyword:
                            continue
                        if keyword and re.search(r"%s" % keyword, file_path_str, re.IGNORECASE):
                            logger.info(f"{file_path}  Hit listener's blocking words (computing) {keyword}， Not dealt with")
                            is_blocked = True
                            break
                if is_blocked:
                    err_msgs.append(f"{file_path.name}  Hit listener's blocking words (computing)")
                    #  Reckoning
                    processed_num += 1
                    skip_num += 1
                    continue

                #  Successful transfers are no longer processed
                if not force:
                    transferd = self.transferhis.get_by_src(file_path_str)
                    if transferd and transferd.status:
                        logger.info(f"{file_path}  Successfully transferred， If reprocessing is required， Please delete the history。")
                        #  Reckoning
                        processed_num += 1
                        skip_num += 1
                        continue

                #  Update progress
                self.progress.update(value=processed_num / total_num * 100,
                                     text=f" Moving. （{processed_num + 1}/{total_num}）{file_path.name} ...",
                                     key=ProgressKey.FileTransfer)

                if not meta:
                    #  Document metadata
                    file_meta = MetaInfoPath(file_path)
                else:
                    file_meta = meta

                #  Merger season
                if season is not None:
                    file_meta.begin_season = season

                if not file_meta:
                    logger.error(f"{file_path}  Unable to recognize valid information")
                    err_msgs.append(f"{file_path}  Unable to recognize valid information")
                    #  Reckoning
                    processed_num += 1
                    fail_num += 1
                    continue

                #  Custom recognition
                if formaterHandler:
                    #  Initial set、 Endgame、PART
                    begin_ep, end_ep, part = formaterHandler.split_episode(file_path.stem)
                    if begin_ep is not None:
                        file_meta.begin_episode = begin_ep
                        file_meta.part = part
                    if end_ep is not None:
                        file_meta.end_episode = end_ep

                if not mediainfo:
                    #  Identify media messages
                    file_mediainfo = self.recognize_media(meta=file_meta)
                else:
                    file_mediainfo = mediainfo

                if not file_mediainfo:
                    logger.warn(f'{file_path}  No media messages recognized')
                    #  Added transfer failure history
                    his = self.transferhis.add_fail(
                        src_path=file_path,
                        mode=transfer_type,
                        meta=file_meta,
                        download_hash=download_hash
                    )
                    self.post_message(Notification(
                        mtype=NotificationType.Manual,
                        title=f"{file_path.name}  No media messages recognized， Out of stock！\n"
                              f" Return (to a previous condition)：```\n/redo {his.id} [tmdbid]|[ Typology]\n```  Manual recognition transfer。"
                    ))
                    #  Reckoning
                    processed_num += 1
                    fail_num += 1
                    continue

                #  If not enabled does the new inbound media follow theTMDB Information changes are then based ontmdbid Query the previoustitle
                if not settings.SCRAP_FOLLOW_TMDB:
                    transfer_history = self.transferhis.get_by_type_tmdbid(tmdbid=file_mediainfo.tmdb_id,
                                                                           mtype=file_mediainfo.type.value)
                    if transfer_history:
                        file_mediainfo.title = transfer_history.title

                logger.info(f"{file_path.name}  Identify as：{file_mediainfo.type.value} {file_mediainfo.title_year}")

                #  Updating media images
                self.obtain_images(mediainfo=file_mediainfo)

                #  Getting set data
                if file_mediainfo.type == MediaType.TV:
                    episodes_info = self.tmdbchain.tmdb_episodes(tmdbid=file_mediainfo.tmdb_id,
                                                                 season=file_meta.begin_season or 1)
                else:
                    episodes_info = None

                #  Get downloadhash
                if not download_hash:
                    download_file = self.downloadhis.get_file_by_fullpath(file_path_str)
                    if download_file:
                        download_hash = download_file.download_hash

                #  Execution transfer
                transferinfo: TransferInfo = self.transfer(meta=file_meta,
                                                           mediainfo=file_mediainfo,
                                                           path=file_path,
                                                           transfer_type=transfer_type,
                                                           target=target,
                                                           episodes_info=episodes_info)
                if not transferinfo:
                    logger.error(" Failure to run the file transfer module")
                    return False, " Failure to run the file transfer module"
                if not transferinfo.success:
                    #  Transfer failure
                    logger.warn(f"{file_path.name}  Failure to stock：{transferinfo.message}")
                    err_msgs.append(f"{file_path.name} {transferinfo.message}")
                    #  Added transfer failure history
                    self.transferhis.add_fail(
                        src_path=file_path,
                        mode=transfer_type,
                        download_hash=download_hash,
                        meta=file_meta,
                        mediainfo=file_mediainfo,
                        transferinfo=transferinfo
                    )
                    #  Send a message
                    self.post_message(Notification(
                        mtype=NotificationType.Manual,
                        title=f"{file_mediainfo.title_year} {file_meta.season_episode}  Failure to stock！",
                        text=f" Rationale：{transferinfo.message or ' Uncharted'}",
                        image=file_mediainfo.get_message_image()
                    ))
                    #  Reckoning
                    processed_num += 1
                    fail_num += 1
                    continue

                #  Summary information
                mkey = (file_mediainfo.tmdb_id, file_meta.begin_season)
                if mkey not in medias:
                    #  New information
                    metas[mkey] = file_meta
                    medias[mkey] = file_mediainfo
                    season_episodes[mkey] = file_meta.episode_list
                    transfers[mkey] = transferinfo
                else:
                    #  Merger season集清单
                    season_episodes[mkey] = list(set(season_episodes[mkey] + file_meta.episode_list))
                    #  Consolidation of transfer data
                    transfers[mkey].file_count += transferinfo.file_count
                    transfers[mkey].total_size += transferinfo.total_size
                    transfers[mkey].file_list.extend(transferinfo.file_list)
                    transfers[mkey].file_list_new.extend(transferinfo.file_list_new)
                    transfers[mkey].fail_list.extend(transferinfo.fail_list)

                #  Add transfer success history
                self.transferhis.add_success(
                    src_path=file_path,
                    mode=transfer_type,
                    download_hash=download_hash,
                    meta=file_meta,
                    mediainfo=file_mediainfo,
                    transferinfo=transferinfo
                )
                #  Scraping of individual documents
                if settings.SCRAP_METADATA:
                    self.scrape_metadata(path=transferinfo.target_path, mediainfo=file_mediainfo)
                #  Update progress
                processed_num += 1
                self.progress.update(value=processed_num / total_num * 100,
                                     text=f"{file_path.name}  Transfer completed",
                                     key=ProgressKey.FileTransfer)

            #  Directory or file transfer complete
            self.progress.update(text=f"{trans_path}  Transfer completed， Follow-up being implemented ...",
                                 key=ProgressKey.FileTransfer)

            #  Implementation follow-up
            for mkey, media in medias.items():
                transfer_meta = metas[mkey]
                transfer_info = transfers[mkey]
                #  Media catalog
                if transfer_info.target_path.is_file():
                    transfer_info.target_path = transfer_info.target_path.parent
                #  Refresh media library， Root or quarter directory
                if settings.REFRESH_MEDIASERVER:
                    self.refresh_mediaserver(mediainfo=media, file_path=transfer_info.target_path)
                #  Send notification
                se_str = None
                if media.type == MediaType.TV:
                    se_str = f"{transfer_meta.season} {StringUtils.format_ep(season_episodes[mkey])}"
                self.send_transfer_message(meta=transfer_meta,
                                           mediainfo=media,
                                           transferinfo=transfer_info,
                                           season_episode=se_str)
                #  Broadcasting incident
                self.eventmanager.send_event(EventType.TransferComplete, {
                    'meta': transfer_meta,
                    'mediainfo': media,
                    'transferinfo': transfer_info
                })

        #  Close进度
        logger.info(f"{path}  Transfer completed， Common {total_num}  File，"
                    f" Fail (e.g. experiments) {fail_num}  Classifier for individual things or people, general, catch-all classifier， Skip over {skip_num}  Classifier for individual things or people, general, catch-all classifier")

        self.progress.update(value=100,
                             text=f"{path}  Transfer completed， Common {total_num}  File，"
                                  f" Fail (e.g. experiments) {fail_num}  Classifier for individual things or people, general, catch-all classifier， Skip over {skip_num}  Classifier for individual things or people, general, catch-all classifier",
                             key=ProgressKey.FileTransfer)
        self.progress.end(ProgressKey.FileTransfer)

        return True, "\n".join(err_msgs)

    @staticmethod
    def __get_trans_paths(directory: Path):
        """
        Get a list of transfer catalogs
        """

        if not directory.exists():
            logger.warn(f" Catalog does not exist：{directory}")
            return []

        #  Single document
        if directory.is_file():
            return [directory]

        #  Blu-ray disk
        if SystemUtils.is_bluray_dir(directory):
            return [directory]

        #  List of paths to be transferred
        trans_paths = []

        #  First check the current directory's lower level directories， To support the case of ensembles
        for sub_dir in SystemUtils.list_sub_directory(directory):
            #  If it's the original blu-ray
            if SystemUtils.is_bluray_dir(sub_dir):
                trans_paths.append(sub_dir)
            #  Directories without media files are skipped
            elif SystemUtils.list_files(sub_dir, extensions=settings.RMT_MEDIAEXT):
                trans_paths.append(sub_dir)

        if not trans_paths:
            #  No valid subdirectories， Direct transfer of the current directory
            trans_paths.append(directory)
        else:
            #  When there are subdirectories， Add files from the current directory to the transfer task
            trans_paths.extend(
                SystemUtils.list_sub_files(directory, extensions=settings.RMT_MEDIAEXT)
            )
        return trans_paths

    def remote_transfer(self, arg_str: str, channel: MessageChannel, userid: Union[str, int] = None):
        """
        Remote retransfer， Parameters  Historical recordID TMDBID| Typology
        """

        def args_error():
            self.post_message(Notification(channel=channel,
                                           title=" Please enter the correct command format：/redo [id] [tmdbid]|[ Typology]，"
                                                 "[id] Historical record number", userid=userid))

        if not arg_str:
            args_error()
            return
        arg_strs = str(arg_str).split()
        if len(arg_strs) != 2:
            args_error()
            return
        #  Historical recordID
        logid = arg_strs[0]
        if not logid.isdigit():
            args_error()
            return
        # TMDB ID
        tmdb_strs = arg_strs[1].split('|')
        tmdbid = tmdb_strs[0]
        if not logid.isdigit():
            args_error()
            return
        #  Typology
        type_str = tmdb_strs[1] if len(tmdb_strs) > 1 else None
        if not type_str or type_str not in [MediaType.MOVIE.value, MediaType.TV.value]:
            args_error()
            return
        state, errmsg = self.re_transfer(logid=int(logid),
                                         mtype=MediaType(type_str), tmdbid=int(tmdbid))
        if not state:
            self.post_message(Notification(channel=channel, title=" Failed to organize manually",
                                           text=errmsg, userid=userid))
            return

    def re_transfer(self, logid: int,
                    mtype: MediaType = None, tmdbid: int = None) -> Tuple[bool, str]:
        """
        Based on historical records， Re-identification transfer， Only process the correspondingsrc Catalogs
        :param logid:  Historical recordID
        :param mtype:  Media type
        :param tmdbid: TMDB ID
        """
        #  Query history
        history: TransferHistory = self.transferhis.get(logid)
        if not history:
            logger.error(f" History does not exist，ID：{logid}")
            return False, " History does not exist"
        #  No download history， Re-transfer by source directory path
        src_path = Path(history.src)
        if not src_path.exists():
            return False, f" Source directory does not exist：{src_path}"
        dest_path = Path(history.dest) if history.dest else None
        #  Search for media information
        if mtype and tmdbid:
            mediainfo = self.recognize_media(mtype=mtype, tmdbid=tmdbid)
        else:
            meta = MetaInfoPath(src_path)
            mediainfo = self.recognize_media(meta=meta)
        if not mediainfo:
            return False, f" No media messages recognized， Typology：{mtype.value}，tmdbid：{tmdbid}"
        #  Re-implementation of transfers
        logger.info(f"{src_path.name}  Identify as：{mediainfo.title_year}")
        #  Updating media images
        self.obtain_images(mediainfo=mediainfo)

        #  Deleting old organized files
        if history.dest:
            self.delete_files(Path(history.dest))

        #  Forcible transfer
        state, errmsg = self.do_transfer(path=src_path,
                                         mediainfo=mediainfo,
                                         download_hash=history.download_hash,
                                         target=dest_path,
                                         force=True)
        if not state:
            return False, errmsg

        return True, ""

    def manual_transfer(self, in_path: Path,
                        target: Path = None,
                        tmdbid: int = None,
                        mtype: MediaType = None,
                        season: int = None,
                        transfer_type: str = None,
                        epformat: EpisodeFormat = None,
                        min_filesize: int = 0) -> Tuple[bool, Union[str, list]]:
        """
        Manual transfer
        :param in_path:  Source file path
        :param target:  Target path
        :param tmdbid: TMDB ID
        :param mtype:  Media type
        :param season:  Classifier for seasonal crop yield or seasons of a tv series度
        :param transfer_type:  Type of transfer
        :param epformat:  Episode format
        :param min_filesize:  Minimum file size(MB)
        """
        logger.info(f"Manual transfer：{in_path} ...")

        if tmdbid:
            #  InputtedTMDBID Time interval recognition
            #  Identify media messages
            mediainfo: MediaInfo = self.mediachain.recognize_media(tmdbid=tmdbid, mtype=mtype)
            if not mediainfo:
                return False, f" Media message recognition failure，tmdbid: {tmdbid}, type: {mtype.value}"
            #  Initiation of progress
            self.progress.start(ProgressKey.FileTransfer)
            self.progress.update(value=0,
                                 text=f" Commencement of transfer {in_path} ...",
                                 key=ProgressKey.FileTransfer)
            #  Commencement of transfer
            state, errmsg = self.do_transfer(
                path=in_path,
                mediainfo=mediainfo,
                target=target,
                season=season,
                epformat=epformat,
                min_filesize=min_filesize
            )
            if not state:
                return False, errmsg

            self.progress.end(ProgressKey.FileTransfer)
            logger.info(f"{in_path}  Transfer completed")
            return True, ""
        else:
            #  No inputTMDBID Hour， Identification by document
            state, errmsg = self.do_transfer(path=in_path,
                                             target=target,
                                             transfer_type=transfer_type,
                                             season=season,
                                             epformat=epformat,
                                             min_filesize=min_filesize)
            return state, errmsg

    def send_transfer_message(self, meta: MetaBase, mediainfo: MediaInfo,
                              transferinfo: TransferInfo, season_episode: str = None):
        """
        Send inbound success message
        """
        msg_title = f"{mediainfo.title_year} {meta.season_episode if not season_episode else season_episode}  In stock"
        if mediainfo.vote_average:
            msg_str = f" Score (of student's work)：{mediainfo.vote_average}， Typology：{mediainfo.type.value}"
        else:
            msg_str = f" Typology：{mediainfo.type.value}"
        if mediainfo.category:
            msg_str = f"{msg_str}， Form：{mediainfo.category}"
        if meta.resource_term:
            msg_str = f"{msg_str}， Mass (in physics)：{meta.resource_term}"
        msg_str = f"{msg_str}， Common{transferinfo.file_count} File，" \
                  f" Adults and children：{StringUtils.str_filesize(transferinfo.total_size)}"
        if transferinfo.message:
            msg_str = f"{msg_str}， The following files failed to be processed：\n{transferinfo.message}"
        #  Dispatch
        self.post_message(Notification(
            mtype=NotificationType.Organize,
            title=msg_title, text=msg_str, image=mediainfo.get_message_image()))

    @staticmethod
    def delete_files(path: Path):
        """
        Delete transferred files and empty directories
        :param path:  File path
        """
        logger.info(f" Start deleting files and empty directories：{path} ...")
        if not path.exists():
            return
        if path.is_file():
            #  Delete file、nfo、jpg And other documents of the same name
            pattern = path.stem.replace('[', '?').replace(']', '?')
            files = path.parent.glob(f"{pattern}.*")
            for file in files:
                Path(file).unlink()
            logger.warn(f" File {path}  Deleted")
            #  Parent directory needs to be deleted
        elif str(path.parent) == str(path.root):
            #  Root directory， Non-deletion
            logger.warn(f" Root directory {path}  Cannot be deleted！")
            return
        else:
            #  Non-root directory， Just deleted the directory.
            shutil.rmtree(path)
            #  Delete catalog
            logger.warn(f" Catalogs {path}  Deleted")
            #  Parent directory needs to be deleted

        #  Determine if there is a media file under the current media parent path， There is no need to traverse the parent if
        if not SystemUtils.exits_files(path.parent, settings.RMT_MEDIAEXT):
            #  Root path for secondary categorization of media libraries
            library_root_names = [
                settings.LIBRARY_MOVIE_NAME or ' Cinematic',
                settings.LIBRARY_TV_NAME or ' Dramas',
                settings.LIBRARY_ANIME_NAME or ' Cartoons and comics',
            ]

            #  Determine if the parent directory is empty,  Delete if empty
            for parent_path in path.parents:
                #  Iterate the parent directory to the root path of the media library secondary category
                if str(parent_path.name) in library_root_names:
                    break
                if str(parent_path.parent) != str(path.root):
                    #  Parent directory is not the root directory， Before deleting the parent directory.
                    if not SystemUtils.exits_files(parent_path, settings.RMT_MEDIAEXT):
                        #  Delete if there are no media files in the current path
                        shutil.rmtree(parent_path)
                        logger.warn(f" Catalogs {parent_path}  Deleted")
