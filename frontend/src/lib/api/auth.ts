import api from "./client";
import type { User } from "@/types";

export async function login(email: string, password: string) {
  const res = await api.post("/auth/login", { email, password });
  return res.data;
}

export async function logout() {
  await api.post("/auth/logout");
}

export async function getMe(): Promise<User> {
  const res = await api.get("/auth/me");
  return res.data;
}

export async function updateProfile(data: { name?: string; avatar_url?: string }) {
  const res = await api.patch("/auth/me", data);
  return res.data;
}

export async function changePassword(currentPassword: string, newPassword: string) {
  const res = await api.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return res.data;
}
