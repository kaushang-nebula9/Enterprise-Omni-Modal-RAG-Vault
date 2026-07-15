import React, { useState, useMemo, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  Trash2,
  X,
  AlertTriangle,
  ChevronDown,
} from "lucide-react";
import { documentService } from "../../services/documentService";
import type {
  DocumentResponse,
  FileType,
  DocumentStatus,
} from "../../types/document";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "--";
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

const FILE_TYPE_ICON: Record<FileType, React.FC<{ className?: string }>> = {
  text: FileText,
  pdf: File,
  docx: FilePen,
  pptx: Presentation,
  excel: FileSpreadsheet,
  audio: FileMusic,
};

const FILE_TYPE_BADGE: Record<FileType, { label: string; className: string }> =
  {
    pdf: {
      label: "PDF",
      className: "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400",
    },
    docx: {
      label: "DOCX",
      className:
        "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
    },
    pptx: {
      label: "PPTX",
      className:
        "bg-orange-100 text-orange-700 dark:bg-orange-950/40 dark:text-orange-400",
    },
    excel: {
      label: "Excel",
      className:
        "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400",
    },
    audio: {
      label: "Audio",
      className:
        "bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400",
    },
    text: {
      label: "TXT",
      className:
        "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400",
    },
  };

const STATUS_BADGE: Record<
  DocumentStatus,
  { label: string; className: string; pulse?: boolean }
> = {
  pending: {
    label: "Pending",
    className:
      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  },
  processing: {
    label: "Processing",
    className:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-400",
    pulse: true,
  },
  ready: {
    label: "Ready",
    className:
      "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400",
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400",
  },
};

// ---------------------------------------------------------------------------
// Skeleton Row
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <tr className="border-b border-slate-100 dark:border-slate-800">
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i} className="px-4 py-4">
          <div
            className="h-4 bg-slate-200 dark:bg-slate-800 rounded animate-pulse"
            style={{ width: `${60 + ((i * 13) % 40)}%` }}
          />
        </td>
      ))}
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Upload Modal
// ---------------------------------------------------------------------------

interface UploadModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

function UploadModal({ onClose, onSuccess }: UploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => documentService.uploadPersonalDocument(file),
    onSuccess: () => {
      onSuccess();
    },
    onError: (err: any) => {
      setError(
        err?.response?.data?.detail || "Upload failed. Please try again.",
      );
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!selectedFile) return setError("Please select a file.");
    uploadMutation.mutate(selectedFile);
  }

  const isLoading = uploadMutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-md text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-800">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
            Upload Personal Document
          </h2>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors rounded-lg p-1 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* File picker */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              File
            </label>
            <label
              className={`flex flex-col items-center justify-center w-full border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors ${
                selectedFile
                  ? "border-indigo-400 bg-indigo-50 dark:border-indigo-500 dark:bg-indigo-950/40"
                  : "border-slate-300 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20"
              }`}
            >
              <Upload
                className={`w-8 h-8 mb-2 ${selectedFile ? "text-indigo-500 dark:text-indigo-400" : "text-slate-400 dark:text-slate-500"}`}
              />
              {selectedFile ? (
                <span className="text-sm font-medium text-indigo-700 dark:text-indigo-400 text-center break-all">
                  {selectedFile.name}
                </span>
              ) : (
                <>
                  <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                    Click to select a file
                  </span>
                  <span className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                    PDF, DOCX, PPTX, XLSX, TXT, MP3, WAV, M4A
                  </span>
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

          {error && (
            <div className="flex items-start gap-2 text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/50 rounded-lg px-3 py-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-400 text-white font-semibold rounded-xl px-4 py-3 transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <svg
                  className="animate-spin w-4 h-4"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                Uploading and processing...
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
  );
}

// ---------------------------------------------------------------------------
// Delete Modal
// ---------------------------------------------------------------------------

interface DeleteModalProps {
  document: DocumentResponse;
  onClose: () => void;
  onSuccess: () => void;
}

function DeleteModal({ document, onClose, onSuccess }: DeleteModalProps) {
  const deleteMutation = useMutation({
    mutationFn: () => documentService.deletePersonalDocument(document.id),
    onSuccess: () => onSuccess(),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-sm text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
        <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-800">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
            Delete Personal Document
          </h2>
        </div>
        <div className="px-6 py-5">
          <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
            Are you sure you want to delete{" "}
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              {document.filename}
            </span>
            ? This will permanently remove the document and all its embeddings.
            This action cannot be undone.
          </p>
        </div>
        <div className="flex gap-3 px-6 pb-6">
          <button
            onClick={onClose}
            disabled={deleteMutation.isPending}
            className="flex-1 px-4 py-2.5 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors disabled:opacity-70"
          >
            {deleteMutation.isPending ? (
              <svg
                className="animate-spin w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v8H4z"
                />
              </svg>
            ) : (
              <Trash2 className="w-4 h-4" />
            )}
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type ModalState =
  | { type: "none" }
  | { type: "upload" }
  | { type: "delete"; document: DocumentResponse };

export default function YourDocumentsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Dropdown states & refs
  const [isTypeDropdownOpen, setIsTypeDropdownOpen] = useState(false);
  const [isStatusDropdownOpen, setIsStatusDropdownOpen] = useState(false);
  const typeDropdownRef = useRef<HTMLDivElement>(null);
  const statusDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        typeDropdownRef.current &&
        !typeDropdownRef.current.contains(event.target as Node)
      ) {
        setIsTypeDropdownOpen(false);
      }
      if (
        statusDropdownRef.current &&
        !statusDropdownRef.current.contains(event.target as Node)
      ) {
        setIsStatusDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const [modal, setModal] = useState<ModalState>({ type: "none" });
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [expandedDocIds, setExpandedDocIds] = useState<Set<string>>(new Set());

  const toggleExpand = (docId: string) => {
    setExpandedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  const { data: documents = [], isLoading: docsLoading } = useQuery({
    queryKey: ["personal-documents"],
    queryFn: documentService.getPersonalDocuments,
  });

  const { data: authorizedDocuments = [], isLoading: authDocsLoading } =
    useQuery({
      queryKey: ["authorized-documents"],
      queryFn: documentService.getAuthorizedDocuments,
    });

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      // 1. Search name
      if (search && !doc.filename.toLowerCase().includes(search.toLowerCase()))
        return false;

      // 2. Type filter
      if (filterType !== "all" && doc.file_type !== filterType) return false;

      // 3. Status filter
      if (filterStatus !== "all" && doc.status !== filterStatus) return false;

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
    });
  }, [documents, search, filterType, filterStatus, startDate, endDate]);

  function handleSuccess(message: string) {
    setModal({ type: "none" });
    queryClient.invalidateQueries({ queryKey: ["personal-documents"] });
    setSuccessMessage(message);
    setTimeout(() => setSuccessMessage(null), 4000);
  }

  function handleDownload(doc: DocumentResponse) {
    documentService.downloadPersonalDocument(doc.id, doc.filename);
  }

  return (
    <div className="space-y-6 text-slate-800 dark:text-slate-100 animate-in fade-in duration-300">
      {/* Success toast */}
      {successMessage && (
        <div className="fixed top-6 right-6 z-50 flex items-center gap-3 bg-emerald-600 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium animate-fade-in">
          <svg
            className="w-4 h-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          {successMessage}
        </div>
      )}

      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Your documents
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Manage your personal files and documents
          </p>
        </div>
        <button
          onClick={() => setModal({ type: "upload" })}
          className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors shadow-sm"
        >
          <Upload className="w-4 h-4" />
          New Document
        </button>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col lg:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full flex-1 min-w-[200px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search documents by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 focus:bg-white dark:focus:bg-slate-900 transition-all"
          />
        </div>

        <div className="hidden lg:block w-px h-8 bg-slate-200 dark:bg-slate-800 mx-1 shrink-0"></div>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-end gap-3 w-full lg:w-auto shrink-0">
          {/* File Type */}
          <div
            className="relative inline-block text-left"
            ref={typeDropdownRef}
          >
            <button
              onClick={() => setIsTypeDropdownOpen(!isTypeDropdownOpen)}
              type="button"
              className="inline-flex items-center justify-between gap-2 px-3.5 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[128px] cursor-pointer shadow-sm"
            >
              <span>
                {filterType === "all" && "All Types"}
                {filterType === "pdf" && "PDF"}
                {filterType === "text" && "TXT"}
                {filterType === "audio" && "Audio"}
                {filterType === "pptx" && "PPTX"}
                {filterType === "docx" && "DOCX"}
                {filterType === "excel" && "Excel"}
              </span>
              <ChevronDown
                className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isTypeDropdownOpen ? "rotate-180" : ""}`}
              />
            </button>

            {isTypeDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-40 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1">
                {(
                  [
                    "all",
                    "pdf",
                    "text",
                    "audio",
                    "pptx",
                    "docx",
                    "excel",
                  ] as const
                ).map((typeVal) => (
                  <button
                    key={typeVal}
                    onClick={() => {
                      setFilterType(typeVal);
                      setIsTypeDropdownOpen(false);
                    }}
                    type="button"
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                      filterType === typeVal
                        ? "text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15"
                        : "text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    {typeVal === "all" && "All Types"}
                    {typeVal === "pdf" && "PDF"}
                    {typeVal === "text" && "TXT"}
                    {typeVal === "audio" && "Audio"}
                    {typeVal === "pptx" && "PPTX"}
                    {typeVal === "docx" && "DOCX"}
                    {typeVal === "excel" && "Excel"}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Status */}
          <div
            className="relative inline-block text-left"
            ref={statusDropdownRef}
          >
            <button
              onClick={() => setIsStatusDropdownOpen(!isStatusDropdownOpen)}
              type="button"
              className="inline-flex items-center justify-between gap-2 px-3.5 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[140px] cursor-pointer shadow-sm"
            >
              <span>
                {filterStatus === "all" && "All Status"}
                {filterStatus === "pending" && "Pending"}
                {filterStatus === "processing" && "Processing"}
                {filterStatus === "ready" && "Ready"}
                {filterStatus === "failed" && "Failed"}
              </span>
              <ChevronDown
                className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isStatusDropdownOpen ? "rotate-180" : ""}`}
              />
            </button>

            {isStatusDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-44 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1">
                {(
                  ["all", "pending", "processing", "ready", "failed"] as const
                ).map((statusVal) => (
                  <button
                    key={statusVal}
                    onClick={() => {
                      setFilterStatus(statusVal);
                      setIsStatusDropdownOpen(false);
                    }}
                    type="button"
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                      filterStatus === statusVal
                        ? "text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15"
                        : "text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    {statusVal === "all" && "All Status"}
                    {statusVal === "pending" && "Pending"}
                    {statusVal === "processing" && "Processing"}
                    {statusVal === "ready" && "Ready"}
                    {statusVal === "failed" && "Failed"}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Date Range */}
          <div className="flex items-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl px-2 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-within:ring-2 focus-within:ring-indigo-400 dark:focus-within:ring-indigo-500 focus-within:bg-white dark:focus-within:bg-slate-900 overflow-hidden">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-transparent text-sm text-slate-700 dark:text-slate-300 font-medium py-2 focus:outline-none cursor-pointer w-[115px]"
              title="Start Date"
            />
            <span className="text-slate-300 dark:text-slate-655 font-medium px-1">
              -
            </span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-transparent text-sm text-slate-700 dark:text-slate-300 font-medium py-2 focus:outline-none cursor-pointer w-[115px]"
              title="End Date"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full table-fixed text-sm">
            <colgroup>
              <col style={{ width: "30%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "16%" }} />
              <col style={{ width: "15%" }} />
              <col style={{ width: "15%" }} />
            </colgroup>
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800">
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                  File Name
                </th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                  Type
                </th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                  Size
                </th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                  Upload Date
                </th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                  Status
                </th>
                <th className="px-4 py-3.5 text-right font-semibold text-slate-600 dark:text-slate-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {docsLoading ? (
                Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              ) : filteredDocuments.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-16 text-center text-slate-400 dark:text-slate-500"
                  >
                    <div className="flex flex-col items-center gap-3">
                      <FileText className="w-12 h-12 text-slate-200 dark:text-slate-800" />
                      <div>
                        <p className="font-medium text-slate-500 dark:text-slate-400">
                          {search
                            ? "No documents match your search"
                            : "No personal documents yet"}
                        </p>
                        {!search && (
                          <p className="text-sm mt-1 text-slate-400 dark:text-slate-500">
                            Upload your first personal document to get started
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((doc) => {
                  const TypeIcon = FILE_TYPE_ICON[doc.file_type] ?? File;
                  const badge = FILE_TYPE_BADGE[doc.file_type];
                  const statusInfo = STATUS_BADGE[doc.status];

                  return (
                    <tr
                      key={doc.id}
                      className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      {/* File Name */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <TypeIcon className="w-5 h-5 text-slate-400 dark:text-slate-500 shrink-0" />
                          <span
                            className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-[300px]"
                            title={doc.filename}
                          >
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
                      <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {formatBytes(doc.file_size)}
                      </td>

                      {/* Date */}
                      <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {formatDate(doc.uploaded_at)}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${statusInfo.className} ${
                            statusInfo.pulse ? "animate-pulse" : ""
                          }`}
                        >
                          {statusInfo.label}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            title="Download"
                            onClick={() => handleDownload(doc)}
                            className="p-2 text-slate-400 dark:text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 rounded-lg transition-colors"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            title="Delete"
                            onClick={() =>
                              setModal({ type: "delete", document: doc })
                            }
                            className="p-2 text-slate-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-lg transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer count */}
        {!docsLoading && filteredDocuments.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950">
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Showing {filteredDocuments.length} of {documents.length} document
              {documents.length !== 1 ? "s" : ""}
            </p>
          </div>
        )}
      </div>

      {/* Organisational Documents Section */}
      <div className="border-t border-slate-200 dark:border-slate-800 my-8" />

      <div className="space-y-4">
        <div>
          <h2 className="font-sora text-lg font-semibold text-slate-800 dark:text-slate-100">
            Documents shared by your organisation
          </h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
            These are documents your role has been given access to query in
            chat.
          </p>
        </div>

        {authDocsLoading ? (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full table-fixed text-sm">
                <colgroup>
                  <col style={{ width: "30%" }} />
                  <col style={{ width: "12%" }} />
                  <col style={{ width: "12%" }} />
                  <col style={{ width: "16%" }} />
                  <col style={{ width: "15%" }} />
                  <col style={{ width: "15%" }} />
                </colgroup>
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800">
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      File Name
                    </th>
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      Type
                    </th>
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      Size
                    </th>
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      Upload Date
                    </th>
                    <th
                      className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400"
                      colSpan={2}
                    >
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {Array.from({ length: 3 }).map((_, idx) => (
                    <tr
                      key={idx}
                      className="border-b border-slate-100 dark:border-slate-800 animate-pulse"
                    >
                      <td className="px-4 py-4">
                        <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-2/3" />
                      </td>
                      <td className="px-4 py-4">
                        <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/2" />
                      </td>
                      <td className="px-4 py-4">
                        <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/2" />
                      </td>
                      <td className="px-4 py-4">
                        <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-2/3" />
                      </td>
                      <td className="px-4 py-4" colSpan={2}>
                        <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-5/6" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : authorizedDocuments.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 bg-slate-50/50 dark:bg-slate-900/40 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
            <FileText className="w-12 h-12 text-slate-200 dark:text-slate-800 mb-3" />
            <p className="text-slate-400 dark:text-slate-500 text-sm">
              Your role does not currently have access to any organisational
              documents.
            </p>
          </div>
        ) : (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full table-fixed text-sm">
                <colgroup>
                  <col style={{ width: "30%" }} />
                  <col style={{ width: "12%" }} />
                  <col style={{ width: "12%" }} />
                  <col style={{ width: "16%" }} />
                  <col style={{ width: "15%" }} />
                  <col style={{ width: "15%" }} />
                </colgroup>
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800">
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      File Name
                    </th>
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      Type
                    </th>
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      Size
                    </th>
                    <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                      Upload Date
                    </th>
                    <th
                      className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400"
                      colSpan={2}
                    >
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {authorizedDocuments.map((doc) => {
                    const TypeIcon = FILE_TYPE_ICON[doc.file_type] ?? File;
                    const badge = FILE_TYPE_BADGE[doc.file_type];
                    const desc = doc.description;
                    const isExpanded = expandedDocIds.has(doc.id);

                    return (
                      <tr
                        key={doc.id}
                        className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors align-top"
                      >
                        {/* File Name */}
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <TypeIcon className="w-5 h-5 text-slate-400 dark:text-slate-500 shrink-0" />
                            <span
                              className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-[280px]"
                              title={doc.filename}
                            >
                              {doc.filename}
                            </span>
                            {doc.granted_via === "inherited" &&
                              doc.inherited_from_role_name && (
                                <span className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-100 dark:bg-violet-950/60 text-violet-700 dark:text-violet-400 whitespace-nowrap">
                                  Auto-access via {doc.inherited_from_role_name}
                                </span>
                              )}
                            {doc.granted_via === "department" &&
                              doc.department_name && (
                                <span className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 whitespace-nowrap">
                                  Shared with {doc.department_name} department
                                </span>
                              )}
                          </div>
                        </td>

                        {/* File Type */}
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${badge.className}`}
                          >
                            {badge.label}
                          </span>
                        </td>

                        {/* Size */}
                        <td className="px-4 py-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                          {formatBytes(doc.file_size)}
                        </td>

                        {/* Upload Date */}
                        <td className="px-4 py-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                          {formatDate(doc.uploaded_at)}
                        </td>

                        {/* Description */}
                        <td className="px-4 py-4" colSpan={2}>
                          {!desc ? (
                            <span className="text-slate-400 dark:text-slate-500 text-sm italic">
                              No description available
                            </span>
                          ) : (
                            <div className="text-slate-500 dark:text-slate-400 text-sm leading-relaxed">
                              <div
                                onClick={() => toggleExpand(doc.id)}
                                className={`cursor-pointer transition-all duration-150 ${isExpanded ? "whitespace-normal text-slate-800 dark:text-slate-200" : "truncate"}`}
                                title={
                                  isExpanded
                                    ? "Click to show less"
                                    : "Click to expand description"
                                }
                              >
                                {desc}
                              </div>
                              {isExpanded && (
                                <button
                                  onClick={() => toggleExpand(doc.id)}
                                  className="text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 font-semibold focus:outline-none hover:underline mt-1 text-xs"
                                >
                                  show less
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      {modal.type === "upload" && (
        <UploadModal
          onClose={() => setModal({ type: "none" })}
          onSuccess={() =>
            handleSuccess("Document uploaded and processed successfully")
          }
        />
      )}
      {modal.type === "delete" && (
        <DeleteModal
          document={modal.document}
          onClose={() => setModal({ type: "none" })}
          onSuccess={() => handleSuccess("Document deleted successfully")}
        />
      )}
    </div>
  );
}
