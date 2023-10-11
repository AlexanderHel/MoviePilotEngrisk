# -*- coding: utf-8 -*-
import re
from typing import Optional

from lxml import etree

from app.log import logger
from app.plugins.sitestatistic.siteuserinfo import ISiteUserInfo, SITE_BASE_ORDER, SiteSchema
from app.utils.string import StringUtils


class NexusPhpSiteUserInfo(ISiteUserInfo):
    schema = SiteSchema.NexusPhp
    order = SITE_BASE_ORDER * 2

    @classmethod
    def match(cls, html_text: str) -> bool:
        """
        Default useNexusPhp Analyze
        :param html_text:
        :return:
        """
        return True

    def _parse_site_page(self, html_text: str):
        html_text = self._prepare_html_text(html_text)

        user_detail = re.search(r"userdetails.php\?id=(\d+)", html_text)
        if user_detail and user_detail.group().strip():
            self._user_detail_page = user_detail.group().strip().lstrip('/')
            self.userid = user_detail.group(1)
            self._torrent_seeding_page = f"getusertorrentlistajax.php?userid={self.userid}&type=seeding"
        else:
            user_detail = re.search(r"(userdetails)", html_text)
            if user_detail and user_detail.group().strip():
                self._user_detail_page = user_detail.group().strip().lstrip('/')
                self.userid = None
                self._torrent_seeding_page = None

    def _parse_message_unread(self, html_text):
        """
        Parses the number of unread messages
        :param html_text:
        :return:
        """
        html = etree.HTML(html_text)
        if not html:
            return

        message_labels = html.xpath('//a[@href="messages.php"]/..')
        message_labels.extend(html.xpath('//a[contains(@href, "messages.php")]/..'))
        if message_labels:
            message_text = message_labels[0].xpath("string(.)")

            logger.debug(f"{self.site_name}  Original message {message_text}")
            message_unread_match = re.findall(r"[^Date]( Message box\s*|\(| You do.\xa0)(\d+)", message_text)

            if message_unread_match and len(message_unread_match[-1]) == 2:
                self.message_unread = StringUtils.str_int(message_unread_match[-1][1])
            elif message_text.isdigit():
                self.message_unread = StringUtils.str_int(message_text)

    def _parse_user_base_info(self, html_text: str):
        #  Merger analysis， Reduce additional request calls
        self._parse_user_traffic_info(html_text)
        self._user_traffic_page = None

        self._parse_message_unread(html_text)

        html = etree.HTML(html_text)
        if not html:
            return

        ret = html.xpath(f'//a[contains(@href, "userdetails") and contains(@href, "{self.userid}")]//b//text()')
        if ret:
            self.username = str(ret[0])
            return
        ret = html.xpath(f'//a[contains(@href, "userdetails") and contains(@href, "{self.userid}")]//text()')
        if ret:
            self.username = str(ret[0])

        ret = html.xpath('//a[contains(@href, "userdetails")]//strong//text()')
        if ret:
            self.username = str(ret[0])
            return

    def _parse_user_traffic_info(self, html_text):
        html_text = self._prepare_html_text(html_text)
        upload_match = re.search(r"[^ Assemble] First (of multiple parts)[ Pass on] Measure word?[:：_<>/a-zA-Z-=\"'\s#;]+([\d,.\s]+[KMGTPI]*B)", html_text,
                                 re.IGNORECASE)
        self.upload = StringUtils.num_filesize(upload_match.group(1).strip()) if upload_match else 0
        download_match = re.search(r"[^ Total subshadow power] Arrive at (a decision, conclusion etc)[ Also] Measure word?[:：_<>/a-zA-Z-=\"'\s#;]+([\d,.\s]+[KMGTPI]*B)", html_text,
                                   re.IGNORECASE)
        self.download = StringUtils.num_filesize(download_match.group(1).strip()) if download_match else 0
        ratio_match = re.search(r" Sharing rate[:：_<>/a-zA-Z-=\"'\s#;]+([\d,.\s]+)", html_text)
        #  Calculation of sharing rate
        calc_ratio = 0.0 if self.download <= 0.0 else round(self.upload / self.download, 3)
        #  Prioritize the use of on-page shares
        self.ratio = StringUtils.str_float(ratio_match.group(1)) if (
                ratio_match and ratio_match.group(1).strip()) else calc_ratio
        leeching_match = re.search(r"(Torrents leeching| Downloading)[\u4E00-\u9FA5\D\s]+(\d+)[\s\S]+<", html_text)
        self.leeching = StringUtils.str_int(leeching_match.group(2)) if leeching_match and leeching_match.group(
            2).strip() else 0
        html = etree.HTML(html_text)
        has_ucoin, self.bonus = self._parse_ucoin(html)
        if has_ucoin:
            return
        tmps = html.xpath('//a[contains(@href,"mybonus")]/text()') if html else None
        if tmps:
            bonus_text = str(tmps[0]).strip()
            bonus_match = re.search(r"([\d,.]+)", bonus_text)
            if bonus_match and bonus_match.group(1).strip():
                self.bonus = StringUtils.str_float(bonus_match.group(1))
                return
        bonus_match = re.search(r"mybonus.[\[\]:：<>/a-zA-Z_\-=\"'\s#;.( Using magic beans]+\s*([\d,.]+)[<()&\s]", html_text)
        try:
            if bonus_match and bonus_match.group(1).strip():
                self.bonus = StringUtils.str_float(bonus_match.group(1))
                return
            bonus_match = re.search(r"[ Magic power level|\]][\[\]:：<>/a-zA-Z_\-=\"'\s#;]+\s*([\d,.]+|\"[\d,.]+\")[<>()&\s]",
                                    html_text,
                                    flags=re.S)
            if bonus_match and bonus_match.group(1).strip():
                self.bonus = StringUtils.str_float(bonus_match.group(1).strip('"'))
        except Exception as err:
            logger.error(f"{self.site_name}  Error resolving magic value,  Error message: {err}")

    @staticmethod
    def _parse_ucoin(html):
        """
        Analyzeucoin,  Uniform conversion to copper coins
        :param html:
        :return:
        """
        if html:
            gold, silver, copper = None, None, None

            golds = html.xpath('//span[@class = "ucoin-symbol ucoin-gold"]//text()')
            if golds:
                gold = StringUtils.str_float(str(golds[-1]))
            silvers = html.xpath('//span[@class = "ucoin-symbol ucoin-silver"]//text()')
            if silvers:
                silver = StringUtils.str_float(str(silvers[-1]))
            coppers = html.xpath('//span[@class = "ucoin-symbol ucoin-copper"]//text()')
            if coppers:
                copper = StringUtils.str_float(str(coppers[-1]))
            if gold or silver or copper:
                gold = gold if gold else 0
                silver = silver if silver else 0
                copper = copper if copper else 0
                return True, gold * 100 * 100 + silver * 100 + copper
        return False, 0.0

    def _parse_user_torrent_seeding_info(self, html_text: str, multi_page: bool = False) -> Optional[str]:
        """
        Seeding information
        :param html_text:
        :param multi_page:  Whether multiple pages of data
        :return:  Next page address
        """
        html = etree.HTML(str(html_text).replace(r'\/', '/'))
        if not html:
            return None

        #  Extended links exist on the home page， Using extended links
        seeding_url_text = html.xpath('//a[contains(@href,"torrents.php") '
                                      'and contains(@href,"seeding")]/@href')
        if multi_page is False and seeding_url_text and seeding_url_text[0].strip():
            self._torrent_seeding_page = seeding_url_text[0].strip()
            return self._torrent_seeding_page

        size_col = 3
        seeders_col = 4
        #  Look for sth.size Columns
        size_col_xpath = '//tr[position()=1]/' \
                         'td[(img[@class="size"] and img[@alt="size"])' \
                         ' or (text() = " Adults and children")' \
                         ' or (a/img[@class="size" and @alt="size"])]'
        if html.xpath(size_col_xpath):
            size_col = len(html.xpath(f'{size_col_xpath}/preceding-sibling::td')) + 1
        #  Look for sth.seeders Columns
        seeders_col_xpath = '//tr[position()=1]/' \
                            'td[(img[@class="seeders"] and img[@alt="seeders"])' \
                            ' or (text() = " Undergoing cultivation")' \
                            ' or (a/img[@class="seeders" and @alt="seeders"])]'
        if html.xpath(seeders_col_xpath):
            seeders_col = len(html.xpath(f'{seeders_col_xpath}/preceding-sibling::td')) + 1

        page_seeding = 0
        page_seeding_size = 0
        page_seeding_info = []
        #  In the event that table class="torrents"， Failing agreementtable[@class="torrents"]
        table_class = '//table[@class="torrents"]' if html.xpath('//table[@class="torrents"]') else ''
        seeding_sizes = html.xpath(f'{table_class}//tr[position()>1]/td[{size_col}]')
        seeding_seeders = html.xpath(f'{table_class}//tr[position()>1]/td[{seeders_col}]/b/a/text()')
        if not seeding_seeders:
            seeding_seeders = html.xpath(f'{table_class}//tr[position()>1]/td[{seeders_col}]//text()')
        if seeding_sizes and seeding_seeders:
            page_seeding = len(seeding_sizes)

            for i in range(0, len(seeding_sizes)):
                size = StringUtils.num_filesize(seeding_sizes[i].xpath("string(.)").strip())
                seeders = StringUtils.str_int(seeding_seeders[i])

                page_seeding_size += size
                page_seeding_info.append([seeders, size])

        self.seeding += page_seeding
        self.seeding_size += page_seeding_size
        self.seeding_info.extend(page_seeding_info)

        #  Existence of next page data
        next_page = None
        next_page_text = html.xpath('//a[contains(.//text(), " Next page") or contains(.//text(), " Next page")]/@href')
        if next_page_text:
            next_page = next_page_text[-1].strip()
            # fix up page url
            if self.userid not in next_page:
                next_page = f'{next_page}&userid={self.userid}&type=seeding'

        return next_page

    def _parse_user_detail_info(self, html_text: str):
        """
        Parsing additional user information， Joining time， Hierarchy
        :param html_text:
        :return:
        """
        html = etree.HTML(html_text)
        if not html:
            return

        self._get_user_level(html)

        self._fixup_traffic_info(html)

        #  Date of accession
        join_at_text = html.xpath(
            '//tr/td[text()=" Date of accession" or text()=" Registration date" or *[text()=" Date of accession"]]/following-sibling::td[1]//text()'
            '|//div/b[text()=" Date of accession"]/../text()')
        if join_at_text:
            self.join_at = StringUtils.unify_datetime_str(join_at_text[0].split(' (')[0].strip())

        #  Seeding volume &  Determinant (math.)
        # seeding  If you can't get the page， Get it again here
        seeding_sizes = html.xpath('//tr/td[text()=" Current upload"]/following-sibling::td[1]//'
                                   'table[tr[1][td[4 and text()=" Sizes"]]]//tr[position()>1]/td[4]')
        seeding_seeders = html.xpath('//tr/td[text()=" Current upload"]/following-sibling::td[1]//'
                                     'table[tr[1][td[5 and text()=" Breeder"]]]//tr[position()>1]/td[5]//text()')
        tmp_seeding = len(seeding_sizes)
        tmp_seeding_size = 0
        tmp_seeding_info = []
        for i in range(0, len(seeding_sizes)):
            size = StringUtils.num_filesize(seeding_sizes[i].xpath("string(.)").strip())
            seeders = StringUtils.str_int(seeding_seeders[i])

            tmp_seeding_size += size
            tmp_seeding_info.append([seeders, size])

        if not self.seeding_size:
            self.seeding_size = tmp_seeding_size
        if not self.seeding:
            self.seeding = tmp_seeding
        if not self.seeding_info:
            self.seeding_info = tmp_seeding_info

        seeding_sizes = html.xpath('//tr/td[text()=" Do seed counts"]/following-sibling::td[1]//text()')
        if seeding_sizes:
            seeding_match = re.search(r" Total number of species:\s+(\d+)", seeding_sizes[0], re.IGNORECASE)
            seeding_size_match = re.search(r" Total seeding volume:\s+([\d,.\s]+[KMGTPI]*B)", seeding_sizes[0], re.IGNORECASE)
            tmp_seeding = StringUtils.str_int(seeding_match.group(1)) if (
                    seeding_match and seeding_match.group(1)) else 0
            tmp_seeding_size = StringUtils.num_filesize(
                seeding_size_match.group(1).strip()) if seeding_size_match else 0
        if not self.seeding_size:
            self.seeding_size = tmp_seeding_size
        if not self.seeding:
            self.seeding = tmp_seeding

        self._fixup_torrent_seeding_page(html)

    def _fixup_torrent_seeding_page(self, html):
        """
        Fix the link to the seed page
        :param html:
        :return:
        """
        #  Separate seed page
        seeding_url_text = html.xpath('//a[contains(@href,"getusertorrentlist.php") '
                                      'and contains(@href,"seeding")]/@href')
        if seeding_url_text:
            self._torrent_seeding_page = seeding_url_text[0].strip()
        #  Through (a gap)JS The call kind of gets the userID
        seeding_url_text = html.xpath('//a[contains(@href, "javascript: getusertorrentlistajax") '
                                      'and contains(@href,"seeding")]/@href')
        csrf_text = html.xpath('//meta[@name="x-csrf"]/@content')
        if not self._torrent_seeding_page and seeding_url_text:
            user_js = re.search(r"javascript: getusertorrentlistajax\(\s*'(\d+)", seeding_url_text[0])
            if user_js and user_js.group(1).strip():
                self.userid = user_js.group(1).strip()
                self._torrent_seeding_page = f"getusertorrentlistajax.php?userid={self.userid}&type=seeding"
        elif seeding_url_text and csrf_text:
            if csrf_text[0].strip():
                self._torrent_seeding_page \
                    = f"ajax_getusertorrentlist.php"
                self._torrent_seeding_params = {'userid': self.userid, 'type': 'seeding', 'csrf': csrf_text[0].strip()}

        #  Assortment
        #  Temporary shielding
        # seeding_url_text = html.xpath('//tr/td[text()=" Current crop"]/following-sibling::td[1]'
        #                              '/table//td/a[contains(@href,"seeding")]/@href')
        # if seeding_url_text:
        #    self._torrent_seeding_page = seeding_url_text

    def _get_user_level(self, html):
        #  Hierarchy  Getting the same row level data， Image format levels， Gettitle Text， Otherwise take a text message
        user_levels_text = html.xpath('//tr/td[text()=" Grade" or text()=" Hierarchy" or *[text()=" Hierarchy"]]/'
                                      'following-sibling::td[1]/img[1]/@title')
        if user_levels_text:
            self.user_level = user_levels_text[0].strip()
            return

        user_levels_text = html.xpath('//tr/td[text()=" Grade" or text()=" Hierarchy"]/'
                                      'following-sibling::td[1 and not(img)]'
                                      '|//tr/td[text()=" Grade" or text()=" Hierarchy"]/'
                                      'following-sibling::td[1 and img[not(@title)]]')
        if user_levels_text:
            self.user_level = user_levels_text[0].xpath("string(.)").strip()
            return

        user_levels_text = html.xpath('//tr/td[text()=" Grade" or text()=" Hierarchy"]/'
                                      'following-sibling::td[1]')
        if user_levels_text:
            self.user_level = user_levels_text[0].xpath("string(.)").strip()
            return

        user_levels_text = html.xpath('//a[contains(@href, "userdetails")]/text()')
        if not self.user_level and user_levels_text:
            for user_level_text in user_levels_text:
                user_level_match = re.search(r"\[(.*)]", user_level_text)
                if user_level_match and user_level_match.group(1).strip():
                    self.user_level = user_level_match.group(1).strip()
                    break

    def _parse_message_unread_links(self, html_text: str, msg_links: list) -> Optional[str]:
        html = etree.HTML(html_text)
        if not html:
            return None

        message_links = html.xpath('//tr[not(./td/img[@alt="Read"])]/td/a[contains(@href, "viewmessage")]/@href')
        msg_links.extend(message_links)
        #  Existence of next page data
        next_page = None
        next_page_text = html.xpath('//a[contains(.//text(), " Next page") or contains(.//text(), " Next page")]/@href')
        if next_page_text:
            next_page = next_page_text[-1].strip()

        return next_page

    def _parse_message_content(self, html_text):
        html = etree.HTML(html_text)
        if not html:
            return None, None, None
        #  Caption
        message_head_text = None
        message_head = html.xpath('//h1/text()'
                                  '|//div[@class="layui-card-header"]/span[1]/text()')
        if message_head:
            message_head_text = message_head[-1].strip()

        #  News time
        message_date_text = None
        message_date = html.xpath('//h1/following-sibling::table[.//tr/td[@class="colhead"]]//tr[2]/td[2]'
                                  '|//div[@class="layui-card-header"]/span[2]/span[2]')
        if message_date:
            message_date_text = message_date[0].xpath("string(.)").strip()

        #  Message
        message_content_text = None
        message_content = html.xpath('//h1/following-sibling::table[.//tr/td[@class="colhead"]]//tr[3]/td'
                                     '|//div[contains(@class,"layui-card-body")]')
        if message_content:
            message_content_text = message_content[0].xpath("string(.)").strip()

        return message_head_text, message_date_text, message_content_text

    def _fixup_traffic_info(self, html):
        # fixup bonus
        if not self.bonus:
            bonus_text = html.xpath('//tr/td[text()=" Magic power level" or text()=" Cat food"]/following-sibling::td[1]/text()')
            if bonus_text:
                self.bonus = StringUtils.str_float(bonus_text[0].strip())
