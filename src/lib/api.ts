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
  // Without a timeout a hung backend leaves the caller spinning forever --
  // and in the walk-in triage that also leaves `isAnalyzing` stuck on, which
  // disables every button in the symptom box.
  timeout: 30000,
});

api.interceptors.request.use(
  (config) => {
    // The /doctor/* namespace is the doctor portal: it authenticates with its
    // own JWT (issued by /doctor/auth/login) so a patient token can never hit
    // the diagnosis endpoints and vice versa.
    const isDoctorRoute =
      typeof config.url === "string" && config.url.startsWith("/doctor");
    const token = isDoctorRoute
      ? localStorage.getItem("doctor_access_token")
      : localStorage.getItem("access_token");

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