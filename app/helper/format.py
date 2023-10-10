import re
from typing import Tuple, Optional

import parse


class FormatParser(object):
    _key = ""
    _split_chars = r"\.|\s+|\(|\)|\[|]|-|\+|【|】|/|～|;|&|\||#|_|「|」|~"

    def __init__(self, eformat: str, details: str = None, part: str = None,
                 offset: int = None, key: str = "ep"):
        """
        :params eformat:  Formatting strings
        :params details:  Formatting details
        :params part:  Subset
        :params offset:  Offset
        :prams key: EP Keywords.
        """
        self._format = eformat
        self._start_ep = None
        self._end_ep = None
        self._part = None
        if part:
            self._part = part
        if details:
            if re.compile("\\d{1,4}-\\d{1,4}").match(details):
                self._start_ep = details
                self._end_ep = details
            else:
                tmp = details.split(",")
                if len(tmp) > 1:
                    self._start_ep = int(tmp[0])
                    self._end_ep = int(tmp[0]) if int(tmp[0]) > int(tmp[1]) else int(tmp[1])
                else:
                    self._start_ep = self._end_ep = int(tmp[0])
        self.__offset = int(offset) if offset else 0
        self._key = key

    @property
    def format(self):
        return self._format

    @property
    def start_ep(self):
        return self._start_ep

    @property
    def end_ep(self):
        return self._end_ep

    @property
    def part(self):
        return self._part

    @property
    def offset(self):
        return self.__offset

    def match(self, file: str) -> bool:
        if not self._format:
            return True
        s, e = self.__handle_single(file)
        if not s:
            return False
        if self._start_ep is None:
            return True
        if self._start_ep <= s <= self._end_ep:
            return True
        return False

    def split_episode(self, file_name: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """
        No. of split episodes， Returns the number of starting episodes， Number of ending episodes，Part Text
        """
        #  Specific episodes assigned， Direct return
        if self._start_ep is not None and self._start_ep == self._end_ep:
            if isinstance(self._start_ep, str):
                s, e = self._start_ep.split("-")
                if int(s) == int(e):
                    return int(s) + self.__offset, None, self.part
                return int(s) + self.__offset, int(e) + self.__offset, self.part
            return self._start_ep + self.__offset, None, self.part
        if not self._format:
            return None, None, None
        s, e = self.__handle_single(file_name)
        return s + self.__offset if s is not None else None, \
            e + self.__offset if e is not None else None, self.part

    def __handle_single(self, file: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Process a single set， Returns the number of beginning and ending episodes of a single episode
        """
        if not self._format:
            return None, None
        ret = parse.parse(self._format, file)
        if not ret or not ret.__contains__(self._key):
            return None, None
        episodes = ret.__getitem__(self._key)
        if not re.compile(r"^(EP)?(\d{1,4})(-(EP)?(\d{1,4}))?$", re.IGNORECASE).match(episodes):
            return None, None
        episode_splits = list(filter(lambda x: re.compile(r'[a-zA-Z]*\d{1,4}', re.IGNORECASE).match(x),
                                     re.split(r'%s' % self._split_chars, episodes)))
        if len(episode_splits) == 1:
            return int(re.compile(r'[a-zA-Z]*', re.IGNORECASE).sub("", episode_splits[0])), None
        else:
            return int(re.compile(r'[a-zA-Z]*', re.IGNORECASE).sub("", episode_splits[0])), int(
                re.compile(r'[a-zA-Z]*', re.IGNORECASE).sub("", episode_splits[1]))
