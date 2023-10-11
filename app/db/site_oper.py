from typing import Tuple, List

from app.db import DbOper
from app.db.models.site import Site


class SiteOper(DbOper):
    """
    Site management
    """

    def add(self, **kwargs) -> Tuple[bool, str]:
        """
        New sites
        """
        site = Site(**kwargs)
        if not site.get_by_domain(self._db, kwargs.get("domain")):
            site.create(self._db)
            return True, "New sites成功"
        return False, " Site already exists"

    def get(self, sid: int) -> Site:
        """
        Querying a single site
        """
        return Site.get(self._db, sid)

    def list(self) -> List[Site]:
        """
        Get site list
        """
        return Site.list(self._db)

    def list_active(self) -> List[Site]:
        """
        按状态Get site list
        """
        return Site.get_actives(self._db)

    def delete(self, sid: int):
        """
        Delete site
        """
        Site.delete(self._db, sid)

    def update(self, sid: int, payload: dict) -> Site:
        """
        Updating the site
        """
        site = Site.get(self._db, sid)
        site.update(self._db, payload)
        return site

    def get_by_domain(self, domain: str) -> Site:
        """
        Get sites by domain name
        """
        return Site.get_by_domain(self._db, domain)

    def exists(self, domain: str) -> bool:
        """
        Determine if a site exists
        """
        return Site.get_by_domain(self._db, domain) is not None

    def update_cookie(self, domain: str, cookies: str) -> Tuple[bool, str]:
        """
        Updating the siteCookie
        """
        site = Site.get_by_domain(self._db, domain)
        if not site:
            return False, " Site does not exist"
        site.update(self._db, {
            "cookie": cookies
        })
        return True, "Updating the siteCookie成功"

    def update_rss(self, domain: str, rss: str) -> Tuple[bool, str]:
        """
        Updating the siterss
        """
        site = Site.get_by_domain(self._db, domain)
        if not site:
            return False, " Site does not exist"
        site.update(self._db, {
            "rss": rss
        })
        return True, "Updating the siteRSS地址成功"
