from sqlalchemy import Boolean, Column, Integer, String, Sequence
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.models import Base


class User(Base):
    """
    User interface
    """
    # ID
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    #  User id
    name = Column(String, index=True, nullable=False)
    #  Inbox， Not yet activated
    email = Column(String)
    #  Encrypted password
    hashed_password = Column(String)
    #  Enable or disable
    is_active = Column(Boolean(), default=True)
    #  Administrator or not
    is_superuser = Column(Boolean(), default=False)
    #  Avatar
    avatar = Column(String)

    @staticmethod
    def authenticate(db: Session, name: str, password: str):
        user = db.query(User).filter(User.name == name).first()
        if not user:
            return None
        if not verify_password(password, str(user.hashed_password)):
            return None
        return user

    @staticmethod
    def get_by_name(db: Session, name: str):
        return db.query(User).filter(User.name == name).first()

    def delete_by_name(self, db: Session, name: str):
        user = self.get_by_name(db, name)
        if user:
            user.delete(db, user.id)
        return True
