import re
from typing import List, Tuple, Union, Dict, Optional

from app.core.context import TorrentInfo, MediaInfo
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.filter.RuleParser import RuleParser


class FilterModule(_ModuleBase):
    #  Rules parser
    parser: RuleParser = None
    #  Media information
    media: MediaInfo = None

    #  Built-in rule set
    rule_set: Dict[str, dict] = {
        #  Blu-ray disk
        "BLU": {
            "include": [r'Blu-?Ray.+VC-?1|Blu-?Ray.+AVC|UHD.+blu-?ray.+HEVC|MiniBD'],
            "exclude": [r'[Hx].?264|[Hx].?265|WEB-?DL|WEB-?RIP|REMUX']
        },
        # 4K
        "4K": {
            "include": [r'4k|2160p|x2160'],
            "exclude": []
        },
        # 1080P
        "1080P": {
            "include": [r'1080[pi]|x1080'],
            "exclude": []
        },
        # 720P
        "720P": {
            "include": [r'720[pi]|x720'],
            "exclude": []
        },
        #  Chinese character
        "CNSUB": {
            "include": [
                r'[ Chinese traditional and simplified chinese](/|\s|\\|\|)?[ Traditional, simplified, english and cantonese]|[ English simplified chinese traditional (stg)](/|\s|\\|\|)?[ Chinese traditional and simplified form of chinese characters]| Traditional| Simplified chinese|[ China][ Word matching]| Guoyu, book of historical narrative c. 10th-5th century bc| Chinese (mandarin)| Chinese writing| Chinese character'],
            "exclude": [],
            "tmdb": {
                "original_language": "zh,cn"
            }
        },
        #  Special effects montage
        "SPECSUB": {
            "include": [r' Especially efficacious'],
            "exclude": []
        },
        # BluRay
        "BLURAY": {
            "include": [r'Blu-?Ray'],
            "exclude": []
        },
        # UHD
        "UHD": {
            "include": [r'UHD|UltraHD'],
            "exclude": []
        },
        # H265
        "H265": {
            "include": [r'[Hx].?265|HEVC'],
            "exclude": []
        },
        # H264
        "H264": {
            "include": [r'[Hx].?264|AVC'],
            "exclude": []
        },
        #  Dolby
        "DOLBY": {
            "include": [r"Dolby[\s.]+Vision|DOVI|[\s.]+DV[\s.]+| Dolby vision"],
            "exclude": []
        },
        # HDR
        "HDR": {
            "include": [r"[\s.]+HDR[\s.]+|HDR10|HDR10\+"],
            "exclude": []
        },
        #  Re-encoding
        "REMUX": {
            "include": [r'REMUX'],
            "exclude": []
        },
        # WEB-DL
        "WEBDL": {
            "include": [r'WEB-?DL|WEB-?RIP'],
            "exclude": []
        },
        #  Free (of charge)
        "FREE": {
            "downloadvolumefactor": 0
        },
        #  Mandarin dub
        "CNVOI": {
            "include": [r'[ Country][ Language] Dubbing (filmmaking)|[ Country] Make up (a prescription)|[ Country][ Language]'],
            "exclude": []
        }
    }

    def init_module(self) -> None:
        self.parser = RuleParser()

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        pass

    def filter_torrents(self, rule_string: str,
                        torrent_list: List[TorrentInfo],
                        season_episodes: Dict[int, list] = None,
                        mediainfo: MediaInfo = None) -> List[TorrentInfo]:
        """
        Filtering seed resources
        :param rule_string:   Filter rules
        :param torrent_list:   Resource list
        :param season_episodes:   Season episode filter {season:[episodes]}
        :param mediainfo:   Media information
        :return:  Filtered resource list， Add resource prioritization
        """
        if not rule_string:
            return torrent_list
        self.media = mediainfo
        #  Back to seed list
        ret_torrents = []
        for torrent in torrent_list:
            #  Return only if you can hit the priority
            if not self.__get_order(torrent, rule_string):
                continue
            #  Season episode filter
            if season_episodes \
                    and not self.__match_season_episodes(torrent, season_episodes):
                continue
            ret_torrents.append(torrent)

        return ret_torrents

    @staticmethod
    def __match_season_episodes(torrent: TorrentInfo, season_episodes: Dict[int, list]):
        """
        Determine if the seed matches the number of season episodes
        """
        #  Season of matchmaking
        seasons = season_episodes.keys()
        meta = MetaInfo(title=torrent.title, subtitle=torrent.description)
        #  Seed season
        torrent_seasons = meta.season_list
        if not torrent_seasons:
            #  Processed on a first quarter basis
            torrent_seasons = [1]
        #  Seed collection
        torrent_episodes = meta.episode_list
        if not set(torrent_seasons).issubset(set(seasons)):
            #  Seed season不在过滤季中
            logger.info(f" Torrent {torrent.site_name} - {torrent.title}  It's not the season of need.")
            return False
        if not torrent_episodes:
            #  Processed as a match for the entire season
            return True
        if len(torrent_seasons) == 1:
            need_episodes = season_episodes.get(torrent_seasons[0])
            if need_episodes \
                    and not set(torrent_episodes).intersection(set(need_episodes)):
                #  No single-season episodes with no crossover
                logger.info(f" Torrent {torrent.site_name} - {torrent.title} "
                            f" Classifier for sections of a tv series e.g. episode {torrent_episodes}  There are no required sets：{need_episodes}")
                return False
        return True

    def __get_order(self, torrent: TorrentInfo, rule_str: str) -> Optional[TorrentInfo]:
        """
        Get rule priority for seed matches， The larger the value, the higher the priority， Returns if not matchedNone
        """
        #  Multilevel rule
        rule_groups = rule_str.split('>')
        #  Prioritization
        res_order = 100
        #  Whether or not it matches
        matched = False

        for rule_group in rule_groups:
            #  Parse rule set
            parsed_group = self.parser.parse(rule_group.strip())
            if self.__match_group(torrent, parsed_group.as_list()[0]):
                #  Interrupt when a match occurs
                matched = True
                logger.info(f" Torrent {torrent.site_name} - {torrent.title}  Priority is {100 - res_order + 1}")
                torrent.pri_order = res_order
                break
            #  Prioritization降低，继续匹配
            res_order -= 1

        return None if not matched else torrent

    def __match_group(self, torrent: TorrentInfo, rule_group: Union[list, str]) -> bool:
        """
        Determine if a seed matches a rule set
        """
        if not isinstance(rule_group, list):
            #  Not a list， Description is the name of the rule
            return self.__match_rule(torrent, rule_group)
        elif isinstance(rule_group, list) and len(rule_group) == 1:
            #  There is only one rule item
            return self.__match_group(torrent, rule_group[0])
        elif rule_group[0] == "not":
            #  Non-operational
            return not self.__match_group(torrent, rule_group[1:])
        elif rule_group[1] == "and":
            #  Interoperability
            return self.__match_group(torrent, rule_group[0]) and self.__match_group(torrent, rule_group[2:])
        elif rule_group[1] == "or":
            #  Or operation
            return self.__match_group(torrent, rule_group[0]) or self.__match_group(torrent, rule_group[2:])

    def __match_rule(self, torrent: TorrentInfo, rule_name: str) -> bool:
        """
        Determine if a seed matches a rule entry
        """
        if not self.rule_set.get(rule_name):
            #  The rules don't exist.
            return False
        # TMDB Rules and regulations
        tmdb = self.rule_set[rule_name].get("tmdb")
        #  In line withTMDB The direct return of the ruleTrue， I.e. not filtered
        if tmdb and self.__match_tmdb(tmdb):
            return True
        #  Includes rule entries
        includes = self.rule_set[rule_name].get("include") or []
        #  Exclusionary rule term
        excludes = self.rule_set[rule_name].get("exclude") or []
        # FREE Rules and regulations
        downloadvolumefactor = self.rule_set[rule_name].get("downloadvolumefactor")
        #  Match
        content = f"{torrent.title} {torrent.description} {' '.join(torrent.labels or [])}"
        for include in includes:
            if not re.search(r"%s" % include, content, re.IGNORECASE):
                #  No inclusions found
                return False
        for exclude in excludes:
            if re.search(r"%s" % exclude, content, re.IGNORECASE):
                #  Discovering exclusions
                return False
        if downloadvolumefactor is not None:
            if torrent.downloadvolumefactor != downloadvolumefactor:
                # FREE Rules and regulations不匹配
                return False
        return True

    def __match_tmdb(self, tmdb: dict) -> bool:
        """
        Determine if the seeds matchTMDB Rules and regulations
        """
        def __get_media_value(key: str):
            try:
                return getattr(self.media, key)
            except ValueError:
                return ""

        if not self.media:
            return False

        for attr, value in tmdb.items():
            if not value:
                continue
            #  Gainmedia Value of the message
            info_value = __get_media_value(attr)
            if not info_value:
                #  No such value， Mismatch
                return False
            elif attr == "production_countries":
                #  State information
                info_values = [str(val.get("iso_3166_1")).upper() for val in info_value]
            else:
                # media Conversion of information into arrays
                if isinstance(info_value, list):
                    info_values = [str(val).upper() for val in info_value]
                else:
                    info_values = [str(info_value).upper()]
            #  Filtering values into arrays
            if value.find(",") != -1:
                values = [str(val).upper() for val in value.split(",")]
            else:
                values = [str(value).upper()]
            #  No intersection is a mismatch
            if not set(values).intersection(set(info_values)):
                return False

        return True
