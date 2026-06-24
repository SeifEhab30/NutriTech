# =====================================================
# NutriTech v2 - Pipeline Orchestrator
# user -> goal -> calorie target -> scored foods -> plan
# =====================================================

from typing import Any, Dict, Optional

from app.nutritech.models.goal import map_to_final_goal, predict_general_goal
from app.nutritech.models.user import build_user_profile, calc_daily_calorie_target
from app.nutritech.services.data_loader import get_food_store
from app.nutritech.services.planner import build_daily_plan
from app.nutritech.services.scoring import score_candidates

# Min main-dish (protein anchor) candidates needed to build sensible meals.
_MIN_MAINS = 3


def full_pipeline(payload: Dict[str, Any], seed: Optional[int] = None) -> Dict[str, Any]:
    store = get_food_store()

    # 1) profile
    user = build_user_profile(payload)

    # 2) general goal (rule-based when 'auto') -> final goal
    general = (
        predict_general_goal(user)
        if user["general_goal_user"] == "auto"
        else user["general_goal_user"]
    )
    final_goal = map_to_final_goal(general, user["diet_type_user"])
    diabetes = bool(user["diabetes"])

    # 3) calorie + macro targets (diabetes flag overrides macros)
    info = calc_daily_calorie_target(user, final_goal, diabetes=diabetes)

    # 4) score eligible foods (apply health flags + exclusions)
    candidates = score_candidates(
        store.df,
        final_goal,
        cuisine_pref=user["cuisine_pref"],
        dislikes=user["dislikes"],
        allergies=user["allergies"],
        hypertension=bool(user["hypertension"]),
        diabetes=diabetes,
    )

    # 4b) pool-starvation guard. The planner fills around thin side roles, but
    # it needs a non-empty pool and some main-dish (protein) anchors.
    if candidates is None or candidates.empty:
        raise ValueError(
            "Your restrictions and allergies leave no foods to plan with. "
            "Please relax a restriction or remove an allergy."
        )
    n_mains = int((candidates["role"] == "main").sum())
    if n_mains < _MIN_MAINS:
        raise ValueError(
            "Your restrictions and allergies leave too few main-dish foods "
            "(protein sources) to build meals. Please relax a restriction or "
            "remove an allergy."
        )

    # 5) compose the daily plan with the portion solver
    daily_plan = build_daily_plan(
        candidates,
        meals_per_day=user["meals_per_day"],
        snacks_per_day=user["snacks_per_day"],
        daily_calories=float(info["target_calories"]),
        final_goal=final_goal,
        macro_targets=(
            float(info["target_protein"]),
            float(info["target_carbs"]),
            float(info["target_fat"]),
        ),
        seed=seed,
    )

    return {
        "general_goal": general,
        "final_goal_used": final_goal,
        "daily_calories": float(info["target_calories"]),
        "daily_protein": info["target_protein"],
        "daily_carbs": info["target_carbs"],
        "daily_fat": info["target_fat"],
        "calorie_info": info,
        "daily_plan": daily_plan,
        "user_profile": user,
    }
