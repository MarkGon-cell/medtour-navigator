import axios from "axios";

// Dynamically use current hostname so phones on LAN (e.g. 192.168.x.x) connect to the PC backend on port 8000
const getBaseUrl = () => {
  if (typeof window !== "undefined" && window.location) {
    const hostname = window.location.hostname;
    if (hostname && hostname !== "localhost" && hostname !== "127.0.0.1") {
      // Served over HTTPS (e.g. an ngrok tunnel): call the backend on the
      // same origin — the Vite dev proxy forwards /auth, /hospitals/*, etc.
      // to FastAPI. Avoids mixed-content blocking on the phone.
      if (window.location.protocol === "https:") {
        return "";
      }
      // Plain HTTP over LAN: talk directly to the PC backend on port 8000.
      return `http://${hostname}:8000`;
    }
  }
  return import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
};

const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;