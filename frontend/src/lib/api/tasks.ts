import api from "./client";

export const boardsApi = {
  list: () => api.get("/boards").then(r => r.data),
  create: (data: { name: string; description?: string }) => api.post("/boards", data).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/boards/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/boards/${id}`).then(r => r.data),
};

export const tasksApi = {
  list: (params?: { status?: string; board_id?: string; assignee_id?: string; priority?: string }) =>
    api.get("/tasks", { params }).then(r => r.data),
  create: (data: any) => api.post("/tasks", data).then(r => r.data),
  get: (id: string) => api.get(`/tasks/${id}`).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/tasks/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/tasks/${id}`).then(r => r.data),
  addComment: (id: string, content: string) => api.post(`/tasks/${id}/comments`, { content }).then(r => r.data),
  myTasks: () => api.get("/tasks/my-tasks").then(r => r.data),
  overdue: () => api.get("/tasks/overdue").then(r => r.data),
};
