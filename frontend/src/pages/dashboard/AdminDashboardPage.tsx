import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { adminService } from '../../services/adminService';
import { evaluationService } from '../../services/evaluationService';
import { useAuthStore } from '../../store/authStore';
import { formatCompactNumber } from '../../utils/format';
import { 
  FileText, 
  Users, 
  ShieldCheck, 
  Building2, 
  Calendar, 
  UserPlus, 
  ShieldPlus, 
  Upload, 
  Plus, 
  ArrowRight,
  TrendingUp,
  Award
} from 'lucide-react';

const AdminDashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  // Date range picker values: default to last 7 days
  const getPastDateString = (daysAgo: number) => {
    const d = new Date();
    d.setDate(d.getDate() - daysAgo);
    return d.toISOString().split('T')[0];
  };

  const todayStr = new Date().toISOString().split('T')[0];
  const [startDate, setStartDate] = useState<string>(getPastDateString(6));
  const [endDate, setEndDate] = useState<string>(todayStr);

  // Evaluation states
  const [isEvalModalOpen, setIsEvalModalOpen] = useState(false);
  const [evalScope, setEvalScope] = useState<'count' | 'date_range'>('count');
  const [evalCount, setEvalCount] = useState<number>(50);
  const [evalStartDate, setEvalStartDate] = useState<string>(getPastDateString(6));
  const [evalEndDate, setEvalEndDate] = useState<string>(todayStr);
  const [isSubmittingEval, setIsSubmittingEval] = useState(false);

  // Queries
  const { data: usageData, isLoading: usageLoading } = useQuery({
    queryKey: ['adminUsage', startDate, endDate],
    queryFn: () => adminService.getUsageSummary(startDate, endDate),
  });

  const { data: latestEval, refetch: refetchLatestEval } = useQuery({
    queryKey: ['latestEvaluation'],
    queryFn: () => evaluationService.getLatestEvaluation(),
  });

  const handleRunEvaluation = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingEval(true);
    try {
      await evaluationService.runEvaluation({
        query_count: evalScope === 'count' ? evalCount : undefined,
        date_range_start: evalScope === 'date_range' ? new Date(evalStartDate).toISOString() : undefined,
        date_range_end: evalScope === 'date_range' ? new Date(evalEndDate).toISOString() : undefined,
      });
      setIsEvalModalOpen(false);
      alert('Evaluation run has started in the background. You will receive a notification when it completes.');
      refetchLatestEval();
    } catch (err: any) {
      console.error('Failed to run evaluation:', err);
      alert('Failed to start evaluation. ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsSubmittingEval(false);
    }
  };

  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['adminOverview'],
    queryFn: adminService.getDashboardOverview,
  });

  const { data: documentInsights, isLoading: insightsLoading } = useQuery({
    queryKey: ['adminDocumentInsights'],
    queryFn: adminService.getDocumentInsights,
  });

  // Aggregate totals for selected date range
  const totalClaudeInput = usageData?.usage?.reduce((acc, curr) => acc + curr.claude_input_tokens, 0) || 0;
  const totalClaudeOutput = usageData?.usage?.reduce((acc, curr) => acc + curr.claude_output_tokens, 0) || 0;
  const totalOpenRouterInput = usageData?.usage?.reduce((acc, curr) => acc + curr.openrouter_input_tokens, 0) || 0;
  const totalOpenRouterOutput = usageData?.usage?.reduce((acc, curr) => acc + curr.openrouter_output_tokens, 0) || 0;

  const totalHaikuInput = usageData?.usage?.reduce((acc, curr) => acc + (curr.claude_haiku_input_tokens || 0), 0) || 0;
  const totalHaikuOutput = usageData?.usage?.reduce((acc, curr) => acc + (curr.claude_haiku_output_tokens || 0), 0) || 0;
  const totalSonnetInput = usageData?.usage?.reduce((acc, curr) => acc + (curr.claude_sonnet_input_tokens || 0), 0) || 0;
  const totalSonnetOutput = usageData?.usage?.reduce((acc, curr) => acc + (curr.claude_sonnet_output_tokens || 0), 0) || 0;
  const totalOpusInput = usageData?.usage?.reduce((acc, curr) => acc + (curr.claude_opus_input_tokens || 0), 0) || 0;
  const totalOpusOutput = usageData?.usage?.reduce((acc, curr) => acc + (curr.claude_opus_output_tokens || 0), 0) || 0;

  const haikuCost = (totalHaikuInput * 1.0) / 1000000 + (totalHaikuOutput * 5.0) / 1000000;
  const sonnetCost = (totalSonnetInput * 3.0) / 1000000 + (totalSonnetOutput * 15.0) / 1000000;
  const opusCost = (totalOpusInput * 5.0) / 1000000 + (totalOpusOutput * 25.0) / 1000000;
  const totalClaudeCost = haikuCost + sonnetCost + opusCost;

  const formatCost = (val: number): string => {
    if (val === 0) return '$0.00';
    if (val < 0.01) return `$${val.toFixed(4)}`;
    return `$${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };


  // Custom SVG Mini Line/Area Chart for "Requests per day"
  const renderUsageChart = () => {
    if (usageLoading) {
      return (
        <div className="h-48 w-full flex items-center justify-center bg-slate-50 dark:bg-slate-900/40 rounded-xl animate-pulse">
          <span className="text-sm text-slate-400">Loading chart data...</span>
        </div>
      );
    }

    const items = usageData?.usage || [];
    if (items.length === 0) {
      return (
        <div className="h-48 w-full flex items-center justify-center bg-slate-50 dark:bg-slate-900/40 border border-slate-100 dark:border-slate-800/80 rounded-xl">
          <span className="text-sm text-slate-400">No request data found for this range</span>
        </div>
      );
    }

    const maxRequests = Math.max(...items.map((i) => i.request_count), 5);
    const height = 140;
    const paddingLeft = 35;
    const paddingRight = 10;
    const paddingTop = 15;
    const paddingBottom = 25;
    
    // We want the SVG to scale nicely
    const width = 800;
    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;

    // Calculate path points
    const points = items.map((item, idx) => {
      const x = paddingLeft + (idx / Math.max(items.length - 1, 1)) * chartWidth;
      const y = paddingTop + chartHeight - (item.request_count / maxRequests) * chartHeight;
      return { x, y, label: item.date, value: item.request_count };
    });

    const pathData = points.reduce((acc, p, i) => {
      return acc + (i === 0 ? `M ${p.x} ${p.y}` : ` L ${p.x} ${p.y}`);
    }, '');

    const areaData = points.length > 0 
      ? `${pathData} L ${points[points.length - 1].x} ${paddingTop + chartHeight} L ${points[0].x} ${paddingTop + chartHeight} Z`
      : '';

    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-4 w-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-indigo-500" />
            <h3 className="font-semibold text-slate-700 dark:text-slate-200 text-sm">Requests per day</h3>
          </div>
          <span className="text-sm font-medium px-2 py-0.5 rounded-full text-indigo-600  dark:text-indigo-400">
            Total range requests: {items.reduce((a, c) => a + c.request_count, 0)}
          </span>
        </div>

        <div className="w-full overflow-x-auto">
          <svg className="w-full min-w-[500px]" viewBox={`0 0 ${width} ${height}`}>
            {/* Grid Lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((ratio, index) => {
              const yVal = paddingTop + chartHeight * ratio;
              const gridLabel = Math.round(maxRequests * (1 - ratio));
              return (
                <g key={index}>
                  <line 
                    x1={paddingLeft} 
                    y1={yVal} 
                    x2={width - paddingRight} 
                    y2={yVal} 
                    className="stroke-slate-100 dark:stroke-slate-800/60" 
                    strokeWidth={1} 
                    strokeDasharray="4 4"
                  />
                  <text 
                    x={paddingLeft - 8} 
                    y={yVal + 4} 
                    className="fill-slate-400 dark:fill-slate-500 font-sora text-[10px] text-right"
                    textAnchor="end"
                  >
                    {gridLabel}
                  </text>
                </g>
              );
            })}

            {/* Filled Area */}
            {areaData && (
              <path 
                d={areaData} 
                className="fill-indigo-50/60 dark:fill-indigo-950/20"
              />
            )}

            {/* Line Path */}
            {pathData && (
              <path 
                d={pathData} 
                className="stroke-indigo-500 dark:stroke-indigo-400"
                strokeWidth={2}
                fill="none"
              />
            )}

            {/* Data Circles / Tooltips */}
            {points.map((p, idx) => (
              <g key={idx} className="group/dot cursor-pointer">
                <circle 
                  cx={p.x} 
                  cy={p.y} 
                  r={3.5} 
                  className="fill-white stroke-indigo-500 dark:fill-slate-900 dark:stroke-indigo-400 stroke-2"
                />
                <circle 
                  cx={p.x} 
                  cy={p.y} 
                  r={8} 
                  className="fill-indigo-500/10 opacity-0 group-hover/dot:opacity-100 transition-opacity"
                />
                <text
                  x={p.x}
                  y={p.y - 10}
                  textAnchor="middle"
                  className="fill-slate-700 dark:fill-slate-300 font-sora text-[9px] font-semibold opacity-0 group-hover/dot:opacity-100 transition-opacity pointer-events-none"
                >
                  {p.value}
                </text>
              </g>
            ))}

            {/* X Axis Labels */}
            {points.map((p, idx) => {
              // Show fewer dates to avoid cluttering
              const shouldShowLabel = points.length <= 10 || idx % Math.ceil(points.length / 7) === 0 || idx === points.length - 1;
              if (!shouldShowLabel) return null;
              
              // format label "MM/DD" or "YYYY-MM-DD"
              const dateParts = p.label.split('-');
              const displayDate = dateParts.length >= 3 ? `${dateParts[1]}/${dateParts[2]}` : p.label;

              return (
                <text 
                  key={idx}
                  x={p.x} 
                  y={height - 6} 
                  className="fill-slate-400 dark:fill-slate-500 font-medium text-[9px]"
                  textAnchor="middle"
                >
                  {displayDate}
                </text>
              );
            })}
          </svg>
        </div>
      </div>
    );
  };

  // Custom SVG Pie/Donut Chart for Document Insights File Types
  const renderFileDistributionChart = () => {
    if (insightsLoading) {
      return (
        <div className="h-44 w-full bg-slate-50 dark:bg-slate-900/40 rounded-xl animate-pulse"></div>
      );
    }

    const dist = documentInsights?.distribution || [];
    if (dist.length === 0) {
      return (
        <div className="h-44 w-full flex items-center justify-center border border-slate-100 dark:border-slate-800/80 rounded-xl text-sm text-slate-400">
          No document insights available
        </div>
      );
    }

    const totalCount = dist.reduce((a, c) => a + c.count, 0);
    const radius = 55;
    const circ = 2 * Math.PI * radius;
    let accumulatedPercent = 0;

    const colors = [
      'stroke-violet-500 dark:stroke-violet-400',
      'stroke-emerald-500 dark:stroke-emerald-400',
      'stroke-sky-500 dark:stroke-sky-400',
      'stroke-amber-500 dark:stroke-amber-400',
      'stroke-rose-500 dark:stroke-rose-400',
      'stroke-indigo-500 dark:stroke-indigo-400'
    ];

    const bgColors = [
      'bg-violet-500 dark:bg-violet-400',
      'bg-emerald-500 dark:bg-emerald-400',
      'bg-sky-500 dark:bg-sky-400',
      'bg-amber-500 dark:bg-amber-400',
      'bg-rose-500 dark:bg-rose-400',
      'bg-indigo-500 dark:bg-indigo-400'
    ];

    return (
      <div className="flex flex-col md:flex-row items-center gap-6 py-2">
        <div className="relative w-36 h-36 flex items-center justify-center shrink-0">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 140 140">
            {dist.map((item, index) => {
              const percent = item.count / totalCount;
              const strokeLength = percent * circ;
              const strokeOffset = circ - (accumulatedPercent * circ);
              accumulatedPercent += percent;

              return (
                <circle
                  key={index}
                  cx="70"
                  cy="70"
                  r={radius}
                  fill="none"
                  className={colors[index % colors.length]}
                  strokeWidth="14"
                  strokeDasharray={`${strokeLength} ${circ - strokeLength}`}
                  strokeDashoffset={strokeOffset}
                  strokeLinecap="round"
                />
              );
            })}
          </svg>
          <div className="absolute flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-slate-800 dark:text-slate-100 font-sora">{totalCount}</span>
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Docs</span>
          </div>
        </div>

        <div className="flex flex-wrap md:flex-col gap-3 justify-center w-full">
          {dist.map((item, index) => {
            const pct = ((item.count / totalCount) * 100).toFixed(0);
            return (
              <div key={index} className="flex items-center justify-between w-full md:max-w-xs px-3 py-1.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                <div className="flex items-center gap-2.5">
                  <span className={`w-3 h-3 rounded-full shrink-0 ${bgColors[index % bgColors.length]}`} />
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300 capitalize">{item.file_type}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{item.count}</span>
                  <span className="text-[10px] text-slate-400">({pct}%)</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-8 w-full">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="font-sora text-3xl font-semibold text-slate-800 dark:text-slate-100">
            Welcome, {user?.full_name}
          </h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            Here's the latest performance and activity insights across your enterprise RAG vault.
          </p>
        </div>

        {/* Date Picker (Top right of Usage area but fits nicely here) */}
        <div className="flex items-center gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-2 rounded-xl shadow-sm self-start">
          <Calendar className="w-4 h-4 text-slate-400 dark:text-slate-500 ml-1.5" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="bg-transparent border-none text-xs font-medium focus:ring-0 text-slate-700 dark:text-slate-300 focus:outline-none max-w-[110px]"
          />
          <span className="text-slate-300 dark:text-slate-700 font-light">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="bg-transparent border-none text-xs font-medium focus:ring-0 text-slate-700 dark:text-slate-300 focus:outline-none max-w-[110px]"
          />
        </div>
      </div>

      {/* 1. Usage Section (top of dashboard) */}
      <section className="flex flex-col gap-5">
        <h3 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-800/60 pb-2">
          Usage Statistics
        </h3>
        
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Requests Line Chart */}
          <div className="lg:col-span-2 flex w-full">
            {renderUsageChart()}
          </div>

          {/* Token Totals Card */}
          <div className="flex w-full">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between gap-4 group hover:shadow-md transition-shadow relative overflow-hidden w-full h-full">
              
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-500 dark:text-indigo-400">Total Tokens Usage</span>
              </div>

              <div className="flex flex-col gap-0.5 mt-1">
                <span className="text-3xl font-bold font-sora text-slate-800 dark:text-slate-100">
                  {formatCompactNumber(totalClaudeInput + totalClaudeOutput + totalOpenRouterInput + totalOpenRouterOutput)}
                </span>
                <span className="text-xs text-slate-400">Total processed tokens in range</span>
              </div>

              <div className="border-t border-slate-100 dark:border-slate-800/80 pt-4 flex flex-col gap-4">
                {/* Claude breakdown */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      Claude
                    </span>
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      {formatCompactNumber(totalClaudeInput + totalClaudeOutput)}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-550 dark:text-slate-400">
                    <span>Input: {formatCompactNumber(totalClaudeInput)}</span>
                    <span>Output: {formatCompactNumber(totalClaudeOutput)}</span>
                  </div>
                </div>

                {/* OpenRouter breakdown */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      OpenRouter
                    </span>
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      {formatCompactNumber(totalOpenRouterInput + totalOpenRouterOutput)}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-550 dark:text-slate-400">
                    <span>Input: {formatCompactNumber(totalOpenRouterInput)}</span>
                    <span>Output: {formatCompactNumber(totalOpenRouterOutput)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Claude Cost Card */}
          <div className="flex w-full">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between gap-4 group hover:shadow-md transition-shadow relative overflow-hidden w-full h-full">
              
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-500 dark:text-emerald-400">Token Cost</span>
              </div>

              <div className="flex flex-col gap-0.5 mt-1">
                <span className="text-3xl font-bold font-sora text-slate-800 dark:text-slate-100">
                  {formatCost(totalClaudeCost)}
                </span>
                <span className="text-xs text-slate-400">Total estimated token usage cost in range</span>
              </div> 

              <div className="border-t border-slate-100 dark:border-slate-800/80 pt-4 flex flex-col gap-3 mb-4">
                {/* Haiku cost breakdown */}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-800 dark:text-slate-400 flex items-center gap-1.5">
                    Haiku 4.5
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {formatCost(haikuCost)}
                  </span>
                </div>

                {/* Sonnet cost breakdown */}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-800 dark:text-slate-400 flex items-center gap-1.5">
                    Sonnet 4.6
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {formatCost(sonnetCost)}
                  </span>
                </div>

                {/* Opus cost breakdown */}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-800 dark:text-slate-400 flex items-center gap-1.5">
                    Opus 4.8
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {formatCost(opusCost)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Answer Quality Card */}
          <div className="flex w-full lg:col-span-2">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between gap-4 group hover:shadow-md transition-shadow relative overflow-hidden w-full h-full">
              
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-500 dark:text-indigo-400">Answer Quality (LLM-as-Judge)</span>
                {latestEval && (
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${
                    latestEval.status === 'completed' ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400' :
                    latestEval.status === 'running' ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 animate-pulse' :
                    latestEval.status === 'failed' ? 'bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400' :
                    'bg-slate-50 dark:bg-slate-850 text-slate-500'
                  }`}>
                    {latestEval.status}
                  </span>
                )}
              </div>

              {!latestEval ? (
                <div className="flex flex-col gap-2 mt-2">
                  <span className="text-xl font-bold font-sora text-slate-400 dark:text-slate-500 font-sans">No evaluation run yet</span>
                  <span className="text-xs text-slate-400 font-sans">Run an evaluation to measure faithfulness and relevance.</span>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4 mt-2">
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-slate-400 font-medium font-sans">Avg Faithfulness</span>
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-bold font-sora text-slate-800 dark:text-slate-100">
                        {latestEval.avg_faithfulness_score !== undefined && latestEval.avg_faithfulness_score !== null
                          ? `${Math.round(latestEval.avg_faithfulness_score)}%`
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-slate-400 font-medium font-sans">Avg Retrieval Relevance</span>
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-bold font-sora text-slate-800 dark:text-slate-100">
                        {latestEval.avg_relevance_score !== undefined && latestEval.avg_relevance_score !== null
                          ? `${Math.round(latestEval.avg_relevance_score)}%`
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <div className="border-t border-slate-100 dark:border-slate-800/80 pt-4 flex items-center justify-between gap-4 mt-auto">
                <span className="text-xs text-slate-450 dark:text-slate-500 font-sans">
                  {latestEval ? `Last run: ${new Date(latestEval.created_at).toLocaleDateString()}` : 'Evaluate model outputs'}
                </span>
                <div className="flex items-center gap-2">
                  {latestEval && (
                    <button
                      onClick={() => navigate(`/dashboard/evaluations/${latestEval.id}`)}
                      className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline transition-all cursor-pointer font-sans"
                    >
                      View Details
                    </button>
                  )}
                  <button
                    onClick={() => setIsEvalModalOpen(true)}
                    className="bg-indigo-650 bg-indigo-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1 shadow-sm hover:shadow font-sans cursor-pointer"
                  >
                    Run Evaluation
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Overview Section */}
      <section className="flex flex-col gap-5">
        <h3 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-800/60 pb-2">
          Overview
        </h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Departments Count */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex items-center justify-between group hover:border-slate-300 dark:hover:border-slate-700 transition-colors">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Departments</span>
              <span className="text-3xl font-bold text-slate-800 dark:text-slate-100 font-sora">
                {overviewLoading ? '...' : overview?.department_count || 0}
              </span>
            </div>
            <div className="p-3 bg-violet-50 dark:bg-violet-950/40 text-violet-500 rounded-lg group-hover:scale-110 transition-transform">
              <Building2 className="w-6 h-6" />
            </div>
          </div>

          {/* Document Count */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex items-center justify-between group hover:border-slate-300 dark:hover:border-slate-700 transition-colors">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Documents</span>
              <span className="text-3xl font-bold text-slate-800 dark:text-slate-100 font-sora">
                {overviewLoading ? '...' : overview?.document_count || 0}
              </span>
            </div>
            <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-500 rounded-lg group-hover:scale-110 transition-transform">
              <FileText className="w-6 h-6" />
            </div>
          </div>

          {/* Roles Count */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex items-center justify-between group hover:border-slate-300 dark:hover:border-slate-700 transition-colors">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Roles Count</span>
              <span className="text-3xl font-bold text-slate-800 dark:text-slate-100 font-sora">
                {overviewLoading ? '...' : overview?.role_count || 0}
              </span>
            </div>
            <div className="p-3 bg-sky-50 dark:bg-sky-950/40 text-sky-500 rounded-lg group-hover:scale-110 transition-transform">
              <ShieldCheck className="w-6 h-6" />
            </div>
          </div>

          {/* Members Count */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex items-center justify-between group hover:border-slate-300 dark:hover:border-slate-700 transition-colors">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Members Count</span>
              <span className="text-3xl font-bold text-slate-800 dark:text-slate-100 font-sora">
                {overviewLoading ? '...' : overview?.member_count || 0}
              </span>
            </div>
            <div className="p-3 bg-rose-50 dark:bg-rose-950/40 text-rose-500 rounded-lg group-hover:scale-110 transition-transform">
              <Users className="w-6 h-6" />
            </div>
          </div>
        </div>
      </section>

      {/* 3. Document & Knowledge Base Insights Section */}
      <section className="flex flex-col gap-5">
        <h3 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-800/60 pb-2">
          Document & Knowledge Base Insights
        </h3>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Distribution chart */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-4">
            <h4 className="font-semibold text-sm text-slate-700 dark:text-slate-300">Document Type Distribution</h4>
            <div className="my-auto">
              {renderFileDistributionChart()}
            </div>
          </div>

          {/* Latest Uploads list */}
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-sm text-slate-700 dark:text-slate-300">Latest 3 Uploads</h4>
              <button 
                onClick={() => navigate('/dashboard/documents')}
                className="text-xs font-medium text-indigo-500 hover:text-indigo-600 flex items-center gap-1 hover:underline"
              >
                View all <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="overflow-x-auto w-full">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-100 dark:border-slate-800/80 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                    <th className="pb-3 px-3">Filename</th>
                    <th className="pb-3 px-3">Type</th>
                    <th className="pb-3 px-3">Uploaded By</th>
                    <th className="pb-3 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/40 text-xs">
                  {insightsLoading ? (
                    [0, 1, 2].map((i) => (
                      <tr key={i} className="animate-pulse">
                        <td className="py-4 px-3"><div className="h-3.5 bg-slate-200 dark:bg-slate-800 rounded w-44" /></td>
                        <td className="py-4 px-3"><div className="h-3.5 bg-slate-200 dark:bg-slate-800 rounded w-12" /></td>
                        <td className="py-4 px-3"><div className="h-3.5 bg-slate-200 dark:bg-slate-800 rounded w-20" /></td>
                        <td className="py-4 px-3"><div className="h-3.5 bg-slate-200 dark:bg-slate-800 rounded w-16" /></td>
                      </tr>
                    ))
                  ) : !documentInsights?.recent_documents || documentInsights.recent_documents.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-8 px-3 text-center text-slate-400 dark:text-slate-500">
                        No documents uploaded yet.
                      </td>
                    </tr>
                  ) : (
                    documentInsights.recent_documents.map((doc, idx) => {
                      const statusColorMap: Record<string, string> = {
                        pending: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
                        processing: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-400',
                        ready: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400',
                        failed: 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400',
                      };

                      return (
                        <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/10">
                          <td className="py-3 px-3 font-medium text-slate-700 dark:text-slate-350 max-w-[200px] truncate" title={doc.filename}>
                            {doc.filename}
                          </td>
                          <td className="py-3 px-3 text-slate-500 dark:text-slate-450 uppercase font-semibold text-[10px]">
                            {doc.file_type}
                          </td>
                          <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                            {doc.uploaded_by}
                          </td>
                          <td className="py-3 px-3">
                            <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusColorMap[doc.status] || 'bg-slate-100 text-slate-600'}`}>
                              {doc.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Quick Actions Section */}
      <section className="flex flex-col gap-5">
        <h3 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-800/60 pb-2">
          Quick Actions
        </h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Invite Employee Action */}
          <button 
            onClick={() => navigate('/dashboard/team', { state: { openInvite: true } })}
            className="flex items-center gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-600/80 p-5 rounded-xl text-left shadow-sm group hover:-translate-y-0.5 transition-all duration-200"
          >
            <div className="p-3.5 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 rounded-xl group-hover:bg-indigo-500 group-hover:text-white transition-all duration-300">
              <UserPlus className="w-5 h-5" />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Invite Employee</span>
              <span className="text-[11px] text-slate-400 dark:text-slate-500">Send workspace invites</span>
            </div>
          </button>

          {/* Create Role Action */}
          <button 
            onClick={() => navigate('/dashboard/roles', { state: { openCreate: true } })}
            className="flex items-center gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-600/80 p-5 rounded-xl text-left shadow-sm group hover:-translate-y-0.5 transition-all duration-200"
          >
            <div className="p-3.5 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 rounded-xl group-hover:bg-indigo-500 group-hover:text-white transition-all duration-300">
              <ShieldPlus className="w-5 h-5" />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Create Role</span>
              <span className="text-[11px] text-slate-400 dark:text-slate-500">Add custom hierarchy roles</span>
            </div>
          </button>

          {/* Upload Document Action */}
          <button 
            onClick={() => navigate('/dashboard/documents', { state: { openUpload: true } })}
            className="flex items-center gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-600/80 p-5 rounded-xl text-left shadow-sm group hover:-translate-y-0.5 transition-all duration-200"
          >
            <div className="p-3.5 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 rounded-xl group-hover:bg-indigo-500 group-hover:text-white transition-all duration-300">
              <Upload className="w-5 h-5" />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Upload Document</span>
              <span className="text-[11px] text-slate-400 dark:text-slate-500">Inject raw files to vault</span>
            </div>
          </button>

          {/* Create Department Action */}
          <button 
            onClick={() => navigate('/dashboard/team', { state: { openCreateDept: true } })}
            className="flex items-center gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-600/80 p-5 rounded-xl text-left shadow-sm group hover:-translate-y-0.5 transition-all duration-200"
          >
            <div className="p-3.5 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 rounded-xl group-hover:bg-indigo-500 group-hover:text-white transition-all duration-300">
              <Plus className="w-5 h-5" />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Create Department</span>
              <span className="text-[11px] text-slate-400 dark:text-slate-500">Group roles into categories</span>
            </div>
          </button>
        </div>
      </section>

      {/* Run Evaluation Modal */}
      {isEvalModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 dark:bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 w-full max-w-md shadow-2xl flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between">
              <h4 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Award className="w-5 h-5 text-indigo-500" />
                Run LLM-as-Judge Evaluation
              </h4>
              <button 
                onClick={() => setIsEvalModalOpen(false)}
                className="text-slate-400 dark:text-slate-500 hover:text-slate-650 dark:hover:text-slate-300 transition-colors text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <p className="text-slate-500 dark:text-slate-450 text-xs leading-relaxed font-sans">
              Evaluate the quality of generated answers based on faithfulness (factuality against context) and retrieval relevance.
            </p>

            <form onSubmit={handleRunEvaluation} className="flex flex-col gap-4 mt-2">
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 font-sans">Evaluation Scope</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300 cursor-pointer font-sans">
                    <input
                      type="radio"
                      checked={evalScope === 'count'}
                      onChange={() => setEvalScope('count')}
                      className="text-indigo-650 focus:ring-indigo-500"
                    />
                    Latest Queries Count
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300 cursor-pointer font-sans">
                    <input
                      type="radio"
                      checked={evalScope === 'date_range'}
                      onChange={() => setEvalScope('date_range')}
                      className="text-indigo-650 focus:ring-indigo-500"
                    />
                    Custom Date Range
                  </label>
                </div>
              </div>

              {evalScope === 'count' ? (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="eval-count" className="text-xs font-semibold text-slate-500 dark:text-slate-400 font-sans">Number of Queries</label>
                  <input
                    id="eval-count"
                    type="number"
                    min="1"
                    max="1000"
                    value={evalCount}
                    onChange={(e) => setEvalCount(parseInt(e.target.value) || 10)}
                    className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
                  />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="eval-start-date" className="text-xs font-semibold text-slate-500 dark:text-slate-400 font-sans">Start Date</label>
                    <input
                      id="eval-start-date"
                      type="date"
                      value={evalStartDate}
                      onChange={(e) => setEvalStartDate(e.target.value)}
                      className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="eval-end-date" className="text-xs font-semibold text-slate-500 dark:text-slate-400 font-sans">End Date</label>
                    <input
                      id="eval-end-date"
                      type="date"
                      value={evalEndDate}
                      onChange={(e) => setEvalEndDate(e.target.value)}
                      className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 mt-4">
                <button
                  type="button"
                  onClick={() => setIsEvalModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 text-sm font-semibold rounded-xl hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors font-sans cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingEval}
                  className="px-4 py-2 bg-indigo-650 bg-indigo-700 disabled:bg-indigo-650/50 text-white text-sm font-semibold rounded-xl shadow-sm transition-colors font-sans cursor-pointer"
                >
                  {isSubmittingEval ? 'Scheduling...' : 'Run Evaluation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboardPage;
