import api from './api';
import type { ReportStatus } from '../types/chat';

// Trigger report generation for a session
export const createReport = async (sessionId: string): Promise<{ report_id: string; status: string }> => {
  const response = await api.post(`/api/sessions/${sessionId}/reports`);
  return response.data;
};

// Poll report status
export const getReportStatus = async (reportId: string): Promise<ReportStatus> => {
  const response = await api.get(`/api/reports/${reportId}/status`);
  return response.data;
};

// Fetch the latest report status for a session
export const getLatestReportStatus = async (sessionId: string): Promise<ReportStatus> => {
  const response = await api.get(`/api/sessions/${sessionId}/reports/latest`);
  return response.data;
};

// Get download URL - returns a blob
export const downloadReport = async (reportId: string): Promise<Blob> => {
  const response = await api.get(`/api/reports/${reportId}/download`, {
    responseType: 'blob'
  });
  return response.data;
};
