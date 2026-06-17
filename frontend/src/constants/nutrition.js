// Shared option lists — keep frontend values aligned with the backend's
// canonical vocabulary (goals/diets) and exclusion tokens.

export const GOALS = [
  { value: "weight_loss", label: "Weight Loss" },
  { value: "weight_gain", label: "Muscle Gain" },
  { value: "maintain_weight", label: "Maintenance" },
];

export const ACTIVITY_LEVELS = [
  { value: "sedentary", label: "Sedentary" },
  { value: "moderate", label: "Moderate" },
  { value: "active", label: "Active" },
];

export const DIET_TYPES = [
  { value: "balanced", label: "Balanced" },
  { value: "high_protein", label: "High Protein" },
  // keto is only valid with weight_loss (handled in the UI)
  { value: "keto", label: "Keto", goal: "weight_loss" },
];

// Restriction/preference checklist -> stored in `dislikes`
export const RESTRICTIONS = [
  { value: "vegetarian", label: "Vegetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "pescatarian", label: "Pescatarian" },
  { value: "red_meat", label: "No Red Meat" },
  { value: "seafood", label: "No Seafood" },
  { value: "dairy", label: "No Dairy" },
  { value: "eggs", label: "No Eggs" },
  { value: "nuts", label: "No Nuts" },
  { value: "legumes", label: "No Legumes" },
];

// Big-9 allergens -> stored in `allergies`
export const ALLERGENS = [
  { value: "peanuts", label: "Peanuts" },
  { value: "tree_nuts", label: "Tree Nuts" },
  { value: "milk", label: "Milk" },
  { value: "eggs", label: "Eggs" },
  { value: "fish", label: "Fish" },
  { value: "shellfish", label: "Shellfish" },
  { value: "soy", label: "Soy" },
  { value: "wheat", label: "Wheat / Gluten" },
  { value: "sesame", label: "Sesame" },
];

// "vegetarian, dairy" -> ["vegetarian","dairy"]
export function splitTokens(s) {
  if (!s) return [];
  if (Array.isArray(s)) return s;
  return String(s)
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

// "weight_gain_high_protein" -> "weight gain high protein"
// (CSS text-transform handles any capitalization)
export function humanize(s) {
  if (!s) return "";
  return String(s).replace(/_/g, " ");
}
