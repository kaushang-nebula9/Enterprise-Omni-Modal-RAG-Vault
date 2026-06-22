import api from './api'
import type { SessionResponse, SessionDetailResponse, CitationResponse } from '../types/chat'
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

  sendQuery: (
    sessionId: string,
    content: string,
    onToken: (token: string) => void,
    onDone: (citations: CitationResponse[], messageId: string) => void,
    onError: (error: string) => void,
    documentId?: string
  ): void => {
    const baseURL = api.defaults.baseURL || 'http://localhost:8000'
    const url = `${baseURL}/api/v1/chat/sessions/${sessionId}/query`

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content,
        document_id: documentId,
      }),
      credentials: 'include',
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = await response.text()
          throw new Error(text || 'Failed to send query')
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('Response body is not readable')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { value, done } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            const trimmedLine = line.trim()
            if (!trimmedLine) continue

            if (trimmedLine.startsWith('data:')) {
              const dataStr = trimmedLine.slice(5).trim()
              try {
                const parsed = JSON.parse(dataStr)
                if (parsed.type === 'token') {
                  onToken(parsed.content)
                } else if (parsed.type === 'done') {
                  onDone(parsed.citations, parsed.message_id)
                } else if (parsed.type === 'error') {
                  onError(parsed.content)
                }
              } catch (e) {
                console.error('Failed to parse SSE event data', e, trimmedLine)
              }
            }
          }
        }

        if (buffer.trim()) {
          const trimmedLine = buffer.trim()
          if (trimmedLine.startsWith('data:')) {
            const dataStr = trimmedLine.slice(5).trim()
            try {
              const parsed = JSON.parse(dataStr)
              if (parsed.type === 'token') {
                onToken(parsed.content)
              } else if (parsed.type === 'done') {
                onDone(parsed.citations, parsed.message_id)
              } else if (parsed.type === 'error') {
                onError(parsed.content)
              }
            } catch (e) {
              console.error('Failed to parse final SSE event data', e, trimmedLine)
            }
          }
        }
      })
      .catch((error) => {
        onError(error.message || String(error))
      })
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

  transcribeVoiceQuery: async (audioBlob: Blob): Promise<{ text: string }> => {
    const formData = new FormData()
    const ext = audioBlob.type.split('/')[1]?.split(';')[0] || 'webm'
    formData.append('audio', audioBlob, `voice_query.${ext}`)
    const response = await api.post<{ text: string }>(
      '/api/v1/chat/transcribe',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return response.data
  },
}
