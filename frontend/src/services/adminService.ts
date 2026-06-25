import api from './api';
import type { UserResponse, AdminStatsResponse, TenantResponse, MessageResponse } from '../types/auth';
import type { UpdateMemberPayload, UpdateOrganisationPayload } from '../types/admin';

export const adminService = {
  getStats: async (): Promise<AdminStatsResponse> => {
    const response = await api.get('/api/v1/admin/stats');
    return response.data;
  },

  getMembers: async (): Promise<UserResponse[]> => {
    const response = await api.get('/api/v1/admin/members');
    return response.data;
  },

  updateMember: async (userId: string, data: UpdateMemberPayload): Promise<UserResponse> => {
    const response = await api.patch(`/api/v1/admin/members/${userId}`, data);
    return response.data;
  },

  deleteMember: async (userId: string): Promise<MessageResponse> => {
    const response = await api.delete(`/api/v1/admin/members/${userId}`);
    return response.data;
  },

  getOrganisation: async (): Promise<TenantResponse> => {
    const response = await api.get('/api/v1/admin/organisation');
    return response.data;
  },

  updateOrganisation: async (data: UpdateOrganisationPayload): Promise<TenantResponse> => {
    const response = await api.patch('/api/v1/admin/organisation', data);
    return response.data;
  },

  deleteOrganisation: async (): Promise<MessageResponse> => {
    const response = await api.delete('/api/v1/admin/organisation');
    return response.data;
  },

  getModels: async (): Promise<AvailableModel[]> => {
    const response = await api.get('/api/v1/admin/models');
    return response.data;
  },

  createModel: async (data: { display_name: string; provider: 'anthropic' | 'openrouter'; model_string: string; is_active: boolean }): Promise<AvailableModel> => {
    const response = await api.post('/api/v1/admin/models', data);
    return response.data;
  },

  updateModel: async (modelId: string, data: { display_name?: string; provider?: 'anthropic' | 'openrouter'; model_string?: string; is_active?: boolean }): Promise<AvailableModel> => {
    const response = await api.patch(`/api/v1/admin/models/${modelId}`, data);
    return response.data;
  },

  deleteModel: async (modelId: string): Promise<MessageResponse> => {
    const response = await api.delete(`/api/v1/admin/models/${modelId}`);
    return response.data;
  }
};

import type { AvailableModel } from '../types/chat';
