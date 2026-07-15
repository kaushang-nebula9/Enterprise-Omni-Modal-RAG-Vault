export interface UpdateMemberPayload {
  role_id?: string
  is_active?: boolean
}

export interface UpdateOrganisationPayload {
  name?: string
  website?: string
  monthly_budget_limit?: number | null
  default_model_id?: string | null
}

export interface CreateRolePayload {
  name: string
  parent_role_id?: string | null
  department_id?: string | null
}

export interface UpdateRolePayload {
  name: string
  parent_role_id?: string | null
  department_id?: string | null
}

export interface RoleTreeNode {
  id: string
  name: string
  parent_role_id: string | null
  is_admin: boolean
  is_default: boolean
  descendant_count: number
  children: RoleTreeNode[]
}

export interface UsageSummaryItem {
  date: string
  request_count: number
  total_tokens: number
  claude_input_tokens: number
  claude_output_tokens: number
  openrouter_input_tokens: number
  openrouter_output_tokens: number
  claude_haiku_input_tokens: number
  claude_haiku_output_tokens: number
  claude_sonnet_input_tokens: number
  claude_sonnet_output_tokens: number
  claude_opus_input_tokens: number
  claude_opus_output_tokens: number
  openrouter_llama_input_tokens?: number
  openrouter_llama_output_tokens?: number
  openrouter_gemma_input_tokens?: number
  openrouter_gemma_output_tokens?: number
  openrouter_nemotron_input_tokens?: number
  openrouter_nemotron_output_tokens?: number
  openrouter_gpt_input_tokens?: number
  openrouter_gpt_output_tokens?: number
  openrouter_cohere_input_tokens?: number
  openrouter_cohere_output_tokens?: number
}

export interface UsageSummaryResponse {
  usage: UsageSummaryItem[]
}

export interface DashboardOverviewResponse {
  department_count: number
  document_count: number
  role_count: number
  member_count: number
  total_reports?: number
  total_report_size_bytes?: number
}

export interface DocumentTypeCount {
  file_type: string
  count: number
}

export interface RecentDocumentItem {
  filename: string
  file_type: string
  uploaded_by: string
  uploaded_at: string
  status: string
}

export interface DocumentInsightsResponse {
  distribution: DocumentTypeCount[]
  recent_documents: RecentDocumentItem[]
}

