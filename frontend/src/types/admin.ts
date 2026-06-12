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
}

export interface UpdateRolePayload {
  name: string
}
