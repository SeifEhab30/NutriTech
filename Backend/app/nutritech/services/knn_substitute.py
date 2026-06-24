# =====================================================
# NutriTech v2 - KNN Meal Substitution
# Swap a food in a plan for a nutritionally similar one
# (same role, nearest macro-vector neighbor), then re-solve
# its grams so the meal stays balanced.
# =====================================================

import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.nutritech.core.config import (
    ALLERGEN_EXPANSIONS,
    COMPONENT_KEYS,
    DEFAULT_MAX_GRAMS,
    MIN_PORTION_MULT,
    MAX_PORTION_MULT,
    NUTRIENT_FEATURES,
    ROLE_MAX_GRAMS,
)
from app.nutritech.services.planner import GARNISH, _item_from
from app.nutritech.services.scoring import apply_dislikes

_GARNISH_RE = "|".join(re.escape(g) for g in GARNISH)


def _resolve_grams(repl: pd.Series, target_cal: float) -> float:
    """Grams of `repl` to hit target_cal, clamped to serving + per-role bounds."""
    kpg = max(float(repl["kcal_100g"]), 1e-6) / 100.0
    serv = max(float(repl["serving_g"]), 1.0)
    grams = target_cal / kpg if kpg > 0 else serv
    cap = min(serv * MAX_PORTION_MULT, ROLE_MAX_GRAMS.get(str(repl.get("role")), DEFAULT_MAX_GRAMS))
    return min(cap, max(serv * MIN_PORTION_MULT, grams))


def _find_in_plan(plan: Dict[str, Any], target_name: str):
    """Return (slot, key, item) for the food matching target_name, else (None, None, None)."""
    t = str(target_name).strip().lower()
    for slot, meal in (plan.get("meals", {}) or {}).items():
        if not isinstance(meal, dict):
            continue
        for key in COMPONENT_KEYS:
            it = meal.get(key)
            if isinstance(it, dict) and str(it.get("name", "")).strip().lower() == t:
                return slot, key, it
    return None, None, None


def _used_names(plan: Dict[str, Any]) -> set:
    used = set()
    for meal in (plan.get("meals", {}) or {}).values():
        if not isinstance(meal, dict):
            continue
        for key in COMPONENT_KEYS:
            it = meal.get(key)
            if isinstance(it, dict) and it.get("name"):
                used.add(str(it["name"]).strip().lower())
    return used


def knn_find_substitute(
    original: pd.Series,
    store,
    *,
    used_names: Optional[set] = None,
    dislikes: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    prefer_same_cluster: bool = True,
    top_k: int = 5,
) -> List[pd.Series]:
    """Nearest foods (same role) to `original` by scaled macro vector.

    `allergies` are a hard exclude (allergen expansions); `dislikes` are the
    user's restrictions/preferences — both keep unwanted foods out of the swaps.
    """
    cand = store.df.copy()
    cand = cand[cand["role"] == original.get("role")]
    cand = cand[cand["name"].astype(str).str.lower() != str(original["name"]).strip().lower()]
    # never offer pure flavorings (lemon, garlic, ...) as a substitute
    cand = cand[~cand["name"].astype(str).str.lower().str.contains(_GARNISH_RE, na=False)]

    if used_names:
        low = {str(x).strip().lower() for x in used_names}
        cand = cand[~cand["name"].astype(str).str.lower().isin(low)]
    if allergies:
        cand = apply_dislikes(cand, allergies, ALLERGEN_EXPANSIONS)
    if dislikes:
        cand = apply_dislikes(cand, dislikes)
    if prefer_same_cluster and "cluster" in cand.columns and "cluster" in original:
        same = cand[cand["cluster"] == original["cluster"]]
        if not same.empty:
            cand = same
    if cand.empty:
        return []

    scaler = store.knn_scaler
    q = scaler.transform(original[NUTRIENT_FEATURES].to_numpy(dtype=float).reshape(1, -1))
    X = scaler.transform(cand[NUTRIENT_FEATURES].to_numpy(dtype=float))
    dist = np.linalg.norm(X - q, axis=1)
    order = np.argsort(dist)[: int(top_k)]
    return [cand.iloc[int(i)] for i in order]


def _write_back(plan: Dict[str, Any], slot: str, key: str, new_item: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of `plan` with one slot/key replaced and totals refreshed."""
    new_plan = dict(plan)
    new_plan["meals"] = dict(plan["meals"])
    new_meal = dict(new_plan["meals"][slot])
    new_meal[key] = new_item
    new_meal["total_calories"] = round(
        sum(new_meal[k]["calories"] for k in COMPONENT_KEYS
            if isinstance(new_meal.get(k), dict)), 1)
    new_plan["meals"][slot] = new_meal
    return new_plan


def get_substitute_options(
    plan: Dict[str, Any],
    food_name: str,
    store,
    *,
    dislikes: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    prefer_same_cluster: bool = False,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """Candidate swaps for one food, each priced to the item's current calories."""
    _, _, item = _find_in_plan(plan, food_name)
    if item is None:
        return []
    rows = store.df[store.df["name"].astype(str).str.lower() == str(food_name).strip().lower()]
    if rows.empty:
        return []
    original = rows.iloc[0]
    target_cal = float(item.get("calories", 0.0))

    subs = knn_find_substitute(
        original, store,
        used_names=_used_names(plan),
        dislikes=dislikes,
        allergies=allergies,
        prefer_same_cluster=prefer_same_cluster,
        top_k=top_k,
    )
    options = []
    for repl in subs:
        grams = _resolve_grams(repl, target_cal)
        options.append({
            "name": str(repl["name"]),
            "role": str(repl["role"]),
            "grams": round(float(grams), 1),
            "calories": round(float(repl["kcal_100g"]) * grams / 100.0, 1),
            "protein": round(float(repl["protein_100g"]) * grams / 100.0, 1),
            "carbs": round(float(repl["carbs_100g"]) * grams / 100.0, 1),
            "fat": round(float(repl["fat_100g"]) * grams / 100.0, 1),
        })
    return options


def apply_named_substitute(
    plan: Dict[str, Any],
    food_name: str,
    replacement_name: str,
    store,
) -> Dict[str, Any]:
    """Swap `food_name` for the specific `replacement_name` the user chose."""
    slot, key, item = _find_in_plan(plan, food_name)
    if item is None:
        return plan
    rows = store.df[store.df["name"].astype(str).str.lower() == str(replacement_name).strip().lower()]
    if rows.empty:
        return plan
    repl = rows.iloc[0]
    grams = _resolve_grams(repl, float(item.get("calories", 0.0)))
    return _write_back(plan, slot, key, _item_from(repl, grams))


def replace_disliked_in_daily_plan(
    plan: Dict[str, Any],
    disliked_name: str,
    store,
    *,
    dislikes: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    prefer_same_cluster: bool = True,
) -> Dict[str, Any]:
    slot, key, item = _find_in_plan(plan, disliked_name)
    if item is None:
        return plan

    # original food's per-100g row from the store
    rows = store.df[store.df["name"].astype(str).str.lower() == str(disliked_name).strip().lower()]
    if rows.empty:
        return plan
    original = rows.iloc[0]

    subs = knn_find_substitute(
        original, store,
        used_names=_used_names(plan),
        dislikes=dislikes,
        allergies=allergies,
        prefer_same_cluster=prefer_same_cluster,
    )
    if not subs:
        return plan

    grams = _resolve_grams(subs[0], float(item.get("calories", 0.0)))
    return _write_back(plan, slot, key, _item_from(subs[0], grams))
