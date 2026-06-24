# =====================================================
# NutriTech v2 - Core Configuration & Constants
# Clean rebuild: the curated dataset is pre-tagged (role,
# cuisine, diet_tags), so the old 200+ lines of runtime
# blocklists are gone.
# =====================================================

import os

# -----------------------------------------------------
# DATA PATH  -> curated everyday-foods dataset (257 rows)
# -----------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../Backend/app
PROJECT_ROOT = os.path.dirname(BASE_DIR)                                                  # .../Backend
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "foods_curated.csv")

# -----------------------------------------------------
# DATASET COLUMNS (new per-100g schema)
# -----------------------------------------------------
MACRO_COLS = ["kcal_100g", "protein_100g", "carbs_100g", "fat_100g",
              "fiber_100g", "sugar_100g", "sodium_100g"]
RATIO_COLS = ["protein_ratio", "carb_ratio", "fat_ratio"]

# Features used by K-Means clustering and KNN substitution
NUTRIENT_FEATURES = MACRO_COLS
CLUSTER_FEATURES = MACRO_COLS + RATIO_COLS

N_CLUSTERS = 8

# -----------------------------------------------------
# USER PROFILE
# -----------------------------------------------------
ACTIVITY_MAP = {"sedentary": 0, "moderate": 1, "active": 2}

# Daily protein ceiling = weight_kg * multiplier (sanity cap)
DAY_PROTEIN_MULTIPLIER = {
    "weight_loss": 1.8,
    "maintenance": 1.8,
    "weight_gain": 2.2,
    "keto": 2.2,
    "default": 1.8,
}

# -----------------------------------------------------
# SODIUM CAPS  (per-100g of food)
# -----------------------------------------------------
SODIUM_CAP_HYPERTENSION = 500.0   # mg / 100g hard cap when hypertensive
SODIUM_CAP_DEFAULT = 900.0        # mg / 100g soft cap otherwise

# -----------------------------------------------------
# NAME-TERM GROUPS  (reused by dislikes, restrictions, allergens)
# All 257 foods are single-ingredient components, so name-substring
# matching is a reliable (best-effort) exclusion.
# -----------------------------------------------------
_MEAT = ["beef", "veal", "lamb", "corned"]                     # red meat cuts
_POULTRY = ["chicken", "turkey", "duck", "quail", "cornish", "poultry"]
_FISH = ["fish", "tuna", "salmon", "cod", "tilapia", "trout", "herring",
         "sardine", "mackerel", "halibut", "haddock", "grouper", "snapper",
         "bass", "perch", "pollock", "mahi", "mullet", "catfish", "swordfish",
         "sole", "flounder", "anchovy"]
_SHELLFISH = ["shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster",
              "scallop", "squid", "calamari", "octopus"]
_DAIRY = ["milk", "cheese", "yogurt", "feta", "mozzarella", "cheddar",
          "ricotta", "kefir", "cream"]
_EGGS = ["egg"]
_TREE_NUTS = ["almond", "walnut", "cashew", "pistachio", "pecan", "hazelnut",
              "macadamia", "brazil nut", "pine nut", "chestnut"]
_PEANUTS = ["peanut"]
_SOY = ["soy", "edamame", "tofu", "tempeh"]
_LEGUMES = ["bean", "lentil", "pea", "peas", "chickpea", "garbanzo", "fava",
            "mung", "adzuki", "pinto", "kidney", "lima", "navy", "split pea",
            "black-eyed", "ful"] + _SOY
_GLUTEN = ["wheat", "bread", "pasta", "bagel", "muffin", "macaroni", "couscous",
           "bulgur", "barley", "rye", "spelt", "noodle", "tortilla", "pita",
           "granola", "sourdough", "cracker", "cereal", "flour"]
_SESAME = ["sesame", "tahini"]

# -----------------------------------------------------
# DISLIKE / RESTRICTION EXPANSIONS
# (a checklist token or a typed dislike -> name terms to exclude)
# -----------------------------------------------------
DISLIKE_EXPANSIONS = {
    # dietary patterns
    "vegetarian": _MEAT + _POULTRY + _FISH + _SHELLFISH,
    "vegan": _MEAT + _POULTRY + _FISH + _SHELLFISH + _DAIRY + _EGGS,
    "pescatarian": _MEAT + _POULTRY,
    "red_meat": _MEAT,
    "seafood": _FISH + _SHELLFISH,
    "dairy": _DAIRY,
    "eggs": _EGGS,
    "nuts": _TREE_NUTS + _PEANUTS + ["nut"],
    "legumes": _LEGUMES,
    # legacy / single-food dislikes
    "bean": _LEGUMES,
    "rice": ["rice", "basmati"],
    "chicken": ["chicken", "poultry"],
    "fish": _FISH,
}

# -----------------------------------------------------
# ALLERGEN EXPANSIONS  (big-9; hard, never-relaxed exclusion)
# -----------------------------------------------------
ALLERGEN_EXPANSIONS = {
    "peanuts": _PEANUTS,
    "tree_nuts": _TREE_NUTS,
    "milk": _DAIRY,
    "eggs": _EGGS,
    "fish": _FISH,
    "shellfish": _SHELLFISH,
    "soy": _SOY,
    "wheat": _GLUTEN,
    "sesame": _SESAME,
}

# -----------------------------------------------------
# MEAL STRUCTURE
# -----------------------------------------------------
# Dynamic meal/snack counts: the user picks how many main meals + snacks.
MEALS_MIN, MEALS_MAX = 2, 6
SNACKS_MIN, SNACKS_MAX = 0, 4

# Legacy presets (kept for reference; the planner now builds splits dynamically).
MEAL_SPLITS = {
    3: {"breakfast": 0.30, "lunch": 0.40, "dinner": 0.30},
    5: {"breakfast": 0.25, "snack_1": 0.10, "lunch": 0.30,
        "snack_2": 0.10, "dinner": 0.25},
}

# Ordered component slots a built meal may hold: protein main, carb, veg/fruit,
# and a fat component. Single source of truth shared by the planner, the
# substitution service, and the frontend meal card.
COMPONENT_KEYS = ("main", "side", "optional", "extra")

# Which roles compose each slot. The solver fills these from scored candidates.
# Roles available in the dataset: main, carb, veg, fruit, fat, side.
SLOT_TEMPLATES = {
    "breakfast": ["main", "carb", "fruit", "fat"],
    "lunch":     ["main", "carb", "veg", "fat"],
    "dinner":    ["main", "carb", "veg", "fat"],
    "snack_1":   ["fruit", "fat"],
    "snack_2":   ["side", "fruit"],
}

# Fallback role templates for dynamically-named slots (meal_3+, snack_3+).
# A small fat component (nuts/seeds/avocado, capped at ROLE_MAX_GRAMS["fat"])
# is included so meals can reach the diet's fat target; on keto the carb role
# is already remapped to fat and de-duplicated in _resolve_template.
MEAL_TEMPLATE_DEFAULT = ["main", "carb", "veg", "fat"]
SNACK_TEMPLATE_DEFAULT = ["fruit", "fat"]

# Relative calorie weight per main meal (others default to 1.0).
# breakfast/lunch/dinner = 1.0/1.33/1.0 reproduces the original 0.30/0.40/0.30
# three-meal split exactly.
_MEAL_WEIGHTS = {"breakfast": 1.0, "lunch": 1.33, "dinner": 1.0}
_SNACK_SHARE = 0.10        # calorie share per snack
_SNACK_SHARE_CAP = 0.40    # total share snacks may take


def clamp_meal_counts(n_meals, n_snacks):
    """Coerce requested meal/snack counts into the supported range."""
    m = max(MEALS_MIN, min(MEALS_MAX, int(n_meals)))
    s = max(SNACKS_MIN, min(SNACKS_MAX, int(n_snacks)))
    return m, s


def _main_slot_names(n_meals):
    """Friendly names for the common cases; generic 'meal_k' beyond 3."""
    if n_meals <= 1:
        return ["breakfast"]
    if n_meals == 2:
        return ["breakfast", "dinner"]
    if n_meals == 3:
        return ["breakfast", "lunch", "dinner"]
    extra = [f"meal_{i}" for i in range(3, n_meals)]   # meal_3 .. meal_{n-1}
    return ["breakfast", "lunch"] + extra + ["dinner"]


def build_day_structure(n_meals, n_snacks):
    """Ordered [(kind, slot)] for the day, snacks woven between meals.
    First main meal is always 'breakfast' so the lighter-breakfast logic
    keeps applying."""
    n_meals, n_snacks = clamp_meal_counts(n_meals, n_snacks)
    meals = _main_slot_names(n_meals)
    remaining = [f"snack_{i}" for i in range(1, n_snacks + 1)]
    order = []
    for i, m in enumerate(meals):
        order.append(("meal", m))
        if remaining and i < len(meals) - 1:
            order.append(("snack", remaining.pop(0)))
    order.extend(("snack", s) for s in remaining)
    return order


def build_meal_splits(structure):
    """Calorie share per slot for a day structure (sums to ~1.0)."""
    snacks = [slot for kind, slot in structure if kind == "snack"]
    snack_total = min(len(snacks) * _SNACK_SHARE, _SNACK_SHARE_CAP) if snacks else 0.0
    snack_each = (snack_total / len(snacks)) if snacks else 0.0
    meals = [slot for kind, slot in structure if kind == "meal"]
    weights = [_MEAL_WEIGHTS.get(m, 1.0) for m in meals]
    wsum = sum(weights) or 1.0
    meal_budget = 1.0 - snack_total

    splits = {}
    for kind, slot in structure:
        if kind == "snack":
            splits[slot] = snack_each
        else:
            splits[slot] = meal_budget * (_MEAL_WEIGHTS.get(slot, 1.0) / wsum)
    return splits

# -----------------------------------------------------
# BREAKFAST PROTEINS
# Breakfast should use lighter proteins (eggs, ful/beans, dairy) rather than
# dense meats/fish. For the breakfast "main" slot only, exclude these dense
# proteins and additionally allow cheeses/plain-yogurt (which live in role=side).
# -----------------------------------------------------
BREAKFAST_MAIN_EXCLUDE = _MEAT + _POULTRY + _FISH + _SHELLFISH
BREAKFAST_SIDE_PROTEIN = ["cheese", "mozzarella", "feta", "ricotta", "brie",
                          "gouda", "parmesan", "provolone", "yogurt"]

# Realistic portion bounds, as a multiple of each food's serving_g
MIN_PORTION_MULT = 0.4
MAX_PORTION_MULT = 2.5

# Absolute realistic ceilings per role (grams). Stops the solver from scaling
# low-calorie produce into implausible amounts (e.g. 300 g of lemon/cranberry).
ROLE_MAX_GRAMS = {
    "main": 300.0,
    "carb": 250.0,
    "veg": 200.0,
    "fruit": 200.0,
    "fat": 80.0,
    "side": 200.0,
}
DEFAULT_MAX_GRAMS = 250.0

# -----------------------------------------------------
# CLUSTER NAMES (display only; K-Means cluster ids are arbitrary)
# -----------------------------------------------------
CLUSTER_NAMES = {i: f"cluster_{i}" for i in range(N_CLUSTERS)}

# Kept for any legacy import; new schema uses MACRO_COLS.
BASE_FOOD_COLUMNS = ["name", "item_kind", "serving_g"] + MACRO_COLS + [
    "role", "cuisine", "diet_tags", "usda_description"
]
