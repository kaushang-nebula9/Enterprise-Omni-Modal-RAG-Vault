import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useThemeStore } from './store/themeStore';
import AuthLayout from './layouts/AuthLayout';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage';
import ResetPasswordPage from './pages/auth/ResetPasswordPage';
import AcceptInvitePage from './pages/auth/AcceptInvitePage';
import GoogleOrgSetupPage from './pages/auth/GoogleOrgSetupPage';
import AuthGuard from './components/auth/AuthGuard';
import DashboardLayout from './layouts/DashboardLayout';
import ProtectedAdminRoute from './components/auth/ProtectedAdminRoute';
import DashboardMainPage from './pages/dashboard/DashboardMainPage';
import { TeamManagementPage } from './pages/dashboard/TeamManagementPage';
import { RolesPermissionsPage } from './pages/dashboard/RolesPermissionsPage';
import { OrganisationSettingsPage } from './pages/dashboard/OrganisationSettingsPage';
import { ProfileSettingsPage } from './pages/dashboard/ProfileSettingsPage';
import DocumentsPage from './pages/dashboard/DocumentsPage';
import ChatPage from './pages/dashboard/ChatPage';
import YourDocumentsPage from './pages/dashboard/YourDocumentsPage';

const App: React.FC = () => {
  const theme = useThemeStore((state) => state.theme);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  return (
    <BrowserRouter>
      <Routes>
        {/* Public Authentication Routes (Wrapped in split layout) */}
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/accept-invite" element={<AcceptInvitePage />} />
          <Route path="/register/google-org" element={<GoogleOrgSetupPage />} />
        </Route>

        {/* Protected Dashboard Route */}
        <Route
          path="/dashboard"
          element={
            <AuthGuard>
              <DashboardLayout />
            </AuthGuard>
          }
        >
          <Route index element={<DashboardMainPage />} />
          <Route path="documents" element={<ProtectedAdminRoute><DocumentsPage /></ProtectedAdminRoute>} />
          <Route path="team" element={<ProtectedAdminRoute><TeamManagementPage /></ProtectedAdminRoute>} />
          <Route path="roles" element={<ProtectedAdminRoute><RolesPermissionsPage /></ProtectedAdminRoute>} />
          <Route path="settings" element={<ProtectedAdminRoute><OrganisationSettingsPage /></ProtectedAdminRoute>} />
          
          <Route path="chat" element={<ChatPage />} />
          <Route path="your-documents" element={<YourDocumentsPage />} />
          <Route path="profile" element={<ProfileSettingsPage />} />
        </Route>

        {/* Root Redirect to Login */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        
        {/* Fallback Redirect */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
