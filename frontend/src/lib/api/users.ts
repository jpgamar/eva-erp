import api from "./client";

export const usersApi = {
  list: () => api.get("/users").then(r => r.data),
  invite: (data: { email: string; name: string; role?: string }) =>
    api.post("/users/invite", data).then(r => r.data),
  update: (id: string, data: { role?: string; is_active?: boolean }) =>
    api.patch(`/users/${id}`, data).then(r => r.data),
  deactivate: (id: string) => api.delete(`/users/${id}`).then(r => r.data),
};
