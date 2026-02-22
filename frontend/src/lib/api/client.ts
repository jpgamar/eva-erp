import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Intercept 401s and try to refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        await axios.post("/api/v1/auth/refresh", {}, { withCredentials: true });
        return api(originalRequest);
      } catch {
        // Refresh failed — let the (app) layout handle the unauthenticated state.
        // Never hard-redirect here; the AuthProvider will detect user=null and redirect.
      }
    }

    return Promise.reject(error);
  }
);

export default api;
