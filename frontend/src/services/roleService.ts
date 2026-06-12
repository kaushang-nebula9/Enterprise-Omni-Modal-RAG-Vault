import api from './api';
import type { RoleResponse, MessageResponse } from '../types/auth';
import type { CreateRolePayload, UpdateRolePayload } from '../types/admin';

export const roleService = {
  getRoles: async (): Promise<RoleResponse[]> => {
    const response = await api.get('/api/v1/roles');
    return response.data;
  },

  createRole: async (data: CreateRolePayload): Promise<RoleResponse> => {
    const response = await api.post('/api/v1/roles', data);
    return response.data;
  },

  updateRole: async (roleId: string, data: UpdateRolePayload): Promise<RoleResponse> => {
    const response = await api.patch(`/api/v1/roles/${roleId}`, data);
    return response.data;
  },

  deleteRole: async (roleId: string): Promise<MessageResponse> => {
    const response = await api.delete(`/api/v1/roles/${roleId}`);
    return response.data;
  }
};
