export interface SessionResponse {
  id: string;
  user_id: string;
  tenant_id: string;
  title: string;
  is_pinned: boolean;
  db_connection_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CitationResponse {
  id: string;
  document_id: string;
  filename: string;
  chunk_text: string;
  page_number: number | null;
  chunk_index: number;
}

export interface AvailableModel {
  id: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  provider_id?: string | null;
  base_url?: string | null;
  input_cost_per_million_tokens?: number | null;
  output_cost_per_million_tokens?: number | null;
  tenant_id?: string | null;
  api_key?: string;
  is_default?: boolean;
  model_name?: string | null;
  /** True when this is the tenant's admin-configured default chat model */
  is_tenant_default?: boolean;
  tier?: "fast" | "balanced" | "powerful";
}

export interface MessageResponse {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations: CitationResponse[];
  attached_file?: {
    name: string;
    size: number;
  };
  model_id?: string;
  model?: AvailableModel;
  follow_up_questions?: string[];
  generated_sql?: string;
  query_results?: any[];
  chart_spec?: ChartSpec | null;
  resolved_model?: string | null;
  was_fallback?: boolean;
  fallback_model_name?: string | null;
}

export interface ChartDataPoint {
  [key: string]: string | number;
}

export interface ChartSpec {
  chart_type: "bar" | "line" | "area" | "pie";
  title: string;
  x_key: string;
  y_keys: string[];
  data: ChartDataPoint[];
}

export interface SessionDetailResponse extends SessionResponse {
  messages: MessageResponse[];
}

export interface QueryResponse {
  answer: string;
  citations: CitationResponse[];
  message_id: string;
}

export interface ReportAgentStep {
  step_name:
    | "gather"
    | "cluster"
    | "synthesize"
    | "assemble"
    | "render"
    | "deliver";
  status: "running" | "success" | "failed";
  duration_ms: number | null;
  error_message: string | null;
}

export interface ReportStatus {
  report_id: string;
  session_id: string;
  session_title?: string;
  source_type: string;
  sources_used: string[];
  status: "generating" | "complete" | "failed";
  title: string;
  created_at: string;
  completed_at: string | null;
  steps: ReportAgentStep[];
}
