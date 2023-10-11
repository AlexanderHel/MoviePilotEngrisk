# -*- coding: utf-8 -*-
import re
from typing import Optional

from lxml import etree

from app.plugins.sitestatistic.siteuserinfo import ISiteUserInfo, SITE_BASE_ORDER, SiteSchema
from app.utils.string import StringUtils


class GazelleSiteUserInfo(ISiteUserInfo):
    schema = SiteSchema.Gazelle
    order = SITE_BASE_ORDER

    @classmethod
    def match(cls, html_text: str) -> bool:
        html = etree.HTML(html_text)
        if not html:
            return False

        printable_text = html.xpath("string(.)") if html else ""

        return "Powered by Gazelle" in printable_text or "DIC Music" in printable_text

    def _parse_user_base_info(self, html_text: str):
        html_text = self._prepare_html_text(html_text)
        html = etree.HTML(html_text)

        tmps = html.xpath('//a[contains(@href, "user.php?id=")]')
        if tmps:
            user_id_match = re.search(r"user.php\?id=(\d+)", tmps[0].attrib['href'])
            if user_id_match and user_id_match.group().strip():
                self.userid = user_id_match.group(1)
                self._torrent_seeding_page = f"torrents.php?type=seeding&userid={self.userid}"
                self._user_detail_page = f"user.php?id={self.userid}"
                self.username = tmps[0].text.strip()

        tmps = html.xpath('//*[@id="header-uploaded-value"]/@data-value')
        if tmps:
            self.upload = StringUtils.num_filesize(tmps[0])
        else:
            tmps = html.xpath('//li[@id="stats_seeding"]/span/text()')
            if tmps:
                self.upload = StringUtils.num_filesize(tmps[0])

        tmps = html.xpath('//*[@id="header-downloaded-value"]/@data-value')
        if tmps:
            self.download = StringUtils.num_filesize(tmps[0])
        else:
            tmps = html.xpath('//li[@id="stats_leeching"]/span/text()')
            if tmps:
                self.download = StringUtils.num_filesize(tmps[0])

        self.ratio = 0.0 if self.download <= 0.0 else round(self.upload / self.download, 3)

        tmps = html.xpath('//a[contains(@href, "bonus.php")]/@data-tooltip')
        if tmps:
            bonus_match = re.search(r"([\d,.]+)", tmps[0])
            if bonus_match and bonus_match.group(1).strip():
                self.bonus = StringUtils.str_float(bonus_match.group(1))
        else:
            tmps = html.xpath('//a[contains(@href, "bonus.php")]')
            if tmps:
                bonus_text = tmps[0].xpath("string(.)")
                bonus_match = re.search(r"([\d,.]+)", bonus_text)
                if bonus_match and bonus_match.group(1).strip():
                    self.bonus = StringUtils.str_float(bonus_match.group(1))

    def _parse_site_page(self, html_text: str):
        # TODO
        pass

    def _parse_user_detail_info(self, html_text: str):
        """
        Parsing additional user information， Joining time， Hierarchy
        :param html_text:
        :return:
        """
        html = etree.HTML(html_text)
        if not html:
            return None

        #  User level
        user_levels_text = html.xpath('//*[@id="class-value"]/@data-value')
        if user_levels_text:
            self.user_level = user_levels_text[0].strip()
        else:
            user_levels_text = html.xpath('//li[contains(text(), " User level")]/text()')
            if user_levels_text:
                self.user_level = user_levels_text[0].split(':')[1].strip()

        #  Date of accession
        join_at_text = html.xpath('//*[@id="join-date-value"]/@data-value')
        if join_at_text:
            self.join_at = StringUtils.unify_datetime_str(join_at_text[0].strip())
        else:
            join_at_text = html.xpath(
                '//div[contains(@class, "box_userinfo_stats")]//li[contains(text(), " Joining time")]/span/text()')
            if join_at_text:
                self.join_at = StringUtils.unify_datetime_str(join_at_text[0].strip())

    def _parse_user_torrent_seeding_info(self, html_text: str, multi_page: bool = False) -> Optional[str]:
        """
        Seeding information
        :param html_text:
        :param multi_page:  Whether multiple pages of data
        :return:  Next page address
        """
        html = etree.HTML(html_text)
        if not html:
            return None

        size_col = 3
        #  Look for sth.size Columns
        if html.xpath('//table[contains(@id, "torrent")]//tr[1]/td'):
            size_col = len(html.xpath('//table[contains(@id, "torrent")]//tr[1]/td')) - 3
        #  Look for sth.seeders Columns
        seeders_col = size_col + 2

        page_seeding = 0
        page_seeding_size = 0
        page_seeding_info = []
        seeding_sizes = html.xpath(f'//table[contains(@id, "torrent")]//tr[position()>1]/td[{size_col}]')
        seeding_seeders = html.xpath(f'//table[contains(@id, "torrent")]//tr[position()>1]/td[{seeders_col}]/text()')
        if seeding_sizes and seeding_seeders:
            page_seeding = len(seeding_sizes)

            for i in range(0, len(seeding_sizes)):
                size = StringUtils.num_filesize(seeding_sizes[i].xpath("string(.)").strip())
                seeders = int(seeding_seeders[i])

                page_seeding_size += size
                page_seeding_info.append([seeders, size])

        if multi_page:
            self.seeding += page_seeding
            self.seeding_size += page_seeding_size
            self.seeding_info.extend(page_seeding_info)
        else:
            if not self.seeding:
                self.seeding = page_seeding
            if not self.seeding_size:
                self.seeding_size = page_seeding_size
            if not self.seeding_info:
                self.seeding_info = page_seeding_info

        #  Existence of next page data
        next_page = None
        next_page_text = html.xpath('//a[contains(.//text(), "Next") or contains(.//text(), " Next page")]/@href')
        if next_page_text:
            next_page = next_page_text[-1].strip()

        return next_page

    def _parse_user_traffic_info(self, html_text: str):
        # TODO
        pass

    def _parse_message_unread_links(self, html_text: str, msg_links: list) -> Optional[str]:
        return None

    def _parse_message_content(self, html_text):
        return None, None, None
