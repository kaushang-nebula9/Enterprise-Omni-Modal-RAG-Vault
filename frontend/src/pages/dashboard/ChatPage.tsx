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
  Mic,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { chatService } from '../../services/chatService'
import { documentService } from '../../services/documentService'
import type { MessageResponse } from '../../types/chat'
import type { DocumentResponse, FileType } from '../../types/document'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'


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
  
  const activeSessionIdRef = useRef<string | null>(null)
  const mirrorRef = useRef<HTMLDivElement>(null)

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageResponse[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)
  const [attachedDocument, setAttachedDocument] = useState<DocumentResponse | null>(null)
  
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [audioLevels, setAudioLevels] = useState<number[]>([0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
  const [recordingSeconds, setRecordingSeconds] = useState(0)

  const renderHighlightedText = (text: string) => {
    let filenameToHighlight = ""
    if (attachedDocument) {
      filenameToHighlight = attachedDocument.filename
    } else if (uploadedFile?.status === 'ready') {
      filenameToHighlight = uploadedFile.file.name
    }

    if (!filenameToHighlight || !text.includes(filenameToHighlight)) {
      return text
    }

    // Split by filename to highlight it
    const index = text.indexOf(filenameToHighlight)
    const before = text.substring(0, index)
    const filename = text.substring(index, index + filenameToHighlight.length)
    const after = text.substring(index + filenameToHighlight.length)

    return (
      <>
        {before}
        <span
          onClick={() => textareaRef.current?.focus()}
          className="font-semibold bg-indigo-100 dark:bg-indigo-900/60 text-indigo-800 dark:text-indigo-200 px-2 rounded-full border border-indigo-200 dark:border-indigo-800/50 transition-colors duration-150 hover:bg-indigo-200 dark:hover:bg-indigo-800/80 inline-flex items-center gap-1 align-middle pointer-events-auto cursor-pointer select-none "
        >
          <FileText className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
          <span className='text-sm'>{filename}</span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              handleDetach()
            }}
            className="hover:bg-indigo-300 dark:hover:bg-indigo-700/80 rounded-full p-0.5 transition-colors flex items-center justify-center"
            title="Detach file"
          >
            <X className="w-3 h-3 text-indigo-800 dark:text-indigo-200" />
          </button>
        </span>
        {after}
      </>
    )
  }

  const handleDetach = () => {
    let filenameToRemove = ""
    if (attachedDocument) {
      filenameToRemove = attachedDocument.filename
    } else if (uploadedFile?.status === 'ready') {
      filenameToRemove = uploadedFile.file.name
    }

    if (filenameToRemove) {
      const index = inputValue.indexOf(filenameToRemove)
      if (index !== -1) {
        const before = inputValue.substring(0, index)
        const after = inputValue.substring(index + filenameToRemove.length)
        let newText = before + after
        if (before.endsWith(' ') && after.startsWith(' ')) {
          newText = before.slice(0, -1) + after
        }
        setInputValue(newText)
      }
    }

    setAttachedDocument(null)
    setUploadedFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }

    setTimeout(() => {
      textareaRef.current?.focus()
    }, 50)
  }

  const renderMessageContentWithHighlights = (msg: MessageResponse) => {
    const text = msg.content
    const fileName = msg.attached_file?.name

    if (!fileName || !text.includes(fileName)) {
      return text
    }

    const index = text.indexOf(fileName)
    const before = text.substring(0, index)
    const filenameText = text.substring(index, index + fileName.length)
    const after = text.substring(index + fileName.length)

    return (
      <>
        {before}
        <span className="font-semibold text-sm mb-1 bg-white/10 px-2 rounded-full transition-colors duration-150 hover:bg-white/20 hover:cursor-pointer inline-flex items-center gap-1 align-middle">
          <FileText className="w-3.5 h-3.5 text-indigo-200" />
          {filenameText}
        </span>
        {after}
      </>
    )
  }

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

  // Select document and remove the trigger slash, inserting document filename instead of slash
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
        const newText = text.substring(0, slashIndex) + " " + doc.filename + " " + textAfterCursor
        setInputValue(newText)

        setTimeout(() => {
          textareaRef.current?.focus()
          const newCursorPos = slashIndex + doc.filename.length + 2
          textareaRef.current?.setSelectionRange(newCursorPos, newCursorPos)
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

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const isCancelledRef = useRef(false)
  const audioChunksRef = useRef<Blob[]>([])
  const recordingTimeoutRef = useRef<number | null>(null)
  const timerIntervalRef = useRef<number | null>(null)

  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animationFrameRef = useRef<number | null>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, isStreaming])

  // Toast auto-dismiss
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(timer)
  }, [toast])

  // Auto-resize textarea and sync scroll with mirrorRef
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const scrollHeight = textareaRef.current.scrollHeight
      textareaRef.current.style.height = `${scrollHeight}px`
      if (mirrorRef.current) {
        mirrorRef.current.scrollTop = textareaRef.current.scrollTop
      }
    }
  }, [inputValue])

  // Returns the current sessionId, creating one lazily if needed
  const ensureSession = useCallback(async (): Promise<string | null> => {
    if (sessionId) return sessionId
    try {
      const newSession = await chatService.createSession()
      activeSessionIdRef.current = newSession.id
      setSessionId(newSession.id)
      setSearchParams({ session: newSession.id }, { replace: true })
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      return newSession.id
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to create chat session.'
      setError(msg)
      return null
    }
  }, [sessionId, setSearchParams, queryClient])

  const handleSend = useCallback(async (content?: string) => {
    const text = (content ?? inputValue).trim()
    if (!text || isLoading || isStreaming) return

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

    const tempAssistantId = `temp-assistant-${Date.now()}`
    const tempAssistantMsg: MessageResponse = {
      id: tempAssistantId,
      session_id: sid,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      citations: [],
    }

    setMessages((prev) => [...prev, tempUserMsg, tempAssistantMsg])
    setInputValue('')
    
    // Capture document IDs before resetting state
    const docId = attachedDocument?.id || (uploadedFile?.status === 'ready' ? uploadedFile.id : undefined)
    
    setUploadedFile(null)
    setAttachedDocument(null)
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setIsLoading(true)
    setIsStreaming(true)

    chatService.sendQuery(
      sid,
      text,
      (token) => {
        setIsLoading(false)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempAssistantId
              ? { ...msg, content: msg.content + token }
              : msg
          )
        )
      },
      (citations, messageId) => {
        setIsStreaming(false)
        setIsLoading(false)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempAssistantId
              ? { ...msg, id: messageId, citations }
              : msg
          )
        )
        queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      },
      (err) => {
        setIsStreaming(false)
        setIsLoading(false)
        setError(err)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempAssistantId && msg.content === ''
              ? { ...msg, content: 'Error: Failed to get response.' }
              : msg
          )
        )
      },
      docId
    )
  }, [inputValue, isLoading, isStreaming, ensureSession, uploadedFile, attachedDocument, queryClient])

  const urlSessionId = searchParams.get('session')
  const autoQuery = searchParams.get('q')

  // Listen to URL changes to load sessions or clear state
  useEffect(() => {
    // If URL has no session, clear current session (New Chat scenario)
    if (!urlSessionId) {
      if (sessionId !== null) {
        activeSessionIdRef.current = null
        setSessionId(null)
        setMessages([])
        setUploadedFile(null)
        setAttachedDocument(null)
        setInputValue('')
        if (textareaRef.current) textareaRef.current.style.height = 'auto'
      }
      return
    }

    // If URL session matches the currently loaded session or the active transitioning session, do nothing
    if (urlSessionId === sessionId || urlSessionId === activeSessionIdRef.current) return

    // Otherwise, load the new session from the backend
    const loadSession = async () => {
      try {
        const session = await chatService.getSession(urlSessionId)
        activeSessionIdRef.current = session.id
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
    if (!text || isLoading || isStreaming) return

    const tempUserMsg: MessageResponse = {
      id: `temp-${Date.now()}`,
      session_id: sid,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
      citations: [],
    }

    const tempAssistantId = `temp-assistant-${Date.now()}`
    const tempAssistantMsg: MessageResponse = {
      id: tempAssistantId,
      session_id: sid,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      citations: [],
    }

    setMessages((prev) => [...prev, tempUserMsg, tempAssistantMsg])
    setIsLoading(true)
    setIsStreaming(true)

    chatService.sendQuery(
      sid,
      text,
      (token) => {
        setIsLoading(false)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempAssistantId
              ? { ...msg, content: msg.content + token }
              : msg
          )
        )
      },
      (citations, messageId) => {
        setIsStreaming(false)
        setIsLoading(false)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempAssistantId
              ? { ...msg, id: messageId, citations }
              : msg
          )
        )
        queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      },
      (err) => {
        setIsStreaming(false)
        setIsLoading(false)
        setError(err)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempAssistantId && msg.content === ''
              ? { ...msg, content: 'Error: Failed to get response.' }
              : msg
          )
        )
      }
    )
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

      // Auto-insert file name to input text area so it is highlighted inline
      const text = inputValue
      const space = text && !text.endsWith(' ') ? ' ' : ''
      const newText = text + space + file.name + ' '
      setInputValue(newText)
      setTimeout(() => {
        textareaRef.current?.focus()
        if (textareaRef.current) {
          textareaRef.current.setSelectionRange(newText.length, newText.length)
        }
      }, 50)
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

  const startRecording = async () => {
    try {
      setError(null)
      isCancelledRef.current = false
      audioChunksRef.current = []
      setRecordingSeconds(0)

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = async () => {
        if (isCancelledRef.current) {
          return
        }
        const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType || 'audio/webm' })
        setIsTranscribing(true)
        try {
          const result = await chatService.transcribeVoiceQuery(audioBlob)
          if (result && result.text) {
            setInputValue((prev) => (prev ? (prev.endsWith(' ') ? prev : prev + ' ') + result.text : result.text))
          }
        } catch (err: any) {
          console.error(err)
          setToast({ message: "Could not transcribe audio. Please try again.", type: "error" })
        } finally {
          setIsTranscribing(false)
        }
      }

      // Web Audio API setup for waveform visualizer
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
      if (AudioContextClass) {
        const audioContext = new AudioContextClass()
        audioContextRef.current = audioContext
        const source = audioContext.createMediaStreamSource(stream)
        const analyser = audioContext.createAnalyser()
        analyser.fftSize = 64
        source.connect(analyser)
        analyserRef.current = analyser

        const bufferLength = analyser.frequencyBinCount
        const dataArray = new Uint8Array(bufferLength)

        const updateWaveform = () => {
          if (!analyserRef.current) return
          analyserRef.current.getByteFrequencyData(dataArray)
          const numBars = 10
          const levels: number[] = []
          for (let i = 0; i < numBars; i++) {
            const val = dataArray[i * 2 + 1] || 0
            levels.push(val / 255)
          }
          setAudioLevels(levels)
          animationFrameRef.current = requestAnimationFrame(updateWaveform)
        }
        animationFrameRef.current = requestAnimationFrame(updateWaveform)
      }

      mediaRecorder.start()
      setIsRecording(true)

      // Auto stop at 2 minutes (120,000ms)
      recordingTimeoutRef.current = window.setTimeout(() => {
        stopRecording()
      }, 120000)

      // Timer interval
      timerIntervalRef.current = window.setInterval(() => {
        setRecordingSeconds((prev) => prev + 1)
      }, 1000)

    } catch (err: any) {
      console.error(err)
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError("Microphone access denied. Please allow microphone access to use voice input.")
      } else {
        setError("Could not start recording. Please try again.")
      }
    }
  }

  const stopRecording = useCallback(() => {
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current)
      recordingTimeoutRef.current = null
    }
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    analyserRef.current = null

    setIsRecording(false)
  }, [])

  const cancelRecording = useCallback(() => {
    isCancelledRef.current = true
    stopRecording()
  }, [stopRecording])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recordingTimeoutRef.current) clearTimeout(recordingTimeoutRef.current)
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close()
      }
    }
  }, [])

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

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const isAdmin = user?.role?.is_admin ?? false
  const isFileUploading = uploadedFile?.status === 'uploading'
  // Send is disabled while the AI is replying OR a document is still being processed OR recording/transcribing is active
  const isSendDisabled = !inputValue.trim() || isLoading || isStreaming || isFileUploading || isRecording || isTranscribing

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    setInputValue(value)

    // Clear attachment if filename is deleted/modified in input box
    if (attachedDocument && !value.includes(attachedDocument.filename)) {
      setAttachedDocument(null)
    }
    if (uploadedFile?.status === 'ready' && !value.includes(uploadedFile.file.name)) {
      setUploadedFile(null)
    }

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const scrollHeight = textareaRef.current.scrollHeight
      textareaRef.current.style.height = `${scrollHeight}px`
      if (mirrorRef.current) {
        mirrorRef.current.scrollTop = textareaRef.current.scrollTop
      }
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
                      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 text-sm shadow-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors duration-150">
                        <FileText className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                        <span className="max-w-[180px] truncate font-bold">{msg.attached_file.name}</span>
                        <span className="text-slate-400 dark:text-slate-500">{formatFileSize(msg.attached_file.size)}</span>
                      </div>
                    )}
                    <div className="bg-indigo-700 dark:bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-3">
                      <p className="whitespace-pre-wrap">{renderMessageContentWithHighlights(msg)}</p>
                      <p className="text-indigo-300 dark:text-indigo-200 text-xs mt-1 text-right">{formatTime(msg.created_at)}</p>
                    </div>
                  </div>
                ) : msg.content === '' && msg.citations.length === 0 ? null : (
                  <div className="mr-auto max-w-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm text-slate-800 dark:text-slate-100">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        table: ({ ...props }) => (
                          <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm custom-scrollbar">
                            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-left border-collapse" {...props} />
                          </div>
                        ),
                        thead: ({ ...props }) => (
                          <thead className="bg-slate-50 dark:bg-slate-800/50" {...props} />
                        ),
                        tbody: ({ ...props }) => (
                          <tbody className="divide-y divide-slate-100 dark:divide-slate-850 bg-white dark:bg-slate-900" {...props} />
                        ),
                        tr: ({ ...props }) => (
                          <tr className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors duration-150" {...props} />
                        ),
                        th: ({ ...props }) => (
                          <th className="px-4 py-2.5 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider border-b border-slate-200 dark:border-slate-850" {...props} />
                        ),
                        td: ({ ...props }) => (
                          <td className="px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 whitespace-nowrap" {...props} />
                        ),
                        p: ({ ...props }) => (
                          <p className="mb-2 last:mb-0 leading-relaxed" {...props} />
                        ),
                        ul: ({ ...props }) => (
                          <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />
                        ),
                        ol: ({ ...props }) => (
                          <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />
                        ),
                        li: ({ ...props }) => (
                          <li className="text-sm" {...props} />
                        ),
                      }}
                    >
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
              <div className="mr-auto w-fit bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
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
              {uploadedFile && (uploadedFile.status === 'uploading' || uploadedFile.error) && (
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

              {/* Input area */}
              <div className="relative">
                {!isAdmin && (
                  <>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isFileUploading || isLoading || isStreaming}
                      type="button"
                      className="absolute left-2 bottom-2.5 z-20 flex items-center justify-center w-10 h-10 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400"
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

                {isRecording ? (
                  <div
                    className={`flex items-center gap-4 py-3.5 h-[52px] w-full ${
                      !isAdmin ? "pl-12" : "pl-4"
                    } pr-24 text-slate-800 dark:text-slate-100 z-10`}
                  >
                    {/* Soundwave animation */}
                    <div className="flex items-center gap-1 h-8">
                      {audioLevels.map((level, idx) => {
                        const height = 8 + (level * 24);
                        return (
                          <div
                            key={idx}
                            className="w-0.5 bg-indigo-600 dark:bg-indigo-500 rounded-full transition-all duration-100"
                            style={{ height: `${height}px` }}
                          />
                        );
                      })}
                    </div>
                    {/* Timer */}
                    <span className="text-slate-500 dark:text-slate-400 text-sm font-medium">
                      {formatTimer(recordingSeconds)}
                    </span>
                    {/* Status */}
                    <span className="text-slate-400 dark:text-slate-500 text-sm select-none">
                      Recording voice query...
                    </span>
                  </div>
                ) : (
                  <>
                    {/* Mirror Div for inline highlighted tags */}
                    <div
                      ref={mirrorRef}
                      className={`absolute inset-0 pointer-events-none whitespace-pre-wrap break-words py-3 pt-4 border-0 overflow-y-auto custom-scrollbar select-none text-slate-800 dark:text-slate-100 z-10 ${
                        !isAdmin ? "pl-12 pr-24" : "pl-4 pr-24"
                      }`}
                      style={{
                        fontFamily: 'inherit',
                        fontSize: 'inherit',
                        lineHeight: 'inherit',
                        maxHeight: '200px',
                      }}
                    >
                      {renderHighlightedText(inputValue)}
                    </div>

                    <textarea
                      ref={textareaRef}
                      value={inputValue}
                      onChange={handleInputChange}
                      onKeyDown={handleKeyDown}
                      onScroll={(e) => {
                        if (mirrorRef.current) {
                          mirrorRef.current.scrollTop = e.currentTarget.scrollTop
                        }
                      }}
                      disabled={isFileUploading || isLoading || isStreaming || isTranscribing}
                      placeholder={
                        isFileUploading
                          ? "Please wait while the document is processed..."
                          : "Ask about your documents..."
                      }
                      rows={1}
                      className={`w-full text-transparent caret-slate-800 dark:caret-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 bg-transparent py-3 pt-4 resize-none focus:outline-none border-0 placeholder:pl-1 custom-scrollbar relative z-0 ${
                        !isAdmin ? "pl-12 pr-24" : "pl-4 pr-24"
                      }`}
                      style={{ maxHeight: "200px" }}
                    />
                  </>
                )}

                {/* Cancel Button */}
                {isRecording && (
                  <button
                    onClick={cancelRecording}
                    type="button"
                    className="absolute right-[104px] bottom-2 z-20 flex items-center justify-center w-10 h-10 rounded-full text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:text-slate-500 dark:hover:text-red-400 dark:hover:bg-slate-800 transition-all duration-200"
                    title="Cancel recording"
                  >
                    <X className="w-5 h-5" />
                  </button>
                )}

                {/* Mic Button */}
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={isTranscribing}
                  type="button"
                  className={`absolute right-14 bottom-2 z-20 flex items-center justify-center w-10 h-10 rounded-full transition-all duration-200 ${
                    isRecording
                      ? "bg-red-500 hover:bg-red-600 text-white animate-pulse"
                      : isTranscribing
                      ? "bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed"
                      : "text-slate-400 hover:text-indigo-600 dark:text-slate-500 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                  }`}
                  title={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Record voice query"}
                >
                  {isTranscribing ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : isRecording ? (
                    <div className="w-3.5 h-3.5 bg-white rounded-sm" />
                  ) : (
                    <Mic className="w-5 h-5" />
                  )}
                </button>

                {/* Send Button */}
                <button
                  onClick={() => handleSend()}
                  disabled={isSendDisabled}
                  type="button"
                  className="absolute right-2 bottom-2 z-20 flex items-center justify-center w-10 h-10 rounded-full bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white disabled:opacity-50"
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
