import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  generatePlan,
  substituteFood,
  substituteOptions,
  getCurrentPlan,
  saveCurrentPlan,
  generateWeeklyPlan,
  getCurrentWeekly,
  saveCurrentWeekly,
} from "../api/planApi";
import { RESTRICTIONS, ALLERGENS, humanize } from "../constants/nutrition";
import CheckGrid from "./CheckGrid";
import MealCard from "./MealCard";
import { usePremium, PremiumLock } from "./PremiumGate";
import "./MealPlanner.css";

const rand = () => Math.floor(Math.random() * 1e6);
const MEALS_MIN = 2, MEALS_MAX = 6, SNACKS_MIN = 0, SNACKS_MAX = 4;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const MealPlanner = () => {
  const [mode, setMode] = useState("daily"); // "daily" | "weekly"
  const [meals, setMeals] = useState(3);   // main meals
  const [snacks, setSnacks] = useState(0); // snacks
  const [custom, setCustom] = useState(false); // custom meal-count mode
  const [plan, setPlan] = useState(null); // full /plan/daily response
  const [weekly, setWeekly] = useState(null); // full /plan/weekly response
  const [openDays, setOpenDays] = useState({ 0: true }); // weekly day expand state
  const [error, setError] = useState(null);
  const [needsProfile, setNeedsProfile] = useState(false);
  const [loading, setLoading] = useState(false);
  const [picker, setPicker] = useState(null); // { name, options, loading, applying }
  const { premium } = usePremium(); // weekly plan is Premium-only

  const weeklyLocked = mode === "weekly" && !premium;

  // Customize-for-this-plan overrides (otherwise profile values are used).
  const [customize, setCustomize] = useState(false);
  const [dislikes, setDislikes] = useState([]);
  const [allergies, setAllergies] = useState([]);

  // Restore the last saved daily + weekly plans when returning to the page.
  useEffect(() => {
    (async () => {
      try {
        const saved = await getCurrentPlan();
        setPlan(saved);
        const dp = saved?.daily_plan;
        if (dp?.meals_per_day) {
          setMeals(dp.meals_per_day);
          const sn = dp.snacks_per_day || 0;
          setSnacks(sn);
          // a non-standard combo -> show the custom controls
          if (!((dp.meals_per_day === 3 && sn === 0) ||
                (dp.meals_per_day === 3 && sn === 2))) {
            setCustom(true);
          }
        }
      } catch {
        /* no saved daily plan yet */
      }
      try {
        setWeekly(await getCurrentWeekly());
      } catch {
        /* no saved weekly plan yet */
      }
    })();
  }, []);

  const toggle = (list, setList) => (token) =>
    setList(
      list.includes(token) ? list.filter((t) => t !== token) : [...list, token]
    );

  const buildPayload = (extra = {}) => {
    const p = { meals_per_day: meals, snacks_per_day: snacks, ...extra };
    if (customize) {
      p.dislikes = dislikes;
      p.allergies = allergies;
    }
    return p;
  };

  const handleError = (err) => {
    if (err.status === 400 && /profile not found/i.test(err.message)) {
      setNeedsProfile(true);
      setError(null);
    } else {
      setNeedsProfile(false);
      setError(err.message);
    }
  };

  const handleGenerate = async (seed) => {
    setLoading(true);
    setError(null);
    setNeedsProfile(false);
    try {
      const data = await generatePlan(buildPayload(seed != null ? { seed } : {}));
      setPlan(data);
      saveCurrentPlan(data).catch(() => {});
    } catch (err) {
      handleError(err);
      setPlan(null);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateWeekly = async (seed) => {
    setLoading(true);
    setError(null);
    setNeedsProfile(false);
    try {
      const data = await generateWeeklyPlan(buildPayload(seed != null ? { seed } : {}));
      setWeekly(data);
      setOpenDays({ 0: true });
      saveCurrentWeekly(data).catch(() => {});
    } catch (err) {
      handleError(err);
      setWeekly(null);
    } finally {
      setLoading(false);
    }
  };

  // Open the picker and load candidate swaps for a food (daily view only).
  const openPicker = async (name) => {
    if (!plan) return;
    setError(null);
    setPicker({ name, options: [], loading: true, applying: false });
    try {
      const data = await substituteOptions({
        plan: plan.daily_plan,
        food_name: name,
        dislikes: customize ? dislikes : [],
      });
      setPicker({ name, options: data.options, loading: false, applying: false });
    } catch (err) {
      setError(err.message);
      setPicker(null);
    }
  };

  // Apply the chosen replacement.
  const chooseSubstitute = async (replacementName) => {
    if (!plan || !picker) return;
    setPicker((p) => ({ ...p, applying: true }));
    try {
      const data = await substituteFood({
        plan: plan.daily_plan,
        disliked_name: picker.name,
        replacement_name: replacementName,
      });
      setPlan((prev) => {
        const next = { ...prev, daily_plan: data.updated_plan };
        saveCurrentPlan(next).catch(() => {});
        return next;
      });
      setPicker(null);
    } catch (err) {
      setError(err.message);
      setPicker(null);
    }
  };

  // Render slots in the order the backend returns them (dynamic meal counts).
  const dailySlots = plan ? Object.keys(plan.daily_plan.meals) : [];

  const isPreset = (m, s) => !custom && meals === m && snacks === s;
  const pickPreset = (m, s) => { setCustom(false); setMeals(m); setSnacks(s); };
  const step = (setter, val, lo, hi) => () => setter(clamp(val, lo, hi));

  return (
    <div className="meal-planner-page">
      <div className="meal-planner-container">
        <div className="planner-header">
          <h2>Personalized Meal Planner</h2>
          <p>Select your preference and let us plan your day.</p>
        </div>

        <div className="mode-toggle">
          <button className={`mode-tab ${mode === "daily" ? "active" : ""}`}
            onClick={() => setMode("daily")}>
            Daily Plan
          </button>
          <button className={`mode-tab ${mode === "weekly" ? "active" : ""}`}
            onClick={() => setMode("weekly")}>
            Weekly Plan
          </button>
        </div>

        {weeklyLocked && <PremiumLock feature="Weekly meal plans" />}

        {!weeklyLocked && (
        <>
        <div className="selection-section">
          <h3>How many meals do you want to eat?</h3>
          <div className="meal-options-grid">
            <div className={`meal-option-card ${isPreset(3, 0) ? "selected" : ""}`}
              onClick={() => pickPreset(3, 0)}>
              <div className="option-icon">🍽️</div>
              <span className="option-label">3 Meals</span>
              <span className="option-desc">Breakfast, Lunch, Dinner</span>
            </div>
            <div className={`meal-option-card ${isPreset(3, 2) ? "selected" : ""}`}
              onClick={() => pickPreset(3, 2)}>
              <div className="option-icon">🥗</div>
              <span className="option-label">5 Meals</span>
              <span className="option-desc">3 Main Meals + 2 Snacks</span>
            </div>
            <div className={`meal-option-card ${custom ? "selected" : ""}`}
              onClick={() => setCustom(true)}>
              <div className="option-icon">⚙️</div>
              <span className="option-label">Custom</span>
              <span className="option-desc">Pick your own meals & snacks</span>
            </div>
          </div>

          {custom && (
            <div className="custom-counts">
              <div className="counter">
                <span className="counter-label">Main meals</span>
                <div className="counter-ctrl">
                  <button type="button" onClick={step(setMeals, meals - 1, MEALS_MIN, MEALS_MAX)}
                    disabled={meals <= MEALS_MIN}>−</button>
                  <span className="counter-val">{meals}</span>
                  <button type="button" onClick={step(setMeals, meals + 1, MEALS_MIN, MEALS_MAX)}
                    disabled={meals >= MEALS_MAX}>+</button>
                </div>
                <span className="counter-range">{MEALS_MIN}–{MEALS_MAX}</span>
              </div>
              <div className="counter">
                <span className="counter-label">Snacks</span>
                <div className="counter-ctrl">
                  <button type="button" onClick={step(setSnacks, snacks - 1, SNACKS_MIN, SNACKS_MAX)}
                    disabled={snacks <= SNACKS_MIN}>−</button>
                  <span className="counter-val">{snacks}</span>
                  <button type="button" onClick={step(setSnacks, snacks + 1, SNACKS_MIN, SNACKS_MAX)}
                    disabled={snacks >= SNACKS_MAX}>+</button>
                </div>
                <span className="counter-range">{SNACKS_MIN}–{SNACKS_MAX}</span>
              </div>
            </div>
          )}
        </div>

        <div className="customize-section">
          <label className="checkbox">
            <input type="checkbox" checked={customize}
              onChange={(e) => setCustomize(e.target.checked)} />
            Customize for this plan (overrides profile)
          </label>

          {customize && (
            <div className="customize-panel">
              <div className="form-group">
                <label>Restrictions</label>
                <CheckGrid options={RESTRICTIONS} selected={dislikes}
                  onToggle={toggle(dislikes, setDislikes)} />
              </div>
              <div className="form-group">
                <label>Allergies</label>
                <CheckGrid options={ALLERGENS} selected={allergies}
                  onToggle={toggle(allergies, setAllergies)} variant="allergen" />
              </div>
            </div>
          )}
        </div>

        <button className="generate-plan-btn"
          onClick={() => (mode === "weekly" ? handleGenerateWeekly() : handleGenerate())}
          disabled={loading}>
          {loading
            ? "Generating…"
            : mode === "weekly"
            ? "Generate Weekly Plan"
            : "Generate Meal Plan"}
        </button>

        {needsProfile && (
          <p className="planner-notice">
            You need to set up your profile first.{" "}
            <Link to="/profile">Go to Profile →</Link>
          </p>
        )}
        {error && <p className="planner-error">{error}</p>}

        {/* ---- DAILY VIEW ---- */}
        {mode === "daily" && plan && (
          <div className="plan-results">
            <div className="plan-summary">
              <div className="plan-summary-head">
                <h3>Your Daily Plan</h3>
                <button className="regen-btn"
                  onClick={() => handleGenerate(rand())} disabled={loading}>
                  ↻ Regenerate
                </button>
              </div>
              <p className="plan-summary-line">
                Target: <strong>{Math.round(plan.daily_calories)} kcal</strong>
                {"  ·  "}Plan total:{" "}
                <strong>{Math.round(plan.daily_plan.total_calories)} kcal</strong>
              </p>
              <p className="plan-summary-macros">
                Daily macros — P {Math.round(plan.daily_protein)}g · C{" "}
                {Math.round(plan.daily_carbs)}g · F {Math.round(plan.daily_fat)}g
                {"  ·  "}Goal: {humanize(plan.final_goal)}
              </p>
            </div>

            <div className="meals-grid">
              {dailySlots.map((s) => (
                <MealCard key={s} slot={s} meal={plan.daily_plan.meals[s]}
                  onSwap={openPicker} />
              ))}
            </div>
          </div>
        )}

        {/* ---- WEEKLY VIEW ---- */}
        {mode === "weekly" && weekly && (
          <div className="plan-results">
            <div className="plan-summary">
              <div className="plan-summary-head">
                <h3>Your Weekly Plan</h3>
                <button className="regen-btn"
                  onClick={() => handleGenerateWeekly(rand())} disabled={loading}>
                  ↻ Regenerate
                </button>
              </div>
              <p className="plan-summary-line">
                Target: <strong>{Math.round(weekly.weekly.target_calories)} kcal/day</strong>
                {"  ·  "}Avg total:{" "}
                <strong>{Math.round(weekly.weekly.avg_calories)} kcal/day</strong>
              </p>
              <p className="plan-summary-macros">
                Avg macros — P {Math.round(weekly.weekly.avg_protein)}g · C{" "}
                {Math.round(weekly.weekly.avg_carbs)}g · F {Math.round(weekly.weekly.avg_fat)}g
                {"  ·  "}Goal: {humanize(weekly.weekly.final_goal)}
              </p>
            </div>

            {weekly.days.map((day) => {
              const open = !!openDays[day.index];
              const slots = Object.keys(day.daily_plan.meals);
              return (
                <div key={day.index} className="week-day">
                  <button className="week-day-head"
                    onClick={() =>
                      setOpenDays((o) => ({ ...o, [day.index]: !o[day.index] }))
                    }>
                    <span className="week-day-name">{day.day}</span>
                    <span className="week-day-cals">
                      {Math.round(day.daily_plan.total_calories)} kcal
                    </span>
                    <span className="week-day-toggle">{open ? "▲" : "▼"}</span>
                  </button>
                  {open && (
                    <div className="meals-grid">
                      {slots.map((s) => (
                        <MealCard key={s} slot={s} meal={day.daily_plan.meals[s]} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        </>
        )}
      </div>

      {picker && (
        <div className="picker-overlay" onClick={() => setPicker(null)}>
          <div className="picker-card" onClick={(e) => e.stopPropagation()}>
            <div className="picker-head">
              <h4>Swap “{picker.name}”</h4>
              <button className="picker-close" onClick={() => setPicker(null)}>×</button>
            </div>
            {picker.loading ? (
              <p className="picker-empty">Finding alternatives…</p>
            ) : picker.options.length === 0 ? (
              <p className="picker-empty">No alternatives available.</p>
            ) : (
              <ul className="picker-list">
                {picker.options.map((o) => (
                  <li key={o.name}>
                    <button className="picker-option" disabled={picker.applying}
                      onClick={() => chooseSubstitute(o.name)}>
                      <span className="picker-name">{o.name}</span>
                      <span className="picker-meta">
                        {Math.round(o.grams)}g · {Math.round(o.calories)} kcal ·
                        {" "}P{Math.round(o.protein)} C{Math.round(o.carbs)} F{Math.round(o.fat)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MealPlanner;
