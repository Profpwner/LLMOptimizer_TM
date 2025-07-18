import axios, { AxiosInstance } from 'axios';
import { OptimizationResult, Suggestion } from '../types';

// API configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance with interceptors
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor
  client.interceptors.request.use(
    (config) => {
      // Add auth token if available
      const token = localStorage.getItem('authToken');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        // Handle unauthorized access
        localStorage.removeItem('authToken');
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }
  );

  return client;
};

const apiClient = createApiClient();

// API methods
export const fetchOptimizationResults = async (contentId: string): Promise<OptimizationResult> => {
  const response = await apiClient.get(`/optimization/results/${contentId}`);
  return response.data;
};

export const applySuggestion = async (suggestionId: string, contentId: string): Promise<any> => {
  const response = await apiClient.post(`/optimization/suggestions/${suggestionId}/apply`, {
    contentId,
  });
  return response.data;
};

export const applyMultipleSuggestions = async (
  suggestionIds: string[],
  contentId: string
): Promise<any> => {
  const response = await apiClient.post(`/optimization/suggestions/apply-batch`, {
    suggestionIds,
    contentId,
  });
  return response.data;
};

export const rejectSuggestion = async (suggestionId: string, reason?: string): Promise<any> => {
  const response = await apiClient.post(`/optimization/suggestions/${suggestionId}/reject`, {
    reason,
  });
  return response.data;
};

export const exportOptimizationResults = async (
  contentId: string,
  format: 'pdf' | 'csv' | 'json'
): Promise<Blob> => {
  const response = await apiClient.get(`/optimization/results/${contentId}/export`, {
    params: { format },
    responseType: 'blob',
  });
  return response.data;
};

export const saveOptimizationSettings = async (settings: any): Promise<any> => {
  const response = await apiClient.post('/optimization/settings', settings);
  return response.data;
};

export const getOptimizationHistory = async (
  page: number = 1,
  limit: number = 20
): Promise<{ results: OptimizationResult[]; total: number }> => {
  const response = await apiClient.get('/optimization/history', {
    params: { page, limit },
  });
  return response.data;
};

// WebSocket URL for real-time updates
export const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

export default apiClient;