export type EvaluationStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface EvaluationRun {
  id: string;
  tenant_id: string;
  requested_by_user_id: string;
  status: EvaluationStatus;
  query_count: number;
  date_range_start?: string;
  date_range_end?: string;
  avg_faithfulness_score?: number;
  avg_relevance_score?: number;
  created_at: string;
  completed_at?: string;
}

export interface EvaluationResult {
  id: string;
  evaluation_run_id: string;
  query_log_id: string;
  faithfulness_score: number;
  relevance_score: number;
  unsupported_claims: string[];
  reasoning: string;
  created_at: string;
  question?: string;
  answer?: string;
  model_string?: string;
}

export interface EvaluationDetail {
  run: EvaluationRun;
  results: EvaluationResult[];
}

export interface ModelEvaluationBreakdown {
  model_string: string;
  query_count: number;
  avg_faithfulness_score: number;
  avg_relevance_score: number;
}
