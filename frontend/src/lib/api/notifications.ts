import api from "./client";
import type { NotificationListResponse, UnreadCountResponse } from "@/types";

export async function getNotifications(params?: { read?: boolean; limit?: number; offset?: number }) {
  const res = await api.get<NotificationListResponse>("/notifications", { params });
  return res.data;
}

export async function getUnreadCount() {
  const res = await api.get<UnreadCountResponse>("/notifications/unread-count");
  return res.data;
}

export async function markAsRead(id: string) {
  const res = await api.patch(`/notifications/${id}/read`);
  return res.data;
}

export async function markAllAsRead() {
  const res = await api.post("/notifications/mark-all-read");
  return res.data;
}

export async function deleteNotification(id: string) {
  const res = await api.delete(`/notifications/${id}`);
  return res.data;
}
