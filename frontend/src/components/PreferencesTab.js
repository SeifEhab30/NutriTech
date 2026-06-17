import React, { useState, useEffect } from "react";
import { getProfile, updateProfile, getNeeds } from "../api/profileApi";
import OptionCard from "./OptionCard";
import CheckGrid from "./CheckGrid";
import {
  GOALS,
  ACTIVITY_LEVELS,
  DIET_TYPES,
  RESTRICTIONS,
  ALLERGENS,
  splitTokens,
} from "../constants/nutrition";

const EMPTY = {
  age: "",
  gender: "male",
  height: "",
  weight: "",
  activity_level: "sedentary",
  general_goal: "weight_loss",
  diet_type: "balanced",
  diabetes: false,
  hypertension: false,
  dislikes: [],
  allergies: [],
};

// Preferences tab: the canonical profile editor (body stats, goal/diet, health
// flags, cuisine, restrictions, allergies) + the computed daily needs.
const PreferencesTab = () => {
  const [form, setForm] = useState(EMPTY);
  const [needs, setNeeds] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(true);

  // Prefill from the saved profile (404 => start blank).
  useEffect(() => {
    (async () => {
      try {
        const p = await getProfile();
        setForm({
          ...EMPTY,
          ...p,
          age: p.age ?? "",
          height: p.height ?? "",
          weight: p.weight ?? "",
          diabetes: !!p.diabetes,
          hypertension: !!p.hypertension,
          dislikes: splitTokens(p.dislikes),
          allergies: splitTokens(p.allergies),
        });
        try {
          setNeeds(await getNeeds());
        } catch {
          /* needs unavailable until profile is complete */
        }
      } catch (err) {
        if (err.status !== 404) setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Keto only valid with weight_loss.
  useEffect(() => {
    if (form.general_goal !== "weight_loss" && form.diet_type === "keto") {
      setForm((f) => ({ ...f, diet_type: "balanced" }));
    }
  }, [form.general_goal, form.diet_type]);

  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  const toggleIn = (key) => (token) =>
    setForm((f) => {
      const list = f[key];
      return {
        ...f,
        [key]: list.includes(token)
          ? list.filter((t) => t !== token)
          : [...list, token],
      };
    });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (!form.age || !form.height || !form.weight) {
      setError("Please fill age, height and weight.");
      return;
    }
    try {
      const data = await updateProfile({
        age: Number(form.age),
        gender: form.gender,
        height: Number(form.height),
        weight: Number(form.weight),
        activity_level: form.activity_level,
        general_goal: form.general_goal,
        diet_type: form.diet_type,
        diabetes: form.diabetes,
        hypertension: form.hypertension,
        dislikes: form.dislikes,
        allergies: form.allergies,
      });
      setNeeds(data.daily_needs || null);
      setSuccess(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const dietOptions = DIET_TYPES.filter(
    (d) => !d.goal || d.goal === form.general_goal
  );

  if (loading) return <p>Loading…</p>;

  return (
    <>
      <form className="profile-form" onSubmit={handleSubmit}>
        {error && <p className="error">{error}</p>}
        {success && <p className="success">Profile saved!</p>}

        <div className="form-row">
          <div className="form-group">
            <label>Age</label>
            <input
              type="number"
              min="1"
              value={form.age}
              onChange={(e) => set("age")(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Gender</label>
            <div className="options-container">
              <OptionCard label="Male" value="male" selectedValue={form.gender} onClick={set("gender")} />
              <OptionCard label="Female" value="female" selectedValue={form.gender} onClick={set("gender")} />
            </div>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Height (cm)</label>
            <input type="number" min="1" step="0.1" value={form.height}
              onChange={(e) => set("height")(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Weight (kg)</label>
            <input type="number" min="1" step="0.1" value={form.weight}
              onChange={(e) => set("weight")(e.target.value)} required />
          </div>
        </div>

        <div className="form-group">
          <label>Activity Level</label>
          <div className="options-container">
            {ACTIVITY_LEVELS.map((a) => (
              <OptionCard key={a.value} label={a.label} value={a.value}
                selectedValue={form.activity_level} onClick={set("activity_level")} />
            ))}
          </div>
        </div>

        <div className="form-group">
          <label>Goal</label>
          <div className="options-container">
            {GOALS.map((g) => (
              <OptionCard key={g.value} label={g.label} value={g.value}
                selectedValue={form.general_goal} onClick={set("general_goal")} />
            ))}
          </div>
        </div>

        <div className="form-group">
          <label>Diet Type</label>
          <select value={form.diet_type} onChange={(e) => set("diet_type")(e.target.value)}>
            {dietOptions.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Health Conditions</label>
          <div className="checkbox-row">
            <label className="checkbox">
              <input type="checkbox" checked={form.diabetes}
                onChange={(e) => set("diabetes")(e.target.checked)} />
              Diabetes
            </label>
            <label className="checkbox">
              <input type="checkbox" checked={form.hypertension}
                onChange={(e) => set("hypertension")(e.target.checked)} />
              Hypertension
            </label>
          </div>
        </div>

        <div className="form-group">
          <label>Dietary Restrictions</label>
          <CheckGrid
            options={RESTRICTIONS}
            selected={form.dislikes}
            onToggle={toggleIn("dislikes")}
          />
        </div>

        <div className="form-group">
          <label>Allergies</label>
          <CheckGrid
            options={ALLERGENS}
            selected={form.allergies}
            onToggle={toggleIn("allergies")}
            variant="allergen"
          />
          <small className="hint">
            Best-effort filtering by food name — not a medical guarantee.
          </small>
        </div>

        <button type="submit">Save Profile</button>
      </form>

      {needs && (
        <div className="results-section">
          <h3>Your Daily Needs</h3>
          <div className="results-grid">
            <div className="result-card"><h4>Calories</h4><p>{needs.calories} kcal</p></div>
            <div className="result-card"><h4>Protein</h4><p>{needs.protein} g</p></div>
            <div className="result-card"><h4>Carbs</h4><p>{needs.carbs} g</p></div>
            <div className="result-card"><h4>Fats</h4><p>{needs.fats} g</p></div>
          </div>
        </div>
      )}
    </>
  );
};

export default PreferencesTab;
