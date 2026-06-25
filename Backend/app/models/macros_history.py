from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class MacrosHistory(Base):
    __tablename__ = "macros_history"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    calories = Column(Integer)
    protein = Column(Integer)
    carbs = Column(Integer)
    fats = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")