import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { adminService } from '../../services/adminService';
import { 
  Calendar, 
  History, 
  ChevronLeft, 
  ChevronRight, 
  User, 
  Clock, 
  Info,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  'role.created': { label: 'Role Created', color: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950/20 dark:text-green-400 dark:border-green-900/50' },
  'role.parent_changed': { label: 'Role Parent Changed', color: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/20 dark:text-amber-400 dark:border-amber-900/50' },
  'role.updated': { label: 'Role Updated', color: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/20 dark:text-blue-400 dark:border-blue-900/50' },
  'role.deleted': { label: 'Role Deleted', color: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/20 dark:text-red-400 dark:border-red-900/50' },
  'department.created': { label: 'Department Created', color: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950/20 dark:text-green-400 dark:border-green-900/50' },
  'department.updated': { label: 'Department Updated', color: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/20 dark:text-blue-400 dark:border-blue-900/50' },
  'document.assigned_to_role': { label: 'Doc Assigned to Role', color: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/20 dark:text-purple-400 dark:border-purple-900/50' },
  'document.assigned_to_department': { label: 'Doc Assigned to Dept', color: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/20 dark:text-indigo-400 dark:border-indigo-900/50' },
  'budget_limit.updated': { label: 'Budget Updated', color: 'bg-pink-50 text-pink-700 border-pink-200 dark:bg-pink-950/20 dark:text-pink-400 dark:border-pink-900/50' },
  'default_model.updated': { label: 'Default Model Updated', color: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/20 dark:text-teal-400 dark:border-teal-900/50' },
  'employee.invited': { label: 'Employee Invited', color: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/20 dark:text-emerald-400 dark:border-emerald-900/50' },
  'employee.role_changed': { label: 'Employee Role Changed', color: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/20 dark:text-orange-400 dark:border-orange-900/50' },
};

export const AuditLogPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const limit = 15;
  const offset = (page - 1) * limit;

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ['auditLogs', page, actionFilter, startDate, endDate],
    queryFn: () => adminService.getAuditLogs({
      limit,
      offset,
      action: actionFilter || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined
    }),
    placeholderData: (previousData) => previousData,
  });

  const totalLogs = data?.total || 0;
  const totalPages = Math.ceil(totalLogs / limit) || 1;
  const logs = data?.items || [];

  const handleResetFilters = () => {
    setActionFilter('');
    setStartDate('');
    setEndDate('');
    setPage(1);
  };

  const toggleRow = (id: string) => {
    if (expandedRow === id) {
      setExpandedRow(null);
    } else {
      setExpandedRow(id);
    }
  };

  const formatTimestamp = (isoString: string) => {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short'
    });
  };

  return (
    <div className="flex flex-col gap-6 w-full h-full pb-12 text-slate-800 dark:text-slate-100">
      {/* Header */}
      <div className="flex items-center gap-3 shrink-0">
        <div>
          <h1 className="text-2xl font-bold font-sora">Audit Log</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Track and monitor admin actions that change tenant-wide state
          </p>
        </div>
      </div>

      {/* Filters Section */}
      <section className="">        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          {/* Action Filter */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-500 dark:text-slate-400">Action Type</label>
            <select
              value={actionFilter}
              onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
              className="w-full px-3.5 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-sm focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all cursor-pointer"
            >
              <option value="">All Actions</option>
              {Object.entries(ACTION_LABELS).map(([value, { label }]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {/* Start Date */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-500 dark:text-slate-400">Start Date</label>
            <div className="relative">
              <input
                type="date"
                value={startDate}
                onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
                className="w-full pl-3.5 pr-10 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-sm focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all"
              />
              <Calendar className="absolute right-3 top-2.5 w-4 h-4 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* End Date */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-500 dark:text-slate-400">End Date</label>
            <div className="relative">
              <input
                type="date"
                value={endDate}
                onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
                className="w-full pl-3.5 pr-10 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-sm focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all"
              />
              <Calendar className="absolute right-3 top-2.5 w-4 h-4 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Reset Filters */}
          <div>
            <button
              onClick={handleResetFilters}
              className="w-full sm:w-auto px-4 py-2 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-300 rounded-lg text-sm font-medium transition-colors"
            >
              Reset Filters
            </button>
          </div>
        </div>
      </section>

      {/* Audit Log Table */}
      <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 select-none">
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">Timestamp</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">Actor</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">Action Type</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">Description</th>
                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {isLoading && logs.length === 0 ? (
                // Skeleton Loader
                Array.from({ length: 5 }).map((_, idx) => (
                  <tr key={idx} className="animate-pulse">
                    <td className="px-6 py-4"><div className="h-4 bg-slate-100 dark:bg-slate-800 rounded w-28" /></td>
                    <td className="px-6 py-4"><div className="h-4 bg-slate-100 dark:bg-slate-800 rounded w-24" /></td>
                    <td className="px-6 py-4"><div className="h-6 bg-slate-100 dark:bg-slate-800 rounded-full w-32" /></td>
                    <td className="px-6 py-4"><div className="h-4 bg-slate-100 dark:bg-slate-800 rounded w-64" /></td>
                    <td className="px-6 py-4"><div className="h-4 bg-slate-100 dark:bg-slate-800 rounded w-8 ml-auto" /></td>
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-slate-400 dark:text-slate-500">
                    <div className="flex flex-col items-center gap-2">
                      <History className="w-8 h-8 opacity-40" />
                      <span className="text-sm font-medium">No audit events found</span>
                    </div>
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
                  const actionStyle = ACTION_LABELS[log.action] || { label: log.action, color: 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800/40 dark:text-slate-300 dark:border-slate-800' };
                  const isExpanded = expandedRow === log.id;
                  
                  return (
                    <React.Fragment key={log.id}>
                      <tr className="hover:bg-slate-50/50 dark:hover:bg-slate-800/10 transition-colors">
                        {/* Timestamp */}
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 dark:text-slate-400">
                          <div className="flex items-center gap-2">
                            <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <span>{formatTimestamp(log.created_at)}</span>
                          </div>
                        </td>
                        {/* Actor */}
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-700 dark:text-slate-300">
                          <div className="flex items-center gap-2">
                            <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <span>{log.actor_name}</span>
                          </div>
                        </td>
                        {/* Action Type */}
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${actionStyle.color}`}>
                            {actionStyle.label}
                          </span>
                        </td>
                        {/* Description */}
                        <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-300 font-medium">
                          {log.description}
                        </td>
                        {/* Details Toggle */}
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                          {log.metadata ? (
                            <button
                              onClick={() => toggleRow(log.id)}
                              className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 p-1.5 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-950/20 transition-all inline-flex items-center gap-1"
                            >
                              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </button>
                          ) : (
                            <span className="text-xs text-slate-400 dark:text-slate-600 select-none">-</span>
                          )}
                        </td>
                      </tr>
                      {/* Expanded Metadata Row */}
                      {isExpanded && log.metadata && (
                        <tr className="bg-slate-50/40 dark:bg-slate-900/40">
                          <td colSpan={5} className="px-8 py-4 border-t border-slate-100 dark:border-slate-800/40">
                            <div className="flex gap-2.5 text-xs text-slate-500 dark:text-slate-400 font-semibold mb-2 items-center">
                              <Info className="w-3.5 h-3.5 text-indigo-500" />
                              <span>Event Metadata</span>
                            </div>
                            <pre className="text-xs font-mono p-3 bg-slate-100/60 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/80 rounded-lg text-slate-700 dark:text-slate-300 overflow-x-auto max-w-full">
                              {JSON.stringify(log.metadata, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/20 dark:bg-slate-900/10 flex items-center justify-between select-none">
            <span className="text-sm text-slate-500 dark:text-slate-400">
              Showing page <span className="font-semibold text-slate-700 dark:text-slate-300">{page}</span> of{' '}
              <span className="font-semibold text-slate-700 dark:text-slate-300">{totalPages}</span>
            </span>
            
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1 || isLoading}
                className="p-2 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:pointer-events-none transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || isLoading || isPlaceholderData}
                className="p-2 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:pointer-events-none transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

export default AuditLogPage;
