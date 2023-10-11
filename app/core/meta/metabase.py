from dataclasses import dataclass, asdict
from typing import Union, Optional, List, Self

import cn2an
import regex as re


from app.utils.string import StringUtils
from app.schemas.types import MediaType

import sys
sys.stdout.reconfigure(encoding='utf-8')

@dataclass
class MetaBase(object):
    """
    Media information base class
    """
    #  Documents processed or not
    isfile: bool = False
    #  Original title string（ Not processed for identifiers）
    title: str = ""
    #  String for identification（ After identifier processing）
    org_string: Optional[str] = None
    #  Subheading
    subtitle: Optional[str] = None
    #  Typology  Cinematic、 Dramas
    type: MediaType = MediaType.UNKNOWN
    #  Recognized chinese names
    cn_name: Optional[str] = None
    #  Recognizable english names
    en_name: Optional[str] = None
    #  Particular year
    year: Optional[str] = None
    #  Total number of quarters
    total_season: int = 0
    #  The beginning of the identification season  Digital (electronics etc)
    begin_season: Optional[int] = None
    #  End of season for identification  Digital (electronics etc)
    end_season: Optional[int] = None
    #  Total episodes
    total_episode: int = 0
    #  Identified starting set
    begin_episode: Optional[int] = None
    #  Identified end sets
    end_episode: Optional[int] = None
    # Partx Cd Dvd Disk Disc
    part: Optional[str] = None
    #  Types of resources identified
    resource_type: Optional[str] = None
    #  Effectiveness of identification
    resource_effect: Optional[str] = None
    #  Recognized resolution
    resource_pix: Optional[str] = None
    #  Identified production team/ Subtitling team
    resource_team: Optional[str] = None
    #  Recognized custom placeholders
    customization: Optional[str] = None
    #  Video encoding
    video_encode: Optional[str] = None
    #  Audio encoding
    audio_encode: Optional[str] = None
    #  Identifier information for the application
    apply_words: Optional[List[str]] = None

    #  Subheading解析
    _subtitle_flag = False
    _subtitle_season_re = r"(?<![ Altogether]\s*)[ (prefix indicating ordinal number, e.g. first, number two etc)\s]+([0-9 One, two, three, four, five, six, seven, eight, nine, ten.S\-]+)\s* Classifier for seasonal crop yield or seasons of a tv series(?!\s*[ Altogether])"
    _subtitle_season_all_re = r"[ Altogether]\s*([0-9 One, two, three, four, five, six, seven, eight, nine, ten.]+)\s* Classifier for seasonal crop yield or seasons of a tv series|([0-9 One, two, three, four, five, six, seven, eight, nine, ten.]+)\s* Classifier for seasonal crop yield or seasons of a tv series\s* Surname quan"
    _subtitle_episode_re = r"(?<![ Altogether]\s*)[ (prefix indicating ordinal number, e.g. first, number two etc)\s]+([0-9 One, two, three, four, five, six, seven, eight, nine, ten, zero.EP\-]+)\s*[ Talking period](?!\s*[ Altogether])"
    _subtitle_episode_all_re = r"([0-9 One, two, three, four, five, six, seven, eight, nine, ten, zero.]+)\s* Classifier for sections of a tv series e.g. episode\s* Surname quan|[ Altogether]\s*([0-9 One, two, three, four, five, six, seven, eight, nine, ten, zero.]+)\s*[ Talking period]"

    def __init__(self, title: str, subtitle: str = None, isfile: bool = False):
        if not title:
            return
        self.org_string = title
        self.subtitle = subtitle
        self.isfile = isfile

    @property
    def name(self) -> str:
        """
        Return name
        """
        if self.cn_name and StringUtils.is_all_chinese(self.cn_name):
            return self.cn_name
        elif self.en_name:
            return self.en_name
        elif self.cn_name:
            return self.cn_name
        return ""

    def init_subtitle(self, title_text: str):
        """
        Subtitle recognition
        """
        if not title_text:
            return
        title_text = f" {title_text} "
        if re.search(r'[ All season episodes]', title_text, re.IGNORECASE):
            #  (prefix indicating ordinal number, e.g. first, number two etc)x Classifier for seasonal crop yield or seasons of a tv series
            season_str = re.search(r'%s' % self._subtitle_season_re, title_text, re.IGNORECASE)
            if season_str:
                seasons = season_str.group(1)
                if seasons:
                    seasons = seasons.upper().replace("S", "").strip()
                else:
                    return
                try:
                    end_season = None
                    if seasons.find('-') != -1:
                        seasons = seasons.split('-')
                        begin_season = int(cn2an.cn2an(seasons[0].strip(), mode='smart'))
                        if len(seasons) > 1:
                            end_season = int(cn2an.cn2an(seasons[1].strip(), mode='smart'))
                    else:
                        begin_season = int(cn2an.cn2an(seasons, mode='smart'))
                except Exception as err:
                    print(str(err))
                    return
                if self.begin_season is None and isinstance(begin_season, int):
                    self.begin_season = begin_season
                    self.total_season = 1
                if self.begin_season is not None \
                        and self.end_season is None \
                        and isinstance(end_season, int) \
                        and end_season != self.begin_season:
                    self.end_season = end_season
                    self.total_season = (self.end_season - self.begin_season) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
            #  (prefix indicating ordinal number, e.g. first, number two etc)x Classifier for sections of a tv series e.g. episode
            episode_str = re.search(r'%s' % self._subtitle_episode_re, title_text, re.IGNORECASE)
            if episode_str:
                episodes = episode_str.group(1)
                if episodes:
                    episodes = episodes.upper().replace("E", "").replace("P", "").strip()
                else:
                    return
                try:
                    end_episode = None
                    if episodes.find('-') != -1:
                        episodes = episodes.split('-')
                        begin_episode = int(cn2an.cn2an(episodes[0].strip(), mode='smart'))
                        if len(episodes) > 1:
                            end_episode = int(cn2an.cn2an(episodes[1].strip(), mode='smart'))
                    else:
                        begin_episode = int(cn2an.cn2an(episodes, mode='smart'))
                except Exception as err:
                    print(str(err))
                    return
                if self.begin_episode is None and isinstance(begin_episode, int):
                    self.begin_episode = begin_episode
                    self.total_episode = 1
                if self.begin_episode is not None \
                        and self.end_episode is None \
                        and isinstance(end_episode, int) \
                        and end_episode != self.begin_episode:
                    self.end_episode = end_episode
                    self.total_episode = (self.end_episode - self.begin_episode) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
            # x Holistic
            episode_all_str = re.search(r'%s' % self._subtitle_episode_all_re, title_text, re.IGNORECASE)
            if episode_all_str:
                episode_all = episode_all_str.group(1)
                if not episode_all:
                    episode_all = episode_all_str.group(2)
                if episode_all and self.begin_episode is None:
                    try:
                        self.total_episode = int(cn2an.cn2an(episode_all.strip(), mode='smart'))
                    except Exception as err:
                        print(str(err))
                        return
                    self.begin_episode = None
                    self.end_episode = None
                    self.type = MediaType.TV
                    self._subtitle_flag = True
            #  Surname quanx Classifier for seasonal crop yield or seasons of a tv series x Final round number (i.e. third quarter of a year)
            season_all_str = re.search(r"%s" % self._subtitle_season_all_re, title_text, re.IGNORECASE)
            if season_all_str:
                season_all = season_all_str.group(1)
                if not season_all:
                    season_all = season_all_str.group(2)
                if season_all and self.begin_season is None and self.begin_episode is None:
                    try:
                        self.total_season = int(cn2an.cn2an(season_all.strip(), mode='smart'))
                    except Exception as err:
                        print(str(err))
                        return
                    self.begin_season = 1
                    self.end_season = self.total_season
                    self.type = MediaType.TV
                    self._subtitle_flag = True

    @property
    def season(self) -> str:
        """
        Return to the beginning of the season、 End of season string， Sure it's the return of episodes without seasonsS01
        """
        if self.begin_season is not None:
            return "S%s" % str(self.begin_season).rjust(2, "0") \
                if self.end_season is None \
                else "S%s-S%s" % \
                     (str(self.begin_season).rjust(2, "0"),
                      str(self.end_season).rjust(2, "0"))
        else:
            if self.type == MediaType.TV:
                return "S01"
            else:
                return ""

    @property
    def sea(self) -> str:
        """
        Returns the start of the season string， Surely the episodes are returning empty without seasons
        """
        if self.begin_season is not None:
            return self.season
        else:
            return ""
    
    @property
    def season_seq(self) -> str:
        """
        Come (or go) backbegin_season  Figures， Return of the tv series without seasons1
        """
        if self.begin_season is not None:
            return str(self.begin_season)
        else:
            if self.type == MediaType.TV:
                return "1"
            else:
                return ""

    @property
    def season_list(self) -> List[int]:
        """
        Returns an array of seasons
        """
        if self.begin_season is None:
            if self.type == MediaType.TV:
                return [1]
            else:
                return []
        elif self.end_season is not None:
            return [season for season in range(self.begin_season, self.end_season + 1)]
        else:
            return [self.begin_season]

    @property
    def episode(self) -> str:
        """
        Return to start set、 End-set string
        """
        if self.begin_episode is not None:
            return "E%s" % str(self.begin_episode).rjust(2, "0") \
                if self.end_episode is None \
                else "E%s-E%s" % \
                     (
                         str(self.begin_episode).rjust(2, "0"),
                         str(self.end_episode).rjust(2, "0"))
        else:
            return ""
    
    @property
    def episode_list(self) -> List[int]:
        """
        Array of return sets
        """
        if self.begin_episode is None:
            return []
        elif self.end_episode is not None:
            return [episode for episode in range(self.begin_episode, self.end_episode + 1)]
        else:
            return [self.begin_episode]

    @property
    def episodes(self) -> str:
        """
        Juxtaposition expressions for return sets， Used to support single file multisets
        """
        return "E%s" % "E".join(str(episode).rjust(2, '0') for episode in self.episode_list)

    @property
    def episode_seqs(self) -> str:
        """
        Returns an expression for the number of episodes in a single file with multiple episodes， Used to support single file multisets
        """
        episodes = self.episode_list
        if episodes:
            #  Classifier for sections of a tv series e.g. episode xx
            if len(episodes) == 1:
                return str(episodes[0])
            else:
                return "%s-%s" % (episodes[0], episodes[-1])
        else:
            return ""

    @property
    def episode_seq(self) -> str:
        """
        Come (or go) backbegin_episode  Figures
        """
        episodes = self.episode_list
        if episodes:
            return str(episodes[0])
        else:
            return ""

    @property
    def season_episode(self) -> str:
        """
        Returns the seasonal set string
        """
        if self.type == MediaType.TV:
            seaion = self.season
            episode = self.episode
            if seaion and episode:
                return "%s %s" % (seaion, episode)
            elif seaion:
                return "%s" % seaion
            elif episode:
                return "%s" % episode
        else:
            return ""
        return ""

    @property
    def resource_term(self) -> str:
        """
        Returns the resource type string， With resolution
        """
        ret_string = ""
        if self.resource_type:
            ret_string = f"{ret_string} {self.resource_type}"
        if self.resource_effect:
            ret_string = f"{ret_string} {self.resource_effect}"
        if self.resource_pix:
            ret_string = f"{ret_string} {self.resource_pix}"
        return ret_string

    @property
    def edition(self) -> str:
        """
        Returns the resource type string， Without resolution
        """
        ret_string = ""
        if self.resource_type:
            ret_string = f"{ret_string} {self.resource_type}"
        if self.resource_effect:
            ret_string = f"{ret_string} {self.resource_effect}"
        return ret_string.strip()

    @property
    def release_group(self) -> str:
        """
        Return to publishing groups/ Subtitle strings
        """
        if self.resource_team:
            return self.resource_team
        else:
            return ""

    @property
    def video_term(self) -> str:
        """
        Return to video encoding
        """
        return self.video_encode or ""

    @property
    def audio_term(self) -> str:
        """
        Returns the audio encoding
        """
        return self.audio_encode or ""

    def is_in_season(self, season: Union[list, int, str]) -> bool:
        """
        Does it include seasons
        """
        if isinstance(season, list):
            if self.end_season is not None:
                meta_season = list(range(self.begin_season, self.end_season + 1))
            else:
                if self.begin_season is not None:
                    meta_season = [self.begin_season]
                else:
                    meta_season = [1]

            return set(meta_season).issuperset(set(season))
        else:
            if self.end_season is not None:
                return self.begin_season <= int(season) <= self.end_season
            else:
                if self.begin_season is not None:
                    return int(season) == self.begin_season
                else:
                    return int(season) == 1

    def is_in_episode(self, episode: Union[list, int, str]) -> bool:
        """
        Does it contain sets
        """
        if isinstance(episode, list):
            if self.end_episode is not None:
                meta_episode = list(range(self.begin_episode, self.end_episode + 1))
            else:
                meta_episode = [self.begin_episode]
            return set(meta_episode).issuperset(set(episode))
        else:
            if self.end_episode is not None:
                return self.begin_episode <= int(episode) <= self.end_episode
            else:
                return int(episode) == self.begin_episode

    def set_season(self, sea: Union[list, int, str]):
        """
        Renewal season
        """
        if not sea:
            return
        if isinstance(sea, list):
            if len(sea) == 1 and str(sea[0]).isdigit():
                self.begin_season = int(sea[0])
                self.end_season = None
            elif len(sea) > 1 and str(sea[0]).isdigit() and str(sea[-1]).isdigit():
                self.begin_season = int(sea[0])
                self.end_season = int(sea[-1])
        elif str(sea).isdigit():
            self.begin_season = int(sea)
            self.end_season = None

    def set_episode(self, ep: Union[list, int, str]):
        """
        New episode
        """
        if not ep:
            return
        if isinstance(ep, list):
            if len(ep) == 1 and str(ep[0]).isdigit():
                self.begin_episode = int(ep[0])
                self.end_episode = None
            elif len(ep) > 1 and str(ep[0]).isdigit() and str(ep[-1]).isdigit():
                self.begin_episode = int(ep[0])
                self.end_episode = int(ep[-1])
                self.total_episode = (self.end_episode - self.begin_episode) + 1
        elif str(ep).isdigit():
            self.begin_episode = int(ep)
            self.end_episode = None

    def set_episodes(self, begin: int, end: int):
        """
        Setting the start set end set
        """
        if begin:
            self.begin_episode = begin
        if end:
            self.end_episode = end
        if self.begin_episode and self.end_episode:
            self.total_episode = (self.end_episode - self.begin_episode) + 1
            
    def merge(self, meta: Self):
        """
        MergeMeta Text
        """
        #  Typology
        if self.type == MediaType.UNKNOWN \
                and meta.type != MediaType.UNKNOWN:
            self.type = meta.type
        #  Name (of a thing)
        if not self.name:
            self.cn_name = meta.cn_name
            self.en_name = meta.en_name
        #  Particular year
        if not self.year:
            self.year = meta.year
        #  Classifier for seasonal crop yield or seasons of a tv series
        if (self.type == MediaType.TV
                and not self.season):
            self.begin_season = meta.begin_season
            self.end_season = meta.end_season
            self.total_season = meta.total_season
        #  Initial set
        if (self.type == MediaType.TV
                and not self.episode):
            self.begin_episode = meta.begin_episode
            self.end_episode = meta.end_episode
            self.total_episode = meta.total_episode
        #  Releases
        if not self.resource_type:
            self.resource_type = meta.resource_type
        #  Resolution (of a photo)
        if not self.resource_pix:
            self.resource_pix = meta.resource_pix
        #  Production team/ Subtitling team
        if not self.resource_team:
            self.resource_team = meta.resource_team
        #  Custom placeholders
        if not self.customization:
            self.customization = meta.customization
        #  Especially efficacious
        if not self.resource_effect:
            self.resource_effect = meta.resource_effect
        #  Video encoding
        if not self.video_encode:
            self.video_encode = meta.video_encode
        #  Audio encoding
        if not self.audio_encode:
            self.audio_encode = meta.audio_encode
        # Part
        if not self.part:
            self.part = meta.part

    def to_dict(self):
        """
        Convert to dictionary
        """
        dicts = asdict(self)
        dicts["type"] = self.type.value if self.type else None
        dicts["season_episode"] = self.season_episode
        dicts["edition"] = self.edition
        dicts["name"] = self.name
        return dicts
