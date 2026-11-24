import { apiClient } from './axios';
import type {
  AiAnalysisRead,
  ZoneSummaryItem,
  AnalysisReviewCreate,
  AnalysisReviewRead,
  ReviewQueueItem,
} from '../types/api.types';

export const analysisService = {
  getAreaAnalysis: async (areaId: number): Promise<AiAnalysisRead> => {
    const response = await apiClient.get<AiAnalysisRead>(`/api/v1/hara/areas/${areaId}/analysis`);
    return response.data;
  },

  getPointAnalysis: async (lon: number, lat: number): Promise<AiAnalysisRead> => {
    const response = await apiClient.get<AiAnalysisRead>(`/api/v1/hara/point/analysis?lon=${lon}&lat=${lat}`);
    return response.data;
  },

  getZones: async (): Promise<ZoneSummaryItem[]> => {
    const response = await apiClient.get<ZoneSummaryItem[]>('/api/v1/hara/zones');
    return response.data;
  },

  getModelInfo: async (): Promise<Record<string, unknown>> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/ml/model-info');
    return response.data;
  },

  createAnalysisReview: async (areaId: number, data: AnalysisReviewCreate): Promise<AnalysisReviewRead> => {
    const response = await apiClient.post<AnalysisReviewRead>(
      `/api/v1/expert/areas/${areaId}/analysis-review`,
      data
    );
    return response.data;
  },

  getReviewQueue: async (limit = 20): Promise<ReviewQueueItem[]> => {
    const response = await apiClient.get<ReviewQueueItem[]>(
      `/api/v1/expert/analysis-review/queue?limit=${limit}`
    );
    return response.data;
  },
};
