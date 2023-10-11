import re
from pathlib import Path
from threading import Lock
from typing import Optional, List, Tuple, Union, Dict

from jinja2 import Template

from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.schemas import TransferInfo, ExistMediaInfo, TmdbEpisode
from app.schemas.types import MediaType
from app.utils.system import SystemUtils

lock = Lock()


class FileTransferModule(_ModuleBase):

    def init_module(self) -> None:
        pass

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

    def transfer(self, path: Path, meta: MetaBase, mediainfo: MediaInfo,
                 transfer_type: str, target: Path = None,
                 episodes_info: List[TmdbEpisode] = None) -> TransferInfo:
        """
        File transfer
        :param path:   File path
        :param meta: 预识别的元数据，仅单File transfer时传递
        :param mediainfo:   Identified media messages
        :param transfer_type:   Migration pattern
        :param target:   Target path
        :param episodes_info:  All episode information for the current season
        :return: {path, target_path, message}
        """
        #  Getting the target path
        if not target:
            target = self.get_target_path(in_path=path)
        else:
            target = self.get_library_path(target)
        if not target:
            logger.error(" Media library catalog not found， Unable to transfer files")
            return TransferInfo(success=False,
                                path=path,
                                message=" Media library catalog not found")
        #  Divert or distract (attention etc)
        return self.transfer_media(in_path=path,
                                   in_meta=meta,
                                   mediainfo=mediainfo,
                                   transfer_type=transfer_type,
                                   target_dir=target,
                                   episodes_info=episodes_info)

    @staticmethod
    def __transfer_command(file_item: Path, target_file: Path, transfer_type: str) -> int:
        """
        Using system commands to process individual files
        :param file_item:  File path
        :param target_file:  Target file path
        :param transfer_type: RmtMode Migration pattern
        """
        with lock:

            #  Divert or distract (attention etc)
            if transfer_type == 'link':
                #  Hard link
                retcode, retmsg = SystemUtils.link(file_item, target_file)
            elif transfer_type == 'softlink':
                #  Soft link (computing)
                retcode, retmsg = SystemUtils.softlink(file_item, target_file)
            elif transfer_type == 'move':
                #  Mobility
                retcode, retmsg = SystemUtils.move(file_item, target_file)
            elif transfer_type == 'rclone_move':
                # Rclone Move
                retcode, retmsg = SystemUtils.rclone_move(file_item, target_file)
            elif transfer_type == 'rclone_copy':
                # Rclone Copy
                retcode, retmsg = SystemUtils.rclone_copy(file_item, target_file)
            else:
                #  Make a copy of
                retcode, retmsg = SystemUtils.copy(file_item, target_file)

        if retcode != 0:
            logger.error(retmsg)

        return retcode

    def __transfer_other_files(self, org_path: Path, new_path: Path,
                               transfer_type: str, over_flag: bool) -> int:
        """
        Transfer of other related documents by filename
        :param org_path:  Original filename
        :param new_path:  New filename
        :param transfer_type: RmtMode Migration pattern
        :param over_flag:  Whether or not to override， Because ofTrue It will be deleted and then transferred.
        """
        retcode = self.__transfer_subtitles(org_path, new_path, transfer_type)
        if retcode != 0:
            return retcode
        retcode = self.__transfer_audio_track_files(org_path, new_path, transfer_type, over_flag)
        if retcode != 0:
            return retcode
        return 0

    def __transfer_subtitles(self, org_path: Path, new_path: Path, transfer_type: str) -> int:
        """
        Transfer the corresponding subtitle file according to the file name
        :param org_path:  Original filename
        :param new_path:  New filename
        :param transfer_type: RmtMode Migration pattern
        """
        #  Regular formula for subtitles
        _zhcn_sub_re = r"([.\[(](((zh[-_])?(cn|ch[si]|sg|sc))|zho?" \
                       r"|chinese|(cn|ch[si]|sg|zho?|eng)[-_&](cn|ch[si]|sg|zho?|eng)" \
                       r"| Bamboo strips used for writing (old)[ Embodiment]?)[.\])])" \
                       r"|([\u4e00-\u9fa5]{0,3}[ Both sides of the coin][\u4e00-\u9fa5]{0,2}[ Literary language][\u4e00-\u9fa5]{0,3})" \
                       r"| Simplified chinese| Simple chinese|JPSC" \
                       r"|(?<![a-z0-9])gb(?![a-z0-9])"
        _zhtw_sub_re = r"([.\[(](((zh[-_])?(hk|tw|cht|tc))" \
                       r"| In great numbers[ Embodiment]?)[.\])])" \
                       r"| Traditional chinese[ Writing style]| Center[ Writing style] Elaborate form| Elaborate form|JPTC" \
                       r"|(?<![a-z0-9])big5(?![a-z0-9])"
        _eng_sub_re = r"[.\[(]eng[.\])]"

        #  Compare filenames and transfer subtitles
        org_dir: Path = org_path.parent
        file_list: List[Path] = SystemUtils.list_files(org_dir, settings.RMT_SUBEXT)
        if len(file_list) == 0:
            logger.debug(f"{org_dir}  No subtitle files found in the directory...")
        else:
            logger.debug(" List of subtitle files：" + str(file_list))
            #  Recognizing file names
            metainfo = MetaInfo(title=org_path.name)
            for file_item in file_list:
                #  Recognizing subtitle file names
                sub_file_name = re.sub(_zhtw_sub_re,
                                       ".",
                                       re.sub(_zhcn_sub_re,
                                              ".",
                                              file_item.name,
                                              flags=re.I),
                                       flags=re.I)
                sub_file_name = re.sub(_eng_sub_re, ".", sub_file_name, flags=re.I)
                sub_metainfo = MetaInfo(title=file_item.name)
                #  Match subtitle file name
                if (org_path.stem == Path(sub_file_name).stem) or \
                        (sub_metainfo.cn_name and sub_metainfo.cn_name == metainfo.cn_name) \
                        or (sub_metainfo.en_name and sub_metainfo.en_name == metainfo.en_name):
                    if metainfo.season \
                            and metainfo.season != sub_metainfo.season:
                        continue
                    if metainfo.episode \
                            and metainfo.episode != sub_metainfo.episode:
                        continue
                    new_file_type = ""
                    #  Compatibilityjellyfin Subtitle recognition( Multiple identification), emby Then the last suffix will be recognized
                    if re.search(_zhcn_sub_re, file_item.name, re.I):
                        new_file_type = ".chi.zh-cn"
                    elif re.search(_zhtw_sub_re, file_item.name,
                                   re.I):
                        new_file_type = ".zh-tw"
                    elif re.search(_eng_sub_re, file_item.name, re.I):
                        new_file_type = ".eng"
                    #  By comparing subtitle file sizes   Try to transfer all the subtitles present
                    file_ext = file_item.suffix
                    new_sub_tag_dict = {
                        ".eng": ". English (language)",
                        ".chi.zh-cn": ". Simplified chinese",
                        ".zh-tw": ". Traditional chinese"
                    }
                    new_sub_tag_list = [
                        new_file_type if t == 0 else "%s%s(%s)" % (new_file_type,
                                                                   new_sub_tag_dict.get(
                                                                       new_file_type, ""
                                                                   ),
                                                                   t) for t in range(6)
                    ]
                    for new_sub_tag in new_sub_tag_list:
                        new_file: Path = new_path.with_name(new_path.stem + new_sub_tag + file_ext)
                        #  If the subtitle file does not exist,  Direct transfer subtitles,  And jump out of the loop
                        try:
                            if not new_file.exists():
                                logger.debug(f" Subtitles are being processed.：{file_item.name}")
                                retcode = self.__transfer_command(file_item=file_item,
                                                                  target_file=new_file,
                                                                  transfer_type=transfer_type)
                                if retcode == 0:
                                    logger.info(f" Subtitling {file_item.name} {transfer_type} Fulfillment")
                                    break
                                else:
                                    logger.error(f" Subtitling {file_item.name} {transfer_type} Fail (e.g. experiments)， Error code {retcode}")
                                    return retcode
                            #  If the subtitle file is the same size as an existing file,  It means it's been transferred.,  Then jump out of the loop
                            elif new_file.stat().st_size == file_item.stat().st_size:
                                logger.info(f" Subtitling new_file  Pre-existing")
                                break
                            #  If not  The cycle continues >  Pass (a bill or inspection etc)new_sub_tag_list  Get newtag Attach to subtitle filename,  Keep checking to see if you can transfer
                        except OSError as reason:
                            logger.info(f" Subtitling {new_file}  There's been an error., Rationale: {reason}")
        return 0

    def __transfer_audio_track_files(self, org_path: Path, new_path: Path,
                                     transfer_type: str, over_flag: bool) -> int:
        """
        Transfer the corresponding track file according to its filename
        :param org_path:  Original filename
        :param new_path:  New filename
        :param transfer_type: RmtMode Migration pattern
        :param over_flag:  Whether or not to override， Because ofTrue It will be deleted and then transferred.
        """
        dir_name = org_path.parent
        file_name = org_path.name
        file_list: List[Path] = SystemUtils.list_files(dir_name, ['.mka'])
        pending_file_list: List[Path] = [file for file in file_list if org_path.stem == file.stem]
        if len(pending_file_list) == 0:
            logger.debug(f"{dir_name}  No matching track file found in the directory")
        else:
            logger.debug(" Track file list：" + str(pending_file_list))
            for track_file in pending_file_list:
                track_ext = track_file.suffix
                new_track_file = new_path.with_name(new_path.stem + track_ext)
                if new_track_file.exists():
                    if not over_flag:
                        logger.warn(f" Track file already exists：{new_track_file}")
                        continue
                    else:
                        logger.info(f" Existing track files are being deleted：{new_track_file}")
                        new_track_file.unlink()
                try:
                    logger.info(f" Transferring track files：{track_file}  Until (a time) {new_track_file}")
                    retcode = self.__transfer_command(file_item=track_file,
                                                      target_file=new_track_file,
                                                      transfer_type=transfer_type)
                    if retcode == 0:
                        logger.info(f" Audio track files {file_name} {transfer_type} Fulfillment")
                    else:
                        logger.error(f" Audio track files {file_name} {transfer_type} Fail (e.g. experiments)， Error code：{retcode}")
                except OSError as reason:
                    logger.error(f" Audio track files {file_name} {transfer_type} Fail (e.g. experiments)：{reason}")
        return 0

    def __transfer_dir(self, file_path: Path, new_path: Path, transfer_type: str) -> int:
        """
        Transferring an entire folder
        :param file_path:  Original path
        :param new_path:  New pathway
        :param transfer_type: RmtMode Migration pattern
        """
        logger.info(f" In the process of (doing something or happening){transfer_type} Catalogs：{file_path}  Until (a time) {new_path}")
        #  Make a copy of
        retcode = self.__transfer_dir_files(src_dir=file_path,
                                            target_dir=new_path,
                                            transfer_type=transfer_type)
        if retcode == 0:
            logger.info(f" File {file_path} {transfer_type} Fulfillment")
        else:
            logger.error(f" File{file_path} {transfer_type} Fail (e.g. experiments)， Error code：{retcode}")

        return retcode

    def __transfer_dir_files(self, src_dir: Path, target_dir: Path, transfer_type: str) -> int:
        """
        Transfer all files in a directory by directory structure
        :param src_dir:  Original path
        :param target_dir:  New pathway
        :param transfer_type: RmtMode Migration pattern
        """
        retcode = 0
        for file in src_dir.glob("**/*"):
            #  Filter out directories
            if file.is_dir():
                continue
            #  Utilizationtarget_dir As the new parent directory of the
            new_file = target_dir.joinpath(file.relative_to(src_dir))
            if new_file.exists():
                logger.warn(f"{new_file}  File already exists")
                continue
            if not new_file.parent.exists():
                new_file.parent.mkdir(parents=True, exist_ok=True)
            retcode = self.__transfer_command(file_item=file,
                                              target_file=new_file,
                                              transfer_type=transfer_type)
            if retcode != 0:
                break

        return retcode

    def __transfer_file(self, file_item: Path, new_file: Path, transfer_type: str,
                        over_flag: bool = False) -> int:
        """
        Transferring a file， Simultaneous processing of other relevant documents
        :param file_item:  Original file path
        :param new_file:  New file path
        :param transfer_type: RmtMode Migration pattern
        :param over_flag:  Whether or not to override， Because ofTrue It will be deleted and then transferred.
        """
        if new_file.exists():
            if not over_flag:
                logger.warn(f" File already exists：{new_file}")
                return 0
            else:
                logger.info(f" Existing files are being deleted：{new_file}")
                new_file.unlink()
        logger.info(f" Transferring files：{file_item}  Until (a time) {new_file}")
        #  Creating a parent directory
        new_file.parent.mkdir(parents=True, exist_ok=True)
        retcode = self.__transfer_command(file_item=file_item,
                                          target_file=new_file,
                                          transfer_type=transfer_type)
        if retcode == 0:
            logger.info(f" File {file_item} {transfer_type} Fulfillment")
        else:
            logger.error(f" File {file_item} {transfer_type} Fail (e.g. experiments)， Error code：{retcode}")
            return retcode
        #  Processing of other relevant documents
        return self.__transfer_other_files(org_path=file_item,
                                           new_path=new_file,
                                           transfer_type=transfer_type,
                                           over_flag=over_flag)

    @staticmethod
    def __get_dest_dir(mediainfo: MediaInfo, target_dir: Path) -> Path:
        """
        Based on the setup and installation of the media library directory
        :param mediainfo:  Media information
        :target_dir:  Media library root directory
        """
        if mediainfo.type == MediaType.MOVIE:
            #  Cinematic
            if settings.LIBRARY_MOVIE_NAME:
                target_dir = target_dir / settings.LIBRARY_MOVIE_NAME / mediainfo.category
            else:
                #  Purpose directory plus type and secondary categorization
                target_dir = target_dir / mediainfo.type.value / mediainfo.category

        if mediainfo.type == MediaType.TV:
            #  Dramas
            if settings.LIBRARY_ANIME_NAME \
                    and mediainfo.genre_ids \
                    and set(mediainfo.genre_ids).intersection(set(settings.ANIME_GENREIDS)):
                #  Cartoons and comics
                target_dir = target_dir / settings.LIBRARY_ANIME_NAME / mediainfo.category
            elif settings.LIBRARY_TV_NAME:
                #  Dramas
                target_dir = target_dir / settings.LIBRARY_TV_NAME / mediainfo.category
            else:
                #  Purpose directory plus type and secondary categorization
                target_dir = target_dir / mediainfo.type.value / mediainfo.category
        return target_dir

    def transfer_media(self,
                       in_path: Path,
                       in_meta: MetaBase,
                       mediainfo: MediaInfo,
                       transfer_type: str,
                       target_dir: Path,
                       episodes_info: List[TmdbEpisode] = None
                       ) -> TransferInfo:
        """
        Identify and move a file or all files in a directory
        :param in_path:  Paths of transfer， May be a file or a directory
        :param in_meta： Pre-identified metadata
        :param mediainfo:  Media information
        :param target_dir:  Media library root directory
        :param transfer_type: File transfer方式
        :param episodes_info:  All episode information for the current season
        :return: TransferInfo、 Error message
        """
        #  Checking directory paths
        if not in_path.exists():
            return TransferInfo(success=False,
                                path=in_path,
                                message=f"{in_path}  Path does not exist")

        if not target_dir.exists():
            return TransferInfo(success=False,
                                path=in_path,
                                message=f"{target_dir}  Target path does not exist")

        #  Catalog of media library purposes
        target_dir = self.__get_dest_dir(mediainfo=mediainfo, target_dir=target_dir)

        #  Rename format
        rename_format = settings.TV_RENAME_FORMAT \
            if mediainfo.type == MediaType.TV else settings.MOVIE_RENAME_FORMAT

        #  Determine if a folder
        if in_path.is_dir():
            #  Divert or distract (attention etc)整个目录
            #  Whether or not the original blu-ray disc
            bluray_flag = SystemUtils.is_bluray_dir(in_path)
            if bluray_flag:
                logger.info(f"{in_path}  It's the original blu-ray folder.")
            #  Destination path
            new_path = self.get_rename_path(
                path=target_dir,
                template_string=rename_format,
                rename_dict=self.__get_naming_dict(meta=in_meta,
                                                   mediainfo=mediainfo)
            ).parent
            #  Divert or distract (attention etc)蓝光原盘
            retcode = self.__transfer_dir(file_path=in_path,
                                          new_path=new_path,
                                          transfer_type=transfer_type)
            if retcode != 0:
                logger.error(f" File (paper) {in_path}  Transfer failure， Error code：{retcode}")
                return TransferInfo(success=False,
                                    message=f" Error code：{retcode}",
                                    path=in_path,
                                    target_path=new_path,
                                    is_bluray=bluray_flag)

            logger.info(f" File (paper) {in_path}  The transfer was successful.")
            #  Returns the path after the transfer
            return TransferInfo(success=True,
                                path=in_path,
                                target_path=new_path,
                                total_size=new_path.stat().st_size,
                                is_bluray=bluray_flag)
        else:
            #  Divert or distract (attention etc)单个文件
            if mediainfo.type == MediaType.TV:
                #  Dramas
                if in_meta.begin_episode is None:
                    logger.warn(f" File {in_path}  Transfer failure： Number of unrecognized file sets")
                    return TransferInfo(success=False,
                                        message=f" Number of unrecognized file sets",
                                        path=in_path,
                                        fail_list=[str(in_path)])

                #  End-of-file season is empty
                in_meta.end_season = None
                #  The total number of document seasons is1
                if in_meta.total_season:
                    in_meta.total_season = 1
                #  It is unlikely that the file will exceed2 Classifier for sections of a tv series e.g. episode
                if in_meta.total_episode > 2:
                    in_meta.total_episode = 1
                    in_meta.end_episode = None

            #  Destination file name
            new_file = self.get_rename_path(
                path=target_dir,
                template_string=rename_format,
                rename_dict=self.__get_naming_dict(
                    meta=in_meta,
                    mediainfo=mediainfo,
                    episodes_info=episodes_info,
                    file_ext=in_path.suffix
                )
            )

            #  Determine whether to override
            overflag = False
            if new_file.exists():
                if new_file.stat().st_size < in_path.stat().st_size:
                    logger.info(f" Target file already exists， But the file size is smaller， Will cover：{new_file}")
                    overflag = True

            #  Divert or distract (attention etc)文件
            retcode = self.__transfer_file(file_item=in_path,
                                           new_file=new_file,
                                           transfer_type=transfer_type,
                                           over_flag=overflag)
            if retcode != 0:
                logger.error(f" File {in_path}  Transfer failure， Error code：{retcode}")
                return TransferInfo(success=False,
                                    message=f" Error code：{retcode}",
                                    path=in_path,
                                    target_path=new_file,
                                    fail_list=[str(in_path)])

            logger.info(f" File {in_path}  The transfer was successful.")
            return TransferInfo(success=True,
                                path=in_path,
                                target_path=new_file,
                                file_count=1,
                                total_size=new_file.stat().st_size,
                                is_bluray=False,
                                file_list=[str(in_path)],
                                file_list_new=[str(new_file)])

    @staticmethod
    def __get_naming_dict(meta: MetaBase, mediainfo: MediaInfo, file_ext: str = None,
                          episodes_info: List[TmdbEpisode] = None) -> dict:
        """
        Based on media information， Come (or go) backFormat Dictionaries
        :param meta:  Document metadata
        :param mediainfo:  Identified media messages
        :param file_ext:  File extension
        :param episodes_info:  All episode information for the current season
        """
        #  Get set title
        episode_title = None
        if meta.begin_episode and episodes_info:
            for episode in episodes_info:
                if episode.episode_number == meta.begin_episode:
                    episode_title = episode.name
                    break

        return {
            #  Caption
            "title": mediainfo.title,
            #  Original filename
            "original_name": f"{meta.org_string}{file_ext}",
            #  Title in original language
            "original_title": mediainfo.original_title,
            #  Identifying name
            "name": meta.name,
            #  Particular year
            "year": mediainfo.year or meta.year,
            #  Resource type
            "resourceType": meta.resource_type,
            #  Especially efficacious
            "effect": meta.resource_effect,
            #  Releases
            "edition": meta.edition,
            #  Resolution (of a photo)
            "videoFormat": meta.resource_pix,
            #  Production team/ Subtitling team
            "releaseGroup": meta.resource_team,
            #  Video encoding
            "videoCodec": meta.video_encode,
            #  Audio encoding
            "audioCodec": meta.audio_encode,
            # TMDBID
            "tmdbid": mediainfo.tmdb_id,
            # IMDBID
            "imdbid": mediainfo.imdb_id,
            #  Quarter
            "season": meta.season_seq,
            #  Bugle call
            "episode": meta.episode_seqs,
            #  End of a season SxxExx
            "season_episode": "%s%s" % (meta.season, meta.episodes),
            #  Stage (of a process)/ Classifier for segments, e.g. lessons, train wagons, biblical verses
            "part": meta.part,
            #  Episode title
            "episode_title": episode_title,
            #  File suffix
            "fileExt": file_ext,
            #  Custom placeholders
            "customization": meta.customization
        }

    @staticmethod
    def get_rename_path(template_string: str, rename_dict: dict, path: Path = None) -> Path:
        """
        Generate the full path after renaming
        """
        #  Establishjinja2 Template object
        template = Template(template_string)
        #  Render the generated string
        render_str = template.render(rename_dict)
        #  Destination path
        if path:
            return path / render_str
        else:
            return Path(render_str)

    @staticmethod
    def get_library_path(path: Path):
        """
        Query the media library directory based on the directory it is in， Return to the input directory if you can't find it
        """
        if not path:
            return None
        if not settings.LIBRARY_PATHS:
            return path
        #  Destination path，多路径以,分隔
        dest_paths = settings.LIBRARY_PATHS
        for libpath in dest_paths:
            try:
                if path.is_relative_to(libpath):
                    return libpath
            except Exception as e:
                logger.debug(f" Error calculating media library path：{e}")
                continue
        return path

    @staticmethod
    def get_target_path(in_path: Path = None) -> Optional[Path]:
        """
        Calculate a best destination catalog， There arein_path Look for a match within_path Homologous， Hasn'tin_path Hour， Sequential search1 One size fits all， Hasn'tin_path Cap (a poem)size Hour， Return to section1 Classifier for individual things or people, general, catch-all classifier
        :param in_path:  Source catalog
        """
        if not settings.LIBRARY_PATHS:
            return None
        #  Destination path，多路径以,分隔
        dest_paths = settings.LIBRARY_PATHS
        #  There's only one path.， Direct return
        if len(dest_paths) == 1:
            return dest_paths[0]
        #  Match directories with the longest common parent path
        max_length = 0
        target_path = None
        if in_path:
            for path in dest_paths:
                try:
                    relative = in_path.relative_to(path).as_posix()
                    if len(relative) > max_length:
                        max_length = len(relative)
                        target_path = path
                except Exception as e:
                    logger.debug(f" Error while calculating target path：{e}")
                    continue
            if target_path:
                return target_path
        #  Sequential matching of the first1 Directories that meet space storage requirements
        if in_path.exists():
            file_size = in_path.stat().st_size
            for path in dest_paths:
                if SystemUtils.free_space(path) > file_size:
                    return path
        #  Defaults to the first1 Classifier for individual things or people, general, catch-all classifier
        return dest_paths[0]

    def media_exists(self, mediainfo: MediaInfo, itemid: str = None) -> Optional[ExistMediaInfo]:
        """
        Determine if a media file exists on the local file system
        :param mediainfo:   Identified media messages
        :param itemid:   Media serverItemID
        :return:  Returns if not presentNone， Return information when present， Includes all existing episodes of each season{type: movie/tv, seasons: {season: [episodes]}}
        """
        if not settings.LIBRARY_PATHS:
            return None
        #  Destination path
        dest_paths = settings.LIBRARY_PATHS
        #  Check every media library directory
        for dest_path in dest_paths:
            #  Media library path
            target_dir = self.get_target_path(dest_path)
            if not target_dir:
                continue
            #  Media classification path
            target_dir = self.__get_dest_dir(mediainfo=mediainfo, target_dir=target_dir)
            #  Rename format
            rename_format = settings.TV_RENAME_FORMAT \
                if mediainfo.type == MediaType.TV else settings.MOVIE_RENAME_FORMAT
            #  Relative path
            meta = MetaInfo(mediainfo.title)
            rel_path = self.get_rename_path(
                template_string=rename_format,
                rename_dict=self.__get_naming_dict(meta=meta,
                                                   mediainfo=mediainfo)
            )
            #  Take the relative path of the first1 Top-level catalog
            if rel_path.parts:
                media_path = target_dir / rel_path.parts[0]
            else:
                continue

            #  Check if the media folder exists
            if not media_path.exists():
                continue

            #  Retrieve media files
            media_files = SystemUtils.list_files(directory=media_path, extensions=settings.RMT_MEDIAEXT)
            if not media_files:
                continue

            if mediainfo.type == MediaType.MOVIE:
                #  Cinematic存在任何文件为存在
                logger.info(f" The file system already exists：{mediainfo.title_year}")
                return ExistMediaInfo(type=MediaType.MOVIE)
            else:
                #  Dramas检索集数
                seasons: Dict[int, list] = {}
                for media_file in media_files:
                    file_meta = MetaInfo(media_file.stem)
                    season_index = file_meta.begin_season or 1
                    episode_index = file_meta.begin_episode
                    if not episode_index:
                        continue
                    if season_index not in seasons:
                        seasons[season_index] = []
                    seasons[season_index].append(episode_index)
                #  Back to episode status
                logger.info(f"{mediainfo.title_year}  The file system already exists：{seasons}")
                return ExistMediaInfo(type=MediaType.TV, seasons=seasons)
        #  Non-existent
        return None
