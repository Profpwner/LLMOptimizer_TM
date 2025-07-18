import { generateDemoData, generateHistoricalData } from '../utils/demoData';
import { OptimizationResult } from '../types';

// Mock API delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Mock API service for development
export const mockApi = {
  async fetchOptimizationResults(contentId: string): Promise<OptimizationResult> {
    await delay(1000); // Simulate network delay
    return generateDemoData();
  },

  async applySuggestion(suggestionId: string, contentId: string): Promise<any> {
    await delay(1500); // Simulate processing time
    return { success: true, suggestionId, contentId };
  },

  async exportOptimizationResults(contentId: string, format: string): Promise<Blob> {
    await delay(500);
    const content = JSON.stringify(generateDemoData(), null, 2);
    return new Blob([content], { type: 'application/json' });
  },

  async getOptimizationHistory(page: number, limit: number) {
    await delay(800);
    return {
      results: [generateDemoData()],
      total: 1,
    };
  },
};

// Override the real API with mock in development
if (process.env.NODE_ENV === 'development' && process.env.REACT_APP_USE_MOCK_API === 'true') {
  console.log('Using mock API for development');
  
  // Override the api module
  require('./api').fetchOptimizationResults = mockApi.fetchOptimizationResults;
  require('./api').applySuggestion = mockApi.applySuggestion;
  require('./api').exportOptimizationResults = mockApi.exportOptimizationResults;
  require('./api').getOptimizationHistory = mockApi.getOptimizationHistory;
}