from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    nationality = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False, nullable=False)

    profile = relationship("UserProfile", back_populates="user", uselist=False,
                           cascade="all, delete-orphan", passive_deletes=True)
    # macros_history = relationship("MacrosHistory", back_populates="user")
