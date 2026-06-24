import React, { useState, useEffect, useCallback } from "react";
import { getDay, logEntry, deleteEntry } from "../api/trackerApi";
import { getCurrentPlan, getCurrentWeekly } from "../api/planApi";
import { searchFoods } from "../api/foodsApi";
import { humanize } from "../constants/nutrition";

const COMPONENT_KEYS = ["main", "side", "optional", "extra"];

const todayStr = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD local

// Flatten a daily_plan's meals into a list of { slot, ...component } items.
const flattenPlan = (daily_plan) => {
  const items = [];
  for (const slot of Object.keys(daily_plan.meals)) {
    const meal = daily_plan.meals[slot];
    for (const k of COMPONENT_KEYS) {
      if (meal[k]) items.push({ slot, ...meal[k] });
    }
  }
  return items;
};

// One target-vs-consumed progress bar.
const Bar = ({ label, value, target, unit }) => {
  const pct = target ? Math.min((value / target) * 100, 100) : 0;
  const over = target && value > target;
  return (
    <div className="track-bar">
      <div className="track-bar-head">
        <span>{label}</span>
        <span className="track-bar-nums">
          {Math.round(value)}{target ? ` / ${Math.round(target)}` : ""} {unit}
        </span>
      </div>
      <div className="track-bar-rail">
        <div className={`track-bar-fill ${over ? "over" : ""}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};

const DailyTrackerTab = () => {
  const [date, setDate] = useState(todayStr());
  const [day, setDay] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const [addMode, setAddMode] = useState("plan"); // plan | search | manual
  const [planSrc, setPlanSrc] = useState("daily"); // daily | weekly (for "from plan")
  const [dailyItems, setDailyItems] = useState(null); // saved daily plan items
  const [weekly, setWeekly] = useState(null); // saved weekly plan response
  const [weekDay, setWeekDay] = useState(0); // selected weekly day index
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [grams, setGrams] = useState({}); // per-result grams override
  const [manual, setManual] = useState({ name: "", calories: "", protein: "", carbs: "", fat: "" });

  const load = useCallback(async (d) => {
    setLoading(true);
    try {
      setDay(await getDay(d));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(date); }, [date, load]);

  // Lazy-load the saved DAILY plan when "from plan / daily" opens.
  useEffect(() => {
    if (addMode !== "plan" || planSrc !== "daily" || dailyItems !== null) return;
    (async () => {
      try {
        const plan = await getCurrentPlan();
        setDailyItems(flattenPlan(plan.daily_plan));
      } catch {
        setDailyItems([]); // no saved daily plan
      }
    })();
  }, [addMode, planSrc, dailyItems]);

  // Lazy-load the saved WEEKLY plan when "from plan / weekly" opens.
  useEffect(() => {
    if (addMode !== "plan" || planSrc !== "weekly" || weekly !== null) return;
    (async () => {
      try {
        setWeekly(await getCurrentWeekly());
      } catch {
        setWeekly({ days: [] }); // no saved weekly plan
      }
    })();
  }, [addMode, planSrc, weekly]);

  // Items shown in the "from plan" picker for the current source.
  const planItems =
    planSrc === "daily"
      ? dailyItems
      : weekly && weekly.days && weekly.days[weekDay]
      ? flattenPlan(weekly.days[weekDay].daily_plan)
      : weekly
      ? [] // weekly loaded but empty
      : null; // still loading

  const add = async (payload) => {
    setBusy(true);
    setError(null);
    try {
      setDay(await logEntry({ ...payload, date }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    setBusy(true);
    try {
      setDay(await deleteEntry(id));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runSearch = async (e) => {
    e.preventDefault();
    const query = q.trim();
    if (query.length < 2) return;
    setSearching(true);
    setError(null);
    try {
      const data = await searchFoods(query, 15);
      setResults(data.results || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  };

  const addSearchResult = (r) => {
    const g = Number(grams[r.name]) || r.serving_g || 100;
    const f = g / 100;
    const p = r.per_100g;
    add({
      source: "search",
      name: r.name,
      grams: g,
      calories: p.calories * f,
      protein: p.protein * f,
      carbs: p.carbs * f,
      fat: p.fat * f,
    });
  };

  const addManual = (e) => {
    e.preventDefault();
    if (!manual.name.trim()) return;
    add({
      source: "manual",
      name: manual.name.trim(),
      calories: Number(manual.calories) || 0,
      protein: Number(manual.protein) || 0,
      carbs: Number(manual.carbs) || 0,
      fat: Number(manual.fat) || 0,
    });
    setManual({ name: "", calories: "", protein: "", carbs: "", fat: "" });
  };

  const t = day?.target;
  const tot = day?.totals || { calories: 0, protein: 0, carbs: 0, fats: 0 };

  return (
    <div className="tracker">
      <div className="tracker-head">
        <h3>Daily Tracker</h3>
        <input type="date" value={date} max={todayStr()}
          onChange={(e) => setDate(e.target.value || todayStr())} />
      </div>

      {error && <p className="error">{error}</p>}

      {/* ---- Progress vs target ---- */}
      <div className="track-bars">
        {!t && (
          <p className="hint">Set up your profile to see daily targets.</p>
        )}
        <Bar label="Calories" value={tot.calories} target={t?.calories} unit="kcal" />
        <Bar label="Protein" value={tot.protein} target={t?.protein} unit="g" />
        <Bar label="Carbs" value={tot.carbs} target={t?.carbs} unit="g" />
        <Bar label="Fats" value={tot.fats} target={t?.fats} unit="g" />
      </div>

      {/* ---- Logged entries ---- */}
      <div className="track-entries">
        <h4>Logged ({day?.entries?.length || 0})</h4>
        {loading ? (
          <p>Loading…</p>
        ) : day?.entries?.length ? (
          <ul>
            {day.entries.map((en) => (
              <li key={en.id} className="track-entry">
                <span className="te-name">
                  {en.name}
                  {en.grams ? <em> · {Math.round(en.grams)}g</em> : null}
                  <span className={`te-src te-${en.source}`}>{en.source}</span>
                </span>
                <span className="te-macros">
                  {Math.round(en.calories)} kcal · P{Math.round(en.protein)} C{Math.round(en.carbs)} F{Math.round(en.fat)}
                </span>
                <button className="te-del" disabled={busy}
                  onClick={() => remove(en.id)} title="Remove">✕</button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="hint">Nothing logged for this day yet.</p>
        )}
      </div>

      {/* ---- Add entry ---- */}
      <div className="track-add">
        <div className="mode-toggle">
          {["plan", "search", "manual"].map((m) => (
            <button key={m} className={`mode-tab ${addMode === m ? "active" : ""}`}
              onClick={() => setAddMode(m)}>
              {m === "plan" ? "From Plan" : m === "search" ? "Search" : "Manual"}
            </button>
          ))}
        </div>

        {addMode === "plan" && (
          <div className="add-panel">
            <div className="plan-src-row">
              <div className="plan-src-toggle">
                {["daily", "weekly"].map((s) => (
                  <button key={s}
                    className={`src-tab ${planSrc === s ? "active" : ""}`}
                    onClick={() => setPlanSrc(s)}>
                    {s === "daily" ? "Daily plan" : "Weekly plan"}
                  </button>
                ))}
              </div>
              {planSrc === "weekly" && weekly?.days?.length > 0 && (
                <select className="week-day-select" value={weekDay}
                  onChange={(e) => setWeekDay(Number(e.target.value))}>
                  {weekly.days.map((d) => (
                    <option key={d.index} value={d.index}>{d.day}</option>
                  ))}
                </select>
              )}
            </div>

            {planItems === null ? (
              <p>Loading plan…</p>
            ) : planItems.length === 0 ? (
              <p className="hint">
                No saved {planSrc} plan to pull from. Generate one in the Meal Planner.
              </p>
            ) : (
              <ul className="plan-pick">
                {planItems.map((it, i) => (
                  <li key={i}>
                    <span className="pp-name">
                      <span className="pp-slot">{humanize(it.slot)}</span>
                      {it.name} <em>· {Math.round(it.grams)}g</em>
                    </span>
                    <span className="pp-cals">{Math.round(it.calories)} kcal</span>
                    <button className="pp-add" disabled={busy}
                      onClick={() => add({
                        source: "plan", name: it.name, grams: it.grams,
                        calories: it.calories, protein: it.protein,
                        carbs: it.carbs, fat: it.fat,
                      })}>+ Add</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {addMode === "search" && (
          <div className="add-panel">
            <form onSubmit={runSearch} className="search-row">
              <input type="text" value={q} placeholder="Search a food (e.g. banana)"
                onChange={(e) => setQ(e.target.value)} />
              <button type="submit" disabled={searching}>{searching ? "…" : "Search"}</button>
            </form>
            {results && (results.length === 0 ? (
              <p className="hint">No matches.</p>
            ) : (
              <ul className="plan-pick">
                {results.map((r, i) => (
                  <li key={`${r.name}-${i}`}>
                    <span className="pp-name">
                      {r.name}<span className={`te-src te-${r.source}`}>{r.source}</span>
                    </span>
                    <input className="pp-grams" type="number" min="1"
                      placeholder={`${Math.round(r.serving_g || 100)}g`}
                      value={grams[r.name] ?? ""}
                      onChange={(e) => setGrams((g) => ({ ...g, [r.name]: e.target.value }))} />
                    <button className="pp-add" disabled={busy}
                      onClick={() => addSearchResult(r)}>+ Add</button>
                  </li>
                ))}
              </ul>
            ))}
          </div>
        )}

        {addMode === "manual" && (
          <form className="add-panel manual-form" onSubmit={addManual}>
            <input type="text" placeholder="Food name" value={manual.name}
              onChange={(e) => setManual((m) => ({ ...m, name: e.target.value }))} required />
            <div className="manual-macros">
              {["calories", "protein", "carbs", "fat"].map((k) => (
                <input key={k} type="number" min="0" step="0.1" placeholder={k}
                  value={manual[k]}
                  onChange={(e) => setManual((m) => ({ ...m, [k]: e.target.value }))} />
              ))}
            </div>
            <button type="submit" disabled={busy}>+ Add Entry</button>
          </form>
        )}
      </div>
    </div>
  );
};

export default DailyTrackerTab;
