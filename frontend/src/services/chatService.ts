import api from './api'
import type { SessionResponse, SessionDetailResponse, QueryResponse } from '../types/chat'
import type { DocumentResponse } from '../types/document'
import type { MessageResponse as ApiMessageResponse } from '../types/auth'

export const chatService = {
  createSession: async (): Promise<SessionResponse> => {
    const response = await api.post<SessionResponse>('/api/v1/chat/sessions')
    return response.data
  },

  getSessions: async (): Promise<SessionResponse[]> => {
    const response = await api.get<SessionResponse[]>('/api/v1/chat/sessions')
    return response.data
  },

  getSession: async (sessionId: string): Promise<SessionDetailResponse> => {
    const response = await api.get<SessionDetailResponse>(`/api/v1/chat/sessions/${sessionId}`)
    return response.data
  },

  deleteSession: async (sessionId: string): Promise<ApiMessageResponse> => {
    const response = await api.delete<ApiMessageResponse>(`/api/v1/chat/sessions/${sessionId}`)
    return response.data
  },

  sendQuery: async (sessionId: string, content: string): Promise<QueryResponse> => {
    const response = await api.post<QueryResponse>(`/api/v1/chat/sessions/${sessionId}/query`, { content })
    return response.data
  },

  uploadPrivateDocument: async (sessionId: string, file: File): Promise<DocumentResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post<DocumentResponse>(
      `/api/v1/chat/sessions/${sessionId}/upload`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return response.data
  },
}
