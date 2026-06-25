from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import re
import pandas as pd

from app.ai.gemini_helper import GeminiHelper

DATA_DIR = Path("data")
INDEX_PATH = DATA_DIR / "index.parquet"
SAMPLE_PATH = DATA_DIR / "sample.parquet"

gemini = GeminiHelper()

_index_df: pd.DataFrame | None = None
_sample_df: pd.DataFrame | None = None


def _load_data():
    global _index_df, _sample_df

    if _index_df is None:
        print("📦 Loading food index...")
        _index_df = pd.read_parquet(INDEX_PATH)

    if _sample_df is None:
        print("📦 Loading food sample...")
        _sample_df = pd.read_parquet(SAMPLE_PATH)


# Question / filler / nutrition words that are never food names — stripped from
# a query so natural-language questions still reach the food matcher.
_STOP = {
    "how", "many", "much", "is", "are", "the", "a", "an", "of", "in", "on",
    "for", "to", "me", "my", "i", "you", "your", "what", "whats", "please",
    "tell", "give", "show", "list", "and", "or", "do", "does", "did", "can",
    "could", "would", "with", "per", "about", "there", "its", "it", "that",
    "this", "some", "any", "good", "bad", "vs", "versus", "between", "than",
    "more", "less", "lot", "lots", "eat", "eating", "food", "foods",
    # nutrition terms (not foods)
    "calorie", "calories", "kcal", "energy", "protein", "proteins", "carb",
    "carbs", "carbohydrate", "carbohydrates", "fat", "fats", "fiber", "fibre",
    "sugar", "sugars", "sodium", "salt", "macro", "macros", "macronutrient",
    "macronutrients", "nutrition", "nutritional", "value", "values", "content",
    "amount", "amounts", "gram", "grams", "g", "serving", "servings", "info",
    "information", "breakdown", "contain", "contains", "have", "has", "had",
}
_WORD_RE = re.compile(r"[a-z]+")

# Derivative products that should rank BELOW the whole food when the user didn't
# ask for them ("avocado" -> avocado fruit, not avocado oil).
_DERIV = {
    "oil", "flour", "juice", "powder", "syrup", "extract", "paste", "sauce",
    "dried", "dehydrated", "concentrate", "puree",
}

# Prefer clean generic foods (USDA Standard Reference / Foundation / Survey)
# over the ~1.77M branded products, which dominate raw substring matches.
_TYPE_RANK = {
    "foundation_food": 0,
    "sr_legacy_food": 1,
    "survey_fndds_food": 2,
    "branded_food": 3,
}


def _keywords(query: str) -> List[str]:
    """Food-name tokens left after dropping question/nutrition stopwords."""
    return [t for t in _WORD_RE.findall(query.lower())
            if t not in _STOP and len(t) > 1]


def _match(df, text: str):
    return df[df["description_lc"].str.contains(re.escape(text), na=False)]


def _search_foods(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    _load_data()
    assert _index_df is not None
    df = _index_df

    kws = _keywords(query)
    if not kws:
        # no food-like tokens -> fall back to the raw query substring
        cand = _match(df, query.lower().strip())
        phrase = query.lower().strip()
    else:
        # primary: every keyword present (any order). The cleanest generic USDA
        # entries put qualifiers between words ("chicken, ..., breast, meat
        # only"), so adjacency matching alone would miss them.
        phrase = " ".join(kws)
        mask = df["description_lc"].str.contains(re.escape(kws[0]), na=False)
        for k in kws[1:]:
            mask &= df["description_lc"].str.contains(re.escape(k), na=False)
        cand = df[mask]
        if cand.empty:                               # last resort: longest token
            cand = _match(df, max(kws, key=len))

    if cand.empty:
        return []

    # rank: whole foods over derivatives (avocado fruit over avocado *oil*),
    # then clean data types, exact-phrase matches, and shorter descriptions.
    lc = cand["description_lc"]
    deriv_terms = _DERIV - set(kws)            # don't penalize a requested derivative
    if deriv_terms:
        deriv_re = r"\b(?:" + "|".join(map(re.escape, deriv_terms)) + r")\b"
        _deriv = lc.str.contains(deriv_re, na=False).astype(int)
    else:
        _deriv = 0
    cand = cand.assign(
        _deriv=_deriv,
        _tr=cand["data_type"].map(_TYPE_RANK).fillna(9),
        _len=cand["description"].str.len(),
    ).sort_values(["_deriv", "_tr", "_len"]).head(limit)

    foods = []
    for _, row in cand.iterrows():
        foods.append({
            "description": row["description"],
            "Calories": row["Calories"],
            "Protein": row["Protein"],
            "Carbs": row["Carbs"],
            "Fat": row["Fat"],
        })

    return foods


# ---------------------------------------------------------------------------
# RULE-BASED FAST-PATH (no LLM): single-food macro lookups are answered
# deterministically from the DB row, so they are exact, instant, and cost no
# API quota. Anything conversational (comparisons, meal plans, advice,
# follow-ups) returns None here and falls through to Gemini.
# ---------------------------------------------------------------------------
_NUTRI_WORDS = {
    "macro", "macros", "macronutrient", "macronutrients", "calorie", "calories",
    "kcal", "protein", "carb", "carbs", "carbohydrate", "carbohydrates", "fat",
    "fats", "nutrition", "nutritional", "fiber", "fibre", "sugar", "sodium",
}
# words that signal a request needing reasoning -> keep on Gemini
_DEFER_WORDS = {
    "or", "vs", "versus", "compare", "comparison", "difference", "better",
    "worse", "than", "which", "between", "plan", "diet", "menu", "recipe",
    "alternative", "alternatives", "substitute", "swap", "should", "healthy",
    "lose", "gain", "best", "breakfast", "lunch", "dinner", "snack", "snacks",
}
_AMT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|grams?|gm|g)\b")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _rule_based_answer(message: str, foods: List[Dict[str, Any]]):
    """Deterministic reply for a single-food macro lookup, else None."""
    low = message.lower()
    toks = set(_WORD_RE.findall(low))
    if not (toks & _NUTRI_WORDS):          # must ask about nutrition
        return None
    if toks & _DEFER_WORDS or "/" in low:  # comparison / plan / advice -> Gemini
        return None
    if not foods or not _keywords(message):
        return None

    # quantity: explicit grams -> scale; bare count ("2 eggs") -> defer to Gemini;
    # nothing -> per 100g.
    m = _AMT_RE.search(low)
    if m:
        grams = float(m.group(1)) * (1000.0 if m.group(2) == "kg" else 1.0)
        label, scale = f"{grams:g} g", grams / 100.0
    elif _NUM_RE.search(low):
        return None
    else:
        label, scale = "100 g", 1.0

    f = foods[0]
    try:
        cal = float(f["Calories"]) * scale
        p = float(f["Protein"]) * scale
        c = float(f["Carbs"]) * scale
        ft = float(f["Fat"]) * scale
    except (TypeError, ValueError):
        return None

    lines = [
        f"Macros for {label} of {f['description']}:",
        f"• Calories: {cal:.0f} kcal",
        f"• Protein: {p:.1f} g",
        f"• Carbs: {c:.1f} g",
        f"• Fat: {ft:.1f} g",
    ]
    if len(foods) > 1:
        lines.append("\nIf you meant a different variety, let me know and I'll adjust.")
    return "\n".join(lines)


def ask_chatbot(message: str, history: List[Dict[str, str]] | None = None) -> str:
    foods = _search_foods(message)

    # deterministic fast-path for simple macro lookups (no API call)
    rb = _rule_based_answer(message, foods)
    if rb is not None:
        return rb

    facts = {"foods_found": foods} if foods else None

    reply, ok = gemini.generate(
        user_message=message,
        facts=facts,
        history=history,
    )

    if ok and reply:
        return reply

    return "⚠️ I'm getting a lot of requests right now and hit my usage limit. Please try again in a moment."