from sqlalchemy import Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.db.models import Base


class SystemConfig(Base):
    """
    Configuration table
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  Primary key
    key = Column(String, index=True)
    #  (be) worth
    value = Column(String, nullable=True)

    @staticmethod
    def get_by_key(db: Session, key: str):
        return db.query(SystemConfig).filter(SystemConfig.key == key).first()

    def delete_by_key(self, db: Session, key: str):
        systemconfig = self.get_by_key(db, key)
        if systemconfig:
            systemconfig.delete(db, systemconfig.id)
        return True
