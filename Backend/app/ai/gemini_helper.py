from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# نحاول موديلات بالترتيب لحد ما واحد يشتغل
PREFERRED_MODELS: List[str] = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
]

# How many past messages to feed back as conversation context.
HISTORY_WINDOW = 10


def _is_quota_error(err: Any) -> bool:
    """True when the error means the key is out of quota / rate-limited, so we
    should rotate to the next API key rather than just retry the same one."""
    s = str(err).lower()
    code = getattr(err, "code", None) or getattr(err, "status_code", None)
    return (
        code == 429
        or "resource_exhausted" in s
        or "quota" in s
        or "exhausted" in s
        or "rate limit" in s
        or "429" in s
    )

# ⭐⭐⭐ SYSTEM PROMPT (نسخة احترافية + dynamic meals + RAG) ⭐⭐⭐
SYSTEM_PROMPT = """
You are NutriTech AI — a professional nutrition assistant connected to a FOOD DATABASE.

You ALWAYS prefer database facts over general knowledge.

==============================
🔥 FOOD DATABASE RULES
==============================

If the message includes FOOD DATABASE RESULTS:
- You MUST use the provided nutrition values.
- Do NOT invent macros.
- Do NOT say "approximately".
- Do NOT use external knowledge.

If no foods were found:
- You may use general nutrition knowledge.

Foods are ALWAYS per 100g unless user specifies amount.

==============================
🥗 HOW TO RESPOND
==============================

If user asks about food nutrition:
→ Show calories + protein + carbs + fat clearly.
→ When FOOD DATABASE RESULTS are provided, base your numbers on them.
→ Do NOT claim a source the answer did not use (e.g. when no database
  results were provided, do not say the values come from any database).

If user asks for meal plan:
→ Adapt number of meals based on user request.
→ If user does NOT specify → use:
Breakfast + Lunch + Dinner + 2 Snacks
→ ALWAYS include Daily Total calories & macros.

If user asks for alternatives:
→ Suggest 3–5 alternatives.

Tone:
Friendly, encouraging, short paragraphs.

NEVER say:
"as an AI model"

Always behave as the NutriTech assistant.
""".strip()


@dataclass
class GeminiStatus:
    enabled: bool
    api_key_present: bool
    model: Optional[str]
    ok: bool
    last_error: Optional[str]


class GeminiHelper:
    def __init__(self) -> None:
        load_dotenv()
        # Pool of API keys: GEMINI_API_KEYS (comma-separated) + GEMINI_API_KEY.
        # When one runs out of quota we rotate to the next automatically.
        self.api_keys: List[str] = self._load_keys()
        self.key_idx: int = 0
        # Default to the first preferred model; fall back lazily on real failure
        # (no startup probe -> no quota burned just to boot).
        self.model: str = PREFERRED_MODELS[0]
        self.client: Optional[genai.Client] = None
        self.last_error: Optional[str] = None

        if not self.api_keys:
            self.last_error = "Missing GEMINI_API_KEY"
            logger.warning(self.last_error)
            return

        self._make_client()
        if self.client:
            logger.info(f"✓ Gemini ready → {self.model} "
                        f"({len(self.api_keys)} key(s) in pool)")

    @staticmethod
    def _load_keys() -> List[str]:
        keys: List[str] = []
        for k in (os.getenv("GEMINI_API_KEYS") or "").split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
        single = (os.getenv("GEMINI_API_KEY") or "").strip()
        if single and single not in keys:
            keys.insert(0, single)   # primary key stays first
        return keys

    def _make_client(self) -> None:
        try:
            self.client = genai.Client(api_key=self.api_keys[self.key_idx])
        except Exception as e:
            self.client = None
            self.last_error = f"Init error: {repr(e)}"
            logger.error(self.last_error)

    def _rotate_key(self) -> bool:
        """Switch to the next key in the pool. Returns False if none left."""
        if self.key_idx + 1 >= len(self.api_keys):
            return False
        self.key_idx += 1
        logger.warning(f"Gemini quota hit — rotating to key #{self.key_idx + 1}"
                       f"/{len(self.api_keys)}")
        self._make_client()
        return self.client is not None

    @property
    def api_key(self) -> str:
        """Currently-active key (kept for backward-compat with status())."""
        return self.api_keys[self.key_idx] if self.api_keys else ""

    def status(self) -> GeminiStatus:
        ok = bool(self.client and self.model)
        return GeminiStatus(
            enabled=bool(self.api_keys),
            api_key_present=bool(self.api_keys),
            model=self.model,
            ok=ok,
            last_error=self.last_error,
        )

    # ⭐⭐⭐ الدالة الأهم ⭐⭐⭐
    def generate(
        self,
        user_message: str,
        *,
        facts: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Tuple[Optional[str], bool]:

        if not self.api_keys:
            return None, False
        if self.client is None:
            self._make_client()
            if self.client is None:
                return None, False

        # smart token limits
        if max_tokens is None:
            msg = user_message.lower()
            if "meal plan" in msg or "diet" in msg:
                max_tokens = 4096
            elif "alternatives" in msg:
                max_tokens = 2048
            else:
                max_tokens = 1200

        # 🧠 بناء البرومبت
        parts = [SYSTEM_PROMPT]

        # 🔥 RAG injection (نتائج البحث من الداتا)
        if facts and "foods_found" in facts and facts["foods_found"]:
            foods_text = "\nFOOD DATABASE RESULTS:\n"
            for food in facts["foods_found"]:
                foods_text += (
                    f"- {food['description']} | "
                    f"{food['Calories']} kcal | "
                    f"P:{food['Protein']}g "
                    f"C:{food['Carbs']}g "
                    f"F:{food['Fat']}g\n"
                )
            parts.append(foods_text)

        # 🧠 conversation memory (last HISTORY_WINDOW messages)
        if history:
            parts.append("\nConversation so far:")
            for msg in history[-HISTORY_WINDOW:]:
                role = str(msg.get("role", "user"))
                content = str(msg.get("content", "")).strip()
                if content:
                    parts.append(f"{role}: {content}")

        parts.append(f"\nUser: {user_message}")
        parts.append("Assistant:")

        prompt = "\n".join(parts)
        cfg = types.GenerateContentConfig(
            temperature=temperature, max_output_tokens=max_tokens, top_p=0.95,
            # gemini-2.5-flash is a thinking model: without this it spends part
            # of max_output_tokens on hidden reasoning, truncating the visible
            # reply mid-sentence. 0 disables it; older 2.0 models ignore it.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        # Try every key in the pool; for each key, try preferred models in order.
        for _ in range(len(self.api_keys)):
            text, err = self._generate_once(prompt, cfg)
            if text is not None:
                return text, True
            if _is_quota_error(err) and self._rotate_key():
                continue   # same prompt, next key
            self.last_error = f"Gemini runtime error: {err}"
            logger.error(self.last_error)
            break
        return None, False

    def _generate_once(self, prompt: str, cfg: "types.GenerateContentConfig"):
        """Run the current client across preferred models (current first).
        Returns (text, None) on success or (None, last_error). A quota error is
        returned immediately so the caller can rotate the key."""
        last_err: Any = "no model"
        models = [self.model] + [m for m in PREFERRED_MODELS if m != self.model]
        for m in models:
            try:
                resp = self.client.models.generate_content(
                    model=m, contents=prompt, config=cfg,
                )
                if getattr(resp, "text", None):
                    self.model = m   # remember the working model
                    return resp.text.strip(), None
                last_err = "empty response"
            except Exception as e:
                last_err = e
                if _is_quota_error(e):
                    return None, e          # rotate key, don't try more models
                continue                    # model issue -> try next model
        return None, last_err