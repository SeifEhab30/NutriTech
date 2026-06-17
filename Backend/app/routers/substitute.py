# =====================================================
# NutriTech - Substitute Route
# POST /substitute/          -> swap a food (top match or a chosen one)
# POST /substitute/options   -> list candidate swaps to choose from
# =====================================================

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.nutritech.services.data_loader import get_food_store
from app.nutritech.services.knn_substitute import (
    apply_named_substitute,
    get_substitute_options,
    replace_disliked_in_daily_plan,
)

router = APIRouter(prefix="/substitute", tags=["Meal Substitution"])


def _split(s: Optional[str]) -> List[str]:
    if not s:
        return []
    return [t.strip() for t in str(s).split(",") if t.strip()]


def _exclusions(user: User, req_dislikes: Optional[List[str]]) -> Dict[str, List[str]]:
    """Profile allergies + (profile ∪ request) dislikes — so swaps never offer a
    food the user is allergic to or has excluded, even if the client omits them."""
    profile = getattr(user, "profile", None)
    dislikes = set(_split(getattr(profile, "dislikes", None)) if profile else [])
    dislikes.update(req_dislikes or [])
    allergies = _split(getattr(profile, "allergies", None)) if profile else []
    return {"dislikes": list(dislikes), "allergies": allergies}


class SubstituteRequest(BaseModel):
    plan: Dict[str, Any] = Field(..., description="Existing daily plan dictionary")
    disliked_name: str = Field(..., description="Exact name of the food to replace")
    # If set, swap to this specific food (from the options list); else top match.
    replacement_name: Optional[str] = None
    dislikes: Optional[List[str]] = []
    prefer_same_cluster: bool = True


class OptionsRequest(BaseModel):
    plan: Dict[str, Any]
    food_name: str
    dislikes: Optional[List[str]] = []


@router.post("/options")
def substitute_options(
    request: OptionsRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    store = get_food_store()
    ex = _exclusions(current_user, request.dislikes)
    try:
        options = get_substitute_options(
            request.plan, request.food_name, store,
            dislikes=ex["dislikes"], allergies=ex["allergies"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"options": options}


@router.post("/")
def substitute_food(
    request: SubstituteRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    store = get_food_store()
    ex = _exclusions(current_user, request.dislikes)
    try:
        if request.replacement_name:
            updated = apply_named_substitute(
                request.plan, request.disliked_name, request.replacement_name, store
            )
        else:
            updated = replace_disliked_in_daily_plan(
                plan=request.plan,
                disliked_name=request.disliked_name,
                store=store,
                dislikes=ex["dislikes"],
                allergies=ex["allergies"],
                prefer_same_cluster=request.prefer_same_cluster,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"updated_plan": updated}
