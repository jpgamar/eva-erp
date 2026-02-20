import api from "./client";

export const boardsApi = {
  list: () => api.get("/boards").then(r => r.data),
  create: (data: { name: string; description?: string }) => api.post("/boards", data).then(r => r.data),
  get: (id: string) => api.get(`/boards/${id}`).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/boards/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/boards/${id}`).then(r => r.data),
  createColumn: (boardId: string, data: { name: string; color?: string }) =>
    api.post(`/boards/${boardId}/columns`, data).then(r => r.data),
  updateColumn: (columnId: string, data: any) => api.patch(`/boards/columns/${columnId}`, data).then(r => r.data),
  deleteColumn: (columnId: string) => api.delete(`/boards/columns/${columnId}`).then(r => r.data),
};

export const tasksApi = {
  create: (data: any) => api.post("/tasks", data).then(r => r.data),
  get: (id: string) => api.get(`/tasks/${id}`).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/tasks/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/tasks/${id}`).then(r => r.data),
  move: (id: string, data: { column_id: string; position: number }) =>
    api.post(`/tasks/${id}/move`, data).then(r => r.data),
  addComment: (id: string, content: string) => api.post(`/tasks/${id}/comments`, { content }).then(r => r.data),
  myTasks: () => api.get("/tasks/my-tasks").then(r => r.data),
  overdue: () => api.get("/tasks/overdue").then(r => r.data),
};
