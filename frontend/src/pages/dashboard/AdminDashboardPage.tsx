import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { adminService } from '../../services/adminService';
import { useAuthStore } from '../../store/authStore';
import { FileText, Users, ShieldCheck } from 'lucide-react';

const AdminDashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const { data: stats, isLoading, isError } = useQuery({
    queryKey: ['adminStats'],
    queryFn: adminService.getStats,
  });

  return (
    <div className="flex flex-col gap-8 max-w-6xl mx-auto w-full">
      <div className="flex flex-col gap-2">
        <h2 className="font-sora text-2xl font-semibold text-slate-800 dark:text-slate-100">
          Welcome back, {user?.full_name}
        </h2>
        <p className="text-slate-500 dark:text-slate-400">
          Here is an overview of your organisation.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Documents Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm flex flex-col gap-4 relative overflow-hidden group">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-lg transition-transform group-hover:scale-110">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="font-medium text-slate-500 dark:text-slate-400">Total Documents</h3>
          </div>
          <div className="mt-2">
            {isLoading ? (
              <div className="h-10 w-24 bg-slate-200 dark:bg-slate-800 animate-pulse rounded"></div>
            ) : isError ? (
              <div className="text-sm text-red-400 dark:text-red-300">Could not load stats</div>
            ) : (
              <span className="text-4xl font-bold text-slate-800 dark:text-slate-100 font-sora">
                {stats?.total_documents || 0}
              </span>
            )}
          </div>
        </div>

        {/* Team Members Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm flex flex-col gap-4 relative overflow-hidden group">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-lg transition-transform group-hover:scale-110">
              <Users className="w-6 h-6" />
            </div>
            <h3 className="font-medium text-slate-500 dark:text-slate-400">Team Members</h3>
          </div>
          <div className="mt-2">
            {isLoading ? (
              <div className="h-10 w-24 bg-slate-200 dark:bg-slate-800 animate-pulse rounded"></div>
            ) : isError ? (
              <div className="text-sm text-red-400 dark:text-red-300">Could not load stats</div>
            ) : (
              <span className="text-4xl font-bold text-slate-800 dark:text-slate-100 font-sora">
                {stats?.total_members || 0}
              </span>
            )}
          </div>
        </div>

        {/* Roles Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm flex flex-col gap-4 relative overflow-hidden group">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-lg transition-transform group-hover:scale-110">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h3 className="font-medium text-slate-500 dark:text-slate-400">Roles</h3>
          </div>
          <div className="mt-2">
            {isLoading ? (
              <div className="h-10 w-24 bg-slate-200 dark:bg-slate-800 animate-pulse rounded"></div>
            ) : isError ? (
              <div className="text-sm text-red-400 dark:text-red-300">Could not load stats</div>
            ) : (
              <span className="text-4xl font-bold text-slate-800 dark:text-slate-100 font-sora">
                {stats?.total_roles || 0}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboardPage;
