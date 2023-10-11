import re
from pathlib import Path

from app.core.config import settings
from app.core.meta.customization import CustomizationMatcher
from app.core.meta.metabase import MetaBase
from app.core.meta.releasegroup import ReleaseGroupsMatcher
from app.utils.string import StringUtils
from app.utils.tokens import Tokens
from app.schemas.types import MediaType


class MetaVideo(MetaBase):
    """
    Identify the movie、 Dramas
    """
    #  Control annotation zone
    _stop_name_flag = False
    _stop_cnname_flag = False
    _last_token = ""
    _last_token_type = ""
    _continue_flag = True
    _unknown_name_str = ""
    _source = ""
    _effect = []
    #  Regular district (math.)
    _season_re = r"S(\d{2})|^S(\d{1,2})$|S(\d{1,2})E"
    _episode_re = r"EP?(\d{2,4})$|^EP?(\d{1,4})$|^S\d{1,2}EP?(\d{1,4})$|S\d{2}EP?(\d{2,4})"
    _part_re = r"(^PART[0-9ABI]{0,2}$|^CD[0-9]{0,2}$|^DVD[0-9]{0,2}$|^DISK[0-9]{0,2}$|^DISC[0-9]{0,2}$)"
    _roman_numerals = r"^(?=[MDCLXVI])M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$"
    _source_re = r"^BLURAY$|^HDTV$|^UHDTV$|^HDDVD$|^WEBRIP$|^DVDRIP$|^BDRIP$|^BLU$|^WEB$|^BD$|^HDRip$"
    _effect_re = r"^REMUX$|^UHD$|^SDR$|^HDR\d*$|^DOLBY$|^DOVI$|^DV$|^3D$|^REPACK$"
    _resources_type_re = r"%s|%s" % (_source_re, _effect_re)
    _name_no_begin_re = r"^\[.+?]"
    _name_no_chinese_re = r".* Block of printing|.* Subtitling"
    _name_se_words = [' Common', ' (prefix indicating ordinal number, e.g. first, number two etc)', ' Classifier for seasonal crop yield or seasons of a tv series', ' Classifier for sections of a tv series e.g. episode', ' What sb said', ' Words', ' A period of time']
    _name_nostring_re = r"^PTS|^JADE|^AOD|^CHC|^[A-Z]{1,4}TV[\-0-9UVHDK]*" \
                        r"|HBO$|\s+HBO|\d{1,2}th|\d{1,2}bit|NETFLIX|AMAZON|IMAX|^3D|\s+3D|^BBC\s+|\s+BBC|BBC$|DISNEY\+?|XXX|\s+DC$" \
                        r"|[ (prefix indicating ordinal number, e.g. first, number two etc)\s Common]+[0-9 One, two, three, four, five, six, seven, eight, nine, ten.\-\s]+ Classifier for seasonal crop yield or seasons of a tv series" \
                        r"|[ (prefix indicating ordinal number, e.g. first, number two etc)\s Common]+[0-9 One, two, three, four, five, six, seven, eight, nine, ten, zero.\-\s]+[ Assembled words]" \
                        r"| Published as a serial (in a newspaper)| Japanese drama| American theater| Dramas| Animated film| Cartoons and comics| Europe and america| West germany| Japan and south korea| Ultra-high definition| High definition (photo, audio or television)| Blu-ray (disc format)| Jade channel| Paradise of dreams· Dragon net, a japanese company specializing in online shopping|★?\d* Moon? New trial" \
                        r"| Final season| Collection|[ Multi-chinese, english, portuguese, french, russian, japanese, korean, german, italian, spanish, indian, thai, taiwanese, hong kong, and cantonese bi-lingual simplified chinese and traditional chinese.]+ Subtitling| Releases| Items that are produced| Taiwan edition| Hong kong version|\w+ Subtitling team" \
                        r"| Uncut edition|UNCUT$|UNRATE$|WITH EXTRAS$|RERIP$|SUBBED$|PROPER$|REPACK$|SEASON$|EPISODE$|Complete$|Extended$|Extended Version$" \
                        r"|S\d{2}\s*-\s*S\d{2}|S\d{2}|\s+S\d{1,2}|EP?\d{2,4}\s*-\s*EP?\d{2,4}|EP?\d{2,4}|\s+EP?\d{1,4}" \
                        r"|CD[\s.]*[1-9]|DVD[\s.]*[1-9]|DISK[\s.]*[1-9]|DISC[\s.]*[1-9]" \
                        r"|[248]K|\d{3,4}[PIX]+" \
                        r"|CD[\s.]*[1-9]|DVD[\s.]*[1-9]|DISK[\s.]*[1-9]|DISC[\s.]*[1-9]"
    _resources_pix_re = r"^[SBUHD]*(\d{3,4}[PI]+)|\d{3,4}X(\d{3,4})"
    _resources_pix_re2 = r"(^[248]+K)"
    _video_encode_re = r"^[HX]26[45]$|^AVC$|^HEVC$|^VC\d?$|^MPEG\d?$|^Xvid$|^DivX$|^HDR\d*$"
    _audio_encode_re = r"^DTS\d?$|^DTSHD$|^DTSHDMA$|^Atmos$|^TrueHD\d?$|^AC3$|^\dAudios?$|^DDP\d?$|^DD\d?$|^LPCM\d?$|^AAC\d?$|^FLAC\d?$|^HD\d?$|^MA\d?$"

    def __init__(self, title: str, subtitle: str = None, isfile: bool = False):
        super().__init__(title, subtitle, isfile)
        if not title:
            return
        original_title = title
        self._source = ""
        self._effect = []
        #  Determining whether a number is named purely numerically
        title_path = Path(title)
        if title_path.suffix.lower() in settings.RMT_MEDIAEXT \
                and title_path.stem.isdigit() \
                and len(title_path.stem) < 5:
            self.begin_episode = int(title_path.stem)
            self.type = MediaType.TV
            return
        #  Remove the first line from the name1 Classifier for individual things or people, general, catch-all classifier[] Content
        title = re.sub(r'%s' % self._name_no_begin_re, "", title, count=1)
        #  Particle marking the following noun as a direct objectxxxx-xxxx Year for previous year， Often appearing in seasonal episodes
        title = re.sub(r'([\s.]+)(\d{4})-(\d{4})', r'\1\2', title)
        #  Remove the size.
        title = re.sub(r'[0-9.]+\s*[MGT]i?B(?![A-Z]+)', "", title, flags=re.IGNORECASE)
        #  Take out the year, month and day.
        title = re.sub(r'\d{4}[\s._-]\d{1,2}[\s._-]\d{1,2}', "", title)
        #  Broken up inseparate itemstokens
        tokens = Tokens(title)
        self.tokens = tokens
        #  Parse name、 Particular year、 Classifier for seasonal crop yield or seasons of a tv series、 Classifier for sections of a tv series e.g. episode、 Resource type、 Resolution (of a photo)
        token = tokens.get_next()
        while token:
            # Part
            self.__init_part(token)
            #  Caption
            if self._continue_flag:
                self.__init_name(token)
            #  Particular year
            if self._continue_flag:
                self.__init_year(token)
            #  Resolution (of a photo)
            if self._continue_flag:
                self.__init_resource_pix(token)
            #  Classifier for seasonal crop yield or seasons of a tv series
            if self._continue_flag:
                self.__init_season(token)
            #  Classifier for sections of a tv series e.g. episode
            if self._continue_flag:
                self.__init_episode(token)
            #  Resource type
            if self._continue_flag:
                self.__init_resource_type(token)
            #  Video encoding
            if self._continue_flag:
                self.__init_video_encode(token)
            #  Audio encoding
            if self._continue_flag:
                self.__init_audio_encode(token)
            #  Take the next one.， Until there are no cards for the
            token = tokens.get_next()
            self._continue_flag = True
        #  Composite mass
        if self._effect:
            self._effect.reverse()
            self.resource_effect = " ".join(self._effect)
        if self._source:
            self.resource_type = self._source.strip()
        #  Extract the original diskDIY
        if self.resource_type and "BluRay" in self.resource_type:
            if (self.subtitle and re.findall(r'D[Ii]Y', self.subtitle)) \
                    or re.findall(r'-D[Ii]Y@', original_title):
                self.resource_type = f"{self.resource_type} DIY"
        #  Analyzing subheadings， As long as the season and set
        self.init_subtitle(self.org_string)
        if not self._subtitle_flag and self.subtitle:
            self.init_subtitle(self.subtitle)
        #  Remove unwanted interfering characters from the name， Plain numbers that are too short don't
        self.cn_name = self.__fix_name(self.cn_name)
        self.en_name = StringUtils.str_title(self.__fix_name(self.en_name))
        #  Deal withpart
        if self.part and self.part.upper() == "PART":
            self.part = None
        #  Production team/ Subtitling team
        self.resource_team = ReleaseGroupsMatcher().match(title=original_title) or None
        #  Custom placeholders
        self.customization = CustomizationMatcher().match(title=original_title) or None

    def __fix_name(self, name: str):
        if not name:
            return name
        name = re.sub(r'%s' % self._name_nostring_re, '', name,
                      flags=re.IGNORECASE).strip()
        name = re.sub(r'\s+', ' ', name)
        if name.isdigit() \
                and int(name) < 1800 \
                and not self.year \
                and not self.begin_season \
                and not self.resource_pix \
                and not self.resource_type \
                and not self.audio_encode \
                and not self.video_encode:
            if self.begin_episode is None:
                self.begin_episode = int(name)
                name = None
            elif self.is_in_episode(int(name)) and not self.begin_season:
                name = None
        return name

    def __init_name(self, token: str):
        if not token:
            return
        #  Recycling title
        if self._unknown_name_str:
            if not self.cn_name:
                if not self.en_name:
                    self.en_name = self._unknown_name_str
                elif self._unknown_name_str != self.year:
                    self.en_name = "%s %s" % (self.en_name, self._unknown_name_str)
                self._last_token_type = "enname"
            self._unknown_name_str = ""
        if self._stop_name_flag:
            return
        if token.upper() == "AKA":
            self._continue_flag = False
            self._stop_name_flag = True
            return
        if token in self._name_se_words:
            self._last_token_type = 'name_se_words'
            return
        if StringUtils.is_chinese(token):
            #  Contains chinese， Straight to the title.（ Consecutive numbers or english are retained）， And no longer takes the chinese characters that appear after it
            self._last_token_type = "cnname"
            if not self.cn_name:
                self.cn_name = token
            elif not self._stop_cnname_flag:
                if not re.search("%s" % self._name_no_chinese_re, token, flags=re.IGNORECASE) \
                        and not re.search("%s" % self._name_se_words, token, flags=re.IGNORECASE):
                    self.cn_name = "%s %s" % (self.cn_name, token)
                self._stop_cnname_flag = True
        else:
            is_roman_digit = re.search(self._roman_numerals, token)
            #  Arabic or roman numerals
            if token.isdigit() or is_roman_digit:
                #  Not after the first season.
                if self._last_token_type == 'name_se_words':
                    return
                if self.name:
                    #  The name is followed by 0  Not at the beginning.， It is highly likely that the set
                    if token.startswith('0'):
                        return
                    #  Check to see if it's a real number
                    if token.isdigit():
                        try:
                            int(token)
                        except ValueError:
                            return
                    #  Chinese names followed by a number that is not a year are most likely to be sets.
                    if not is_roman_digit \
                            and self._last_token_type == "cnname" \
                            and int(token) < 1900:
                        return
                    if (token.isdigit() and len(token) < 4) or is_roman_digit:
                        # 4 Numbers or roman numerals up to the first digit， Assembling into existing titles
                        if self._last_token_type == "cnname":
                            self.cn_name = "%s %s" % (self.cn_name, token)
                        elif self._last_token_type == "enname":
                            self.en_name = "%s %s" % (self.en_name, token)
                        self._continue_flag = False
                    elif token.isdigit() and len(token) == 4:
                        # 4 Digital (e.g. phone number)， It could be the year.， Or maybe it's really part of the title， It's also possible that the set
                        if not self._unknown_name_str:
                            self._unknown_name_str = token
                else:
                    #  The first number before the name， Take down
                    if not self._unknown_name_str:
                        self._unknown_name_str = token
            elif re.search(r"%s" % self._season_re, token, re.IGNORECASE):
                #  Classifier for seasonal crop yield or seasons of a tv series的处理
                if self.en_name and re.search(r"SEASON$", self.en_name, re.IGNORECASE):
                    #  If matched to the season， English names end inSeason， ClarificationSeason Belongs to the title， Should not be removed as a disruptive word subsequently
                    self.en_name += ' '
                self._stop_name_flag = True
                return
            elif re.search(r"%s" % self._episode_re, token, re.IGNORECASE) \
                    or re.search(r"(%s)" % self._resources_type_re, token, re.IGNORECASE) \
                    or re.search(r"%s" % self._resources_pix_re, token, re.IGNORECASE):
                #  Classifier for sections of a tv series e.g. episode、来源、版本等不要
                self._stop_name_flag = True
                return
            else:
                #  Suffixes should not be
                if ".%s".lower() % token in settings.RMT_MEDIAEXT:
                    return
                #  English or english+ Digital (electronics etc)， Assemble
                if self.en_name:
                    self.en_name = "%s %s" % (self.en_name, token)
                else:
                    self.en_name = token
                self._last_token_type = "enname"

    def __init_part(self, token: str):
        if not self.name:
            return
        if not self.year \
                and not self.begin_season \
                and not self.begin_episode \
                and not self.resource_pix \
                and not self.resource_type:
            return
        re_res = re.search(r"%s" % self._part_re, token, re.IGNORECASE)
        if re_res:
            if not self.part:
                self.part = re_res.group(1)
            nextv = self.tokens.cur()
            if nextv \
                    and ((nextv.isdigit() and (len(nextv) == 1 or len(nextv) == 2 and nextv.startswith('0')))
                         or nextv.upper() in ['A', 'B', 'C', 'I', 'II', 'III']):
                self.part = "%s%s" % (self.part, nextv)
                self.tokens.get_next()
            self._last_token_type = "part"
            self._continue_flag = False
            self._stop_name_flag = False

    def __init_year(self, token: str):
        if not self.name:
            return
        if not token.isdigit():
            return
        if len(token) != 4:
            return
        if not 1900 < int(token) < 2050:
            return
        if self.year:
            if self.en_name:
                self.en_name = "%s %s" % (self.en_name.strip(), self.year)
            elif self.cn_name:
                self.cn_name = "%s %s" % (self.cn_name, self.year)
        elif self.en_name and re.search(r"SEASON$", self.en_name, re.IGNORECASE):
            #  If matched to year， And the english name ends inSeason， ClarificationSeason Belongs to the title， Should not be removed as a disruptive word subsequently
            self.en_name += ' '
        self.year = token
        self._last_token_type = "year"
        self._continue_flag = False
        self._stop_name_flag = True

    def __init_resource_pix(self, token: str):
        if not self.name:
            return
        re_res = re.findall(r"%s" % self._resources_pix_re, token, re.IGNORECASE)
        if re_res:
            self._last_token_type = "pix"
            self._continue_flag = False
            self._stop_name_flag = True
            resource_pix = None
            for pixs in re_res:
                if isinstance(pixs, tuple):
                    pix_t = None
                    for pix_i in pixs:
                        if pix_i:
                            pix_t = pix_i
                            break
                    if pix_t:
                        resource_pix = pix_t
                else:
                    resource_pix = pixs
                if resource_pix and not self.resource_pix:
                    self.resource_pix = resource_pix.lower()
                    break
            if self.resource_pix \
                    and self.resource_pix.isdigit() \
                    and self.resource_pix[-1] not in 'kpi':
                self.resource_pix = "%sp" % self.resource_pix
        else:
            re_res = re.search(r"%s" % self._resources_pix_re2, token, re.IGNORECASE)
            if re_res:
                self._last_token_type = "pix"
                self._continue_flag = False
                self._stop_name_flag = True
                if not self.resource_pix:
                    self.resource_pix = re_res.group(1).lower()

    def __init_season(self, token: str):
        re_res = re.findall(r"%s" % self._season_re, token, re.IGNORECASE)
        if re_res:
            self._last_token_type = "season"
            self.type = MediaType.TV
            self._stop_name_flag = True
            self._continue_flag = True
            for se in re_res:
                if isinstance(se, tuple):
                    se_t = None
                    for se_i in se:
                        if se_i and str(se_i).isdigit():
                            se_t = se_i
                            break
                    if se_t:
                        se = int(se_t)
                    else:
                        break
                else:
                    se = int(se)
                if self.begin_season is None:
                    self.begin_season = se
                    self.total_season = 1
                else:
                    if se > self.begin_season:
                        self.end_season = se
                        self.total_season = (self.end_season - self.begin_season) + 1
                        if self.isfile and self.total_season > 1:
                            self.end_season = None
                            self.total_season = 1
        elif token.isdigit():
            try:
                int(token)
            except ValueError:
                return
            if self._last_token_type == "SEASON" \
                    and self.begin_season is None \
                    and len(token) < 3:
                self.begin_season = int(token)
                self.total_season = 1
                self._last_token_type = "season"
                self._stop_name_flag = True
                self._continue_flag = False
                self.type = MediaType.TV
        elif token.upper() == "SEASON" and self.begin_season is None:
            self._last_token_type = "SEASON"
        elif self.type == MediaType.TV and self.begin_season is None:
            self.begin_season = 1

    def __init_episode(self, token: str):
        re_res = re.findall(r"%s" % self._episode_re, token, re.IGNORECASE)
        if re_res:
            self._last_token_type = "episode"
            self._continue_flag = False
            self._stop_name_flag = True
            self.type = MediaType.TV
            for se in re_res:
                if isinstance(se, tuple):
                    se_t = None
                    for se_i in se:
                        if se_i and str(se_i).isdigit():
                            se_t = se_i
                            break
                    if se_t:
                        se = int(se_t)
                    else:
                        break
                else:
                    se = int(se)
                if self.begin_episode is None:
                    self.begin_episode = se
                    self.total_episode = 1
                else:
                    if se > self.begin_episode:
                        self.end_episode = se
                        self.total_episode = (self.end_episode - self.begin_episode) + 1
                        if self.isfile and self.total_episode > 2:
                            self.end_episode = None
                            self.total_episode = 1
        elif token.isdigit():
            try:
                int(token)
            except ValueError:
                return
            if self.begin_episode is not None \
                    and self.end_episode is None \
                    and len(token) < 5 \
                    and int(token) > self.begin_episode \
                    and self._last_token_type == "episode":
                self.end_episode = int(token)
                self.total_episode = (self.end_episode - self.begin_episode) + 1
                if self.isfile and self.total_episode > 2:
                    self.end_episode = None
                    self.total_episode = 1
                self._continue_flag = False
                self.type = MediaType.TV
            elif self.begin_episode is None \
                    and 1 < len(token) < 4 \
                    and self._last_token_type != "year" \
                    and self._last_token_type != "videoencode" \
                    and token != self._unknown_name_str:
                self.begin_episode = int(token)
                self.total_episode = 1
                self._last_token_type = "episode"
                self._continue_flag = False
                self._stop_name_flag = True
                self.type = MediaType.TV
            elif self._last_token_type == "EPISODE" \
                    and self.begin_episode is None \
                    and len(token) < 5:
                self.begin_episode = int(token)
                self.total_episode = 1
                self._last_token_type = "episode"
                self._continue_flag = False
                self._stop_name_flag = True
                self.type = MediaType.TV
        elif token.upper() == "EPISODE":
            self._last_token_type = "EPISODE"

    def __init_resource_type(self, token):
        if not self.name:
            return
        source_res = re.search(r"(%s)" % self._source_re, token, re.IGNORECASE)
        if source_res:
            self._last_token_type = "source"
            self._continue_flag = False
            self._stop_name_flag = True
            if not self._source:
                self._source = source_res.group(1)
                self._last_token = self._source.upper()
            return
        elif token.upper() == "DL" \
                and self._last_token_type == "source" \
                and self._last_token == "WEB":
            self._source = "WEB-DL"
            self._continue_flag = False
            return
        elif token.upper() == "RAY" \
                and self._last_token_type == "source" \
                and self._last_token == "BLU":
            self._source = "BluRay"
            self._continue_flag = False
            return
        elif token.upper() == "WEBDL":
            self._source = "WEB-DL"
            self._continue_flag = False
            return
        effect_res = re.search(r"(%s)" % self._effect_re, token, re.IGNORECASE)
        if effect_res:
            self._last_token_type = "effect"
            self._continue_flag = False
            self._stop_name_flag = True
            effect = effect_res.group(1)
            if effect not in self._effect:
                self._effect.append(effect)
            self._last_token = effect.upper()

    def __init_video_encode(self, token: str):
        if not self.name:
            return
        if not self.year \
                and not self.resource_pix \
                and not self.resource_type \
                and not self.begin_season \
                and not self.begin_episode:
            return
        re_res = re.search(r"(%s)" % self._video_encode_re, token, re.IGNORECASE)
        if re_res:
            self._continue_flag = False
            self._stop_name_flag = True
            self._last_token_type = "videoencode"
            if not self.video_encode:
                self.video_encode = re_res.group(1).upper()
                self._last_token = self.video_encode
            elif self.video_encode == "10bit":
                self.video_encode = f"{re_res.group(1).upper()} 10bit"
                self._last_token = re_res.group(1).upper()
        elif token.upper() in ['H', 'X']:
            self._continue_flag = False
            self._stop_name_flag = True
            self._last_token_type = "videoencode"
            self._last_token = token.upper() if token.upper() == "H" else token.lower()
        elif token in ["264", "265"] \
                and self._last_token_type == "videoencode" \
                and self._last_token in ['H', 'X']:
            self.video_encode = "%s%s" % (self._last_token, token)
        elif token.isdigit() \
                and self._last_token_type == "videoencode" \
                and self._last_token in ['VC', 'MPEG']:
            self.video_encode = "%s%s" % (self._last_token, token)
        elif token.upper() == "10BIT":
            self._last_token_type = "videoencode"
            if not self.video_encode:
                self.video_encode = "10bit"
            else:
                self.video_encode = f"{self.video_encode} 10bit"

    def __init_audio_encode(self, token: str):
        if not self.name:
            return
        if not self.year \
                and not self.resource_pix \
                and not self.resource_type \
                and not self.begin_season \
                and not self.begin_episode:
            return
        re_res = re.search(r"(%s)" % self._audio_encode_re, token, re.IGNORECASE)
        if re_res:
            self._continue_flag = False
            self._stop_name_flag = True
            self._last_token_type = "audioencode"
            self._last_token = re_res.group(1).upper()
            if not self.audio_encode:
                self.audio_encode = re_res.group(1)
            else:
                if self.audio_encode.upper() == "DTS":
                    self.audio_encode = "%s-%s" % (self.audio_encode, re_res.group(1))
                else:
                    self.audio_encode = "%s %s" % (self.audio_encode, re_res.group(1))
        elif token.isdigit() \
                and self._last_token_type == "audioencode":
            if self.audio_encode:
                if self._last_token.isdigit():
                    self.audio_encode = "%s.%s" % (self.audio_encode, token)
                elif self.audio_encode[-1].isdigit():
                    self.audio_encode = "%s %s.%s" % (self.audio_encode[:-1], self.audio_encode[-1], token)
                else:
                    self.audio_encode = "%s %s" % (self.audio_encode, token)
            self._last_token = token
