import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  SendHorizontal,
  Plus,
  FileText,
  ChevronDown,
  ChevronUp,
  X,
  Loader2,
  File,
  FilePen,
  Presentation,
  FileSpreadsheet,
  FileMusic,
  Search,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { chatService } from '../../services/chatService'
import { documentService } from '../../services/documentService'
import type { MessageResponse } from '../../types/chat'
import type { DocumentResponse, FileType } from '../../types/document'
import ReactMarkdown from 'react-markdown'

interface UploadedFile {
  file: File
  status: 'uploading' | 'ready'
  error?: string
  id?: string
}

const FILE_TYPE_ICON: Record<FileType, React.FC<{ className?: string }>> = {
  text: FileText,
  pdf: File,
  docx: FilePen,
  pptx: Presentation,
  excel: FileSpreadsheet,
  audio: FileMusic,
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
  const [attachedDocument, setAttachedDocument] = useState<DocumentResponse | null>(null)

  // Dropdown UI states
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [dropdownSearch, setDropdownSearch] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)

  const dropdownRef = useRef<HTMLDivElement>(null)
  const dropdownSearchInputRef = useRef<HTMLInputElement>(null)

  // Fetch authorized documents
  const { data: authorizedDocs, isLoading: isLoadingAuth } = useQuery({
    queryKey: ['authorized-documents'],
    queryFn: () => documentService.getAuthorizedDocuments(),
  })

  // Fetch personal documents
  const { data: personalDocs, isLoading: isLoadingPersonal } = useQuery({
    queryKey: ['personal-documents'],
    queryFn: () => documentService.getPersonalDocuments(),
  })

  // Combined ready documents list
  const allDocs = useMemo(() => {
    const authList = authorizedDocs ?? []
    const personalList = personalDocs ?? []
    const docMap = new Map<string, DocumentResponse>()

    authList.forEach(doc => {
      if (doc.status === 'ready') docMap.set(doc.id, doc)
    })
    personalList.forEach(doc => {
      if (doc.status === 'ready') docMap.set(doc.id, doc)
    })

    return Array.from(docMap.values())
  }, [authorizedDocs, personalDocs])

  // Filtered documents for search query
  const filteredDocs = useMemo(() => {
    const query = dropdownSearch.trim().toLowerCase()
    if (!query) return allDocs
    return allDocs.filter(doc => doc.filename.toLowerCase().includes(query))
  }, [allDocs, dropdownSearch])

  // Reset activeIndex when filtered docs change
  useEffect(() => {
    setActiveIndex(0)
  }, [filteredDocs])

  // Focus search box when dropdown opens
  useEffect(() => {
    if (isDropdownOpen) {
      setTimeout(() => {
        dropdownSearchInputRef.current?.focus()
      }, 50)
    }
  }, [isDropdownOpen])

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isDropdownOpen])

  // Select document and remove the trigger slash
  const handleSelectDocument = (doc: DocumentResponse) => {
    setAttachedDocument(doc)
    setUploadedFile(null) // clear any uploaded file to avoid duplicate attachments
    setIsDropdownOpen(false)
    setDropdownSearch('')

    if (textareaRef.current) {
      const cursor = textareaRef.current.selectionStart
      const text = inputValue
      const textBeforeCursor = text.substring(0, cursor)
      const textAfterCursor = text.substring(cursor)

      const match = textBeforeCursor.match(/(?:^|\s)\/(\S*)$/)
      if (match) {
        const slashIndex = textBeforeCursor.lastIndexOf('/')
        const newText = text.substring(0, slashIndex) + textAfterCursor
        setInputValue(newText)

        setTimeout(() => {
          textareaRef.current?.focus()
          textareaRef.current?.setSelectionRange(slashIndex, slashIndex)
        }, 50)
      } else {
        textareaRef.current.focus()
      }
    }
  }

  // Keyboard navigation for dropdown
  const handleDropdownKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((prev) => (filteredDocs.length > 0 ? (prev + 1) % filteredDocs.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((prev) => (filteredDocs.length > 0 ? (prev - 1 + filteredDocs.length) % filteredDocs.length : 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filteredDocs[activeIndex]) {
        handleSelectDocument(filteredDocs[activeIndex])
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setIsDropdownOpen(false)
      textareaRef.current?.focus()
    }
  }

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

    let attachedFile = undefined
    if (attachedDocument) {
      attachedFile = {
        name: attachedDocument.filename,
        size: attachedDocument.file_size || 0
      }
    } else if (uploadedFile?.status === 'ready') {
      attachedFile = {
        name: uploadedFile.file.name,
        size: uploadedFile.file.size
      }
    }

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
    
    // Capture document IDs before resetting state
    const docId = attachedDocument?.id || (uploadedFile?.status === 'ready' ? uploadedFile.id : undefined)
    
    setUploadedFile(null)
    setAttachedDocument(null)
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setIsLoading(true)

    try {
      const response = await chatService.sendQuery(sid, text, docId)
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
  }, [inputValue, isLoading, ensureSession, uploadedFile, attachedDocument])

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
        setAttachedDocument(null)
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
        setAttachedDocument(null)

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

    setAttachedDocument(null) // clear selected catalog document

    // Show the file pill in "uploading" state
    setUploadedFile({ file, status: 'uploading' })

    // Lazily create a session if this is the first interaction
    const sid = await ensureSession()
    if (!sid) {
      setUploadedFile({ file, status: 'ready', error: 'No session available.' })
      return
    }

    try {
      const response = await chatService.uploadPrivateDocument(sid, file)
      setUploadedFile({ file, status: 'ready', id: response.id })
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
    const value = e.target.value
    setInputValue(value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }

    const selectionStart = e.target.selectionStart
    const textBeforeCursor = value.substring(0, selectionStart)
    const isSlashTrigger = textBeforeCursor === '/' || textBeforeCursor.endsWith(' /') || textBeforeCursor.endsWith('\n/')
    if (isSlashTrigger) {
      setIsDropdownOpen(true)
      setDropdownSearch('')
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
                      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 text-sm shadow-sm">
                        <FileText className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                        <span className="max-w-[180px] truncate font-medium">{msg.attached_file.name}</span>
                        <span className="text-slate-400 dark:text-slate-500">{formatFileSize(msg.attached_file.size)}</span>
                      </div>
                    )}
                    <div className="bg-indigo-700 dark:bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-3">
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      <p className="text-indigo-300 dark:text-indigo-200 text-xs mt-1 text-right">{formatTime(msg.created_at)}</p>
                    </div>
                  </div>
                ) : (
                  <div className="mr-auto max-w-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm text-slate-800 dark:text-slate-100">
                    <ReactMarkdown>
                      {msg.content}
                    </ReactMarkdown>
                    <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">{formatTime(msg.created_at)}</p>

                    {msg.citations.length > 0 && (
                      <div className="mt-2">
                        <button
                          onClick={() => toggleCitations(msg.id)}
                          className="text-indigo-600 dark:text-indigo-400 text-sm hover:underline cursor-pointer flex items-center gap-1"
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
                              <div key={cite.id} className="bg-slate-50 dark:bg-slate-950 rounded-lg p-3 space-y-1">
                                <div className="flex items-center gap-2">
                                  <FileText className="w-4 h-4 text-indigo-500 dark:text-indigo-400 flex-shrink-0" />
                                  <span className="text-slate-700 dark:text-slate-300 font-medium text-sm">{cite.filename}</span>
                                  {cite.page_number !== null && (
                                    <span className="text-slate-500 dark:text-slate-400 text-xs">Page {cite.page_number}</span>
                                  )}
                                </div>
                                <p className="text-slate-500 dark:text-slate-400 text-xs italic">
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
              <div className="mr-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 bg-slate-400 dark:bg-slate-600 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-slate-400 dark:bg-slate-600 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-slate-400 dark:bg-slate-600 rounded-full animate-bounce"
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
            <h2 className="text-3xl font-semibold text-slate-800 dark:text-slate-100 tracking-tight">
              {greeting}
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-lg">How can I help you today?</p>
          </div>
        ) : null}

      <div className="w-full">
        <div className="">
          <div className={`relative max-w-3xl mx-auto h-full ${messages.length === 0 ? 'mb-32' : ''}`}>

            {/* Document Autocomplete Dropdown */}
            {isDropdownOpen && (
              <div
                ref={dropdownRef}
                className="absolute bottom-full left-0 mb-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl p-3 z-50 flex flex-col gap-2 transition-all h-72 w-1/2 text-slate-800 dark:text-slate-100"
              >
                {/* Search Bar */}
                <div className="relative flex items-center flex-shrink-0">
                  <Search className="absolute left-3 w-4 h-4 text-slate-400 dark:text-slate-500" />
                  <input
                    ref={dropdownSearchInputRef}
                    type="text"
                    value={dropdownSearch}
                    onChange={(e) => setDropdownSearch(e.target.value)}
                    onKeyDown={handleDropdownKeyDown}
                    placeholder="Search authorized documents..."
                    className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl pl-9 pr-4 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-500"
                  />
                </div>

                {/* Loading state */}
                {(isLoadingAuth || isLoadingPersonal) ? (
                  <div className="flex-1 flex items-center justify-center gap-2 text-slate-500 dark:text-slate-400 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin text-indigo-600 dark:text-indigo-400" />
                    Loading authorized documents...
                  </div>
                ) : filteredDocs.length === 0 ? (
                  /* Empty state */
                  <div className="flex-1 flex items-center justify-center text-slate-400 dark:text-slate-500 text-sm">
                    No accessible documents found.
                  </div>
                ) : (
                  /* Documents List */
                  <div className="flex-1 overflow-y-auto space-y-0.5 custom-scrollbar pr-1">
                    {filteredDocs.map((doc, idx) => {
                      const Icon = FILE_TYPE_ICON[doc.file_type] || FileText
                      const isActive = idx === activeIndex
                      return (
                        <button
                          key={doc.id}
                          onClick={() => handleSelectDocument(doc)}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left transition-colors ${
                            isActive
                              ? "bg-indigo-700 dark:bg-indigo-600 text-white"
                              : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-white" : "text-indigo-600 dark:text-indigo-400"}`} />
                            <span className="truncate text-sm font-medium pr-1.5">
                              {doc.filename}
                            </span>
                          </div>
                          <div className="flex items-center gap-1 flex-shrink-0 text-xs">
                            {doc.owner_type === 'private' ? (
                              <span className={`px-2 py-0.5 rounded-md ${
                                isActive ? "bg-white/20 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                              }`}>
                                Personal
                              </span>
                            ) : (
                              <span className={`px-2 py-0.5 rounded-md ${
                                isActive ? "bg-white/20 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                              }`}>
                                Org
                              </span>
                            )}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Input row */}
            <div className="border border-slate-200 dark:border-slate-700 rounded-3xl bg-white dark:bg-slate-900 focus-within:ring-2 focus-within:ring-indigo-500 text-slate-800 dark:text-slate-100 mb-2">

              {/* File preview inside input */}
              {uploadedFile && (
                <div className="px-3 pt-3">
                  <div
                    className={`inline-flex items-center gap-2 px-3 py-2 ml-8 rounded-xl border text-sm ${
                      uploadedFile.error
                        ? "border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400"
                        : uploadedFile.status === "uploading"
                        ? "border-indigo-200 dark:border-indigo-900/50 bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400"
                        : "border-emerald-200 dark:border-emerald-900/50 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400"
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
                        className="hover:bg-black/5 dark:hover:bg-white/10 rounded-full p-1"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Attached document preview inside input */}
              {attachedDocument && (
                <div className="px-3 pt-3">
                  <div className="inline-flex items-center gap-2 px-3 py-2 ml-8 rounded-xl border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 text-sm">
                    <FileText className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                    <span className="max-w-[180px] truncate font-medium">
                      {attachedDocument.filename}
                    </span>
                    {attachedDocument.file_size && (
                      <span className="text-slate-500 dark:text-slate-400 text-xs">
                        ({formatFileSize(attachedDocument.file_size)})
                      </span>
                    )}
                    <button
                      onClick={() => setAttachedDocument(null)}
                      className="hover:bg-black/5 dark:hover:bg-white/10 rounded-full p-1"
                    >
                      <X className="w-3 h-3" />
                    </button>
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
                      className="absolute left-2 bottom-2.5 z-10 flex items-center justify-center w-10 h-10 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400"
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
                  className={`w-full text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 bg-transparent py-3 pt-4 resize-none focus:outline-none border-0 placeholder:pl-1 custom-scrollbar ${
                    !isAdmin ? "pl-12 pr-14" : "pl-4 pr-14"
                  }`}
                  style={{ maxHeight: "200px" }}
                />

                <button
                  onClick={() => handleSend()}
                  disabled={isSendDisabled}
                  type="button"
                  className="absolute right-2 bottom-2 flex items-center justify-center w-10 h-10 rounded-full bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white disabled:opacity-50"
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
