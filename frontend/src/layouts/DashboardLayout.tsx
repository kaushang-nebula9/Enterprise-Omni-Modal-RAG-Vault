import React, { useState, useEffect } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/dashboard/Sidebar";
import TopNavbar from "../components/dashboard/TopNavbar";
import { useNotificationStore } from "../store/notificationStore";

const DashboardLayout: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(true);
  const { fetchNotifications, connectSSE, disconnectSSE } =
    useNotificationStore();

  useEffect(() => {
    fetchNotifications();
    connectSSE();
    return () => {
      disconnectSSE();
    };
  }, [fetchNotifications, connectSSE, disconnectSSE]);

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden font-inter">
      <Sidebar
        isExpanded={isExpanded}
        toggleSidebar={() => setIsExpanded(!isExpanded)}
      />
      <div className="flex flex-col flex-1 min-w-0">
        <TopNavbar />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
