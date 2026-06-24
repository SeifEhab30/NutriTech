# =====================================================
# NutriTech v2 - Meal Planner (constrained portion solver)
# Replaces the 960-line guard cascade. Picks foods by role,
# then SOLVES gram amounts so each meal hits its calorie
# target -> the day total lands on target by construction.
# =====================================================

import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.nutritech.core.config import (
    BREAKFAST_MAIN_EXCLUDE,
    BREAKFAST_SIDE_PROTEIN,
    COMPONENT_KEYS,
    DEFAULT_MAX_GRAMS,
    MAX_PORTION_MULT,
    MEAL_TEMPLATE_DEFAULT,
    MIN_PORTION_MULT,
    ROLE_MAX_GRAMS,
    SLOT_TEMPLATES,
    SNACK_TEMPLATE_DEFAULT,
    build_day_structure,
    build_meal_splits,
    clamp_meal_counts,
)

# Precompiled breakfast-protein matchers (substring, case-insensitive).
_BF_EXCLUDE_RE = "|".join(re.escape(t) for t in BREAKFAST_MAIN_EXCLUDE)
_BF_SIDE_RE = "|".join(re.escape(t) for t in BREAKFAST_SIDE_PROTEIN)
_BF_CHEESE_TERMS = ["cheese", "mozzarella", "feta", "ricotta", "brie",
                    "gouda", "parmesan", "provolone"]


def _bf_family(name_l: str) -> str:
    """Group a breakfast protein into a family so the slot rotates fairly
    across eggs / legumes (ful, beans) / cheese / yogurt instead of letting
    high-scoring cheeses dominate."""
    if "egg" in name_l:
        return "egg"
    if any(t in name_l for t in _BF_CHEESE_TERMS):
        return "cheese"
    if "yogurt" in name_l or "labneh" in name_l:
        return "yogurt"
    return "legume"   # beans, ful, chickpeas, tofu, soy, edamame, ...


def _role_cap(role: str) -> float:
    return ROLE_MAX_GRAMS.get(str(role), DEFAULT_MAX_GRAMS)

MACRO_KEYS = ["protein", "carbs", "fat", "fiber", "sugar", "sodium"]

# Flavorings / garnishes that shouldn't be scaled up into a meal component.
GARNISH = {
    "parsley", "mint", "dill", "basil", "cilantro", "capers", "garlic",
    "green onion", "arugula", "watercress", "bell pepper", "lemon", "lime",
}
PER100 = {
    "calories": "kcal_100g", "protein": "protein_100g", "carbs": "carbs_100g",
    "fat": "fat_100g", "fiber": "fiber_100g", "sugar": "sugar_100g", "sodium": "sodium_100g",
}


# =====================================================
# TEMPLATE RESOLUTION (goal-aware)
# =====================================================

def _resolve_template(slot: str, fg: str) -> List[str]:
    if slot in SLOT_TEMPLATES:
        roles = list(SLOT_TEMPLATES[slot])
    elif slot.startswith("snack"):
        roles = list(SNACK_TEMPLATE_DEFAULT)
    else:
        roles = list(MEAL_TEMPLATE_DEFAULT)
    if fg == "keto":
        # no starchy carbs / sugary fruit on keto
        roles = ["fat" if r == "carb" else "veg" if r == "fruit" else r for r in roles]
    elif fg == "diabetes":
        roles = ["veg" if r == "fruit" else r for r in roles]
    # de-dup while preserving order
    seen, out = set(), []
    for r in roles:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


# =====================================================
# PORTION SOLVER
# =====================================================

def solve_portions(items: List[dict], target_cal: float,
                   min_mult: float = MIN_PORTION_MULT,
                   max_mult: float = MAX_PORTION_MULT,
                   iters: int = 10, cap_mult: float = 1.0) -> List[float]:
    """Return grams per item so total calories ~= target_cal, within bounds.
    `cap_mult` loosens the per-role gram ceilings (used on few-meal days where
    each meal carries a larger calorie target)."""
    n = len(items)
    if n == 0 or target_cal <= 0:
        return [0.0] * n
    kpg = [max(float(it["kcal_100g"]), 0.0) / 100.0 for it in items]   # kcal per gram
    serv = [max(float(it["serving_g"]), 1.0) for it in items]
    lo = [serv[i] * min_mult for i in range(n)]
    # cap each item at the smaller of its serving-multiple and a realistic
    # per-role ceiling, so low-calorie produce isn't scaled into huge portions
    hi = [min(serv[i] * max_mult * cap_mult, _role_cap(items[i].get("role")) * cap_mult)
          for i in range(n)]
    hi = [max(hi[i], lo[i]) for i in range(n)]
    g = [min(serv[i], hi[i]) for i in range(n)]

    for _ in range(iters):
        cur = sum(g[i] * kpg[i] for i in range(n))
        err = target_cal - cur
        if abs(err) <= max(5.0, 0.01 * target_cal):
            break
        # items that can still move in the needed direction
        movable = [i for i in range(n) if kpg[i] > 0 and (
            (err > 0 and g[i] < hi[i] - 1e-6) or (err < 0 and g[i] > lo[i] + 1e-6))]
        if not movable:
            break
        denom = sum(kpg[i] for i in movable)
        for i in movable:
            dcal = err * (kpg[i] / denom)          # share of the error (in kcal)
            g[i] = min(hi[i], max(lo[i], g[i] + dcal / kpg[i]))
    return g


# =====================================================
# MACRO-AWARE PORTION BUDGETING
# =====================================================

# Which macro each food role primarily contributes to the meal.
_ROLE_MACRO = {"main": "p", "carb": "c", "fat": "f", "side": "c"}
_FILLER_ROLES = {"veg", "fruit"}
_FILLER_SHARE = 0.08      # calorie share reserved per low-calorie filler
_FILLER_SHARE_CAP = 0.20  # total share fillers may take


def _role_calorie_fractions(roles: List[str], split) -> List[float]:
    """Calorie share per item derived from the diet's macro split (protein,
    carb, fat energy fractions). Protein-role foods get the protein share,
    carb-role the carb share, fat-role the fat share; vegetables/fruit get a
    small fixed filler share. Missing macro buckets have their share
    redistributed across the present ones. This makes the resulting macro
    distribution track the target split instead of just total calories."""
    p_e, c_e, f_e = split
    idx = {"p": [], "c": [], "f": [], "v": []}
    for i, role in enumerate(roles):
        if role in _FILLER_ROLES:
            idx["v"].append(i)
        else:
            idx[_ROLE_MACRO.get(role, "c")].append(i)
    v_total = min(len(idx["v"]) * _FILLER_SHARE, _FILLER_SHARE_CAP)
    rem = 1.0 - v_total
    weights = {"p": p_e if idx["p"] else 0.0,
               "c": c_e if idx["c"] else 0.0,
               "f": f_e if idx["f"] else 0.0}
    wsum = sum(weights.values()) or 1.0
    frac = [0.0] * len(roles)
    for b in ("p", "c", "f"):
        if not idx[b]:
            continue
        per = rem * (weights[b] / wsum) / len(idx[b])
        for i in idx[b]:
            frac[i] = per
    if idx["v"]:
        per_v = v_total / len(idx["v"])
        for i in idx["v"]:
            frac[i] = per_v
    s = sum(frac) or 1.0
    return [x / s for x in frac]


def _macro_portions(items: List[dict], target_cal: float, split,
                    cap_mult: float = 1.0) -> List[float]:
    """Grams per item so the meal matches both its calorie target and the diet's
    macro split. Solves a bounded least-squares fit over [calories, protein,
    carbohydrate, fat] energy using each food's *actual* per-gram nutrients (so
    the incidental protein/fat carried by carb or 'lean' foods is accounted for),
    seeded from a role-based budget and clipped to realistic portion bounds. The
    whole-day normalization later lands the exact calorie total."""
    n = len(items)
    if n == 0 or target_cal <= 0:
        return [0.0] * n
    serv = [max(float(it["serving_g"]), 1.0) for it in items]
    lo = [serv[i] * MIN_PORTION_MULT for i in range(n)]
    hi = [max(min(serv[i] * MAX_PORTION_MULT * cap_mult,
                  _role_cap(items[i].get("role")) * cap_mult), lo[i]) for i in range(n)]

    # per-gram energy contributions (kcal): total, protein, carb, fat
    cal = np.array([max(float(it["kcal_100g"]), 0.0) / 100.0 for it in items])
    pe = np.array([4.0 * float(it["protein_100g"]) / 100.0 for it in items])
    ce = np.array([4.0 * float(it["carbs_100g"]) / 100.0 for it in items])
    fe = np.array([9.0 * float(it["fat_100g"]) / 100.0 for it in items])
    p_e, c_e, f_e = split
    A = np.vstack([cal, pe, ce, fe])                       # 4 x n
    b = np.array([target_cal, p_e * target_cal, c_e * target_cal, f_e * target_cal])

    try:
        g, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        g = np.array([_role_calorie_fractions(
            [str(it.get("role")) for it in items], split)[i] * target_cal /
            max(cal[i], 1e-6) for i in range(n)])
    g = [float(min(hi[i], max(lo[i], g[i]))) for i in range(n)]
    return g


# =====================================================
# FOOD SELECTION
# =====================================================

def _breakfast_main_pool(cands: pd.DataFrame, used: set) -> pd.DataFrame:
    """Light breakfast proteins: role=main minus dense meats/fish, plus the
    cheeses/plain-yogurt that are tagged role=side."""
    avail = cands[~cands["_name_l"].isin(used)]
    light = avail[(avail["role"] == "main") &
                  (~avail["_name_l"].str.contains(_BF_EXCLUDE_RE, na=False))]
    dairy = avail[(avail["role"] == "side") &
                  (avail["_name_l"].str.contains(_BF_SIDE_RE, na=False))]
    return pd.concat([light, dairy])


def _pick_breakfast_main(pool: pd.DataFrame, fg: str, top_k: int = 6) -> pd.Series:
    """Family-balanced breakfast pick: choose a protein family at random, then
    the best-fitting food within it (with a little randomness)."""
    pool = pool.copy()
    pool["_fam"] = pool["_name_l"].map(_bf_family)
    fam = np.random.choice(sorted(pool["_fam"].unique()))
    fp = pool[pool["_fam"] == fam]
    if "high_protein" in fg:
        hp = fp[fp["diet_tags"].str.contains("hp", na=False)]
        if not hp.empty:
            fp = hp
    fp = fp.sort_values("score", ascending=False).head(top_k)
    return fp.sample(n=1).iloc[0]


def _pick(role: str, cands: pd.DataFrame, used: set, cluster_counts: dict,
          fg: str, slot: Optional[str] = None,
          cluster_cap: int = 2, top_k: int = 8) -> Optional[pd.Series]:
    if slot == "breakfast" and role == "main":
        bpool = _breakfast_main_pool(cands, used)
        if not bpool.empty:
            return _pick_breakfast_main(bpool, fg)
        # over-restrictive combo -> fall back to any main
        pool = cands[(cands["role"] == "main") & (~cands["_name_l"].isin(used))]
    else:
        pool = cands[(cands["role"] == role) & (~cands["_name_l"].isin(used))]
    if pool.empty:
        return None
    # variety: cap foods per K-Means cluster. If every cluster is already at the
    # cap, don't fall back to the whole pool (that let one cluster dominate, e.g.
    # 15 foods/cluster on big days) -- restrict to the least-used clusters so the
    # day stays as spread out as the pool allows.
    counts = pool["cluster"].map(lambda c: cluster_counts.get(int(c), 0))
    capped = pool[counts < cluster_cap]
    if not capped.empty:
        pool = capped
    else:
        pool = pool[counts == counts.min()]
    # high-protein goals prefer hp mains
    if "high_protein" in fg and role == "main":
        hp = pool[pool["diet_tags"].str.contains("hp", na=False)]
        if not hp.empty:
            pool = hp
    pool = pool.sort_values("score", ascending=False).head(top_k)
    return pool.sample(n=1).iloc[0]


def _item_from(row: pd.Series, grams: float) -> Dict[str, Any]:
    g = round(float(grams), 1)
    factor = g / 100.0
    item = {
        "name": str(row["name"]),
        "grams": g,
        "calories": round(float(row["kcal_100g"]) * factor, 1),
        "role": str(row["role"]),
        "cluster": int(row.get("cluster", -1)),
    }
    for k in MACRO_KEYS:
        item[k] = round(float(row[PER100[k]]) * factor, 1)
    return item


# =====================================================
# BUILD ONE MEAL
# =====================================================

def _build_meal(slot: str, target_cal: float, cands: pd.DataFrame,
                used: set, cluster_counts: dict, fg: str,
                cap_mult: float = 1.0, split=None) -> Optional[Dict[str, Any]]:
    roles = _resolve_template(slot, fg)
    chosen: List[pd.Series] = []
    for role in roles:
        row = _pick(role, cands, used, cluster_counts, fg, slot=slot)
        if row is None:
            continue
        chosen.append(row)
        used.add(row["_name_l"])
        cluster_counts[int(row["cluster"])] = cluster_counts.get(int(row["cluster"]), 0) + 1
    if not chosen:
        # last resort: any unused candidate
        pool = cands[~cands["_name_l"].isin(used)]
        if pool.empty:
            return None
        row = pool.sort_values("score", ascending=False).iloc[0]
        chosen.append(row)
        used.add(row["_name_l"])

    rows = [r.to_dict() for r in chosen]
    if split is not None and len(rows) > 1:
        grams = _macro_portions(rows, target_cal, split, cap_mult=cap_mult)
    else:
        grams = solve_portions(rows, target_cal, cap_mult=cap_mult)
    items = [_item_from(chosen[i], grams[i]) for i in range(len(chosen))]

    meal = {"target_calories": round(float(target_cal), 1)}
    for i, key in enumerate(COMPONENT_KEYS):
        meal[key] = items[i] if i < len(items) else None
    meal["total_calories"] = round(sum(it["calories"] for it in items), 1)
    return meal


# =====================================================
# BUILD DAILY PLAN
# =====================================================

def build_daily_plan(
    candidates: pd.DataFrame,
    *,
    meals_per_day: int = 3,
    snacks_per_day: int = 0,
    daily_calories: float = 2000.0,
    final_goal: str = "maintenance_balanced",
    macro_targets: Optional[tuple] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:

    if seed is not None:
        np.random.seed(seed)

    # Macro energy split (protein, carb, fat fractions of total calories) used
    # to budget portions so the plan tracks the diet's macro ratios, not only
    # its calorie total. Falls back to calorie-only solving when unavailable.
    split = None
    if macro_targets is not None and daily_calories > 0:
        p_g, c_g, f_g = macro_targets
        split = (4.0 * p_g / daily_calories,
                 4.0 * c_g / daily_calories,
                 9.0 * f_g / daily_calories)

    n_meals, n_snacks = clamp_meal_counts(meals_per_day, snacks_per_day)
    structure = build_day_structure(n_meals, n_snacks)
    splits = build_meal_splits(structure)
    fg = str(final_goal).lower().strip()

    cands = candidates.copy()
    cands["_name_l"] = cands["name"].astype(str).str.lower()
    if "cluster" not in cands.columns:
        cands["cluster"] = 0
    # drop pure flavorings so they aren't scaled into meal components
    # (substring match so "Lemon", "Lemons", "Lemon Juice" are all caught)
    garnish_re = "|".join(re.escape(g) for g in GARNISH)
    cands = cands[~cands["_name_l"].str.contains(garnish_re, na=False)].reset_index(drop=True)

    used: set = set()
    cluster_counts: dict = {}
    meals: Dict[str, Any] = {}

    # Fewer meals -> each carries more calories -> allow bigger portions so the
    # per-role caps don't force an undershoot (e.g. a 2-meal day).
    n_main = max(sum(1 for k, _ in structure if k == "meal"), 1)
    cap_mult = max(1.0, 3.0 / n_main)

    for slot, share in splits.items():
        target_cal = float(daily_calories) * float(share)
        meal = _build_meal(slot, target_cal, cands, used, cluster_counts, fg,
                           cap_mult, split=split)
        if meal is not None:
            meals[slot] = meal

    # ---- final whole-day normalization to the exact target ----
    _normalize_day(meals, float(daily_calories), cap_mult)

    return {
        "meals_per_day": n_meals,
        "snacks_per_day": n_snacks,
        "daily_calories": round(float(daily_calories), 1),
        "total_calories": round(sum(m["total_calories"] for m in meals.values()), 1),
        "meals": meals,
    }


def _scale_item(it: Dict[str, Any], new_g: float) -> None:
    scale = new_g / it["grams"] if it["grams"] else 1.0
    it["grams"] = round(new_g, 1)
    it["calories"] = round(it["calories"] * scale, 1)
    for k in MACRO_KEYS:
        it[k] = round(it[k] * scale, 1)


def _refresh_totals(meals: Dict[str, Any]) -> None:
    for meal in meals.values():
        meal["total_calories"] = round(
            sum(meal[k]["calories"] for k in COMPONENT_KEYS
                if isinstance(meal.get(k), dict)), 1)


def _normalize_day(meals: Dict[str, Any], target: float, cap_mult: float = 1.0) -> None:
    """Land the whole-day total on target. Proportional scaling alone leaves a
    residual whenever some meals hit their per-role gram caps (e.g. a light
    breakfast on a 2-meal keto day): the spare calories can't be recovered from
    a capped meal, so the day undershoots. This redistributes the remaining gap
    onto items still below their cap, iterating until the gap closes or every
    movable item is maxed out."""
    items = [it for meal in meals.values()
             for key in COMPONENT_KEYS
             if isinstance((it := meal.get(key)), dict) and it.get("grams", 0) > 0]
    if not items:
        return

    # Phase 1: proportional scaling. Scaling every item by the same factor
    # preserves the meal's macro ratios (set by the macro-aware budgeting),
    # so the day lands on the calorie target without distorting protein/carb/
    # fat balance. Items pinned at their gram cap leave a residual.
    for _ in range(6):
        total = sum(it["calories"] for it in items)
        if total <= 0:
            return
        if abs(target - total) <= 0.005 * target:
            break
        factor = target / total
        moved = False
        for it in items:
            cap = _role_cap(it.get("role")) * cap_mult
            new_g = max(1.0, min(cap, it["grams"] * factor))
            if abs(new_g - it["grams"]) > 1e-6:
                moved = True
            _scale_item(it, new_g)
        if not moved:
            break

    # Phase 2: redistribute any residual (from capped items) onto items that
    # can still move, sharing it by kcal/gram.
    for _ in range(12):
        total = sum(it["calories"] for it in items)
        if total <= 0:
            return
        gap = target - total                       # +ve: undershoot, -ve: overshoot
        if abs(gap) <= 0.02 * target:
            break
        # kcal/gram for each item; only items that can still move in the needed
        # direction participate (under cap when filling up, above floor when down)
        movers = []
        for it in items:
            kpg = it["calories"] / it["grams"] if it["grams"] else 0.0
            if kpg <= 0:
                continue
            cap = _role_cap(it.get("role")) * cap_mult
            if gap > 0 and it["grams"] < cap - 1e-6:
                movers.append((it, kpg, cap, 1.0))
            elif gap < 0 and it["grams"] > 1.0:
                movers.append((it, kpg, cap, 1.0))
        if not movers:
            break
        denom = sum(kpg for _, kpg, _, _ in movers) or 1.0
        for it, kpg, cap, _ in movers:
            dcal = gap * (kpg / denom)              # this item's share of the gap
            new_g = it["grams"] + dcal / kpg
            new_g = max(1.0, min(cap, new_g))
            _scale_item(it, new_g)

    _refresh_totals(meals)
