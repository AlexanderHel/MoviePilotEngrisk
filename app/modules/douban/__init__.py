from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union

from app.core.config import settings
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.douban.apiv2 import DoubanApi
from app.modules.douban.scraper import DoubanScraper
from app.schemas.types import MediaType
from app.utils.common import retry
from app.utils.system import SystemUtils


class DoubanModule(_ModuleBase):
    doubanapi: DoubanApi = None
    scraper: DoubanScraper = None

    def init_module(self) -> None:
        self.doubanapi = DoubanApi()
        self.scraper = DoubanScraper()

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

    def douban_info(self, doubanid: str) -> Optional[dict]:
        """
        Get douban information
        :param doubanid:  Douban, prc social networking websiteID
        :return:  Douban information
        """
        """
        {
          "rating": {
            "count": 287365,
            "max": 10,
            "star_count": 3.5,
            "value": 6.6
          },
          "lineticket_url": "",
          "controversy_reason": "",
          "pubdate": [
            "2021-10-29( Mainland china)"
          ],
          "last_episode_number": null,
          "interest_control_info": null,
          "pic": {
            "large": "https://img9.doubanio.com/view/photo/m_ratio_poster/public/p2707553644.webp",
            "normal": "https://img9.doubanio.com/view/photo/s_ratio_poster/public/p2707553644.webp"
          },
          "vendor_count": 6,
          "body_bg_color": "f4f5f9",
          "is_tv": false,
          "head_info": null,
          "album_no_interact": false,
          "ticket_price_info": "",
          "webisode_count": 0,
          "year": "2021",
          "card_subtitle": "2021 /  United kingdom of great britain and northern ireland  United states of america /  Movements  Horror (movie)  Take chances /  Kerry (name)· Fukunaga city in north korea /  Daniel (name)· Craig (name)  Rhea, wife of chronos and mother of zeus in greek mythology· Saidu",
          "forum_info": null,
          "webisode": null,
          "id": "20276229",
          "gallery_topic_count": 0,
          "languages": [
            " English (language)",
            " French (language)",
            " Italian (language)",
            " Russian (language)",
            " Spanish language"
          ],
          "genres": [
            " Movements",
            " Horror (movie)",
            " Take chances"
          ],
          "review_count": 926,
          "title": "007： Have no time to die",
          "intro": " The world situation is treacherous， Bond in action again.（ Daniel (name)· Craig (name)  Impersonate） Faced with a crisis unparalleled in history， Legendary agent007 The story culminates in this movie。 New and old characters gathered for appearance， Rhea, wife of chronos and mother of zeus in greek mythology· Seydoux returns， Second time as bond girl madeleine.。 The most terrifying villain of the series, saffron.（ Rami· Marek (name)  Impersonate） Return to the stage with a vengeance， Showing his ruthless side without mercy， Not only does it reveal the secrets hidden in madeleine's body.， There's a conspiracy brewing that threatens millions of lives.， The ghostbusters also seem to have resurfaced.。 Halfway to a new00 Special agent number one（ Lashner (name)· Lynch  Impersonate） With a mysterious woman（ Anna (person's name)· Favor· Amazons  Impersonate） Looks like he's fighting on the same side as bond.， But its true purpose remains a mystery.。 New feuds and old feuds over bond's life and death.， Will he be able to save the world under a dark tide?？",
          "interest_cmt_earlier_tip_title": " Posted in pre-release",
          "has_linewatch": true,
          "ugc_tabs": [
            {
              "source": "reviews",
              "type": "review",
              "title": " Movie review"
            },
            {
              "source": "forum_topics",
              "type": "forum",
              "title": " Talk over"
            }
          ],
          "forum_topic_count": 857,
          "ticket_promo_text": "",
          "webview_info": {},
          "is_released": true,
          "actors": [
            {
              "name": " Daniel (name)· Craig (name)",
              "roles": [
                " Actor or actress",
                " Moviemaker",
                " Dubbing (filmmaking)"
              ],
              "title": " Daniel (name)· Craig (name)（ Self-titled (album)） United kingdom of great britain and northern ireland, England, Cheshire (english county), Chester's movie and tv actors",
              "url": "https://movie.douban.com/celebrity/1025175/",
              "user": null,
              "character": " Impersonate  James (name)· Bond (name) James Bond 007",
              "uri": "douban://douban.com/celebrity/1025175?subject_id=27230907",
              "avatar": {
                "large": "https://qnmob3.doubanio.com/view/celebrity/raw/public/p42588.jpg?imageView2/2/q/80/w/600/h/3000/format/webp",
                "normal": "https://qnmob3.doubanio.com/view/celebrity/raw/public/p42588.jpg?imageView2/2/q/80/w/200/h/300/format/webp"
              },
              "sharing_url": "https://www.douban.com/doubanapp/dispatch?uri=/celebrity/1025175/",
              "type": "celebrity",
              "id": "1025175",
              "latin_name": "Daniel Craig"
            }
          ],
          "interest": null,
          "vendor_icons": [
            "https://img9.doubanio.com/f/frodo/fbc90f355fc45d5d2056e0d88c697f9414b56b44/pics/vendors/tencent.png",
            "https://img2.doubanio.com/f/frodo/8286b9b5240f35c7e59e1b1768cd2ccf0467cde5/pics/vendors/migu_video.png",
            "https://img9.doubanio.com/f/frodo/88a62f5e0cf9981c910e60f4421c3e66aac2c9bc/pics/vendors/bilibili.png"
          ],
          "episodes_count": 0,
          "color_scheme": {
            "is_dark": true,
            "primary_color_light": "868ca5",
            "_base_color": [
              0.6333333333333333,
              0.18867924528301885,
              0.20784313725490197
            ],
            "secondary_color": "f4f5f9",
            "_avg_color": [
              0.059523809523809625,
              0.09790209790209795,
              0.5607843137254902
            ],
            "primary_color_dark": "676c7f"
          },
          "type": "movie",
          "null_rating_reason": "",
          "linewatches": [
            {
              "url": "http://v.youku.com/v_show/id_XNTIwMzM2NDg5Mg==.html?tpa=dW5pb25faWQ9MzAwMDA4XzEwMDAwMl8wMl8wMQ&refer=esfhz_operation.xuka.xj_00003036_000000_FNZfau_19010900",
              "source": {
                "literal": "youku",
                "pic": "https://img1.doubanio.com/img/files/file-1432869267.png",
                "name": " Youku video"
              },
              "source_uri": "youku://play?vid=XNTIwMzM2NDg5Mg==&source=douban&refer=esfhz_operation.xuka.xj_00003036_000000_FNZfau_19010900",
              "free": false
            },
          ],
          "info_url": "https://www.douban.com/doubanapp//h5/movie/20276229/desc",
          "tags": [],
          "durations": [
            "163 Minutes"
          ],
          "comment_count": 97204,
          "cover": {
            "description": "",
            "author": {
              "loc": {
                "id": "108288",
                "name": " Beijing, capital of people's republic of china",
                "uid": "beijing"
              },
              "kind": "user",
              "name": " Rainfall",
              "reg_time": "2020-08-11 16:22:48",
              "url": "https://www.douban.com/people/221011676/",
              "uri": "douban://douban.com/user/221011676",
              "id": "221011676",
              "avatar_side_icon_type": 3,
              "avatar_side_icon_id": "234",
              "avatar": "https://img2.doubanio.com/icon/up221011676-2.jpg",
              "is_club": false,
              "type": "user",
              "avatar_side_icon": "https://img2.doubanio.com/view/files/raw/file-1683625971.png",
              "uid": "221011676"
            },
            "url": "https://movie.douban.com/photos/photo/2707553644/",
            "image": {
              "large": {
                "url": "https://img9.doubanio.com/view/photo/l/public/p2707553644.webp",
                "width": 1082,
                "height": 1600,
                "size": 0
              },
              "raw": null,
              "small": {
                "url": "https://img9.doubanio.com/view/photo/s/public/p2707553644.webp",
                "width": 405,
                "height": 600,
                "size": 0
              },
              "normal": {
                "url": "https://img9.doubanio.com/view/photo/m/public/p2707553644.webp",
                "width": 405,
                "height": 600,
                "size": 0
              },
              "is_animated": false
            },
            "uri": "douban://douban.com/photo/2707553644",
            "create_time": "2021-10-26 15:05:01",
            "position": 0,
            "owner_uri": "douban://douban.com/movie/20276229",
            "type": "photo",
            "id": "2707553644",
            "sharing_url": "https://www.douban.com/doubanapp/dispatch?uri=/photo/2707553644/"
          },
          "cover_url": "https://img9.doubanio.com/view/photo/m_ratio_poster/public/p2707553644.webp",
          "restrictive_icon_url": "",
          "header_bg_color": "676c7f",
          "is_douban_intro": false,
          "ticket_vendor_icons": [
            "https://img9.doubanio.com/view/dale-online/dale_ad/public/0589a62f2f2d7c2.jpg"
          ],
          "honor_infos": [],
          "sharing_url": "https://movie.douban.com/subject/20276229/",
          "subject_collections": [],
          "wechat_timeline_share": "screenshot",
          "countries": [
            " United kingdom of great britain and northern ireland",
            " United states of america"
          ],
          "url": "https://movie.douban.com/subject/20276229/",
          "release_date": null,
          "original_title": "No Time to Die",
          "uri": "douban://douban.com/movie/20276229",
          "pre_playable_date": null,
          "episodes_info": "",
          "subtype": "movie",
          "directors": [
            {
              "name": " Kerry (name)· Fukunaga city in north korea",
              "roles": [
                " Director (film etc)",
                " Moviemaker",
                " Cinematographer",
                " Shoot (a movie)",
                " Actor or actress"
              ],
              "title": " Kerry (name)· Fukunaga city in north korea（ Self-titled (album)） United states of america, California, Auckland film and television actors",
              "url": "https://movie.douban.com/celebrity/1009531/",
              "user": null,
              "character": " Director (film etc)",
              "uri": "douban://douban.com/celebrity/1009531?subject_id=27215222",
              "avatar": {
                "large": "https://qnmob3.doubanio.com/view/celebrity/raw/public/p1392285899.57.jpg?imageView2/2/q/80/w/600/h/3000/format/webp",
                "normal": "https://qnmob3.doubanio.com/view/celebrity/raw/public/p1392285899.57.jpg?imageView2/2/q/80/w/200/h/300/format/webp"
              },
              "sharing_url": "https://www.douban.com/doubanapp/dispatch?uri=/celebrity/1009531/",
              "type": "celebrity",
              "id": "1009531",
              "latin_name": "Cary Fukunaga"
            }
          ],
          "is_show": false,
          "in_blacklist": false,
          "pre_release_desc": "",
          "video": null,
          "aka": [
            "007： There are times when life and death coincide (idiom); don't know if you'll live or die( Harbor)",
            "007： Fight between life and death( Classifier for heavy objects, such as machines, tvs, computers; theater performances)",
            "007： Lit. not allowing room for one's death (idiom); fig. not allowing anyone to pass away",
            " Bond (name)25",
            "007： No time to die.( Translation for bean users)",
            "James Bond 25",
            "Never Dream of Dying",
            "Shatterhand"
          ],
          "is_restrictive": false,
          "trailer": {
            "sharing_url": "https://www.douban.com/doubanapp/dispatch?uri=/movie/20276229/trailer%3Ftrailer_id%3D282585%26trailer_type%3DA",
            "video_url": "https://vt1.doubanio.com/202310011325/3b1f5827e91dde7826dc20930380dfc2/view/movie/M/402820585.mp4",
            "title": " China trailer： Ultimate battle edition ( Chinese subtitles)",
            "uri": "douban://douban.com/movie/20276229/trailer?trailer_id=282585&trailer_type=A",
            "cover_url": "https://img1.doubanio.com/img/trailer/medium/2712944408.jpg",
            "term_num": 0,
            "n_comments": 21,
            "create_time": "2021-11-01",
            "subject_title": "007： Have no time to die",
            "file_size": 10520074,
            "runtime": "00:42",
            "type": "A",
            "id": "282585",
            "desc": ""
          },
          "interest_cmt_earlier_tip_desc": " This short review was posted before the public release date， Authors may watch in advance through other channels， Please refer with caution.。 Their scores will not count towards the overall score。"
        }
        """
        if not doubanid:
            return None
        logger.info(f"开始Get douban information：{doubanid} ...")
        douban_info = self.doubanapi.movie_detail(doubanid)
        if douban_info:
            celebrities = self.doubanapi.movie_celebrities(doubanid)
            if celebrities:
                douban_info["directors"] = celebrities.get("directors")
                douban_info["actors"] = celebrities.get("actors")
        else:
            douban_info = self.doubanapi.tv_detail(doubanid)
            celebrities = self.doubanapi.tv_celebrities(doubanid)
            if douban_info and celebrities:
                douban_info["directors"] = celebrities.get("directors")
                douban_info["actors"] = celebrities.get("actors")
        return douban_info

    def douban_discover(self, mtype: MediaType, sort: str, tags: str,
                        page: int = 1, count: int = 30) -> Optional[List[dict]]:
        """
        Discover douban movies、 Episode
        :param mtype:   Media type
        :param sort:   Sort by
        :param tags:   Tab (of a window) (computing)
        :param page:   Pagination
        :param count:   Quantities
        :return:  Media information list
        """
        logger.info(f" Beginning to discover doujinshi {mtype.value} ...")
        if mtype == MediaType.MOVIE:
            infos = self.doubanapi.movie_recommend(start=(page - 1) * count, count=count,
                                                   sort=sort, tags=tags)
        else:
            infos = self.doubanapi.tv_recommend(start=(page - 1) * count, count=count,
                                                sort=sort, tags=tags)
        if not infos:
            return []
        return infos.get("items") or []

    def movie_showing(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get movies in theaters
        """
        infos = self.doubanapi.movie_showing(start=(page - 1) * count,
                                             count=count)
        if not infos:
            return []
        return infos.get("subject_collection_items")

    def tv_weekly_chinese(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get douban's word-of-mouth chinese drama of the week
        """
        infos = self.doubanapi.tv_chinese_best_weekly(start=(page - 1) * count,
                                                      count=count)
        if not infos:
            return []
        return infos.get("subject_collection_items")

    def tv_weekly_global(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get douban's word-of-mouth foreign drama of the week
        """
        infos = self.doubanapi.tv_global_best_weekly(start=(page - 1) * count,
                                                     count=count)
        if not infos:
            return []
        return infos.get("subject_collection_items")

    def search_medias(self, meta: MetaBase) -> Optional[List[MediaInfo]]:
        """
        Search for media information
        :param meta:   Identified metadata
        :reutrn:  Media information
        """
        #  Returns when douban search is not enabledNone
        if settings.SEARCH_SOURCE != "douban":
            return None

        if not meta.name:
            return []
        result = self.doubanapi.search(meta.name)
        if not result:
            return []
        #  Return data
        ret_medias = []
        for item_obj in result.get("items"):
            if meta.type and meta.type.value != item_obj.get("type_name"):
                continue
            if item_obj.get("type_name") not in (MediaType.TV.value, MediaType.MOVIE.value):
                continue
            ret_medias.append(MediaInfo(douban_info=item_obj.get("target")))

        return ret_medias

    @retry(Exception, 5, 3, 3, logger=logger)
    def match_doubaninfo(self, name: str, mtype: str = None,
                         year: str = None, season: int = None) -> dict:
        """
        Search and match douban information
        :param name:   Name (of a thing)
        :param mtype:   Typology  Cinematic/ Dramas
        :param year:   Particular year
        :param season:   Quarter
        """
        result = self.doubanapi.search(f"{name} {year or ''}".strip(),
                                       ts=datetime.strftime(datetime.now(), '%Y%m%d%H%M%S'))
        if not result:
            logger.warn(f" Not found {name}  The doujinshi information")
            return {}
        #  Trigrate limit
        if "search_access_rate_limit" in result.values():
            logger.warn(f" Trigger beanAPI Speed limit  Error message {result} ...")
            raise Exception(" Trigger beanAPI Speed limit")
        for item_obj in result.get("items"):
            type_name = item_obj.get("type_name")
            if type_name not in [MediaType.TV.value, MediaType.MOVIE.value]:
                continue
            if mtype and mtype != type_name:
                continue
            if mtype == MediaType.TV and not season:
                season = 1
            item = item_obj.get("target")
            title = item.get("title")
            if not title:
                continue
            meta = MetaInfo(title)
            if type_name == MediaType.TV.value:
                meta.type = MediaType.TV
                meta.begin_season = meta.begin_season or 1
            if meta.name == name \
                    and ((not season and not meta.begin_season) or meta.begin_season == season) \
                    and (not year or item.get('year') == year):
                return item
        return {}

    def movie_top250(self, page: int = 1, count: int = 30) -> List[dict]:
        """
        Get douban moviesTOP250
        """
        infos = self.doubanapi.movie_top250(start=(page - 1) * count,
                                            count=count)
        if not infos:
            return []
        return infos.get("subject_collection_items")

    def scrape_metadata(self, path: Path, mediainfo: MediaInfo) -> None:
        """
        Scraping metadata
        :param path:  Media file path
        :param mediainfo:   Identified media messages
        :return:  Success or failure
        """
        if settings.SCRAP_SOURCE != "douban":
            return None
        if SystemUtils.is_bluray_dir(path):
            #  Blu-ray disk
            logger.info(f" Start scraping the original blu-ray discs：{path} ...")
            meta = MetaInfo(path.stem)
            if not meta.name:
                return
            #  Query douban data by name
            doubaninfo = self.match_doubaninfo(name=mediainfo.title,
                                               mtype=mediainfo.type.value,
                                               year=mediainfo.year,
                                               season=meta.begin_season)
            if not doubaninfo:
                logger.warn(f" Not found {mediainfo.title}  The doujinshi information")
                return
            scrape_path = path / path.name
            self.scraper.gen_scraper_files(meta=meta,
                                           mediainfo=MediaInfo(douban_info=doubaninfo),
                                           file_path=scrape_path)
        else:
            #  All files in the directory
            for file in SystemUtils.list_files(path, settings.RMT_MEDIAEXT):
                if not file:
                    continue
                logger.info(f" Start scraping media library files：{file} ...")
                try:
                    meta = MetaInfo(file.stem)
                    if not meta.name:
                        continue
                    #  Query douban data by name
                    doubaninfo = self.match_doubaninfo(name=mediainfo.title,
                                                       mtype=mediainfo.type.value,
                                                       year=mediainfo.year,
                                                       season=meta.begin_season)
                    if not doubaninfo:
                        logger.warn(f" Not found {mediainfo.title}  The doujinshi information")
                        break
                    #  Scrape
                    self.scraper.gen_scraper_files(meta=meta,
                                                   mediainfo=MediaInfo(douban_info=doubaninfo),
                                                   file_path=file)
                except Exception as e:
                    logger.error(f" Scraping files {file}  Fail (e.g. experiments)， Rationale：{e}")
        logger.info(f"{path}  Scraping finish")
