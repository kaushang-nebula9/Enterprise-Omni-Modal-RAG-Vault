import api from "./api";
import type { Notification } from "../types/notification";

export const getNotifications = async (): Promise<Notification[]> => {
  const response = await api.get<Notification[]>("/api/v1/notifications");
  return response.data;
};

export const markNotificationsRead = async (): Promise<{ message: string }> => {
  const response = await api.patch<{ message: string }>(
    "/api/v1/notifications/mark-read",
  );
  return response.data;
};
