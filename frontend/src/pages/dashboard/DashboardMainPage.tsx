import React from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";
import AdminDashboardPage from "./AdminDashboardPage";

const DashboardMainPage: React.FC = () => {
  const { user } = useAuthStore();

  // Members go directly to chat; admins see their overview dashboard
  if (user?.role.is_admin) {
    return <AdminDashboardPage />;
  }
  return <Navigate to="/dashboard/chat" replace />;
};

export default DashboardMainPage;
