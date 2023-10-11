import xml.dom.minidom
from typing import List, Tuple, Union
from urllib.parse import urljoin

from lxml import etree

from app.core.config import settings
from app.helper.browser import PlaywrightHelper
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class RssHelper:
    """
    RSS Help class， AnalyzeRSS Telegram、 GainRSS Address, etc.
    """
    #  StationsRSS Link to get configuration
    rss_link_conf = {
        "default": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
            }
        },
        "hares.top": {
            "xpath": "//*[@id='layui-layer100001']/div[2]/div/p[4]/a/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
            }
        },
        "et8.org": {
            "xpath": "//*[@id='outer']/table/tbody/tr/td/table/tbody/tr/td/a[2]/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
            }
        },
        "pttime.org": {
            "xpath": "//*[@id='outer']/table/tbody/tr/td/table/tbody/tr/td/text()[5]",
            "url": "getrss.php",
            "params": {
                "showrows": 10,
                "inclbookmarked": 0,
                "itemsmalldescr": 1
            }
        },
        "ourbits.club": {
            "xpath": "//a[@class='gen_rsslink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
            }
        },
        "totheglory.im": {
            "xpath": "//textarea/text()",
            "url": "rsstools.php?c51=51&c52=52&c53=53&c54=54&c108=108&c109=109&c62=62&c63=63&c67=67&c69=69&c70=70&c73=73&c76=76&c75=75&c74=74&c87=87&c88=88&c99=99&c90=90&c58=58&c103=103&c101=101&c60=60",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
            }
        },
        "monikadesign.uk": {
            "xpath": "//a/@href",
            "url": "rss",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
            }
        },
        "zhuque.in": {
            "xpath": "//a/@href",
            "url": "user/rss",
            "render": True,
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
            }
        },
        "hdchina.org": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
                "rsscart": 0
            }
        },
        "audiences.me": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
                "torrent_type": 1,
                "exp": 180
            }
        },
        "shadowflow.org": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "paid": 0,
                "search_mode": 0,
                "showrows": 30
            }
        },
        "hddolby.com": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
                "exp": 180
            }
        },
        "hdhome.org": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
                "exp": 180
            }
        },
        "pthome.net": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
                "exp": 180
            }
        },
        "ptsbao.club": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
                "size": 0
            }
        },
        "leaves.red": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 0,
                "paid": 2
            }
        },
        "hdtime.org": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 0,
            }
        },
        "m-team.io": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "showrows": 50,
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "https": 1
            }
        },
        "u2.dmhy.org": {
            "xpath": "//a[@class='faqlink']/@href",
            "url": "getrss.php",
            "params": {
                "inclbookmarked": 0,
                "itemsmalldescr": 1,
                "showrows": 50,
                "search_mode": 1,
                "inclautochecked": 1,
                "trackerssl": 1
            }
        },
    }

    @staticmethod
    def parse(url, proxy: bool = False) -> Union[List[dict], None]:
        """
        AnalyzeRSS Subscribe toURL， GainRSS Seed information in
        :param url: RSS Address
        :param proxy:  Whether to use a proxy
        :return:  Seed information list， IfNone In the name ofRss Expire (as in expiration date)
        """
        #  Commencement of processing
        ret_array: list = []
        if not url:
            return []
        try:
            ret = RequestUtils(proxies=settings.PROXY if proxy else None).get_res(url)
            if not ret:
                return []
            ret.encoding = ret.apparent_encoding
        except Exception as err:
            print(str(err))
            return []
        if ret:
            ret_xml = ret.text
            try:
                #  AnalyzeXML
                dom_tree = xml.dom.minidom.parseString(ret_xml)
                rootNode = dom_tree.documentElement
                items = rootNode.getElementsByTagName("item")
                for item in items:
                    try:
                        #  Caption
                        title = DomUtils.tag_value(item, "title", default="")
                        if not title:
                            continue
                        #  Descriptive
                        description = DomUtils.tag_value(item, "description", default="")
                        #  Seed page
                        link = DomUtils.tag_value(item, "link", default="")
                        #  Seed links
                        enclosure = DomUtils.tag_value(item, "enclosure", "url", default="")
                        if not enclosure and not link:
                            continue
                        #  PortionRSS Only iflink Hasn'tenclosure
                        if not enclosure and link:
                            enclosure = link
                        #  Adults and children
                        size = DomUtils.tag_value(item, "enclosure", "length", default=0)
                        if size and str(size).isdigit():
                            size = int(size)
                        else:
                            size = 0
                        #  Release date
                        pubdate = DomUtils.tag_value(item, "pubDate", default="")
                        if pubdate:
                            #  Convert to time
                            pubdate = StringUtils.get_time(pubdate)
                        #  Return object
                        tmp_dict = {'title': title,
                                    'enclosure': enclosure,
                                    'size': size,
                                    'description': description,
                                    'link': link,
                                    'pubdate': pubdate}
                        ret_array.append(tmp_dict)
                    except Exception as e1:
                        print(str(e1))
                        continue
            except Exception as e2:
                print(str(e2))
                # RSS Expire (as in expiration date)  Visitors (an exhibition etc)RSS  Link has expired， You need to get a new！  pthome RSS Link has expired, You need to get a new one!
                _rss_expired_msg = [
                    "RSS  Link has expired,  You need to get a new!",
                    "RSS Link has expired, You need to get a new one!",
                    "RSS Link has expired, You need to get new!"
                ]
                if ret_xml in _rss_expired_msg:
                    return None
        return ret_array

    def get_rss_link(self, url: str, cookie: str, ua: str, proxy: bool = False) -> Tuple[str, str]:
        """
        Get siterss Address
        :param url:  Site address
        :param cookie:  Websitecookie
        :param ua:  Websiteua
        :param proxy:  Whether to use a proxy
        :return: rss Address、 Error message
        """
        try:
            #  Get site domain name
            domain = StringUtils.get_url_domain(url)
            #  Get configuration
            site_conf = self.rss_link_conf.get(domain) or self.rss_link_conf.get("default")
            # RSS Address
            rss_url = urljoin(url, site_conf.get("url"))
            # RSS Request parameters
            rss_params = site_conf.get("params")
            #  RequestingRSS Web page
            if site_conf.get("render"):
                html_text = PlaywrightHelper().get_page_source(
                    url=rss_url,
                    cookies=cookie,
                    ua=ua,
                    proxies=settings.PROXY if proxy else None
                )
            else:
                res = RequestUtils(
                    cookies=cookie,
                    timeout=60,
                    ua=ua,
                    proxies=settings.PROXY if proxy else None
                ).post_res(url=rss_url, data=rss_params)
                if res:
                    html_text = res.text
                elif res is not None:
                    return "", f" Gain {url} RSS Link failure， Error code：{res.status_code}， Cause of error：{res.reason}"
                else:
                    return "", f" GainRSS Link failure： Connectionless {url} "
            #  AnalyzeHTML
            html = etree.HTML(html_text)
            if html:
                rss_link = html.xpath(site_conf.get("xpath"))
                if rss_link:
                    return str(rss_link[-1]), ""
            return "", f" GainRSS Link failure：{url}"
        except Exception as e:
            return "", f" Gain {url} RSS Link failure：{str(e)}"
