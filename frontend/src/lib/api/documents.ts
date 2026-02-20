import api from "./client";

export const foldersApi = {
  list: (parentId?: string) => api.get("/documents/folders", { params: { parent_id: parentId } }).then(r => r.data),
  create: (data: { name: string; parent_id?: string }) => api.post("/documents/folders", data).then(r => r.data),
  delete: (id: string) => api.delete(`/documents/folders/${id}`).then(r => r.data),
};

export const documentsApi = {
  list: (params?: { folder_id?: string; search?: string }) => api.get("/documents", { params }).then(r => r.data),
  upload: (formData: FormData) => api.post("/documents/upload", formData, { headers: { "Content-Type": "multipart/form-data" } }).then(r => r.data),
  delete: (id: string) => api.delete(`/documents/${id}`).then(r => r.data),
};
