export interface SessionResponse {
  id: string
  user_id: string
  tenant_id: string
  title: string
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export interface CitationResponse {
  id: string
  document_id: string
  filename: string
  chunk_text: string
  page_number: number | null
  chunk_index: number
}

export interface AvailableModel {
  id: string
  display_name: string
  provider: 'anthropic' | 'openrouter'
  model_string: string
  is_active: boolean
  input_price_per_million?: number | null
  output_price_per_million?: number | null
  created_at: string
}

export interface MessageResponse {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  citations: CitationResponse[]
  attached_file?: {
    name: string
    size: number
  }
  model_id?: string
  model?: AvailableModel
}

export interface SessionDetailResponse extends SessionResponse {
  messages: MessageResponse[]
}

export interface QueryResponse {
  answer: string
  citations: CitationResponse[]
  message_id: string
}
