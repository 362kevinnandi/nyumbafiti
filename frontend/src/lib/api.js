import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

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
