from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.profile import (
    UserProfileCreate,
    UserProfileUpdate,
    UserProfile as UserProfileSchema
)
from app.core.security import get_current_user

router = APIRouter(prefix="/profile", tags=["Profile"])


def calculate_daily_needs(profile: UserProfile):
    """
    Calculate BMR, calories, and macros based on user profile
    """

    age = profile.age
    height = profile.height
    weight = profile.weight
    gender = profile.gender
    activity = profile.activity_level
    goal = str(profile.general_goal or "").lower()
    diet = profile.diet_type
    diabetes = bool(profile.diabetes)

    # 🔥 BMR (Mifflin–St Jeor) — aligned with the meal-planner engine
    # (app/nutritech/models/user.py) and the Macros Calculator so the calorie
    # target is identical across Profile, Tracker, Macros Calculator and Planner.
    if gender == "male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    activity_multipliers = {
        "sedentary": 1.2,
        "moderate": 1.55,
        "active": 1.725,
    }

    calories = bmr * activity_multipliers.get(activity, 1.55)

    # Calories from the weight goal (canonical vocab + aliases)
    if goal in ("weight_loss", "lose_weight"):
        calories -= 500
    elif goal in ("weight_gain", "muscle_gain", "gain_weight"):
        calories += 350

    # Clamp to the same safe range as the planner engine so the two never
    # diverge even at extreme inputs (floor 1500 male / 1200 female, ceiling 4500).
    floor = 1500 if gender == "male" else 1200
    calories = max(floor, min(4500, calories))

    # 🔥 Macros — diabetes flag overrides the diet ratios
    if diabetes:
        protein = calories * 0.25 / 4
        carbs = calories * 0.40 / 4
        fats = calories * 0.35 / 9

    elif diet == "keto":
        protein = calories * 0.25 / 4
        carbs = calories * 0.05 / 4
        fats = calories * 0.7 / 9

    elif diet == "high_protein":
        protein = calories * 0.35 / 4
        carbs = calories * 0.35 / 4
        fats = calories * 0.3 / 9

    else:  # balanced
        protein = calories * 0.2 / 4
        carbs = calories * 0.5 / 4
        fats = calories * 0.3 / 9

    return {
        "calories": round(calories),
        "protein": round(protein),
        "carbs": round(carbs),
        "fats": round(fats),
    }


@router.get("/me", response_model=UserProfileSchema)
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return current_user.profile


@router.get("/needs")
def get_my_needs(current_user: User = Depends(get_current_user)):
    """Daily macro targets for the saved profile (read-only, no side effects)."""
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return calculate_daily_needs(current_user.profile)


@router.put("/me")
def update_my_profile(
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    profile = current_user.profile

    def _join(v):
        # checklist/allergy fields arrive as a list; persist as a comma string
        if isinstance(v, (list, tuple)):
            return ",".join(str(x).strip() for x in v if str(x).strip())
        return v

    if not profile:
        payload = data.dict()
        payload["dislikes"] = _join(payload.get("dislikes")) or ""
        payload["allergies"] = _join(payload.get("allergies")) or ""
        profile = UserProfile(**payload, user_id=current_user.id)
        db.add(profile)
    else:
        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            if key in ("dislikes", "allergies"):
                value = _join(value) or ""
            setattr(profile, key, value)

    db.commit()
    db.refresh(profile)

    # 🔥 نحسب الماكروز بعد التحديث
    daily_needs = calculate_daily_needs(profile)

    return {
        "profile": profile,
        "daily_needs": daily_needs
    }