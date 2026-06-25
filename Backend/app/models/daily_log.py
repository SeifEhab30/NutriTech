from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class DailyLog(Base):
    """One logged food/intake entry for a user on a given calendar day.

    `date` is a 'YYYY-MM-DD' string (the user's local day) so SQLite range
    filtering stays simple and free of timezone drift for this single-user app.
    """
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # 'YYYY-MM-DD'

    name = Column(String(120), nullable=False)
    grams = Column(Float, nullable=True)
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    source = Column(String(20), default="manual")  # plan | search | manual

    created_at = Column(DateTime, server_default=func.now())
