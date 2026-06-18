export interface SessionResponse {
  id: string
  user_id: string
  tenant_id: string
  title: string
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
}

export interface SessionDetailResponse extends SessionResponse {
  messages: MessageResponse[]
}

export interface QueryResponse {
  answer: string
  citations: CitationResponse[]
  message_id: string
}
