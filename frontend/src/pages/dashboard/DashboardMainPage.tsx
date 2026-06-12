import React from 'react';
import { useAuthStore } from '../../store/authStore';
import AdminDashboardPage from './AdminDashboardPage';
import MemberDashboardPage from './MemberDashboardPage';

const DashboardMainPage: React.FC = () => {
  const { user } = useAuthStore();
  
  // Conditionally render based on admin status
  if (user?.role.is_admin) {
    return <AdminDashboardPage />;
  }
  return <MemberDashboardPage />;
};

export default DashboardMainPage;
