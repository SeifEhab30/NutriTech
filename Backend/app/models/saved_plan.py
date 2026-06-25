from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.database import Base


class SavedPlan(Base):
    """The user's most recently generated meal plan (one per user)."""
    __tablename__ = "saved_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_json = Column(Text, nullable=False)  # full /plan/daily response object
    weekly_json = Column(Text, nullable=True)  # full /plan/weekly response object
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
