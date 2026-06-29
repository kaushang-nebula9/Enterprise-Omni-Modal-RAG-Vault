import api from './api';
import type { EvaluationRun, EvaluationDetail, ModelEvaluationBreakdown } from '../types/evaluation';

export const evaluationService = {
  runEvaluation: async (payload: {
    query_count?: number;
    date_range_start?: string;
    date_range_end?: string;
  }): Promise<EvaluationRun> => {
    const response = await api.post('/api/v1/evaluations/run', payload);
    return response.data;
  },

  getLatestEvaluation: async (): Promise<EvaluationRun | null> => {
    const response = await api.get('/api/v1/evaluations/latest');
    return response.data;
  },

  getEvaluationDetails: async (id: string): Promise<EvaluationDetail> => {
    const response = await api.get(`/api/v1/evaluations/${id}`);
    return response.data;
  },

  getEvaluationByModel: async (): Promise<ModelEvaluationBreakdown[]> => {
    const response = await api.get('/api/v1/evaluations/by-model');
    return response.data;
  },
};
