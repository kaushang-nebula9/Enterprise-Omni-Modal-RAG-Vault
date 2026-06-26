import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { evaluationService } from '../../services/evaluationService';
import { ArrowLeft, Award, CheckCircle, AlertTriangle, HelpCircle, Calendar, MessageSquare } from 'lucide-react';

const EvaluationResultsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: detail, isLoading, error } = useQuery({
    queryKey: ['evaluationDetails', id],
    queryFn: () => evaluationService.getEvaluationDetails(id || ''),
    enabled: !!id,
  });

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
                Run ID: {run.id}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-2">
            <Calendar className="w-4 h-4 text-slate-400 dark:text-slate-500" />
            <span className="text-xs font-semibold text-slate-650 dark:text-slate-200 font-sans">
              Executed: {formatDate(run.created_at)}
            </span>
          </div>
        </div>
      </div>

      {/* Aggregate Score Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Faithfulness Score */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-500 dark:text-emerald-400">Faithfulness (Factuality)</span>
            <CheckCircle className="w-5 h-5 text-emerald-500" />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-4xl font-bold font-sora text-slate-800 dark:text-slate-100">
              {run.avg_faithfulness_score !== null && run.avg_faithfulness_score !== undefined
                ? `${Math.round(run.avg_faithfulness_score)}%`
                : 'N/A'}
            </span>
            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
              <div 
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${run.avg_faithfulness_score || 0}%` }}
              ></div>
            </div>
          </div>
          <p className="text-slate-500 dark:text-slate-450 text-[11px] leading-relaxed font-sans mt-1">
            Measures if the generated answers make any claims that are not fully supported by the retrieved contexts. Higher means more factual.
          </p>
        </div>

        {/* Relevance Score */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-500 dark:text-indigo-400">Retrieval Relevance</span>
            <HelpCircle className="w-5 h-5 text-indigo-500" />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-4xl font-bold font-sora text-slate-800 dark:text-slate-100">
              {run.avg_relevance_score !== null && run.avg_relevance_score !== undefined
                ? `${Math.round(run.avg_relevance_score)}%`
                : 'N/A'}
            </span>
            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
              <div 
                className="bg-indigo-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${run.avg_relevance_score || 0}%` }}
              ></div>
            </div>
          </div>
          <p className="text-slate-500 dark:text-slate-450 text-[11px] leading-relaxed font-sans mt-1">
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
                  run.status === 'completed' ? 'text-emerald-500' :
                  run.status === 'running' ? 'text-amber-500' :
                  'text-red-500'
                }`}>{run.status}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Queries Evaluated</span>
                <span className="font-semibold text-slate-850 dark:text-slate-100 font-sans">{run.query_count}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Date Range Filter</span>
                <span className="font-semibold text-slate-850 dark:text-slate-100 font-sans text-xs">
                  {run.date_range_start ? `${new Date(run.date_range_start).toLocaleDateString()} to ${new Date(run.date_range_end || '').toLocaleDateString()}` : 'None (Latest count)'}
                </span>
              </div>
            </div>
          </div>
          
          {run.completed_at && (
            <div className="text-[10px] text-slate-400 dark:text-slate-500 font-sans border-t border-slate-100 dark:border-slate-800/80 pt-3">
              Completed in background: {formatDate(run.completed_at)}
            </div>
          )}
        </div>
      </div>

      {/* Individual Query Results Section */}
      <div className="flex flex-col gap-4 mt-4">
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
          <h3 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-indigo-500" />
            Evaluated Queries ({results.length})
          </h3>
          <span className="text-xs text-slate-405 dark:text-slate-500 font-sans">
            Sorted by lowest combined score first (Worst Performing)
          </span>
        </div>

        {results.length === 0 ? (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center flex flex-col items-center justify-center gap-2">
            <AlertTriangle className="w-8 h-8 text-slate-350 dark:text-slate-650" />
            <span className="font-semibold text-slate-800 dark:text-slate-205 font-sans">No evaluated queries found</span>
            <span className="text-xs text-slate-500 dark:text-slate-450 font-sans">Make sure there are queries logged in your vault before running evaluations.</span>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {results.map((result, index) => {
              const combinedScore = result.faithfulness_score + result.relevance_score;
              return (
                <div 
                  key={result.id}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col gap-4 relative overflow-hidden"
                >
                  {/* Score badge headers */}
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-400 font-sans">#{index + 1}</span>
                      <span className="text-xs font-semibold text-slate-400 font-sans">Query Result</span>
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

                      <div className="text-[10px] font-semibold text-slate-400 bg-slate-50 dark:bg-slate-850 px-2 py-1 rounded-xl font-sans">
                        Combined: {combinedScore}/200
                      </div>
                    </div>
                  </div>

                  {/* Question and Answer */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 border-t border-slate-100 dark:border-slate-800/80 pt-4">
                    {/* Question */}
                    <div className="flex flex-col gap-1.5">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-sans">Question Asked</span>
                      <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-900 rounded-xl p-3.5 text-sm font-semibold text-slate-800 dark:text-slate-300 leading-relaxed font-sans italic">
                        "{result.question || 'N/A'}"
                      </div>
                    </div>

                    {/* Answer */}
                    <div className="flex flex-col gap-1.5">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-sans">Generated Answer</span>
                      <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-900 rounded-xl p-3.5 text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-sans whitespace-pre-wrap max-h-60 overflow-y-auto">
                        {result.answer || 'N/A'}
                      </div>
                    </div>
                  </div>

                  {/* Unsupported claims list */}
                  {result.unsupported_claims && result.unsupported_claims.length > 0 && (
                    <div className="bg-red-50/20 dark:bg-red-950/5 border border-red-100 dark:border-red-900/30 rounded-xl p-4 flex flex-col gap-2">
                      <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
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
                  <div className="bg-slate-50 dark:bg-slate-950 border border-slate-150 dark:border-slate-900 rounded-xl p-4 flex flex-col gap-1.5 mt-1">
                    <span className="text-xs font-bold text-indigo-500 uppercase tracking-wider font-sans">Judge Reasoning</span>
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
                      {result.reasoning}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default EvaluationResultsPage;
