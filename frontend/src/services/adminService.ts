import api from './api';
import type { UserResponse, AdminStatsResponse, TenantResponse, MessageResponse } from '../types/auth';
import type { 
  UpdateMemberPayload, 
  UpdateOrganisationPayload,
  UsageSummaryResponse,
  DashboardOverviewResponse,
  DocumentInsightsResponse
} from '../types/admin';
import type { AvailableModel } from '../types/chat';

export const adminService = {
  getStats: async (): Promise<AdminStatsResponse> => {
    const response = await api.get('/api/v1/admin/stats');
    return response.data;
  },

  getUsageSummary: async (startDate?: string, endDate?: string): Promise<UsageSummaryResponse> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const response = await api.get('/api/v1/admin/usage', { params });
    return response.data;
  },

  getDashboardOverview: async (): Promise<DashboardOverviewResponse> => {
    const response = await api.get('/api/v1/admin/dashboard-overview');
    return response.data;
  },

  getDocumentInsights: async (): Promise<DocumentInsightsResponse> => {
    const response = await api.get('/api/v1/admin/document-insights');
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

  createModel: async (data: { 
    display_name: string; 
    provider: 'anthropic' | 'openrouter'; 
    model_string: string; 
    is_active: boolean;
    input_price_per_million?: number | null;
    output_price_per_million?: number | null;
  }): Promise<AvailableModel> => {
    const response = await api.post('/api/v1/admin/models', data);
    return response.data;
  },

  updateModel: async (modelId: string, data: { 
    display_name?: string; 
    provider?: 'anthropic' | 'openrouter'; 
    model_string?: string; 
    is_active?: boolean;
    input_price_per_million?: number | null;
    output_price_per_million?: number | null;
  }): Promise<AvailableModel> => {
    const response = await api.patch(`/api/v1/admin/models/${modelId}`, data);
    return response.data;
  },

  deleteModel: async (modelId: string): Promise<MessageResponse> => {
    const response = await api.delete(`/api/v1/admin/models/${modelId}`);
    return response.data;
  },

  getAuditLogs: async (params: {
    limit?: number;
    offset?: number;
    action?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<{
    items: any[];
    total: number;
    limit: number;
    offset: number;
  }> => {
    const response = await api.get('/api/v1/admin/audit-log', { params });
    return response.data;
  }
};

