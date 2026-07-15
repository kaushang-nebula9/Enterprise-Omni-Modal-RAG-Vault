import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { 
  Search, 
  Download, 
  RefreshCw, 
  Trash2, 
  ExternalLink, 
  FileText, 
  ChevronDown, 
  ChevronUp, 
  Loader2, 
  X,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react';
import { listReports, deleteReport, retryReport, downloadReport, getReportStatus } from '../../services/reportService';
import type { ReportStatus } from '../../types/chat';

export const ReportsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const preSelectedSessionId = searchParams.get('session_id');

  const [reports, setReports] = useState<ReportStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & search states
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'generating' | 'complete' | 'failed'>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'Documents' | 'Database' | 'Mixed'>('all');

  // Expanded report details
  const [expandedReportId, setExpandedReportId] = useState<string | null>(null);
  
  // Deletion state
  const [reportToDelete, setReportToDelete] = useState<ReportStatus | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Polling tracker
  const pollingIntervalsRef = useRef<{ [reportId: string]: number }>({});

  // Dropdown states & refs
  const [isStatusDropdownOpen, setIsStatusDropdownOpen] = useState(false);
  const [isTypeDropdownOpen, setIsTypeDropdownOpen] = useState(false);
  const statusDropdownRef = useRef<HTMLDivElement>(null);
  const typeDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        statusDropdownRef.current &&
        !statusDropdownRef.current.contains(event.target as Node)
      ) {
        setIsStatusDropdownOpen(false);
      }
      if (
        typeDropdownRef.current &&
        !typeDropdownRef.current.contains(event.target as Node)
      ) {
        setIsTypeDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Load initial reports
  const fetchReports = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await listReports();
      setReports(data);
    } catch (err: any) {
      console.error('Failed to load reports:', err);
      setError('Failed to load reports. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  // Polling logic for generating reports
  const startPollingForReport = (reportId: string) => {
    if (pollingIntervalsRef.current[reportId]) return;

    const interval = window.setInterval(async () => {
      try {
        const updated = await getReportStatus(reportId);
        setReports((prev) =>
          prev.map((r) => (r.report_id === reportId ? updated : r))
        );
        if (updated.status === 'complete' || updated.status === 'failed') {
          stopPollingForReport(reportId);
        }
      } catch (err) {
        console.error(`Error polling status for report ${reportId}:`, err);
      }
    }, 3000);

    pollingIntervalsRef.current[reportId] = interval;
  };

  const stopPollingForReport = (reportId: string) => {
    if (pollingIntervalsRef.current[reportId]) {
      clearInterval(pollingIntervalsRef.current[reportId]);
      delete pollingIntervalsRef.current[reportId];
    }
  };

  // Run pollers based on report statuses
  useEffect(() => {
    reports.forEach((r) => {
      if (r.status === 'generating') {
        startPollingForReport(r.report_id);
      } else {
        stopPollingForReport(r.report_id);
      }
    });

    return () => {
      // Clear pollers on unmount
      Object.keys(pollingIntervalsRef.current).forEach((id) => {
        clearInterval(pollingIntervalsRef.current[id]);
      });
      pollingIntervalsRef.current = {};
    };
  }, [reports]);

  // Clean pre-selected session id filter
  const clearSessionFilter = () => {
    const params = new URLSearchParams(searchParams);
    params.delete('session_id');
    setSearchParams(params);
  };

  // Find the session title of pre-selected session
  const preSelectedSessionTitle = useMemo(() => {
    if (!preSelectedSessionId) return '';
    const report = reports.find(r => r.session_id === preSelectedSessionId);
    return report?.session_title || 'Session';
  }, [preSelectedSessionId, reports]);

  // Actions
  const handleDownload = async (reportId: string, title: string) => {
    try {
      const blob = await downloadReport(reportId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${title.replace(/\s+/g, '_')}_report.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert('Failed to download report. ' + (err.message || ''));
    }
  };

  const handleRetry = async (reportId: string) => {
    try {
      setError(null);
      // Optimistically set the status to generating in the table row
      setReports((prev) =>
        prev.map((r) =>
          r.report_id === reportId
            ? { ...r, status: 'generating', title: 'Generating...', steps: [] }
            : r
        )
      );
      await retryReport(reportId);
    } catch (err: any) {
      console.error('Failed to retry report:', err);
      // Reload on failure
      fetchReports();
    }
  };

  const handleDelete = async () => {
    if (!reportToDelete) return;
    setIsDeleting(true);
    try {
      await deleteReport(reportToDelete.report_id);
      setReports((prev) => prev.filter((r) => r.report_id !== reportToDelete.report_id));
      if (expandedReportId === reportToDelete.report_id) {
        setExpandedReportId(null);
      }
      setReportToDelete(null);
    } catch (err: any) {
      alert('Failed to delete report. ' + (err.message || ''));
    } finally {
      setIsDeleting(false);
    }
  };

  // Filtered reports calculation
  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      // 1. Session Filter
      if (preSelectedSessionId && r.session_id !== preSelectedSessionId) {
        return false;
      }
      // 2. Search Query (Title or Session Name)
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesTitle = r.title.toLowerCase().includes(query);
        const matchesSession = (r.session_title || '').toLowerCase().includes(query);
        if (!matchesTitle && !matchesSession) return false;
      }
      // 3. Status Filter
      if (statusFilter !== 'all' && r.status !== statusFilter) {
        return false;
      }
      // 4. Source Type Filter
      if (typeFilter !== 'all' && r.source_type !== typeFilter) {
        return false;
      }
      return true;
    });
  }, [reports, searchQuery, statusFilter, typeFilter, preSelectedSessionId]);

  // Date formatter
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Format Duration helper
  const formatDuration = (ms: number | null) => {
    if (ms === null || ms === undefined) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className="flex flex-col gap-6 h-full text-slate-800 dark:text-slate-100">
      
      {/* Header */}
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h2 className="text-2xl font-bold font-sora tracking-tight text-slate-900 dark:text-slate-100">
            Reports
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            View, download, and manage your custom structured documents generated from chat conversations.
          </p>
        </div>
      </div>

      {/* Pre-filtered by session alert */}
      {preSelectedSessionId && (
        <div className="bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/60 rounded-xl p-3.5 flex items-center justify-between shadow-sm shrink-0">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-indigo-600 dark:bg-indigo-400 animate-pulse" />
            <p className="text-sm font-medium text-indigo-950 dark:text-indigo-200">
              Only showing reports generated from: <span className="font-bold underline">{preSelectedSessionTitle}</span>
            </p>
          </div>
          <button
            onClick={clearSessionFilter}
            className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 font-bold bg-white dark:bg-slate-900 border border-indigo-200 dark:border-indigo-800 hover:bg-slate-50 rounded-lg px-2.5 py-1 transition-all select-none shadow-sm cursor-pointer"
          >
            Clear Filter
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Filters and Controls */}
      <div className=" flex flex-col md:flex-row md:items-center justify-between gap-3">
        
        {/* Search */}
        <div className="relative w-full flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search report title or session name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-colors"
          />
        </div>
        
        <div className="hidden lg:block w-px h-8 bg-slate-200 dark:bg-slate-800 shrink-0"></div>

        {/* Select filters */}
        <div className="flex flex-wrap items-center gap-3">
          
          {/* Status filter */}
          <div className="relative inline-block text-left" ref={statusDropdownRef}>
            <button
              onClick={() => setIsStatusDropdownOpen(!isStatusDropdownOpen)}
              type="button"
              className="inline-flex items-center justify-between gap-2 px-3.5 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[140px] cursor-pointer shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span>
                  {statusFilter === 'all' && 'All Statuses'}
                  {statusFilter === 'complete' && 'Complete'}
                  {statusFilter === 'generating' && 'Generating'}
                  {statusFilter === 'failed' && 'Failed'}
                </span>
              </div>
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isStatusDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isStatusDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-44 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1">
                {(['all', 'complete', 'generating', 'failed'] as const).map((statusVal) => (
                  <button
                    key={statusVal}
                    onClick={() => {
                      setStatusFilter(statusVal);
                      setIsStatusDropdownOpen(false);
                    }}
                    type="button"
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                      statusFilter === statusVal ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15' : 'text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {statusVal === 'all' && 'All Statuses'}
                    {statusVal === 'complete' && 'Complete'}
                    {statusVal === 'generating' && 'Generating'}
                    {statusVal === 'failed' && 'Failed'}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Type filter */}
          <div className="relative inline-block text-left" ref={typeDropdownRef}>
            <button
              onClick={() => setIsTypeDropdownOpen(!isTypeDropdownOpen)}
              type="button"
              className="inline-flex items-center justify-between gap-2 px-3.5 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[160px] cursor-pointer shadow-sm"
            >
              <span>
                {typeFilter === 'all' && 'All Source Types'}
                {typeFilter === 'Documents' && 'Documents Only'}
                {typeFilter === 'Database' && 'Database Only'}
                {typeFilter === 'Mixed' && 'Mixed'}
              </span>
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isTypeDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isTypeDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1">
                {(['all', 'Documents', 'Database', 'Mixed'] as const).map((typeVal) => (
                  <button
                    key={typeVal}
                    onClick={() => {
                      setTypeFilter(typeVal);
                      setIsTypeDropdownOpen(false);
                    }}
                    type="button"
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors ${
                      typeFilter === typeVal ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15' : 'text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {typeVal === 'all' && 'All Source Types'}
                    {typeVal === 'Documents' && 'Documents Only'}
                    {typeVal === 'Database' && 'Database Only'}
                    {typeVal === 'Mixed' && 'Mixed'}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 min-h-0 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-400">
            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
            <span className="text-sm mt-3 font-medium">Loading reports...</span>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <AlertCircle className="w-10 h-10 text-rose-500" />
            <h3 className="text-lg font-semibold text-slate-950 dark:text-slate-200 mt-3">An error occurred</h3>
            <p className="text-sm text-slate-500 max-w-sm mt-1">{error}</p>
            <button
              onClick={fetchReports}
              className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow transition-all cursor-pointer"
            >
              Try Again
            </button>
          </div>
        ) : filteredReports.length === 0 ? (
          /* Empty State */
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center max-w-md mx-auto">
            <div className="w-16 h-16 rounded-full bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 flex items-center justify-center shadow-sm shrink-0">
              <FileText className="w-8 h-8 text-slate-400" />
            </div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-4 font-sora">
              No reports found
            </h3>
            {reports.length === 0 ? (
              <>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">
                  Reports are high-quality PDF summaries generated from your database connections and documents by the Report Generation Agent.
                </p>
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 leading-normal">
                  To create a report, click the "Create Report" button in any chat session.
                </p>
                <button
                  onClick={() => navigate('/dashboard/chat')}
                  className="mt-5 px-5 py-2.5 bg-[#1e3a5f] hover:bg-[#152a45] dark:bg-indigo-500 dark:hover:bg-indigo-400 text-white dark:text-slate-900 rounded-xl text-sm font-bold shadow-md transition-all cursor-pointer select-none"
                >
                  Start a Chat Session
                </button>
              </>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                No reports match your current search queries or filters. Try adjusting them.
              </p>
            )}
          </div>
        ) : (
          /* Table list view */
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 select-none text-xs font-bold text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-4">Report Title</th>
                  <th className="px-6 py-4">Source Session</th>
                  <th className="px-6 py-4">Source Type</th>
                  <th className="px-6 py-4">Created At</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredReports.map((report) => {
                  const isExpanded = expandedReportId === report.report_id;
                  
                  return (
                    <React.Fragment key={report.report_id}>
                      {/* Row Item */}
                      <tr 
                        onClick={() => setExpandedReportId(isExpanded ? null : report.report_id)}
                        className={`hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-all cursor-pointer select-none ${isExpanded ? 'bg-indigo-50/20 dark:bg-indigo-950/10' : ''}`}
                      >
                        {/* Title */}
                        <td className="px-6 py-4 font-semibold text-sm text-slate-900 dark:text-slate-100 max-w-[280px] truncate">
                          <div className="flex items-center gap-2">
                            {isExpanded ? <ChevronUp className="w-4 h-4 text-indigo-500 shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />}
                            <span className="truncate">{report.title}</span>
                          </div>
                        </td>

                        {/* Source Session */}
                        <td className="px-6 py-4 text-sm text-indigo-600 dark:text-indigo-400 font-medium">
                          <Link
                            to={`/dashboard/chat?session=${report.session_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1 hover:underline cursor-pointer"
                          >
                            <span className="max-w-[200px] truncate">{report.session_title || 'Session'}</span>
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        </td>

                        {/* Source Type Badge */}
                        <td className="px-6 py-4 text-sm">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                            report.source_type === 'Documents' 
                              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/40' 
                              : report.source_type === 'Database' 
                                ? 'bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-400 border border-sky-100 dark:border-sky-900/40' 
                                : 'bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400 border border-purple-100 dark:border-purple-900/40'
                          }`}>
                            {report.source_type}
                          </span>
                        </td>

                        {/* Created At */}
                        <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">
                          {formatDate(report.created_at)}
                        </td>

                        {/* Status Badge */}
                        <td className="px-6 py-4 text-sm">
                          {report.status === 'generating' ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400 border border-amber-100 dark:border-amber-900/30">
                              <Loader2 className="w-3 h-3 animate-spin text-amber-600 dark:text-amber-400" />
                              Generating
                            </span>
                          ) : report.status === 'complete' ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30">
                              <CheckCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                              Complete
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-400 border border-rose-100 dark:border-rose-900/30">
                              <XCircle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
                              Failed
                            </span>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="px-6 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-2.5">
                            {/* Download Action */}
                            {report.status === 'complete' && (
                              <button
                                onClick={() => handleDownload(report.report_id, report.title)}
                                className="p-1.5 rounded-lg border border-slate-200 hover:border-indigo-500 hover:bg-indigo-50 text-slate-500 hover:text-indigo-600 dark:border-slate-800 dark:hover:border-indigo-500 dark:hover:bg-indigo-950/40 dark:text-slate-400 dark:hover:text-indigo-400 transition-all cursor-pointer shadow-sm"
                                title="Download Report PDF"
                              >
                                <Download className="w-4 h-4" />
                              </button>
                            )}

                            {/* Retry Action */}
                            {report.status === 'failed' && (
                              <button
                                onClick={() => handleRetry(report.report_id)}
                                className="p-1.5 rounded-lg border border-slate-200 hover:border-amber-500 hover:bg-amber-50 text-slate-500 hover:text-amber-600 dark:border-slate-800 dark:hover:border-amber-500 dark:hover:bg-amber-950/40 dark:text-slate-400 dark:hover:text-amber-400 transition-all cursor-pointer shadow-sm"
                                title="Retry Report Generation"
                              >
                                <RefreshCw className="w-4 h-4" />
                              </button>
                            )}

                            {/* Delete Action */}
                            <button
                              onClick={() => setReportToDelete(report)}
                              className="p-1.5 rounded-lg border border-slate-200 hover:border-red-500 hover:bg-red-50 text-slate-500 hover:text-red-600 dark:border-slate-800 dark:hover:border-red-500 dark:hover:bg-red-950/40 dark:text-slate-400 dark:hover:text-red-400 transition-all cursor-pointer shadow-sm"
                              title="Delete Report"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Detail Expansion Panel */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={6} className="bg-slate-50/50 dark:bg-slate-950/30 p-6 border-b border-slate-200 dark:border-slate-800">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 text-left">
                              
                              {/* Left Info Panel */}
                              <div className="flex flex-col gap-4">
                                <div>
                                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Full Title</h4>
                                  <p className="text-base font-bold text-slate-900 dark:text-slate-100 mt-1">{report.title}</p>
                                </div>

                                <div>
                                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Source Session</h4>
                                  <Link
                                    to={`/dashboard/chat?session=${report.session_id}`}
                                    className="text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:underline inline-flex items-center gap-1 mt-1 cursor-pointer"
                                  >
                                    {report.session_title || 'Chat Session'}
                                    <ExternalLink className="w-3.5 h-3.5" />
                                  </Link>
                                </div>

                                <div>
                                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Sources Used</h4>
                                  {report.sources_used && report.sources_used.length > 0 ? (
                                    <div className="flex flex-wrap gap-2 mt-2">
                                      {report.sources_used.map((source, idx) => (
                                        <span 
                                          key={idx}
                                          className="text-xs font-semibold px-2.5 py-1 bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 rounded-lg text-slate-600 dark:text-slate-300 shadow-sm"
                                        >
                                          {source}
                                        </span>
                                      ))}
                                    </div>
                                  ) : (
                                    <p className="text-xs text-slate-400 dark:text-slate-500 italic mt-1">No specific sources cited.</p>
                                  )}
                                </div>

                                <div className="flex gap-3 mt-4">
                                  {report.status === 'complete' && (
                                    <button
                                      onClick={() => handleDownload(report.report_id, report.title)}
                                      className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-sm transition-all cursor-pointer"
                                    >
                                      <Download className="w-4 h-4" />
                                      Download PDF
                                    </button>
                                  )}
                                  <button
                                    onClick={() => setReportToDelete(report)}
                                    className="inline-flex items-center gap-2 px-4 py-2 border border-red-200 text-red-600 hover:bg-red-50 dark:border-red-900/40 dark:text-red-400 dark:hover:bg-red-950/30 rounded-xl text-xs font-bold transition-all cursor-pointer"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                    Delete Report
                                  </button>
                                </div>
                              </div>

                              {/* Right Step Logs Panel */}
                              <div>
                                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Agent Execution Steps</h4>
                                {report.steps && report.steps.length > 0 ? (
                                  <div className="relative border-l border-slate-200 dark:border-slate-800 ml-3.5 pl-5.5 space-y-4.5">
                                    {report.steps.map((step, idx) => {
                                      const isStepFailed = step.status === 'failed';
                                      const isStepRunning = step.status === 'running';
                                      
                                      return (
                                        <div key={idx} className="relative group">
                                          {/* Connector Icon */}
                                          <div className={`absolute -left-[30px] top-0.5 w-5 h-5 rounded-full border bg-white dark:bg-slate-900 flex items-center justify-center shadow-sm transition-colors ${
                                            isStepFailed 
                                              ? 'border-red-500 text-red-500' 
                                              : isStepRunning 
                                                ? 'border-amber-500 text-amber-500'
                                                : 'border-emerald-500 text-emerald-500'
                                          }`}>
                                            {isStepFailed ? (
                                              <X className="w-3 h-3 font-bold" />
                                            ) : isStepRunning ? (
                                              <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                            ) : (
                                              <CheckCircle className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                                            )}
                                          </div>

                                          {/* Step details */}
                                          <div className={`rounded-xl p-3 border transition-colors ${
                                            isStepFailed 
                                              ? 'bg-rose-50 border-rose-200 text-rose-950 dark:bg-rose-950/30 dark:border-rose-900/60 dark:text-rose-200' 
                                              : 'bg-white dark:bg-slate-900/40 border-slate-200 dark:border-slate-800'
                                          }`}>
                                            <div className="flex items-center justify-between">
                                              <span className="text-sm font-bold capitalize">
                                                {step.step_name} Step
                                              </span>
                                              <span className="text-xs text-slate-400 font-medium">
                                                Duration: {formatDuration(step.duration_ms)}
                                              </span>
                                            </div>
                                            {step.error_message && (
                                              <p className="text-xs text-rose-600 dark:text-rose-400 mt-1.5 border-t border-rose-100 dark:border-rose-900/40 pt-1.5 font-medium leading-relaxed">
                                                Error: {step.error_message}
                                              </p>
                                            )}
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                ) : (
                                  <div className="bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl p-4 flex flex-col items-center justify-center text-center">
                                    <Loader2 className="w-5 h-5 text-indigo-500 animate-spin" />
                                    <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 font-medium">Starting agent run steps...</p>
                                  </div>
                                )}
                              </div>

                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {reportToDelete && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center">
          <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 font-sora">Delete Report</h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-2 leading-relaxed">
              Are you sure you want to delete "{reportToDelete.title}"? This will permanently remove the report from your list and delete its storage file.
            </p>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setReportToDelete(null)}
                className="flex-1 px-4 py-2.5 border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-850 font-semibold transition-all cursor-pointer"
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="flex-1 flex items-center justify-center px-4 py-2.5 bg-red-500 dark:bg-red-650 hover:bg-red-650 dark:hover:bg-red-600 text-white rounded-xl font-bold transition-all cursor-pointer shadow-sm"
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
