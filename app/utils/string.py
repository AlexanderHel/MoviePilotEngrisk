import bisect
import datetime
import hashlib
import random
import re
from typing import Union, Tuple, Optional, Any, List, Generator
from urllib import parse

import cn2an
import dateparser
import dateutil.parser

from app.schemas.types import MediaType


class StringUtils:

    @staticmethod
    def num_filesize(text: Union[str, int, float]) -> int:
        """
        Convert file size text to bytes
        """
        if not text:
            return 0
        if not isinstance(text, str):
            text = str(text)
        if text.isdigit():
            return int(text)
        text = text.replace(",", "").replace(" ", "").upper()
        size = re.sub(r"[KMGTPI]*B?", "", text, flags=re.IGNORECASE)
        try:
            size = float(size)
        except ValueError:
            return 0
        if text.find("PB") != -1 or text.find("PIB") != -1:
            size *= 1024 ** 5
        elif text.find("TB") != -1 or text.find("TIB") != -1:
            size *= 1024 ** 4
        elif text.find("GB") != -1 or text.find("GIB") != -1:
            size *= 1024 ** 3
        elif text.find("MB") != -1 or text.find("MIB") != -1:
            size *= 1024 ** 2
        elif text.find("KB") != -1 or text.find("KIB") != -1:
            size *= 1024
        return round(size)

    @staticmethod
    def str_timelong(time_sec: Union[str, int, float]) -> str:
        """
        Converting numbers to time descriptions
        """
        if not isinstance(time_sec, int) or not isinstance(time_sec, float):
            try:
                time_sec = float(time_sec)
            except ValueError:
                return ""
        d = [(0, ' Unit of angle or arc equivalent one sixtieth of a degree'), (60 - 1, ' Ingredient'), (3600 - 1, ' Hourly'), (86400 - 1, ' Sky')]
        s = [x[0] for x in d]
        index = bisect.bisect_left(s, time_sec) - 1
        if index == -1:
            return str(time_sec)
        else:
            b, u = d[index]
        return str(round(time_sec / (b + 1))) + u

    @staticmethod
    def is_chinese(word: Union[str, list]) -> bool:
        """
        Determine whether it contains chinese
        """
        if not word:
            return False
        if isinstance(word, list):
            word = " ".join(word)
        chn = re.compile(r'[\u4e00-\u9fff]')
        if chn.search(word):
            return True
        else:
            return False

    @staticmethod
    def is_japanese(word: str) -> bool:
        """
        Determine whether it contains japanese
        """
        jap = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')
        if jap.search(word):
            return True
        else:
            return False

    @staticmethod
    def is_korean(word: str) -> bool:
        """
        Determine if korean is included
        """
        kor = re.compile(r'[\uAC00-\uD7FF]')
        if kor.search(word):
            return True
        else:
            return False

    @staticmethod
    def is_all_chinese(word: str) -> bool:
        """
        Determine whether all chinese
        """
        for ch in word:
            if ch == ' ':
                continue
            if '\u4e00' <= ch <= '\u9fff':
                continue
            else:
                return False
        return True

    @staticmethod
    def str_int(text: str) -> int:
        """
        web String conversionint
        :param text:
        :return:
        """
        if text:
            text = text.strip()
        if not text:
            return 0
        try:
            return int(text.replace(',', ''))
        except ValueError:
            return 0

    @staticmethod
    def str_float(text: str) -> float:
        """
        web String conversionfloat
        :param text:
        :return:
        """
        if text:
            text = text.strip()
        if not text:
            return 0.0
        try:
            text = text.replace(',', '')
            if text:
                return float(text)
        except ValueError:
            pass
        return 0.0

    @staticmethod
    def clear(text: Union[list, str], replace_word: str = "",
              allow_space: bool = False) -> Union[list, str]:
        """
        Ignore special characters
        """
        #  Special characters to be ignored
        CONVERT_EMPTY_CHARS = r"[、.。,，·:：;；!！'’\"“”()（）\[\]【】「」\-——\+\|\\_/&#～~]"
        if not text:
            return text
        if not isinstance(text, list):
            text = re.sub(r"[\u200B-\u200D\uFEFF]",
                          "",
                          re.sub(r"%s" % CONVERT_EMPTY_CHARS, replace_word, text),
                          flags=re.IGNORECASE)
            if not allow_space:
                return re.sub(r"\s+", "", text)
            else:
                return re.sub(r"\s+", " ", text).strip()
        else:
            return [StringUtils.clear(x) for x in text]

    @staticmethod
    def clear_upper(text: str) -> str:
        """
        Remove special characters， Capitalize
        """
        if not text:
            return ""
        return StringUtils.clear(text).upper().strip()

    @staticmethod
    def str_filesize(size: Union[str, float, int], pre: int = 2) -> str:
        """
        Calculates bytes into a file size description（ Return after formatting with units）
        """
        if size is None:
            return ""
        size = re.sub(r"\s|B|iB", "", str(size), re.I)
        if size.replace(".", "").isdigit():
            try:
                size = float(size)
                d = [(1024 - 1, 'K'), (1024 ** 2 - 1, 'M'), (1024 ** 3 - 1, 'G'), (1024 ** 4 - 1, 'T')]
                s = [x[0] for x in d]
                index = bisect.bisect_left(s, size) - 1
                if index == -1:
                    return str(size) + "B"
                else:
                    b, u = d[index]
                return str(round(size / (b + 1), pre)) + u
            except ValueError:
                return ""
        if re.findall(r"[KMGTP]", size, re.I):
            return size
        else:
            return size + "B"

    @staticmethod
    def url_equal(url1: str, url2: str) -> bool:
        """
        Compare two addresses to see if they are the same site
        """
        if not url1 or not url2:
            return False
        if url1.startswith("http"):
            url1 = parse.urlparse(url1).netloc
        if url2.startswith("http"):
            url2 = parse.urlparse(url2).netloc
        if url1.replace("www.", "") == url2.replace("www.", ""):
            return True
        return False

    @staticmethod
    def get_url_netloc(url: str) -> Tuple[str, str]:
        """
        GainURL The protocol and domain name portion of the
        """
        if not url:
            return "", ""
        if not url.startswith("http"):
            return "http", url
        addr = parse.urlparse(url)
        return addr.scheme, addr.netloc

    @staticmethod
    def get_url_domain(url: str) -> str:
        """
        GainURL Domain name section， Retain only the last two levels
        """
        if not url:
            return ""
        if 'u2.dmhy.org' in url:
            return 'u2.dmhy.org'
        _, netloc = StringUtils.get_url_netloc(url)
        if netloc:
            locs = netloc.split(".")
            if len(locs) > 3:
                return netloc
            return ".".join(locs[-2:])
        return ""

    @staticmethod
    def get_url_sld(url: str) -> str:
        """
        GainURL The second-level domain name portion of the， Portless， IfIP Then it returnsIP
        """
        if not url:
            return ""
        _, netloc = StringUtils.get_url_netloc(url)
        if not netloc:
            return ""
        netloc = netloc.split(":")[0].split(".")
        if len(netloc) >= 2:
            return netloc[-2]
        return netloc[0]

    @staticmethod
    def get_base_url(url: str) -> str:
        """
        GainURL Root address
        """
        if not url:
            return ""
        scheme, netloc = StringUtils.get_url_netloc(url)
        return f"{scheme}://{netloc}"

    @staticmethod
    def clear_file_name(name: str) -> Optional[str]:
        if not name:
            return None
        return re.sub(r"[*?\\/\"<>~|]", "", name, flags=re.IGNORECASE).replace(":", "：")

    @staticmethod
    def generate_random_str(randomlength: int = 16) -> str:
        """
        Generate a random string of specified length
        """
        random_str = ''
        base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789'
        length = len(base_str) - 1
        for i in range(randomlength):
            random_str += base_str[random.randint(0, length)]
        return random_str

    @staticmethod
    def get_time(date: Any) -> Optional[datetime.datetime]:
        try:
            return dateutil.parser.parse(date)
        except dateutil.parser.ParserError:
            return None

    @staticmethod
    def unify_datetime_str(datetime_str: str) -> str:
        """
        Date time formatting  Convert to 2020-10-14 07:48:04  This format
        #  Take1:  Date string with time zone eg: Sat, 15 Oct 2022 14:02:54 +0800
        #  Take2:  Intermediate zoneT Date string eg: 2020-10-14T07:48:04
        #  Take3:  Intermediate zoneT Date string eg: 2020-10-14T07:48:04.208
        #  Take4:  The date string starts withGMT Wind up eg: Fri, 14 Oct 2022 07:48:04 GMT
        #  Take5:  The date string starts withUTC Wind up eg: Fri, 14 Oct 2022 07:48:04 UTC
        #  Take6:  The date string starts withZ Wind up eg: Fri, 14 Oct 2022 07:48:04Z
        #  Take7:  Date string as relative time eg: 1 month, 2 days ago
        :param datetime_str:
        :return:
        """
        #  If the incoming parameter isNone  Or empty string  Direct return
        if not datetime_str:
            return datetime_str

        try:
            return dateparser.parse(datetime_str).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(str(e))
            return datetime_str

    @staticmethod
    def format_timestamp(timestamp: str, date_format: str = '%Y-%m-%d %H:%M:%S') -> str:
        """
        Timestamp to date
        :param timestamp:
        :param date_format:
        :return:
        """
        if isinstance(timestamp, str) and not timestamp.isdigit():
            return timestamp
        try:
            return datetime.datetime.fromtimestamp(int(timestamp)).strftime(date_format)
        except Exception as e:
            print(str(e))
            return timestamp

    @staticmethod
    def to_bool(text: str, default_val: bool = False) -> bool:
        """
        String conversionbool
        :param text:  Value to be converted
        :param default_val:  Default value
        :return:
        """
        if isinstance(text, str) and not text:
            return default_val
        if isinstance(text, bool):
            return text
        if isinstance(text, int) or isinstance(text, float):
            return True if text > 0 else False
        if isinstance(text, str) and text.lower() in ['y', 'true', '1', 'yes', 'on']:
            return True
        return False

    @staticmethod
    def str_from_cookiejar(cj: dict) -> str:
        """
        Commander-in-chief (military)cookiejar Convert to string
        :param cj:
        :return:
        """
        return '; '.join(['='.join(item) for item in cj.items()])

    @staticmethod
    def get_idlist(content: str, dicts: List[dict]):
        """
        Extract from stringid Listings
        :param content:  String (computer science)
        :param dicts:  Dictionaries
        :return:
        """
        if not content:
            return []
        id_list = []
        content_list = content.split()
        for dic in dicts:
            if dic.get('name') in content_list and dic.get('id') not in id_list:
                id_list.append(dic.get('id'))
                content = content.replace(dic.get('name'), '')
        return id_list, re.sub(r'\s+', ' ', content).strip()

    @staticmethod
    def md5_hash(data: Any) -> str:
        """
        MD5 HASH
        """
        if not data:
            return ""
        return hashlib.md5(str(data).encode()).hexdigest()

    @staticmethod
    def str_timehours(minutes: int) -> str:
        """
        Converting minutes to hours and minutes
        :param minutes:
        :return:
        """
        if not minutes:
            return ""
        hours = minutes // 60
        minutes = minutes % 60
        if hours:
            return "%s Hourly%s Ingredient" % (hours, minutes)
        else:
            return "%s Minutes" % minutes

    @staticmethod
    def str_amount(amount: object, curr="$") -> str:
        """
        Formatting display amounts
        """
        if not amount:
            return "0"
        return curr + format(amount, ",")

    @staticmethod
    def count_words(text: str) -> int:
        """
        Counts the number of words or characters contained in a string， Need to be compatible with mixed chinese and english
        :param text:  String to be calculated
        :return:  Number of words contained in the string
        """
        if not text:
            return 0
        #  Matching chinese characters and english words with regular expressions
        chinese_pattern = '[\u4e00-\u9fa5]'
        english_pattern = '[a-zA-Z]+'

        #  Match chinese characters and english words
        chinese_matches = re.findall(chinese_pattern, text)
        english_matches = re.findall(english_pattern, text)

        #  Filter out spaces and numbers
        chinese_words = [word for word in chinese_matches if word.isalpha()]
        english_words = [word for word in english_matches if word.isalpha()]

        #  Counting chinese characters and english words
        chinese_count = len(chinese_words)
        english_count = len(english_words)

        return chinese_count + english_count

    @staticmethod
    def split_text(text: str, max_length: int) -> Generator:
        """
        Split text into fixed-byte-length arrays， Priority split by newline， Avoid intra-word splits
        """
        if not text:
            yield ''
        #  Subsidiary bank
        lines = re.split('\n', text)
        buf = ''
        for line in lines:
            if len(line.encode('utf-8')) > max_length:
                #  Ultra-long rows continue to split
                blank = ""
                if re.match(r'^[A-Za-z0-9.\s]+', line):
                    #  English lines split by space
                    parts = line.split()
                    blank = " "
                else:
                    #  Chinese row split by character
                    parts = line
                part = ''
                for p in parts:
                    if len((part + p).encode('utf-8')) > max_length:
                        #  Ultra-long term (i.e. long term)Yield
                        yield (buf + part).strip()
                        buf = ''
                        part = f"{blank}{p}"
                    else:
                        part = f"{part}{blank}{p}"
                if part:
                    #  Append the last part tobuf
                    buf += part
            else:
                if len((buf + "\n" + line).encode('utf-8')) > max_length:
                    # buf Ultra-long term (i.e. long term)Yield
                    yield buf.strip()
                    buf = line
                else:
                    #  The short line is appended directly to thebuf
                    if buf:
                        buf = f"{buf}\n{line}"
                    else:
                        buf = line
        if buf:
            #  Processing of the remainder at the end of the text
            yield buf.strip()

    @staticmethod
    def get_keyword(content: str) \
            -> Tuple[Optional[MediaType], Optional[str], Optional[int], Optional[int], Optional[str], Optional[str]]:
        """
        Split medium years from search keywords、 Classifier for seasonal crop yield or seasons of a tv series、 Classifier for sections of a tv series e.g. episode、 Typology
        """
        if not content:
            return None, None, None, None, None, None

        #  Remove movie or tv show keywords from the query
        mtype = MediaType.TV if re.search(r'^( Dramas| Cartoons and comics|\s+ Dramas|\s+ Cartoons and comics)', content) else None
        content = re.sub(r'^( Cinematic| Dramas| Cartoons and comics|\s+ Cinematic|\s+ Dramas|\s+ Cartoons and comics)', '', content).strip()

        #  Let's cut the episode a little bit.
        season_num = None
        episode_num = None
        season_re = re.search(r' (prefix indicating ordinal number, e.g. first, number two etc)\s*([0-9 One, two, three, four, five, six, seven, eight, nine, ten.]+)\s* Classifier for seasonal crop yield or seasons of a tv series', content, re.IGNORECASE)
        if season_re:
            mtype = MediaType.TV
            season_num = int(cn2an.cn2an(season_re.group(1), mode='smart'))

        episode_re = re.search(r' (prefix indicating ordinal number, e.g. first, number two etc)\s*([0-9 One, two, three, four, five, six, seven, eight, nine, ten, zero.]+)\s* Classifier for sections of a tv series e.g. episode', content, re.IGNORECASE)
        if episode_re:
            mtype = MediaType.TV
            episode_num = int(cn2an.cn2an(episode_re.group(1), mode='smart'))
            if episode_num and not season_num:
                season_num = 1

        year_re = re.search(r'[\s(]+(\d{4})[\s)]*', content)
        year = year_re.group(1) if year_re else None

        key_word = re.sub(
            r' (prefix indicating ordinal number, e.g. first, number two etc)\s*[0-9 One, two, three, four, five, six, seven, eight, nine, ten.]+\s* Classifier for seasonal crop yield or seasons of a tv series| (prefix indicating ordinal number, e.g. first, number two etc)\s*[0-9 One, two, three, four, five, six, seven, eight, nine, ten, zero.]+\s* Classifier for sections of a tv series e.g. episode|[\s(]+(\d{4})[\s)]*', '',
            content, flags=re.IGNORECASE).strip()
        key_word = re.sub(r'\s+', ' ', key_word) if key_word else year

        return mtype, key_word, season_num, episode_num, year, content

    @staticmethod
    def str_title(s: str) -> str:
        """
        Capitalization of letters is compatibleNone
        """
        return s.title() if s else s

    @staticmethod
    def escape_markdown(content: str) -> str:
        """
        Escapes Markdown characters in a string of Markdown.

        Credits to: simonsmh

        :param content: The string of Markdown to escape.
        :type content: :obj:`str`

        :return: The escaped string.
        :rtype: :obj:`str`
        """

        parses = re.sub(r"([_*\[\]()~`>#+\-=|.!{}])", r"\\\1", content)
        reparse = re.sub(r"\\\\([_*\[\]()~`>#+\-=|.!{}])", r"\1", parses)
        return reparse

    @staticmethod
    def get_domain_address(address: str, prefix: bool = True) -> Tuple[Optional[str], Optional[int]]:
        """
        Get the domain name and port number from the address
        """
        if not address:
            return None, None
        if prefix and not address.startswith("http"):
            address = "http://" + address
        parts = address.split(":")
        if len(parts) > 3:
            #  Handling unwanted inclusion of multiple colons（ Except for the colon after the agreement）
            return None, None
        domain = ":".join(parts[:-1])
        #  Check to see if the port number is included
        try:
            port = int(parts[-1])
        except ValueError:
            #  The port number is not an integer， Come (or go) back None  Indicate that sth is invalid
            return None, None
        return domain, port

    @staticmethod
    def str_series(array: List[int]) -> str:
        """
        Converting a list of seasonal episodes to string shorthand
        """

        #  Ensure that arrays are sorted in ascending order
        array.sort()

        result = []
        start = array[0]
        end = array[0]

        for i in range(1, len(array)):
            if array[i] == end + 1:
                end = array[i]
            else:
                if start == end:
                    result.append(str(start))
                else:
                    result.append(f"{start}-{end}")
                start = array[i]
                end = array[i]

        #  Processing the last sequence
        if start == end:
            result.append(str(start))
        else:
            result.append(f"{start}-{end}")

        return ",".join(result)

    @staticmethod
    def format_ep(nums: List[int]) -> str:
        """
        Formatting episode lists as continuous intervals
        """
        if not nums:
            return ""
        if len(nums) == 1:
            return f"E{nums[0]:02d}"
        #  Sort the array in ascending order
        nums.sort()
        formatted_ranges = []
        start = nums[0]
        end = nums[0]

        for i in range(1, len(nums)):
            if nums[i] == end + 1:
                end = nums[i]
            else:
                if start == end:
                    formatted_ranges.append(f"E{start:02d}")
                else:
                    formatted_ranges.append(f"E{start:02d}-E{end:02d}")
                start = end = nums[i]

        if start == end:
            formatted_ranges.append(f"E{start:02d}")
        else:
            formatted_ranges.append(f"E{start:02d}-E{end:02d}")

        formatted_string = "、".join(formatted_ranges)
        return formatted_string

    @staticmethod
    def is_number(text: str) -> bool:
        """
        Determine whether a character can be converted to an integer or a floating point number.
        """
        if not text:
            return False
        try:
            float(text)
            return True
        except ValueError:
            return False
