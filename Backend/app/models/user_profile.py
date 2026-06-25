from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    age = Column(Integer)
    gender = Column(String(50))
    height = Column(Float)
    weight = Column(Float)
    activity_level = Column(String(100))
    general_goal = Column(String(100))
    diet_type = Column(String(100))

    # Health flags + preferences (drive the meal planner's filters)
    diabetes = Column(Boolean, default=False)
    hypertension = Column(Boolean, default=False)
    cuisine_pref = Column(String(50), default="any")
    dislikes = Column(Text, default="")    # comma-separated restriction tokens
    allergies = Column(Text, default="")   # comma-separated allergen tokens

    # One-to-One FK
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Reverse relationship
    user = relationship("User", back_populates="profile")