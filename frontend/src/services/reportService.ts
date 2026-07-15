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

// List all reports for the current user
export const listReports = async (): Promise<ReportStatus[]> => {
  const response = await api.get('/api/reports');
  return response.data;
};

// Delete a report
export const deleteReport = async (reportId: string): Promise<void> => {
  await api.delete(`/api/reports/${reportId}`);
};

// Retry a failed report
export const retryReport = async (reportId: string): Promise<{ report_id: string; status: string }> => {
  const response = await api.post(`/api/reports/${reportId}/retry`);
  return response.data;
};

// Fetch all reports for a specific session
export const getSessionReports = async (sessionId: string): Promise<ReportStatus[]> => {
  const response = await api.get(`/api/sessions/${sessionId}/reports`);
  return response.data;
};
