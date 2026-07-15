import React from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";

interface ProtectedMemberRouteProps {
  children: React.ReactNode;
}

const ProtectedMemberRoute: React.FC<ProtectedMemberRouteProps> = ({
  children,
}) => {
  const { user } = useAuthStore();

  if (user && user.role.is_admin) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export default ProtectedMemberRoute;
