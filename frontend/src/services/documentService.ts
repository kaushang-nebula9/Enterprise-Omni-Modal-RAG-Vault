import api from './api'
import type { DocumentResponse } from '../types/document'
import type { MessageResponse } from '../types/auth'

export const documentService = {
  /**
   * Upload a document with multipart/form-data.
   * Appends the file and each roleId as separate form fields.
   */
  uploadDocument: async (file: File, roleIds: string[]): Promise<DocumentResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    roleIds.forEach((id) => formData.append('role_ids', id))
    const response = await api.post('/api/v1/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  /**
   * Fetch all organisation documents for the current tenant.
   */
  getDocuments: async (): Promise<DocumentResponse[]> => {
    const response = await api.get('/api/v1/documents')
    return response.data
  },

  /**
   * Download a document file — triggers a browser file download.
   */
  downloadDocument: async (documentId: string, filename: string): Promise<void> => {
    const response = await api.get(`/api/v1/documents/${documentId}/download`, {
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },

  /**
   * Delete a document by ID.
   */
  deleteDocument: async (documentId: string): Promise<MessageResponse> => {
    const response = await api.delete(`/api/v1/documents/${documentId}`)
    return response.data
  },

  /**
   * Update the access policies (role assignments) for a document.
   */
  updateDocumentAccess: async (
    documentId: string,
    roleIds: string[]
  ): Promise<DocumentResponse> => {
    const response = await api.patch(`/api/v1/documents/${documentId}/access`, {
      role_ids: roleIds,
    })
    return response.data
  },
}
