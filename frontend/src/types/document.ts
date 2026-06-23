import type { RoleResponse } from './auth'

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'
export type FileType = 'text' | 'audio' | 'pdf' | 'docx' | 'pptx' | 'excel'
export type OwnerType = 'organisation' | 'private'
export type Visibility = 'org_wide' | 'private'

export interface DocumentResponse {
  id: string
  tenant_id: string
  uploaded_by: string
  filename: string
  file_type: FileType
  owner_type: OwnerType
  visibility: Visibility
  chunk_count: number
  qdrant_collection: string
  status: DocumentStatus
  file_path: string | null
  file_size?: number | null
  uploaded_at: string
  updated_at: string
  access_policies: RoleResponse[]
  description: string | null
  granted_via?: 'direct' | 'inherited' | null
  inherited_from_role_name?: string | null
}
