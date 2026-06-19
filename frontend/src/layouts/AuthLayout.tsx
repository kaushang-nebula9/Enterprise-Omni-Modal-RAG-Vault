import React from 'react';
import { Outlet } from 'react-router-dom';
import AuthLeftPanel from '../components/auth/AuthLeftPanel';
import ThemeToggle from '../components/shared/ThemeToggle';

const AuthLayout: React.FC = () => {
  return (
    <div className="flex min-h-screen w-full font-sans bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-100">
      {/* Left panel: visible on desktop, hidden on mobile */}
      <div className="hidden w-1/2 md:block">
        <AuthLeftPanel />
      </div>

      {/* Right panel: centers contents, full width on mobile, 1/2 on desktop */}
      <div className="relative flex w-full flex-col justify-center bg-white dark:bg-slate-950 md:w-1/2 min-h-screen">
        <div className="absolute top-4 right-4 z-50">
          <ThemeToggle />
        </div>
        <div className="mx-auto w-full max-w-md px-6 py-12 md:px-8">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;
