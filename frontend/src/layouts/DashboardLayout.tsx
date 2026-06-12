import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/dashboard/Sidebar';
import TopNavbar from '../components/dashboard/TopNavbar';

const DashboardLayout: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-inter">
      <Sidebar isExpanded={isExpanded} toggleSidebar={() => setIsExpanded(!isExpanded)} />
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
