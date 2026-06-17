import { BASE_URL } from "./config";

export async function register(name, email, password) {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });

  if (!res.ok) {
    const errorData = await res.json();
    throw new Error(parseError(errorData));
  }

  return await res.json();
}

// FastAPI returns `detail` as a string (HTTPException) or an array of
// validation errors (422). Normalize both to a readable message.
function parseError(data) {
  const d = data && data.detail;
  if (Array.isArray(d)) {
    return d.map((e) => (e.msg || "").replace(/^Value error,\s*/, "")).join(" ");
  }
  return d || "Server error";
}

export async function login(email, password) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `username=${email}&password=${password}`,
  });

  if (!res.ok) {
    const errorData = await res.json();
    throw new Error(errorData.detail || "Server error");
  }

  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
  window.dispatchEvent(new Event("authchange"));
}

export function getToken() {
  return localStorage.getItem("token");
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// GET /auth/me — current user incl. is_premium (null when not logged in).
export async function getCurrentUser() {
  if (!getToken()) return null;
  const res = await fetch(`${BASE_URL}/auth/me`, { headers: authHeaders() });
  if (!res.ok) return null;
  return res.json();
}

// POST /auth/subscribe — mock upgrade to Premium. Returns the updated user.
export async function subscribe() {
  const res = await fetch(`${BASE_URL}/auth/subscribe`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Subscription failed");
  }
  const user = await res.json();
  window.dispatchEvent(new Event("authchange"));
  return user;
}

// POST /auth/unsubscribe — drop back to Free (handy for demoing the lock).
export async function unsubscribe() {
  const res = await fetch(`${BASE_URL}/auth/unsubscribe`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Request failed");
  }
  const user = await res.json();
  window.dispatchEvent(new Event("authchange"));
  return user;
}
