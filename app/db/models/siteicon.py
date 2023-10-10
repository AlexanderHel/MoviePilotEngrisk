from sqlalchemy import Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.db.models import Base


class SiteIcon(Base):
    """
    Site icon table
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Site name
    name = Column(String, nullable=False)
    #  Domain nameKey
    domain = Column(String, index=True)
    #  Icon address
    url = Column(String, nullable=False)
    #  Icon (computing)Base64
    base64 = Column(String)

    @staticmethod
    def get_by_domain(db: Session, domain: str):
        return db.query(SiteIcon).filter(SiteIcon.domain == domain).first()
