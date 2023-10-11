from typing import Optional

from app.utils.http import RequestUtils


class WebUtils:

    @staticmethod
    def get_location(ip: str):
        """
        Consult (a document etc)IP Belonging to
        """
        return WebUtils.get_location1(ip) or WebUtils.get_location2(ip)

    @staticmethod
    def get_location1(ip: str):
        """
        https://api.mir6.com/api/ip
        {
            "code": 200,
            "msg": "success",
            "data": {
                "ip": "240e:97c:2f:1::5c",
                "dec": "47925092370311863177116789888333643868",
                "country": " Sino",
                "countryCode": "CN",
                "province": " Guangdong province",
                "city": " Guangzhou subprovincial city and capital of guangdong",
                "districts": "",
                "idc": "",
                "isp": " China telecom (chinese company providing mobile phone service)",
                "net": " Data center",
                "zipcode": "510000",
                "areacode": "020",
                "protocol": "IPv6",
                "location": " Sino[CN]  Guangdong province  Guangzhou subprovincial city and capital of guangdong",
                "myip": "125.89.7.89",
                "time": "2023-09-01 17:28:23"
            }
        }
        """
        try:
            r = RequestUtils().get_res(f"https://api.mir6.com/api/ip?ip={ip}&type=json")
            if r:
                return r.json().get("data", {}).get("location") or ''
        except Exception as err:
            print(str(err))
            return ""

    @staticmethod
    def get_location2(ip: str):
        """
        https://whois.pconline.com.cn/ipJson.jsp?json=true&ip=
        {
          "ip": "122.8.12.22",
          "pro": " Shanghai",
          "proCode": "310000",
          "city": " Shanghai",
          "cityCode": "310000",
          "region": "",
          "regionCode": "0",
          "addr": " Shanghai  Tietong",
          "regionNames": "",
          "err": ""
        }
        """
        try:
            r = RequestUtils().get_res(f"https://whois.pconline.com.cn/ipJson.jsp?json=true&ip={ip}")
            if r:
                return r.json().get("addr") or ''
        except Exception as err:
            print(str(err))
            return ""

    @staticmethod
    def get_bing_wallpaper() -> Optional[str]:
        """
        GainBing Daily wallpaper
        """
        url = "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1"
        resp = RequestUtils(timeout=5).get_res(url)
        if resp and resp.status_code == 200:
            try:
                result = resp.json()
                if isinstance(result, dict):
                    for image in result.get('images') or []:
                        return f"https://cn.bing.com{image.get('url')}" if 'url' in image else ''
            except Exception as err:
                print(str(err))
        return None
