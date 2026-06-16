import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Trash2 } from 'lucide-react'
import { chatService } from '../../services/chatService'

const ChatHistoryPage: React.FC = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deleteModalId, setDeleteModalId] = useState<string | null>(null)

  const { data: sessions, isLoading } = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: chatService.getSessions,
  })

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => chatService.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      setDeleteModalId(null)
    },
  })

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  const handleDeleteClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    setDeleteModalId(sessionId)
  }

  const handleConfirmDelete = () => {
    if (deleteModalId) {
      deleteMutation.mutate(deleteModalId)
    }
  }

  // Loading skeleton
  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Chat History</h1>
        <p className="text-slate-500 mt-1 mb-6">Your past conversations.</p>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-slate-100 rounded-xl h-16 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  // Empty state
  if (!sessions || sessions.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Chat History</h1>
        <p className="text-slate-500 mt-1 mb-6">Your past conversations.</p>
        <div className="flex flex-col items-center justify-center py-20">
          <MessageSquare className="w-16 h-16 text-slate-300 mb-4" />
          <p className="text-slate-400 text-lg">No conversations yet.</p>
          <button
            onClick={() => navigate('/dashboard/chat')}
            className="text-indigo-600 hover:text-indigo-500 font-medium mt-2"
          >
            Start a new chat
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800">Chat History</h1>
      <p className="text-slate-500 mt-1 mb-6">Your past conversations.</p>

      <div className="space-y-3">
        {sessions.map((session) => (
          <div
            key={session.id}
            onClick={() => navigate(`/dashboard/chat?session=${session.id}`)}
            className="bg-white border border-slate-200 rounded-xl px-5 py-4 flex items-center justify-between hover:border-indigo-300 cursor-pointer transition-colors group"
          >
            <div className="flex items-start gap-3 min-w-0">
              <MessageSquare className="w-5 h-5 text-indigo-500 flex-shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="text-slate-800 font-medium truncate">{session.title}</p>
                <p className="text-slate-400 text-sm mt-0.5">{formatDate(session.created_at)}</p>
              </div>
            </div>

            <button
              onClick={(e) => handleDeleteClick(e, session.id)}
              className="text-slate-300 hover:text-red-500 p-2 rounded-lg hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
              title="Delete conversation"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Delete confirmation modal */}
      {deleteModalId && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">
            <h2 className="text-lg font-semibold text-slate-800">Delete Conversation</h2>
            <p className="text-slate-500 text-sm mt-2">
              This action cannot be undone. All messages in this conversation will be permanently deleted.
            </p>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setDeleteModalId(null)}
                className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                className="flex-1 px-4 py-2.5 bg-red-500 hover:bg-red-600 text-white rounded-xl font-medium transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ChatHistoryPage
