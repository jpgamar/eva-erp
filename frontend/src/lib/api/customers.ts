import api from "./client";

export const customersApi = {
  list: (params?: { status?: string; search?: string }) =>
    api.get("/customers", { params }).then(r => r.data),
};
