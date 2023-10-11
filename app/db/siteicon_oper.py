from typing import List

from app.db import DbOper
from app.db.models.siteicon import SiteIcon


class SiteIconOper(DbOper):
    """
    Site management
    """

    def list(self) -> List[SiteIcon]:
        """
        Get a list of site icons
        """
        return SiteIcon.list(self._db)

    def get_by_domain(self, domain: str) -> SiteIcon:
        """
        Get site icons by domain
        """
        return SiteIcon.get_by_domain(self._db, domain)

    def update_icon(self, name: str, domain: str, icon_url: str, icon_base64: str) -> bool:
        """
        Updated site icon
        """
        icon_base64 = f"data:image/ico;base64,{icon_base64}" if icon_base64 else ""
        siteicon = SiteIcon(name=name, domain=domain, url=icon_url, base64=icon_base64)
        if not self.get_by_domain(domain):
            siteicon.create(self._db)
        elif icon_base64:
            siteicon.update(self._db, {
                "url": icon_url,
                "base64": icon_base64
            })
        return True
