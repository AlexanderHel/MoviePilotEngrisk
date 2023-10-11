import json
import os
import time
from io import BytesIO
from typing import Tuple

from PIL import Image
from lxml import etree
from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class Tjupt(_ISiteSigninHandler):
    """
    Beiyang check-in
    """
    #  Matching sitesUrl， Each implementation class needs to be set up as its own siteUrl
    site_url = "tjupt.org"

    #  Check-in address
    _sign_in_url = 'https://www.tjupt.org/attendance.php'

    #  Signed in
    _sign_regex = ['<a href="attendance.php"> Signed in today</a>']

    #  Sign in successfully
    _succeed_regex = [' This is your first check-in， This check-in gets\\d+ Power level (math.)。',
                      ' Sign in successfully， This is your first\\d+ Secondary check-in， Signed in continuously\\d+ Sky， This check-in gets\\d+ Power level (math.)。',
                      ' Re-sign in successfully， This check-in gets\\d+ Power level (math.)']

    #  Store the correct answer， Follow-up can be checked directly
    _answer_path = settings.TEMP_PATH / "signin/"
    _answer_file = _answer_path / "tjupt.json"

    @classmethod
    def match(cls, url: str) -> bool:
        """
        Based on siteUrl Determine if the current site check-in class matches， In most cases it is sufficient to use the default implementation
        :param url:  WebsiteUrl
        :return:  Whether or not it matches， If a match is made then the class'ssignin Methodologies
        """
        return True if StringUtils.url_equal(url, cls.site_url) else False

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """
        Perform check-in operations
        :param site_info:  Site information， Contains siteUrl、 WebsiteCookie、UA And other information
        :return:  Check-in results information
        """
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxy = site_info.get("proxy")
        render = site_info.get("render")

        #  Creating a correct answer storage directory
        if not os.path.exists(os.path.dirname(self._answer_file)):
            os.makedirs(os.path.dirname(self._answer_file))

        # 获取Beiyang check-in页面html
        html_text = self.get_page_source(url=self._sign_in_url,
                                         cookie=site_cookie,
                                         ua=ua,
                                         proxy=proxy,
                                         render=render)

        #  Get signed in and returnhtml， Determine if sign-in is successful
        if not html_text:
            logger.error(f"{site}  Failed to sign in， Please check site connectivity")
            return False, ' Failed to sign in， Please check site connectivity'

        if "login.php" in html_text:
            logger.error(f"{site}  Failed to sign in，Cookie Lose effectiveness")
            return False, ' Failed to sign in，Cookie Lose effectiveness'

        sign_status = self.sign_in_result(html_res=html_text,
                                          regexs=self._sign_regex)
        if sign_status:
            logger.info(f"{site}  Signed in today")
            return True, ' Signed in today'

        #  Parsing without signing inhtml
        html = etree.HTML(html_text)
        if not html:
            return False, ' Failed to sign in'
        img_url = html.xpath('//table[@class="captcha"]//img/@src')[0]

        if not img_url:
            logger.error(f"{site}  Failed to sign in， Not getting the sign-in image")
            return False, ' Failed to sign in， Not getting the sign-in image'

        #  Check-in pictures
        img_url = "https://www.tjupt.org" + img_url
        logger.info(f" Get to the sign-in image {img_url}")
        #  Get sign-in imagehash
        captcha_img_res = RequestUtils(cookies=site_cookie,
                                       ua=ua,
                                       proxies=settings.PROXY if proxy else None
                                       ).get_res(url=img_url)
        if not captcha_img_res or captcha_img_res.status_code != 200:
            logger.error(f"{site}  Check-in pictures {img_url}  Request failed")
            return False, ' Failed to sign in， Not getting the sign-in image'
        captcha_img = Image.open(BytesIO(captcha_img_res.content))
        captcha_img_hash = self._tohash(captcha_img)
        logger.debug(f" Check-in pictureshash {captcha_img_hash}")

        #  Check-in answer options
        values = html.xpath("//input[@name='answer']/@value")
        options = html.xpath("//input[@name='answer']/following-sibling::text()")

        if not values or not options:
            logger.error(f"{site}  Failed to sign in， Answer options not captured")
            return False, ' Failed to sign in， Answer options not captured'

        # value+ Options (as in computer software settings)
        answers = list(zip(values, options))
        logger.debug(f" Get all check-in options {answers}")

        #  Check for existing answers
        exits_answers = {}
        try:
            with open(self._answer_file, 'r') as f:
                json_str = f.read()
            exits_answers = json.loads(json_str)
            #  Query local current captchahash Solution
            captcha_answer = exits_answers[captcha_img_hash]

            #  The local presence of thishash The corresponding correct answer then traverses the query
            if captcha_answer:
                for value, answer in answers:
                    if str(captcha_answer) == str(answer):
                        #  That's the answer.
                        return self.__signin(answer=value,
                                             site_cookie=site_cookie,
                                             ua=ua,
                                             proxy=proxy,
                                             site=site)
        except (FileNotFoundError, IOError, OSError) as e:
            logger.debug(f" Failed to query locally known answers：{e}， Continue requesting doujinshi queries")

        #  If the correct answer does not exist locally then request a douban query for a match
        for value, answer in answers:
            if answer:
                #  Douban search
                db_res = RequestUtils().get_res(url=f'https://movie.douban.com/j/subject_suggest?q={answer}')
                if not db_res or db_res.status_code != 200:
                    logger.debug(f" Check-in options {answer}  Douban data not queried")
                    continue

                #  Douban returns results
                db_answers = json.loads(db_res.text)
                if not isinstance(db_answers, list):
                    db_answers = [db_answers]

                if len(db_answers) == 0:
                    logger.debug(f" Check-in options {answer}  Query to douban data is empty")

                for db_answer in db_answers:
                    answer_img_url = db_answer['img']

                    #  Get answershash
                    answer_img_res = RequestUtils(referer="https://movie.douban.com").get_res(url=answer_img_url)
                    if not answer_img_res or answer_img_res.status_code != 200:
                        logger.debug(f" Check-in answers {answer} {answer_img_url}  Request failed")
                        continue

                    answer_img = Image.open(BytesIO(answer_img_res.content))
                    answer_img_hash = self._tohash(answer_img)
                    logger.debug(f" Sign in answer picturehash {answer} {answer_img_hash}")

                    #  Get the similarity between the option image and the check-in image， More than0.9 Default is the correct answer
                    score = self._comparehash(captcha_img_hash, answer_img_hash)
                    logger.info(f" Check-in images and options {answer}  Douban picture similarity {score}")
                    if score > 0.9:
                        #  That's the answer.
                        return self.__signin(answer=value,
                                             site_cookie=site_cookie,
                                             ua=ua,
                                             proxy=proxy,
                                             site=site,
                                             exits_answers=exits_answers,
                                             captcha_img_hash=captcha_img_hash)

            #  Intervals5s， Prevent requests from being blocked by douban too oftenip
            time.sleep(5)
        logger.error(f" Douban image matching， No matches were obtained")

        #  No match signed in successfully， Then the sign-in fails
        return False, ' Failed to sign in， No matches were obtained'

    def __signin(self, answer, site_cookie, ua, proxy, site, exits_answers=None, captcha_img_hash=None):
        """
        Check-in request
        """
        data = {
            'answer': answer,
            'submit': ' Submit (a report etc)'
        }
        logger.debug(f" Submit (a report etc)data {data}")
        sign_in_res = RequestUtils(cookies=site_cookie,
                                   ua=ua,
                                   proxies=settings.PROXY if proxy else None
                                   ).post_res(url=self._sign_in_url, data=data)
        if not sign_in_res or sign_in_res.status_code != 200:
            logger.error(f"{site}  Failed to sign in， Check-in interface request failed")
            return False, ' Failed to sign in， Check-in interface request failed'

        #  Get signed in and returnhtml， Determine if sign-in is successful
        sign_status = self.sign_in_result(html_res=sign_in_res.text,
                                          regexs=self._succeed_regex)
        if sign_status:
            logger.info(f" Sign in successfully")
            if exits_answers and captcha_img_hash:
                #  Sign in successfully写入本地文件
                self.__write_local_answer(exits_answers=exits_answers or {},
                                          captcha_img_hash=captcha_img_hash,
                                          answer=answer)
            return True, ' Sign in successfully'
        else:
            logger.error(f"{site}  Failed to sign in， Please go to page")
            return False, ' Failed to sign in， Please go to page'

    def __write_local_answer(self, exits_answers, captcha_img_hash, answer):
        """
        Check-in successfully written to local file
        """
        try:
            exits_answers[captcha_img_hash] = answer
            #  Serialized data
            formatted_data = json.dumps(exits_answers, indent=4)
            with open(self._answer_file, 'w') as f:
                f.write(formatted_data)
        except (FileNotFoundError, IOError, OSError) as e:
            logger.debug(f"Check-in successfully written to local file失败：{e}")

    @staticmethod
    def _tohash(img, shape=(10, 10)):
        """
        Get picturehash
        """
        img = img.resize(shape)
        gray = img.convert('L')
        s = 0
        hash_str = ''
        for i in range(shape[1]):
            for j in range(shape[0]):
                s = s + gray.getpixel((j, i))
        avg = s / (shape[0] * shape[1])
        for i in range(shape[1]):
            for j in range(shape[0]):
                if gray.getpixel((j, i)) > avg:
                    hash_str = hash_str + '1'
                else:
                    hash_str = hash_str + '0'
        return hash_str

    @staticmethod
    def _comparehash(hash1, hash2, shape=(10, 10)):
        """
        Compare pictureshash
        Return similarity
        """
        n = 0
        if len(hash1) != len(hash2):
            return -1
        for i in range(len(hash1)):
            if hash1[i] == hash2[i]:
                n = n + 1
        return n / (shape[0] * shape[1])
