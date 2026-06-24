import React, { useState } from "react";
import { humanize } from "../constants/nutrition";

// One meal slot's card: component list with an optional per-item swap button,
// a macro breakdown toggle, and a macro footer. Shared by the daily and weekly
// planner views.
const COMPONENT_KEYS = ["main", "side", "optional", "extra"];

const MealCard = ({ slot, meal, onSwap }) => {
  const [expanded, setExpanded] = useState(false);

  const items = COMPONENT_KEYS.map((k) => meal[k]).filter(Boolean);
  const sum = (f) => items.reduce((s, it) => s + (it[f] || 0), 0);

  return (
    <div className="meal-card">
      <div className="meal-card-header">
        <span className="meal-slot-badge">{humanize(slot).toUpperCase()}</span>
      </div>

      <ul className="meal-components">
        {items.map((it, i) => (
          <li key={i} className="component-row">
            <div className="component-main">
              <span className="component-grams">{Math.round(it.grams)}g</span>
              <span className="component-name">{it.name}</span>
              {onSwap && (
                <button className="swap-btn" title="Swap this food"
                  onClick={() => onSwap(it.name)}>
                  ⇄
                </button>
              )}
            </div>
            {expanded && (
              <div className="component-macros">
                <span>{Math.round(it.calories)} kcal</span>
                <span>P {Math.round(it.protein)}g</span>
                <span>C {Math.round(it.carbs)}g</span>
                <span>F {Math.round(it.fat)}g</span>
              </div>
            )}
          </li>
        ))}
      </ul>

      <button className="view-more-btn" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Hide breakdown ▲" : "View breakdown ▼"}
      </button>

      <div className="meal-macros">
        <div className="macro">
          <span className="val">{Math.round(meal.total_calories)}</span>
          <span className="lbl">Kcal</span>
        </div>
        <div className="macro">
          <span className="val">{Math.round(sum("protein"))}g</span>
          <span className="lbl">Protein</span>
        </div>
        <div className="macro">
          <span className="val">{Math.round(sum("carbs"))}g</span>
          <span className="lbl">Carbs</span>
        </div>
        <div className="macro">
          <span className="val">{Math.round(sum("fat"))}g</span>
          <span className="lbl">Fats</span>
        </div>
      </div>
    </div>
  );
};

export default MealCard;
