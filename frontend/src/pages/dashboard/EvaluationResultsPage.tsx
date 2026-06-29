import React from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { evaluationService } from '../../services/evaluationService';
import { ArrowLeft, Award, AlertTriangle, Calendar, MessageSquare, ChevronDown } from 'lucide-react';
import type { EvaluationResult } from '../../types/evaluation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const QueryResultCard: React.FC<{
  result: EvaluationResult;
  index: number;
  getScoreColor: (score: number) => string;
}> = ({ result, index, getScoreColor }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const combinedScore = result.faithfulness_score + result.relevance_score;

  return (
    <div 
      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all flex flex-col gap-4 relative overflow-hidden"
    >
      {/* Header & Toggle area */}
      <div 
        className="flex flex-wrap items-center justify-between gap-4 cursor-pointer select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-400 font-sans">#{index + 1}</span>
            <span className="text-xs font-semibold text-slate-400 font-sans">Query Result</span>
          </div>
          <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-md font-sans border ${
            result.model_string === 'Unknown (legacy)' || !result.model_string
              ? 'bg-amber-50/50 dark:bg-amber-950/20 text-amber-600 dark:text-amber-400 border-amber-100 dark:border-amber-900/20'
              : 'bg-indigo-50/50 dark:bg-indigo-950/20 text-indigo-600 dark:text-indigo-400 border-indigo-100 dark:border-indigo-900/20'
          }`}>
            Model: {result.model_string || 'Unknown (legacy)'}
          </span>
          {result.run_created_at && (
            <span className="text-[10px] font-semibold px-2.5 py-0.5 rounded-md font-sans bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              Run Date: {new Date(result.run_created_at).toLocaleDateString()}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 border px-2.5 py-1 rounded-xl text-xs font-bold font-sans ${getScoreColor(result.faithfulness_score)}`}>
            <span>Faithfulness:</span>
            <span>{result.faithfulness_score}%</span>
          </div>
          
          <div className={`flex items-center gap-1.5 border px-2.5 py-1 rounded-xl text-xs font-bold font-sans ${getScoreColor(result.relevance_score)}`}>
            <span>Relevance:</span>
            <span>{result.relevance_score}%</span>
          </div>

          <div className="text-xs font-semibold text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded-xl font-sans">
            Combined: {combinedScore}/200
          </div>

          <div className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 ml-1">
            <ChevronDown className={`w-4 h-4 transform transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        </div>
      </div>

      {/* Question (always visible as it's the identifier of the query) */}
      <div 
        className="border-t border-slate-100 dark:border-slate-800/80 pt-4 cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-sans">Question Asked</span>
        <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-900 rounded-xl p-3.5 text-sm font-semibold text-slate-800 dark:text-slate-300 leading-relaxed font-sans italic mt-1.5">
          "{result.question || 'N/A'}"
        </div>
      </div>

      {/* Expandable Content (Answer, Unsupported Claims, Reasoning) */}
      {isOpen && (
        <div className="flex flex-col gap-4">
          {/* Answer */}
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-sans">Generated Answer</span>
            <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-900 rounded-xl p-3.5 text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-sans max-h-60 overflow-y-auto">
              {result.answer ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table: ({ ...props }) => (
                      <div className="my-2 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-left border-collapse" {...props} />
                      </div>
                    ),
                    thead: ({ ...props }) => (
                      <thead className="bg-slate-50 dark:bg-slate-800/50" {...props} />
                    ),
                    tbody: ({ ...props }) => (
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-850" {...props} />
                    ),
                    tr: ({ ...props }) => (
                      <tr className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors duration-150" {...props} />
                    ),
                    th: ({ ...props }) => (
                      <th className="px-3 py-2 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider" {...props} />
                    ),
                    td: ({ ...props }) => (
                      <td className="px-3 py-2 text-sm text-slate-700 dark:text-slate-205" {...props} />
                    ),
                    p: ({ ...props }) => (
                      <p className="mb-2 last:mb-0 leading-relaxed" {...props} />
                    ),
                    ul: ({ ...props }) => (
                      <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />
                    ),
                    ol: ({ ...props }) => (
                      <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />
                    ),
                    li: ({ ...props }) => (
                      <li className="text-sm" {...props} />
                    ),
                  }}
                >
                  {result.answer}
                </ReactMarkdown>
              ) : (
                'N/A'
              )}
            </div>
          </div>

          {/* Unsupported claims list */}
          {result.unsupported_claims && result.unsupported_claims.length > 0 && (
            <div className="bg-red-50/20 dark:bg-red-950/5 border border-red-100 dark:border-red-900/30 rounded-xl p-4 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-red-650 dark:text-red-400">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-sans">Claims Unsupported by Source Context ({result.unsupported_claims.length})</span>
              </div>
              <ul className="list-disc pl-5 flex flex-col gap-1">
                {result.unsupported_claims.map((claim, idx) => (
                  <li key={idx} className="text-xs text-red-650 dark:text-slate-400 leading-relaxed font-sans font-medium">
                    {claim}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Reasoning */}
          <div className="bg-slate-50 dark:bg-slate-950 border border-slate-150 dark:border-slate-900 rounded-xl p-4 flex flex-col gap-1.5">
            <span className="text-xs font-bold text-indigo-500 uppercase tracking-wider font-sans">Judge Reasoning</span>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              {result.reasoning}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

const EvaluationResultsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const defaultViewMode = location.state?.defaultViewMode || 'run';
  const [viewMode, setViewMode] = React.useState<'run' | 'all'>(defaultViewMode);
  const [page, setPage] = React.useState(1);
  const limit = 10;

  const { data: detail, isLoading, error } = useQuery({
    queryKey: ['evaluationDetails', id],
    queryFn: () => evaluationService.getEvaluationDetails(id || ''),
    enabled: !!id,
  });

  const { data: modelPerformance, isLoading: isModelPerfLoading } = useQuery({
    queryKey: ['modelPerformance'],
    queryFn: () => evaluationService.getEvaluationByModel(),
  });

  const { data: allResultsData, isLoading: isAllResultsLoading } = useQuery({
    queryKey: ['allEvaluationResults', page, limit],
    queryFn: () => evaluationService.getAllEvaluationResults(limit, (page - 1) * limit),
    enabled: viewMode === 'all',
  });

  const { data: overallEval } = useQuery({
    queryKey: ['overallEvaluation'],
    queryFn: () => evaluationService.getOverallEvaluation(),
    enabled: viewMode === 'all',
  });

  const sortedModelPerformance = React.useMemo(() => {
    if (!modelPerformance) return [];
    return [...modelPerformance].sort((a, b) => b.avg_faithfulness_score - a.avg_faithfulness_score);
  }, [modelPerformance]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-650 rounded-full animate-spin"></div>
        <span className="text-sm font-semibold text-slate-500 dark:text-slate-400 font-sans">Loading evaluation details...</span>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 text-center max-w-md mx-auto">
        <AlertTriangle className="w-12 h-12 text-red-500" />
        <h3 className="font-sora text-lg font-bold text-slate-800 dark:text-slate-100">Error Loading Details</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400 font-sans">
          Could not retrieve results for this evaluation run. It might not exist or you don't have access.
        </p>
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-350 text-sm font-semibold rounded-xl transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </button>
      </div>
    );
  }

  const { run, results } = detail;

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-100 dark:border-emerald-900/40';
    if (score >= 50) return 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border-amber-100 dark:border-amber-900/40';
    return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border-red-100 dark:border-red-900/40';
  };

  return (
    <div className="flex flex-col gap-6 w-full pb-12">
      {/* Back button and page header */}
      <div className="flex flex-col gap-3">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-750 dark:text-slate-400 dark:hover:text-slate-200 transition-colors w-fit group cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Dashboard
        </button>
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-650 dark:text-indigo-400 rounded-xl">
              <Award className="w-6 h-6" />
            </div>
            <div className="flex flex-col gap-0.5">
              <h2 className="font-sora text-2xl font-bold text-slate-800 dark:text-slate-100">
                Evaluation Report
              </h2>
              <span className="text-xs text-slate-400 font-sans">
                {viewMode === 'run' ? `Run ID: ${run.id}` : 'All evaluation runs across your vault'}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* View Scope Toggle */}
            <div className="flex bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold">
              <button
                onClick={() => setViewMode('run')}
                className={`px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
                  viewMode === 'run'
                    ? 'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                }`}
              >
                This Run
              </button>
              <button
                onClick={() => setViewMode('all')}
                className={`px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
                  viewMode === 'all'
                    ? 'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                }`}
              >
                All Evaluations
              </button>
            </div>

            {viewMode === 'run' && (
              <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-2">
                <Calendar className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                <span className="text-xs font-semibold text-slate-650 dark:text-slate-200 font-sans">
                  Executed: {formatDate(run.created_at)}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Aggregate Score Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Faithfulness Score */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-500 dark:text-emerald-400">Faithfulness (Factuality)</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-4xl font-bold font-sora text-slate-800 dark:text-slate-100">
              {viewMode === 'run'
                ? (run.avg_faithfulness_score !== null && run.avg_faithfulness_score !== undefined
                  ? `${Math.round(run.avg_faithfulness_score)}%`
                  : 'N/A')
                : (overallEval?.avg_faithfulness_score !== null && overallEval?.avg_faithfulness_score !== undefined
                  ? `${Math.round(overallEval.avg_faithfulness_score)}%`
                  : 'N/A')}
            </span>
            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
              <div 
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(viewMode === 'run' ? run.avg_faithfulness_score : overallEval?.avg_faithfulness_score) || 0}%`
                }}
              ></div>
            </div>
          </div>
          <p className="text-slate-500 dark:text-slate-400 text-xs leading-relaxed font-sans mt-1">
            Measures if the generated answers make any claims that are not fully supported by the retrieved contexts. Higher means more factual.
          </p>
        </div>

        {/* Relevance Score */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-500 dark:text-indigo-400">Retrieval Relevance</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-4xl font-bold font-sora text-slate-800 dark:text-slate-100">
              {viewMode === 'run'
                ? (run.avg_relevance_score !== null && run.avg_relevance_score !== undefined
                  ? `${Math.round(run.avg_relevance_score)}%`
                  : 'N/A')
                : (overallEval?.avg_relevance_score !== null && overallEval?.avg_relevance_score !== undefined
                  ? `${Math.round(overallEval.avg_relevance_score)}%`
                  : 'N/A')}
            </span>
            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
              <div 
                className="bg-indigo-500 h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(viewMode === 'run' ? run.avg_relevance_score : overallEval?.avg_relevance_score) || 0}%`
                }}
              ></div>
            </div>
          </div>
          <p className="text-slate-500 dark:text-slate-400 text-xs leading-relaxed font-sans mt-1">
            Measures if the retrieved chunks are actually relevant and useful for answering the question. Higher means less noise.
          </p>
        </div>

        {/* Metadata stats */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col gap-4 justify-between">
          <div className="flex flex-col gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Run Configuration</span>
            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Status</span>
                <span className={`font-semibold capitalize ${
                  viewMode === 'run'
                    ? (run.status === 'completed' ? 'text-emerald-500' : run.status === 'running' ? 'text-amber-500' : 'text-red-500')
                    : 'text-emerald-500'
                }`}>
                  {viewMode === 'run' ? run.status : 'All Runs'}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Queries Evaluated</span>
                <span className="font-semibold text-slate-850 dark:text-slate-100 font-sans">
                  {viewMode === 'run' ? run.query_count : (overallEval?.query_count || 0)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Date Range Filter</span>
                <span className="font-semibold text-slate-850 dark:text-slate-100 font-sans text-xs">
                  {viewMode === 'run'
                    ? (run.date_range_start ? `${new Date(run.date_range_start).toLocaleDateString()} to ${new Date(run.date_range_end || '').toLocaleDateString()}` : 'None (Latest count)')
                    : 'All Time'}
                </span>
              </div>
            </div>
          </div>
          
          {viewMode === 'run' ? (
            run.completed_at && (
              <div className="text-xs text-slate-500 dark:text-slate-400 font-sans border-t border-slate-100 dark:border-slate-800/80 pt-3">
                Completed in background: {formatDate(run.completed_at)}
              </div>
            )
          ) : (
            <div className="text-xs text-slate-500 dark:text-slate-400 font-sans border-t border-slate-100 dark:border-slate-800/80 pt-3">
              Cumulative average across all evaluation runs
            </div>
          )}
        </div>
      </div>

      {/* Performance by Model Section */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
        <div className="flex flex-col gap-1 border-b border-slate-150 dark:border-slate-800 pb-3">
          <h3 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Award className="w-5 h-5 text-indigo-500" />
            Performance by Model (Cumulative)
          </h3>
          <p className="text-xs text-slate-400 font-sans">
            Aggregate scores across all evaluation runs grouped by LLM model.
          </p>
        </div>

        {isModelPerfLoading ? (
          <div className="py-8 flex justify-center items-center">
            <div className="w-6 h-6 border-2 border-indigo-200 border-t-indigo-650 rounded-full animate-spin font-sans"></div>
          </div>
        ) : !sortedModelPerformance || sortedModelPerformance.length === 0 ? (
          <div className="text-center py-6 text-sm text-slate-500 dark:text-slate-400 font-sans">
            No model performance data available.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-150 dark:border-slate-800 text-xs font-bold uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-4 font-sans">Model</th>
                  <th className="py-3 px-4 text-center font-sans">Queries</th>
                  <th className="py-3 px-4 text-center font-sans">Avg Faithfulness</th>
                  <th className="py-3 px-4 text-center font-sans">Avg Relevance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/50">
                {sortedModelPerformance.map((row) => {
                  const isLegacy = row.model_string === 'Unknown (legacy)';
                  return (
                    <tr key={row.model_string} className="transition-colors text-sm text-slate-700 dark:text-slate-300">
                      <td className="py-3.5 px-4 font-semibold font-sans flex flex-col gap-1">
                        <span className={isLegacy ? 'text-slate-400 italic' : 'text-slate-850 dark:text-slate-105'}>
                          {row.model_string}
                        </span>
                        {isLegacy && (
                          <span className="text-[10px] text-amber-500 font-normal leading-normal">
                            ⚠️ Queries logged before model tracking was added
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-center font-sans text-slate-500 dark:text-slate-400">
                        {row.query_count}
                      </td>
                      <td className="py-3.5 px-4 text-center font-semibold">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getScoreColor(row.avg_faithfulness_score)}`}>
                          {Math.round(row.avg_faithfulness_score)}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-center font-semibold">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getScoreColor(row.avg_relevance_score)}`}>
                          {Math.round(row.avg_relevance_score)}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Individual Query Results Section */}
      <div className="flex flex-col gap-4 mt-4">
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
          <h3 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-indigo-500" />
            {viewMode === 'run' ? `Evaluated Queries (${results.length})` : `All Evaluated Queries (${allResultsData?.total_count || 0})`}
          </h3>
          <span className="text-xs text-slate-400 dark:text-slate-500 font-sans">
            Sorted by lowest combined score first
          </span>
        </div>

        {viewMode === 'run' ? (
          results.length === 0 ? (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center flex flex-col items-center justify-center gap-2">
              <AlertTriangle className="w-8 h-8 text-slate-350 dark:text-slate-650" />
              <span className="font-semibold text-slate-800 dark:text-slate-205 font-sans">No evaluated queries found</span>
              <span className="text-xs text-slate-500 dark:text-slate-450 font-sans">Make sure there are queries logged in your vault before running evaluations.</span>
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {results.map((result, index) => (
                <QueryResultCard
                  key={result.id}
                  result={result}
                  index={index}
                  getScoreColor={getScoreColor}
                />
              ))}
            </div>
          )
        ) : isAllResultsLoading ? (
          <div className="py-12 flex justify-center items-center">
            <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-650 rounded-full animate-spin"></div>
          </div>
        ) : !allResultsData || allResultsData.results.length === 0 ? (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center flex flex-col items-center justify-center gap-2">
            <AlertTriangle className="w-8 h-8 text-slate-350 dark:text-slate-650" />
            <span className="font-semibold text-slate-800 dark:text-slate-205 font-sans">No evaluated queries found</span>
            <span className="text-xs text-slate-500 dark:text-slate-450 font-sans">No evaluation results have been logged across any runs yet.</span>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {allResultsData.results.map((result, index) => (
              <QueryResultCard
                key={result.id}
                result={result}
                index={(page - 1) * limit + index}
                getScoreColor={getScoreColor}
              />
            ))}

            {/* Pagination Controls */}
            {allResultsData.total_count > limit && (
              <div className="flex items-center justify-between border-t border-slate-200 dark:border-slate-800 pt-4 mt-2">
                <button
                  onClick={() => setPage(p => Math.max(p - 1, 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-705 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50 transition-colors cursor-pointer"
                >
                  Previous
                </button>
                <span className="text-xs text-slate-500 dark:text-slate-400 font-sans">
                  Page {page} of {Math.ceil(allResultsData.total_count / limit)}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(p + 1, Math.ceil(allResultsData.total_count / limit)))}
                  disabled={page >= Math.ceil(allResultsData.total_count / limit)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-705 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50 transition-colors cursor-pointer"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EvaluationResultsPage;
