"use client";

import { useEffect, useState } from "react";
import { Bell, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { getNotifications, getUnreadCount, markAsRead, markAllAsRead } from "@/lib/api/notifications";
import type { Notification } from "@/types";

export function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);

  const fetchUnreadCount = async () => {
    try {
      const data = await getUnreadCount();
      setUnreadCount(data.count);
    } catch {
      // Silently fail
    }
  };

  const fetchNotifications = async () => {
    try {
      const data = await getNotifications({ limit: 10 });
      setNotifications(data.items);
    } catch {
      // Silently fail
    }
  };

  // Poll unread count every 30 seconds
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch full list when dropdown opens
  useEffect(() => {
    if (open) fetchNotifications();
  }, [open]);

  const handleMarkRead = async (id: string) => {
    await markAsRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));
  };

  const handleMarkAllRead = async () => {
    await markAllAsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);
  };

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative h-9 w-9">
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 min-w-5 px-1 text-[10px] flex items-center justify-center"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-h-96 overflow-y-auto">
        <div className="flex items-center justify-between px-3 py-2 border-b">
          <span className="text-sm font-semibold">Notifications</span>
          {unreadCount > 0 && (
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={handleMarkAllRead}>
              <Check className="h-3 w-3 mr-1" />
              Mark all read
            </Button>
          )}
        </div>

        {notifications.length === 0 ? (
          <div className="px-3 py-6 text-center text-sm text-muted-foreground">
            No notifications yet
          </div>
        ) : (
          notifications.map((notification) => (
            <DropdownMenuItem
              key={notification.id}
              className="flex flex-col items-start gap-1 px-3 py-2 cursor-pointer"
              onClick={() => {
                if (!notification.read) handleMarkRead(notification.id);
                if (notification.link) window.location.href = notification.link;
              }}
            >
              <div className="flex items-center gap-2 w-full">
                {!notification.read && (
                  <div className="h-2 w-2 rounded-full bg-primary shrink-0" />
                )}
                <span className="text-sm font-medium truncate">{notification.title}</span>
                <span className="text-xs text-muted-foreground ml-auto shrink-0">
                  {timeAgo(notification.created_at)}
                </span>
              </div>
              <span className="text-xs text-muted-foreground line-clamp-2">
                {notification.body}
              </span>
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
