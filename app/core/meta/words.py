from typing import List, Tuple

import cn2an
import regex as re

from app.db.systemconfig_oper import SystemConfigOper
from app.log import logger
from app.schemas.types import SystemConfigKey
from app.utils.singleton import Singleton


class WordsMatcher(metaclass=Singleton):

    def __init__(self):
        self.systemconfig = SystemConfigOper()

    def prepare(self, title: str) -> Tuple[str, List[str]]:
        """
        Preprocessing headings， Three formats are supported
        1： Blocked word
        2： Superseded word =>  Alternative word
        3： Prepositioning words <>  Post locator >>  Offset（EP）
        """
        appley_words = []
        #  Read customized identifiers
        words: List[str] = self.systemconfig.get(SystemConfigKey.CustomIdentifiers) or []
        for word in words:
            if not word:
                continue
            try:
                if word.count(" => ") and word.count(" && ") and word.count(" >> ") and word.count(" <> "):
                    #  Alternative word
                    thc = str(re.findall(r'(.*?)\s*=>', word)[0]).strip()
                    #  Superseded word
                    bthc = str(re.findall(r'=>\s*(.*?)\s*&&', word)[0]).strip()
                    #  Set pre-offset field
                    pyq = str(re.findall(r'&&\s*(.*?)\s*<>', word)[0]).strip()
                    #  Set post-offset fields
                    pyh = str(re.findall(r'<>(.*?)\s*>>', word)[0]).strip()
                    #  Set offset
                    offsets = str(re.findall(r'>>\s*(.*?)$', word)[0]).strip()
                    #  Alternative word
                    title, message, state = self.__replace_regex(title, thc, bthc)
                    if state:
                        #  Alternative word成功再进行集偏移
                        title, message, state = self.__episode_offset(title, pyq, pyh, offsets)
                elif word.count(" => "):
                    #  Alternative word
                    strings = word.split(" => ")
                    title, message, state = self.__replace_regex(title, strings[0], strings[1])
                elif word.count(" >> ") and word.count(" <> "):
                    #  Set offset
                    strings = word.split(" <> ")
                    offsets = strings[1].split(" >> ")
                    strings[1] = offsets[0]
                    title, message, state = self.__episode_offset(title, strings[0], strings[1],
                                                                  offsets[1])
                else:
                    #  Blocked word
                    title, message, state = self.__replace_regex(title, word, "")

                if state:
                    appley_words.append(word)
                else:
                    logger.debug(f" Failure to replace customized identifiers：{message}")
            except Exception as err:
                print(str(err))

        return title, appley_words

    @staticmethod
    def __replace_regex(title: str, replaced: str, replace: str) -> Tuple[str, str, bool]:
        """
        Regular substitution
        """
        try:
            if not re.findall(r'%s' % replaced, title):
                return title, "", False
            else:
                return re.sub(r'%s' % replaced, r'%s' % replace, title), "", True
        except Exception as err:
            print(str(err))
            return title, str(err), False

    @staticmethod
    def __episode_offset(title: str, front: str, back: str, offset: str) -> Tuple[str, str, bool]:
        """
        Offset of set number (math.)
        """
        try:
            if back and not re.findall(r'%s' % back, title):
                return title, "", False
            if front and not re.findall(r'%s' % front, title):
                return title, "", False
            offset_word_info_re = re.compile(r'(?<=%s.*?)[0-9 One, two, three, four, five, six, seven, eight, nine, ten.]+(?=.*?%s)' % (front, back))
            episode_nums_str = re.findall(offset_word_info_re, title)
            if not episode_nums_str:
                return title, "", False
            episode_nums_offset_str = []
            offset_order_flag = False
            for episode_num_str in episode_nums_str:
                episode_num_int = int(cn2an.cn2an(episode_num_str, "smart"))
                offset_caculate = offset.replace("EP", str(episode_num_int))
                episode_num_offset_int = int(eval(offset_caculate))
                #  Forward offset
                if episode_num_int > episode_num_offset_int:
                    offset_order_flag = True
                #  Backward offset
                elif episode_num_int < episode_num_offset_int:
                    offset_order_flag = False
                #  The original value is a chinese numeral， Convert back to chinese numerals， Arabic numerals are reverted to0 Padding
                if not episode_num_str.isdigit():
                    episode_num_offset_str = cn2an.an2cn(episode_num_offset_int, "low")
                else:
                    count_0 = re.findall(r"^0+", episode_num_str)
                    if count_0:
                        episode_num_offset_str = f"{count_0[0]}{episode_num_offset_int}"
                    else:
                        episode_num_offset_str = str(episode_num_offset_int)
                episode_nums_offset_str.append(episode_num_offset_str)
            episode_nums_dict = dict(zip(episode_nums_str, episode_nums_offset_str))
            #  Number of sets shifted forward， Episodes are processed in ascending order
            if offset_order_flag:
                episode_nums_list = sorted(episode_nums_dict.items(), key=lambda x: x[1])
            #  The set number is shifted backward， Episodes are processed in descending order
            else:
                episode_nums_list = sorted(episode_nums_dict.items(), key=lambda x: x[1], reverse=True)
            for episode_num in episode_nums_list:
                episode_offset_re = re.compile(
                    r'(?<=%s.*?)%s(?=.*?%s)' % (front, episode_num[0], back))
                title = re.sub(episode_offset_re, r'%s' % episode_num[1], title)
            return title, "", True
        except Exception as err:
            print(str(err))
            return title, str(err), False
