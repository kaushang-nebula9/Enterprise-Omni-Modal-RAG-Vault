import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SendHorizontal, Paperclip, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { chatService } from '../../services/chatService'
import type { MessageResponse } from '../../types/chat'
import ReactMarkdown from 'react-markdown'

const ChatPage: React.FC = () => {
  const { user } = useAuthStore()
  const [searchParams] = useSearchParams()

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageResponse[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const sessionReadyRef = useRef(false)
  const initRef = useRef(false)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Toast auto-dismiss
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(timer)
  }, [toast])

  const handleSend = useCallback(async (content?: string) => {
    const text = (content ?? inputValue).trim()
    if (!text || isLoading || !sessionId) return

    setError(null)

    // Optimistically add user message
    const tempUserMsg: MessageResponse = {
      id: `temp-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
      citations: [],
    }
    setMessages((prev) => [...prev, tempUserMsg])
    setInputValue('')
    setIsLoading(true)

    try {
      const response = await chatService.sendQuery(sessionId, text)
      const assistantMsg: MessageResponse = {
        id: response.message_id,
        session_id: sessionId,
        role: 'assistant',
        content: response.answer,
        created_at: new Date().toISOString(),
        citations: response.citations,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to get a response.'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [inputValue, isLoading, sessionId])

  // Initialize session on mount
  useEffect(() => {
    if (initRef.current) return
    initRef.current = true

    const init = async () => {
      const existingSessionId = searchParams.get('session')
      const autoQuery = searchParams.get('q')

      try {
        if (existingSessionId) {
          const session = await chatService.getSession(existingSessionId)
          setSessionId(session.id)
          setMessages(session.messages)
          sessionReadyRef.current = true

          if (autoQuery) {
            // Small delay to let state settle
            setTimeout(() => {
              handleSendDirect(session.id, autoQuery)
            }, 100)
          }
        } else {
          const newSession = await chatService.createSession()
          setSessionId(newSession.id)
          window.history.replaceState(null, '', `?session=${newSession.id}`)
          sessionReadyRef.current = true

          if (autoQuery) {
            setTimeout(() => {
              handleSendDirect(newSession.id, autoQuery)
            }, 100)
          }
        }
      } catch (err: any) {
        const msg = err?.response?.data?.detail || err?.message || 'Failed to initialize chat session.'
        setError(msg)
      }
    }

    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Direct send that takes sessionId as parameter (for use before state updates)
  const handleSendDirect = async (sid: string, content: string) => {
    const text = content.trim()
    if (!text) return

    const tempUserMsg: MessageResponse = {
      id: `temp-${Date.now()}`,
      session_id: sid,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
      citations: [],
    }
    setMessages((prev) => [...prev, tempUserMsg])
    setIsLoading(true)

    try {
      const response = await chatService.sendQuery(sid, text)
      const assistantMsg: MessageResponse = {
        id: response.message_id,
        session_id: sid,
        role: 'assistant',
        content: response.answer,
        created_at: new Date().toISOString(),
        citations: response.citations,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to get a response.'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }

  const toggleCitations = (messageId: string) => {
    setExpandedCitations((prev) => {
      const next = new Set(prev)
      if (next.has(messageId)) {
        next.delete(messageId)
      } else {
        next.add(messageId)
      }
      return next
    })
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !sessionId) return

    try {
      await chatService.uploadPrivateDocument(sessionId, file)
      setToast({ message: 'Document uploaded. You can now ask questions about it.', type: 'success' })
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to upload document.'
      setToast({ message: msg, type: 'error' })
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    })
  }

  const isAdmin = user?.role?.is_admin ?? false

  return (
    <div className="flex flex-col -m-6 h-[calc(100vh-4rem)]">
      {/* Toast notification */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 rounded-xl px-4 py-3 shadow-lg text-sm font-medium transition-all ${
            toast.type === 'success' ? 'bg-emerald-500 text-white' : 'bg-red-500 text-white'
          }`}
        >
          {toast.message}
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && !isLoading ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-slate-400 text-lg">Ask anything about your documents.</p>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto w-full space-y-4">
            {messages.map((msg) => (
              <div key={msg.id}>
                {msg.role === 'user' ? (
                  <div className="ml-auto max-w-2xl bg-indigo-700 text-white rounded-2xl rounded-br-md px-4 py-3">
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    <p className="text-indigo-300 text-xs mt-1 text-right">{formatTime(msg.created_at)}</p>
                  </div>
                ) : (
                  <div className="mr-auto max-w-2xl bg-white border border-slate-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm text-slate-800">
                    <ReactMarkdown>
                      {msg.content}
                    </ReactMarkdown>
                    <p className="text-slate-400 text-xs mt-1">{formatTime(msg.created_at)}</p>

                    {msg.citations.length > 0 && (
                      <div className="mt-2">
                        <button
                          onClick={() => toggleCitations(msg.id)}
                          className="text-indigo-600 text-sm hover:underline cursor-pointer flex items-center gap-1"
                        >
                          Sources ({msg.citations.length})
                          {expandedCitations.has(msg.id) ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>

                        {expandedCitations.has(msg.id) && (
                          <div className="mt-2 space-y-2">
                            {msg.citations.map((cite) => (
                              <div key={cite.id} className="bg-slate-50 rounded-lg p-3 space-y-1">
                                <div className="flex items-center gap-2">
                                  <FileText className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                                  <span className="text-slate-700 font-medium text-sm">{cite.filename}</span>
                                  {cite.page_number !== null && (
                                    <span className="text-slate-500 text-xs">Page {cite.page_number}</span>
                                  )}
                                </div>
                                <p className="text-slate-500 text-xs italic">
                                  {cite.chunk_text.length > 150
                                    ? `${cite.chunk_text.slice(0, 150)}...`
                                    : cite.chunk_text}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Typing indicator */}
            {isLoading && (
              <div className="mr-auto bg-white border border-slate-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="bg-white border-t border-slate-200 px-4 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          {/* Upload button (members only) */}
          {!isAdmin && (
            <>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-slate-400 hover:text-indigo-600 p-2 rounded-lg hover:bg-slate-100 transition-colors"
                title="Upload a document"
              >
                <Paperclip className="w-5 h-5" />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileUpload}
              />
            </>
          )}

          {/* Text input */}
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your documents..."
            rows={1}
            className="flex-1 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none bg-slate-50"
            style={{ maxHeight: '120px' }}
          />

          {/* Send button */}
          <button
            onClick={() => handleSend()}
            disabled={!inputValue.trim() || isLoading}
            className="bg-indigo-700 hover:bg-indigo-600 text-white rounded-xl p-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <SendHorizontal className="w-5 h-5" />
          </button>
        </div>

        {/* Error display */}
        {error && <p className="text-red-500 text-sm mt-1 max-w-3xl mx-auto">{error}</p>}
      </div>
    </div>
  )
}

export default ChatPage
