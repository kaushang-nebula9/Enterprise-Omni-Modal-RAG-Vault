export interface UpdateMemberPayload {
  role_id?: string
  is_active?: boolean
}

export interface UpdateOrganisationPayload {
  name?: string
  website?: string
}

export interface CreateRolePayload {
  name: string
  parent_role_id?: string | null
  department_id?: string | null
}

export interface UpdateRolePayload {
  name: string
  parent_role_id?: string | null
  department_id?: string | null
}

export interface RoleTreeNode {
  id: string
  name: string
  parent_role_id: string | null
  is_admin: boolean
  is_default: boolean
  descendant_count: number
  children: RoleTreeNode[]
}
