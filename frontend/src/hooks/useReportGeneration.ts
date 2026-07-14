import { useState, useRef, useEffect } from 'react';
import type { ReportStatus } from '../types/chat';
import { createReport, getReportStatus, downloadReport, getLatestReportStatus } from '../services/reportService';
import { useNotificationStore } from '../store/notificationStore';

export const useReportGeneration = (sessionId: string) => {
  const [reportId, setReportId] = useState<string | null>(null);
  const [reportStatus, setReportStatus] = useState<ReportStatus | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  // Stop polling helper
  const stopPolling = () => {
    if (pollingIntervalRef.current !== null) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  // Start polling helper
  const startPolling = (id: string) => {
    stopPolling();
    // Poll every 3 seconds
    const interval = window.setInterval(async () => {
      try {
        const status = await getReportStatus(id);
        setReportStatus(status);
        if (status.status === 'complete' || status.status === 'failed') {
          stopPolling();
        }
      } catch (err) {
        console.error('Transient network error while polling report status:', err);
      }
    }, 3000);
    pollingIntervalRef.current = interval;
  };

  // Load latest report when sessionId changes or on mount
  useEffect(() => {
    if (!sessionId) {
      setReportId(null);
      setReportStatus(null);
      setError(null);
      return;
    }

    const loadLatestReport = async () => {
      setError(null);
      try {
        const latest = await getLatestReportStatus(sessionId);
        setReportId(latest.report_id);
        setReportStatus(latest);
        if (latest.status === 'generating') {
          startPolling(latest.report_id);
        }
      } catch (err: any) {
        if (err?.response?.status !== 404) {
          console.error('Failed to load latest report status:', err);
        }
        setReportId(null);
        setReportStatus(null);
      }
    };

    loadLatestReport();

    return () => stopPolling();
  }, [sessionId]);

  // Trigger report generation
  const triggerReport = async () => {
    setIsTriggering(true);
    setError(null);
    setReportStatus(null);
    setReportId(null);
    try {
      const result = await createReport(sessionId);
      setReportId(result.report_id);
      setIsTriggering(false);
      startPolling(result.report_id);
    } catch (err: any) {
      console.error('Failed to trigger report generation:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to start report generation');
      setIsTriggering(false);
    }
  };

  // Download report PDF
  const handleDownload = async () => {
    if (!reportId) return;
    try {
      setError(null);
      const blob = await downloadReport(reportId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `report_${reportId}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Failed to download report:', err);
      setError(err?.message || 'Failed to download report PDF');
    }
  };

  // Listen to SSE notifications
  const eventSource = useNotificationStore((state) => state.eventSource);

  useEffect(() => {
    if (!eventSource || !reportId) return;

    const handleMessage = async (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'report_ready' && data.report_id === reportId) {
          console.log('SSE report_ready notification received for report:', reportId);
          stopPolling();
          const finalStatus = await getReportStatus(reportId);
          setReportStatus(finalStatus);
        }
      } catch (err) {
        console.error('Error handling SSE notification in useReportGeneration:', err);
      }
    };

    eventSource.addEventListener('message', handleMessage);
    return () => {
      eventSource.removeEventListener('message', handleMessage);
    };
  }, [eventSource, reportId]);

  return {
    reportId,
    reportStatus,
    isTriggering,
    error,
    triggerReport,
    handleDownload,
  };
};
