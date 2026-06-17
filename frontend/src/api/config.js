// Single source of truth for the backend URL.
// Defaults to localhost for dev; override at build time with REACT_APP_API_URL
// (e.g. the deployed backend URL) so deploying needs no code changes.
export const BASE_URL =
  process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";
