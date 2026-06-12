import React from 'react';
import { Outlet } from 'react-router-dom';
import AuthLeftPanel from '../components/auth/AuthLeftPanel';

const AuthLayout: React.FC = () => {
  return (
    <div className="flex min-h-screen w-full font-sans bg-white text-slate-800">
      {/* Left panel: visible on desktop, hidden on mobile */}
      <div className="hidden w-1/2 md:block">
        <AuthLeftPanel />
      </div>

      {/* Right panel: centers contents, full width on mobile, 1/2 on desktop */}
      <div className="flex w-full flex-col justify-center bg-white md:w-1/2 min-h-screen">
        <div className="mx-auto w-full max-w-md px-6 py-12 md:px-8">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;
