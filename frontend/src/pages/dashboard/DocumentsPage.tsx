import React, { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FileText,
  File,
  Presentation,
  FileSpreadsheet,
  FileMusic,
  FilePen,
  Search,
  Upload,
  Download,
  Pencil,
  Trash2,
  X,
  CheckSquare,
  Square,
  AlertTriangle,
  ChevronDown,
} from 'lucide-react'
import { documentService } from '../../services/documentService'
import { roleService } from '../../services/roleService'
import type { DocumentResponse, FileType, DocumentStatus } from '../../types/document'
import type { RoleResponse } from '../../types/auth'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return '--'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const FILE_TYPE_ICON: Record<FileType, React.FC<{ className?: string }>> = {
  text: FileText,
  pdf: File,
  docx: FilePen,
  pptx: Presentation,
  excel: FileSpreadsheet,
  audio: FileMusic,
}

const FILE_TYPE_BADGE: Record<FileType, { label: string; className: string }> = {
  pdf: { label: 'PDF', className: 'bg-red-100 text-red-700' },
  docx: { label: 'DOCX', className: 'bg-blue-100 text-blue-700' },
  pptx: { label: 'PPTX', className: 'bg-orange-100 text-orange-700' },
  excel: { label: 'Excel', className: 'bg-green-100 text-green-700' },
  audio: { label: 'Audio', className: 'bg-purple-100 text-purple-700' },
  text: { label: 'TXT', className: 'bg-slate-100 text-slate-700' },
}

const STATUS_BADGE: Record<DocumentStatus, { label: string; className: string; pulse?: boolean }> = {
  pending: { label: 'Pending', className: 'bg-slate-100 text-slate-600' },
  processing: { label: 'Processing', className: 'bg-yellow-100 text-yellow-700', pulse: true },
  ready: { label: 'Ready', className: 'bg-emerald-100 text-emerald-700' },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-700' },
}

// ---------------------------------------------------------------------------
// Skeleton Row
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <tr className="border-b border-slate-100">
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-4 py-4">
          <div className="h-4 bg-slate-200 rounded animate-pulse" style={{ width: `${60 + (i * 13) % 40}%` }} />
        </td>
      ))}
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Upload Modal
// ---------------------------------------------------------------------------

interface UploadModalProps {
  roles: RoleResponse[]
  onClose: () => void
  onSuccess: () => void
}

function UploadModal({ roles, onClose, onSuccess }: UploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const uploadMutation = useMutation({
    mutationFn: ({ file, roleIds }: { file: File; roleIds: string[] }) =>
      documentService.uploadDocument(file, roleIds),
    onSuccess: () => {
      onSuccess()
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Upload failed. Please try again.')
    },
  })

  function toggleRole(id: string) {
    setSelectedRoleIds((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    )
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!selectedFile) return setError('Please select a file.')
    if (selectedRoleIds.length === 0) return setError('Please select at least one role.')
    uploadMutation.mutate({ file: selectedFile, roleIds: selectedRoleIds })
  }

  const isLoading = uploadMutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">Upload Document</h2>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-slate-400 hover:text-slate-600 transition-colors rounded-lg p-1 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* File picker */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">File</label>
            <label
              className={`flex flex-col items-center justify-center w-full border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors ${
                selectedFile
                  ? 'border-indigo-400 bg-indigo-50'
                  : 'border-slate-300 hover:border-indigo-400 hover:bg-indigo-50/40'
              }`}
            >
              <Upload className={`w-8 h-8 mb-2 ${selectedFile ? 'text-indigo-500' : 'text-slate-400'}`} />
              {selectedFile ? (
                <span className="text-sm font-medium text-indigo-700 text-center break-all">{selectedFile.name}</span>
              ) : (
                <>
                  <span className="text-sm font-medium text-slate-600">Click to select a file</span>
                  <span className="text-xs text-slate-400 mt-1">PDF, DOCX, PPTX, XLSX, TXT, MP3, WAV, M4A</span>
                </>
              )}
              <input
                type="file"
                className="hidden"
                accept=".pdf,.docx,.pptx,.xlsx,.xls,.txt,.mp3,.wav,.m4a"
                onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>

          {/* Role multi-select */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Access Roles <span className="text-red-500">*</span>
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {roles.map((role) => {
                const checked = selectedRoleIds.includes(role.id)
                return (
                  <button
                    key={role.id}
                    type="button"
                    onClick={() => toggleRole(role.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all text-left ${
                      checked
                        ? 'border-indigo-400 bg-indigo-50 text-indigo-800'
                        : 'border-slate-200 hover:border-slate-300 text-slate-700'
                    }`}
                  >
                    {checked ? (
                      <CheckSquare className="w-4 h-4 text-indigo-600 shrink-0" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-400 shrink-0" />
                    )}
                    <span className="text-sm font-medium">{role.name}</span>
                    {role.is_admin && (
                      <span className="ml-auto text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">Admin</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 bg-indigo-700 hover:bg-indigo-800 text-white font-semibold rounded-xl px-4 py-3 transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Uploading and processing… this may take a moment
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Upload and Process
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Edit Roles Modal
// ---------------------------------------------------------------------------

interface EditRolesModalProps {
  document: DocumentResponse
  roles: RoleResponse[]
  onClose: () => void
  onSuccess: () => void
}

function EditRolesModal({ document, roles, onClose, onSuccess }: EditRolesModalProps) {
  const currentRoleIds = document.access_policies.map((r) => r.id)
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>(currentRoleIds)
  const [error, setError] = useState<string | null>(null)

  const updateMutation = useMutation({
    mutationFn: (roleIds: string[]) =>
      documentService.updateDocumentAccess(document.id, roleIds),
    onSuccess: () => onSuccess(),
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Failed to update access.')
    },
  })

  function toggleRole(id: string) {
    setSelectedRoleIds((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    )
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (selectedRoleIds.length === 0) return setError('Please select at least one role.')
    setError(null)
    updateMutation.mutate(selectedRoleIds)
  }

  const isLoading = updateMutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Edit Document Access</h2>
            <p className="text-sm text-slate-500 mt-0.5 truncate max-w-xs">{document.filename}</p>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-slate-400 hover:text-slate-600 transition-colors rounded-lg p-1 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {roles.map((role) => {
              const checked = selectedRoleIds.includes(role.id)
              return (
                <button
                  key={role.id}
                  type="button"
                  onClick={() => toggleRole(role.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all text-left ${
                    checked
                      ? 'border-indigo-400 bg-indigo-50 text-indigo-800'
                      : 'border-slate-200 hover:border-slate-300 text-slate-700'
                  }`}
                >
                  {checked ? (
                    <CheckSquare className="w-4 h-4 text-indigo-600 shrink-0" />
                  ) : (
                    <Square className="w-4 h-4 text-slate-400 shrink-0" />
                  )}
                  <span className="text-sm font-medium">{role.name}</span>
                  {role.is_admin && (
                    <span className="ml-auto text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">Admin</span>
                  )}
                </button>
              )
            })}
          </div>

          {error && (
            <div className="flex items-start gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 bg-indigo-700 hover:bg-indigo-800 text-white font-semibold rounded-xl px-4 py-3 transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Saving…
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Delete Modal
// ---------------------------------------------------------------------------

interface DeleteModalProps {
  document: DocumentResponse
  onClose: () => void
  onSuccess: () => void
}

function DeleteModal({ document, onClose, onSuccess }: DeleteModalProps) {
  const deleteMutation = useMutation({
    mutationFn: () => documentService.deleteDocument(document.id),
    onSuccess: () => onSuccess(),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">Delete Document</h2>
        </div>
        <div className="px-6 py-5">
          <p className="text-sm text-slate-600 leading-relaxed">
            Are you sure you want to delete{' '}
            <span className="font-semibold text-slate-800">{document.filename}</span>? This will
            permanently remove the document and all its embeddings. This action cannot be undone.
          </p>
        </div>
        <div className="flex gap-3 px-6 pb-6">
          <button
            onClick={onClose}
            disabled={deleteMutation.isPending}
            className="flex-1 px-4 py-2.5 border border-slate-200 text-slate-700 font-medium rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors disabled:opacity-70"
          >
            {deleteMutation.isPending ? (
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : (
              <Trash2 className="w-4 h-4" />
            )}
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Role Chips
// ---------------------------------------------------------------------------

function RoleChips({ roles }: { roles: RoleResponse[] }) {
  const maxVisible = 2
  const visible = roles.slice(0, maxVisible)
  const overflow = roles.length - maxVisible

  return (
    <div className="flex flex-wrap gap-1.5 items-center">
      {visible.map((role) => (
        <span
          key={role.id}
          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700"
        >
          {role.name}
        </span>
      ))}
      {overflow > 0 && (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-200 text-slate-600">
          +{overflow} more
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type ModalState =
  | { type: 'none' }
  | { type: 'upload' }
  | { type: 'edit'; document: DocumentResponse }
  | { type: 'delete'; document: DocumentResponse }

export default function DocumentsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const [modal, setModal] = useState<ModalState>({ type: 'none' })
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const { data: documents = [], isLoading: docsLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: documentService.getDocuments,
  })

  const { data: roles = [] } = useQuery({
    queryKey: ['roles'],
    queryFn: roleService.getRoles,
  })

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      // 1. Search name
      if (search && !doc.filename.toLowerCase().includes(search.toLowerCase())) return false;
      
      // 2. Type filter
      if (filterType !== 'all' && doc.file_type !== filterType) return false;

      // 3. Status filter
      if (filterStatus !== 'all' && doc.status !== filterStatus) return false;

      // 4. Date filter
      if (startDate || endDate) {
        const uploadedDate = new Date(doc.uploaded_at);
        uploadedDate.setHours(0, 0, 0, 0);

        if (startDate) {
          const start = new Date(startDate);
          start.setHours(0, 0, 0, 0);
          if (uploadedDate < start) return false;
        }
        
        if (endDate) {
          const end = new Date(endDate);
          end.setHours(23, 59, 59, 999);
          if (uploadedDate > end) return false;
        }
      }

      return true;
    })
  }, [documents, search, filterType, filterStatus, startDate, endDate])

  function handleSuccess(message: string) {
    setModal({ type: 'none' })
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    setSuccessMessage(message)
    setTimeout(() => setSuccessMessage(null), 4000)
  }

  function handleDownload(doc: DocumentResponse) {
    documentService.downloadDocument(doc.id, doc.filename)
  }

  return (
    <div className="space-y-6">
      {/* Success toast */}
      {successMessage && (
        <div className="fixed top-6 right-6 z-50 flex items-center gap-3 bg-emerald-600 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium animate-fade-in">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          {successMessage}
        </div>
      )}

      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Documents</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage your organisation's knowledge base</p>
        </div>
        <button
          id="new-document-btn"
          onClick={() => setModal({ type: 'upload' })}
          className="flex items-center gap-2 bg-indigo-700 hover:bg-indigo-800 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors shadow-sm"
        >
          <Upload className="w-4 h-4" />
          New Document
        </button>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col lg:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full flex-1 min-w-[200px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            id="document-search"
            type="text"
            placeholder="Search documents by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:bg-white transition-all"
          />
        </div>

        <div className="hidden lg:block w-px h-8 bg-slate-200 mx-1 shrink-0"></div>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-end gap-3 w-full lg:w-auto shrink-0">
          {/* File Type */}
          <div className="relative shrink-0">
            <select
              value={filterType}
              onChange={(e) => {
                setFilterType(e.target.value)
                e.target.blur()
              }}
              className="peer appearance-none w-32 bg-white border border-slate-200 text-slate-700 text-sm font-medium rounded-xl pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 cursor-pointer hover:bg-slate-100 transition-colors"
            >
              <option value="all">All Types</option>
              <option value="pdf">PDF</option>
              <option value="text">TXT</option>
              <option value="audio">Audio</option>
              <option value="pptx">PPTX</option>
              <option value="docx">DOCX</option>
              <option value="excel">Excel</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
          </div>

          {/* Status */}
          <div className="relative shrink-0">
            <select
              value={filterStatus}
              onChange={(e) => {
                setFilterStatus(e.target.value)
                e.target.blur()
              }}
              className="peer appearance-none w-36 bg-white border border-slate-200 text-slate-700 text-sm font-medium rounded-xl pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 cursor-pointer hover:bg-slate-100 transition-colors"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="ready">Ready</option>
              <option value="failed">Failed</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
          </div>

          {/* Date Range */}
          <div className="flex items-center bg-white border border-slate-200 rounded-xl px-2 hover:bg-slate-100 transition-colors focus-within:ring-2 focus-within:ring-indigo-400 focus-within:bg-white overflow-hidden">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-transparent text-sm text-slate-700 font-medium py-2 focus:outline-none cursor-pointer w-[115px]"
              title="Start Date"
            />
            <span className="text-slate-300 font-medium px-1">-</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-transparent text-sm text-slate-700 font-medium py-2 focus:outline-none cursor-pointer w-[115px]"
              title="End Date"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600">File Name</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600">Type</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600">Size</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600">Upload Date</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600">Status</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600">Roles</th>
                <th className="px-4 py-3.5 text-right font-semibold text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docsLoading ? (
                Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              ) : filteredDocuments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-3">
                      <FileText className="w-12 h-12 text-slate-200" />
                      <div>
                        <p className="font-medium text-slate-500">
                          {search ? 'No documents match your search' : 'No documents yet'}
                        </p>
                        {!search && (
                          <p className="text-sm mt-1">Upload your first document to get started</p>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((doc) => {
                  const TypeIcon = FILE_TYPE_ICON[doc.file_type] ?? File
                  const badge = FILE_TYPE_BADGE[doc.file_type]
                  const statusInfo = STATUS_BADGE[doc.status]

                  return (
                    <tr
                      key={doc.id}
                      className="border-b border-slate-100 hover:bg-slate-50/60 transition-colors"
                    >
                      {/* File Name */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <TypeIcon className="w-5 h-5 text-slate-400 shrink-0" />
                          <span className="font-medium text-slate-800 truncate max-w-[200px]" title={doc.filename}>
                            {doc.filename}
                          </span>
                        </div>
                      </td>

                      {/* File Type */}
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                      </td>

                      {/* Size */}
                      <td className="px-4 py-3.5 text-slate-500 whitespace-nowrap">
                        {formatBytes(doc.file_size)}
                      </td>

                      {/* Date */}
                      <td className="px-4 py-3.5 text-slate-500 whitespace-nowrap">
                        {formatDate(doc.uploaded_at)}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${statusInfo.className} ${
                            statusInfo.pulse ? 'animate-pulse' : ''
                          }`}
                        >
                          {statusInfo.label}
                        </span>
                      </td>

                      {/* Roles */}
                      <td className="px-4 py-3.5">
                        <RoleChips roles={doc.access_policies} />
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            title="Download"
                            onClick={() => handleDownload(doc)}
                            className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            title="Edit roles"
                            onClick={() => setModal({ type: 'edit', document: doc })}
                            className="p-2 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            title="Delete"
                            onClick={() => setModal({ type: 'delete', document: doc })}
                            className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer count */}
        {!docsLoading && filteredDocuments.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/60">
            <p className="text-xs text-slate-400">
              Showing {filteredDocuments.length} of {documents.length} document{documents.length !== 1 ? 's' : ''}
            </p>
          </div>
        )}
      </div>

      {/* Modals */}
      {modal.type === 'upload' && (
        <UploadModal
          roles={roles}
          onClose={() => setModal({ type: 'none' })}
          onSuccess={() => handleSuccess('Document uploaded and processed successfully')}
        />
      )}
      {modal.type === 'edit' && (
        <EditRolesModal
          document={modal.document}
          roles={roles}
          onClose={() => setModal({ type: 'none' })}
          onSuccess={() => handleSuccess('Document access updated successfully')}
        />
      )}
      {modal.type === 'delete' && (
        <DeleteModal
          document={modal.document}
          onClose={() => setModal({ type: 'none' })}
          onSuccess={() => handleSuccess('Document deleted successfully')}
        />
      )}
    </div>
  )
}
