import axios from "axios";

// Use relative URL so Vite proxy forwards requests to FastAPI (127.0.0.1:8000).
// This guarantees that mobile devices connecting to http://192.168.x.x:8080 work seamlessly
// without needing port 8000 exposed on the LAN or blocked by Windows Firewall.
const getBaseUrl = () => {
  if (typeof window !== "undefined") {
    return "";
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