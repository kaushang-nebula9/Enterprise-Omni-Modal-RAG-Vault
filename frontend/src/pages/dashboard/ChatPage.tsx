import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { SendHorizontal, Plus, FileText, ChevronDown, ChevronUp, X, Loader2 } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { chatService } from '../../services/chatService'
import type { MessageResponse } from '../../types/chat'
import ReactMarkdown from 'react-markdown'

interface UploadedFile {
  file: File
  status: 'uploading' | 'ready'
  error?: string
}

const ChatPage: React.FC = () => {
  const { user } = useAuthStore()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageResponse[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

  // Returns the current sessionId, creating one lazily if needed
  const ensureSession = useCallback(async (): Promise<string | null> => {
    if (sessionId) return sessionId
    try {
      const newSession = await chatService.createSession()
      setSessionId(newSession.id)
      setSearchParams({ session: newSession.id }, { replace: true })
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      return newSession.id
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to create chat session.'
      setError(msg)
      return null
    }
  }, [sessionId])

  const handleSend = useCallback(async (content?: string) => {
    const text = (content ?? inputValue).trim()
    if (!text || isLoading) return

    setError(null)

    // Lazily create a session on the first message
    const sid = await ensureSession()
    if (!sid) return

    const attachedFile = uploadedFile?.status === 'ready' ? {
      name: uploadedFile.file.name,
      size: uploadedFile.file.size
    } : undefined;

    // Optimistically add user message
    const tempUserMsg: MessageResponse = {
      id: `temp-${Date.now()}`,
      session_id: sid,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
      citations: [],
      attached_file: attachedFile
    }
    setMessages((prev) => [...prev, tempUserMsg])
    setInputValue('')
    setUploadedFile(null)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
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
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to get a response.'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [inputValue, isLoading, ensureSession, uploadedFile])

  const urlSessionId = searchParams.get('session')
  const autoQuery = searchParams.get('q')

  // Listen to URL changes to load sessions or clear state
  useEffect(() => {
    // If URL has no session, clear current session (New Chat scenario)
    if (!urlSessionId) {
      if (sessionId !== null) {
        setSessionId(null)
        setMessages([])
        setUploadedFile(null)
        setInputValue('')
        if (textareaRef.current) textareaRef.current.style.height = 'auto'
      }
      return
    }

    // If URL session matches the currently loaded session, do nothing
    if (urlSessionId === sessionId) return

    // Otherwise, load the new session from the backend
    const loadSession = async () => {
      try {
        const session = await chatService.getSession(urlSessionId)
        setSessionId(session.id)
        // Sort chronologically, fallback to role for identical timestamps
        const sortedMessages = [...session.messages].sort((a, b) => {
          const timeDiff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          if (timeDiff !== 0) return timeDiff
          if (a.role === 'user' && b.role === 'assistant') return -1
          if (a.role === 'assistant' && b.role === 'user') return 1
          return 0
        })
        setMessages(sortedMessages)
        setUploadedFile(null) // clear any attached file from previous chat

        if (autoQuery) {
          // Small delay to let state settle
          setTimeout(() => {
            handleSendDirect(session.id, autoQuery)
          }, 100)
        }
      } catch (err: any) {
        const msg = err?.response?.data?.detail || err?.message || 'Failed to load chat session.'
        setError(msg)
      }
    }

    loadSession()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlSessionId, autoQuery])

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
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
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
    if (!file) return

    // Reset file input immediately so the same file can be re-selected
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }

    // Show the file pill in "uploading" state
    setUploadedFile({ file, status: 'uploading' })

    // Lazily create a session if this is the first interaction
    const sid = await ensureSession()
    if (!sid) {
      setUploadedFile({ file, status: 'ready', error: 'No session available.' })
      return
    }

    try {
      await chatService.uploadPrivateDocument(sid, file)
      setUploadedFile({ file, status: 'ready' })
      setToast({ message: 'Document ready. You can now ask questions about it.', type: 'success' })
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to upload document.'
      setUploadedFile({ file, status: 'ready', error: msg })
      setToast({ message: msg, type: 'error' })
    }
  }

  const handleRemoveFile = () => {
    setUploadedFile(null)
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
  const isFileUploading = uploadedFile?.status === 'uploading'
  // Send is disabled while the AI is replying OR a document is still being processed
  const isSendDisabled = !inputValue.trim() || isLoading || isFileUploading

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const greeting = useMemo(() => {
    const greetings = ['Hello', 'Hey', 'Hi']
    const randomGreeting = greetings[Math.floor(Math.random() * greetings.length)]
    
    const hour = new Date().getHours()
    let timeGreeting = 'evening'
    if (hour >= 5 && hour < 12) timeGreeting = 'morning'
    else if (hour >= 12 && hour < 17) timeGreeting = 'afternoon'

    const firstName = user?.full_name?.split(' ')[0] || 'there'

    return `${randomGreeting} ${firstName}, good ${timeGreeting}!`
  }, [user?.full_name])

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
          <div className="">
          </div>
        ) : (
          <div className="max-w-3xl mx-auto w-full space-y-4">
            {messages.map((msg) => (
              <div key={msg.id}>
                {msg.role === 'user' ? (
                  <div className="ml-auto max-w-2xl flex flex-col items-end gap-2">
                    {msg.attached_file && (
                      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm shadow-sm">
                        <FileText className="w-4 h-4 text-indigo-500" />
                        <span className="max-w-[180px] truncate font-medium">{msg.attached_file.name}</span>
                        <span className="text-slate-400">{formatFileSize(msg.attached_file.size)}</span>
                      </div>
                    )}
                    <div className="bg-indigo-700 text-white rounded-2xl rounded-br-md px-4 py-3">
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      <p className="text-indigo-300 text-xs mt-1 text-right">{formatTime(msg.created_at)}</p>
                    </div>
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
      <div
        className={
        messages.length === 0
          ? "min-h-[calc(100vh-80px)] flex flex-col items-center justify-center"
        : ""
      }
      >
        {messages.length === 0 && !isLoading ? (

          <div className="flex flex-col items-center justify-center pb-8 space-y-2">
            <h2 className="text-3xl font-semibold text-slate-800 tracking-tight">
              {greeting}
            </h2>
            <p className="text-slate-500 text-lg">How can I help you today?</p>
          </div>
        ) : null}

      <div className="w-full">
        <div className="">
          <div className={`max-w-3xl mx-auto h-full ${messages.length === 0 ? 'mb-32' : ''}`}>

            {/* Input row */}
            <div className="border border-slate-300 rounded-3xl bg-slate-800 focus-within:ring-2 focus-within:ring-indigo-500 text-white mb-2">

              {/* File preview inside input */}
              {uploadedFile && (
                <div className="px-3 pt-3">
                  <div
                    className={`inline-flex items-center gap-2 px-3 py-2 ml-8 rounded-xl border text-sm ${
                      uploadedFile.error
                        ? "border-red-200 bg-red-50 text-red-700"
                        : uploadedFile.status === "uploading"
                        ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                        : "border-emerald-200 bg-emerald-50 text-emerald-700"
                    }`}
                  >
                    {uploadedFile.status === "uploading" ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <FileText className="w-4 h-4" />
                    )}

                    <span className="max-w-[180px] truncate">
                      {uploadedFile.file.name}
                    </span>

                    <span>
                      {formatFileSize(uploadedFile.file.size)}
                    </span>

                    {uploadedFile.status !== "uploading" && (
                      <button
                        onClick={handleRemoveFile}
                        className="hover:bg-black/5 rounded-full p-1"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Input area */}
              <div className="relative">
                {!isAdmin && (
                  <>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isFileUploading}
                      type="button"
                      className="absolute left-2 bottom-2.5 z-10 flex items-center justify-center w-10 h-10 rounded-full hover:bg-white/10"
                    >
                      <Plus className="w-5 h-5" strokeWidth={2.5} />
                    </button>

                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      onChange={handleFileUpload}
                    />
                  </>
                )}

                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    isFileUploading
                      ? "Please wait while the document is processed..."
                      : "Ask about your documents..."
                  }
                  rows={1}
                  className={`w-full placeholder:text-white/80 bg-transparent py-3 pt-4 resize-none focus:outline-none border-0 placeholder:pl-1 custom-scrollbar ${
                    !isAdmin ? "pl-12 pr-14" : "pl-4 pr-14"
                  }`}
                  style={{ maxHeight: "200px" }}
                />

                <button
                  onClick={() => handleSend()}
                  disabled={isSendDisabled}
                  type="button"
                  className="absolute right-2 bottom-2 flex items-center justify-center w-10 h-10 rounded-full bg-indigo-500  text-white disabled:opacity-50"
                >
                  <SendHorizontal className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Error display */}
            {error && (
              <p className="text-red-500 text-sm mt-1">
                {error}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
    </div>
  )
}

export default ChatPage
