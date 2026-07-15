import { create } from "zustand";
import type { Notification } from "../types/notification";
import {
  getNotifications,
  markNotificationsRead,
} from "../services/notificationService";

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  eventSource: EventSource | null;
  fetchNotifications: () => Promise<void>;
  markAllAsRead: () => Promise<void>;
  connectSSE: () => void;
  disconnectSSE: () => void;
  addNotification: (notif: Notification) => void;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const useNotificationStore = create<NotificationState>((set, get) => {
  let reconnectTimeout: any = null;
  let isDisconnecting = false;

  const establishConnection = () => {
    if (get().eventSource) return;

    isDisconnecting = false;
    const url = `${BASE_URL}/api/v1/notifications/stream`;
    const es = new EventSource(url, { withCredentials: true });

    es.onopen = () => {
      console.log("SSE notification connection established.");
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
    };

    es.onmessage = (event) => {
      try {
        const notif = JSON.parse(event.data);
        get().addNotification(notif);
      } catch (err) {
        console.error("Failed to parse incoming SSE notification message", err);
      }
    };

    es.onerror = (err) => {
      console.error("SSE notification connection error:", err);
      es.close();
      set({ eventSource: null });

      // Auto-reconnect on drop, unless explicitly disconnected
      if (!isDisconnecting) {
        console.log("Attempting to reconnect SSE in 5 seconds...");
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(() => {
          establishConnection();
        }, 5000);
      }
    };

    set({ eventSource: es });
  };

  return {
    notifications: [],
    unreadCount: 0,
    eventSource: null,

    fetchNotifications: async () => {
      try {
        const list = await getNotifications();
        const unread = list.filter((n) => !n.is_read).length;
        set({ notifications: list, unreadCount: unread });
      } catch (err) {
        console.error("Failed to fetch notification history:", err);
      }
    },

    markAllAsRead: async () => {
      try {
        await markNotificationsRead();
        set((state) => ({
          notifications: state.notifications.map((n) => ({
            ...n,
            is_read: true,
          })),
          unreadCount: 0,
        }));
      } catch (err) {
        console.error("Failed to mark notifications as read:", err);
      }
    },

    addNotification: (notif: Notification) => {
      set((state) => {
        // Prevent duplicate additions in case of reconnects/multiple delivers
        if (state.notifications.some((n) => n.id === notif.id)) {
          return {};
        }
        return {
          notifications: [notif, ...state.notifications],
          unreadCount: state.unreadCount + (notif.is_read ? 0 : 1),
        };
      });
    },

    connectSSE: () => {
      establishConnection();
    },

    disconnectSSE: () => {
      isDisconnecting = true;
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      const es = get().eventSource;
      if (es) {
        es.close();
        set({ eventSource: null });
      }
    },
  };
});
