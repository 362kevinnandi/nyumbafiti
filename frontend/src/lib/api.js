import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

/**
 * Build an absolute media URL for property images stored on the backend.
 * Accepts paths like "uploads/properties/xyz.jpg" or already-absolute URLs.
 */
export const mediaUrl = (path) => {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  // The K8s ingress only routes /api/* to the backend, so any "uploads/..."
  // path stored on backend must be served via /api/uploads/...
  const clean = path.replace(/^\/+/, "");
  if (clean.startsWith("uploads/")) {
    return `${BACKEND_URL}/api/${clean}`;
  }
  return `${BACKEND_URL}/${clean}`;
};

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Inject token from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("nrm_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response?.status === 401) {
      const path = window.location.pathname;
      if (path !== "/login" && path !== "/register" && path !== "/") {
        localStorage.removeItem("nrm_token");
        localStorage.removeItem("nrm_user");
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export const formatKES = (n) => {
  const num = Number(n || 0);
  return "KES " + num.toLocaleString("en-KE", { maximumFractionDigits: 0 });
};

/**
 * Safely turn an axios error into a string for use in toast messages.
 * Handles FastAPI's 422 shape `{detail: [{msg, loc, ...}, ...]}` which would
 * otherwise crash React if passed directly to a renderer.
 */
export const formatApiError = (err, fallback = "Something went wrong") => {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((x) => {
        if (typeof x === "string") return x;
        if (x?.msg) {
          const loc = Array.isArray(x.loc) ? x.loc.slice(-1)[0] : "";
          return loc ? `${loc}: ${x.msg}` : x.msg;
        }
        return JSON.stringify(x);
      })
      .join("; ");
  }
  try {
    return JSON.stringify(d);
  } catch {
    return fallback;
  }
};
