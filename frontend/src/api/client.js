// Shared API client: one BASE_URL + one auth-aware request() helper.
import { getToken } from "./authApi";
import { BASE_URL } from "./config";

export { BASE_URL };

export async function request(endpoint, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });

  if (!res.ok) {
    let detail = "Server error";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  // 204 / empty bodies
  if (res.status === 204) return null;
  return res.json();
}
