import axios from 'axios';
import { User, OnboardingState, WizardData, AnalyticsEvent } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class OnboardingService {
  private apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  constructor() {
    // Add auth token to requests if available
    this.apiClient.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  // Progress tracking
  async saveProgress(userId: string, progress: Partial<OnboardingState>): Promise<void> {
    try {
      await this.apiClient.post(`/onboarding/progress/${userId}`, progress);
      // Also save to localStorage as backup
      localStorage.setItem(`onboarding_progress_${userId}`, JSON.stringify(progress));
    } catch (error) {
      console.error('Failed to save progress to server, saving locally', error);
      localStorage.setItem(`onboarding_progress_${userId}`, JSON.stringify(progress));
    }
  }

  async loadProgress(userId: string): Promise<Partial<OnboardingState> | null> {
    try {
      const response = await this.apiClient.get(`/onboarding/progress/${userId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to load progress from server, checking local storage', error);
      const localData = localStorage.getItem(`onboarding_progress_${userId}`);
      return localData ? JSON.parse(localData) : null;
    }
  }

  async completeOnboarding(userId: string, wizardData: WizardData): Promise<void> {
    try {
      await this.apiClient.post(`/onboarding/complete/${userId}`, {
        wizardData,
        completedAt: new Date().toISOString(),
      });
      // Clear local storage on successful completion
      localStorage.removeItem(`onboarding_progress_${userId}`);
    } catch (error) {
      console.error('Failed to complete onboarding', error);
      throw error;
    }
  }

  // User preferences
  async saveUserPreferences(userId: string, preferences: any): Promise<void> {
    try {
      await this.apiClient.put(`/users/${userId}/preferences`, preferences);
    } catch (error) {
      console.error('Failed to save user preferences', error);
      throw error;
    }
  }

  async getUserPreferences(userId: string): Promise<any> {
    try {
      const response = await this.apiClient.get(`/users/${userId}/preferences`);
      return response.data;
    } catch (error) {
      console.error('Failed to get user preferences', error);
      throw error;
    }
  }

  // Tour completion tracking
  async markTourCompleted(userId: string, tourId: string): Promise<void> {
    try {
      await this.apiClient.post(`/onboarding/tours/${userId}/complete`, { tourId });
      // Also save locally
      const completedTours = JSON.parse(localStorage.getItem('completed_tours') || '[]');
      if (!completedTours.includes(tourId)) {
        completedTours.push(tourId);
        localStorage.setItem('completed_tours', JSON.stringify(completedTours));
      }
    } catch (error) {
      console.error('Failed to mark tour as completed', error);
    }
  }

  async getCompletedTours(userId: string): Promise<string[]> {
    try {
      const response = await this.apiClient.get(`/onboarding/tours/${userId}/completed`);
      return response.data.tours || [];
    } catch (error) {
      console.error('Failed to get completed tours from server', error);
      return JSON.parse(localStorage.getItem('completed_tours') || '[]');
    }
  }

  // Analytics
  async trackEvent(event: AnalyticsEvent, userId?: string): Promise<void> {
    try {
      await this.apiClient.post('/analytics/events', {
        ...event,
        userId,
        timestamp: new Date().toISOString(),
        sessionId: this.getSessionId(),
      });
    } catch (error) {
      console.error('Failed to track analytics event', error);
      // Store events locally if API fails
      this.storeEventLocally(event);
    }
  }

  async getOnboardingMetrics(userId: string): Promise<any> {
    try {
      const response = await this.apiClient.get(`/analytics/onboarding/${userId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get onboarding metrics', error);
      throw error;
    }
  }

  // Helper methods
  private getSessionId(): string {
    let sessionId = sessionStorage.getItem('onboarding_session_id');
    if (!sessionId) {
      sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('onboarding_session_id', sessionId);
    }
    return sessionId;
  }

  private storeEventLocally(event: AnalyticsEvent): void {
    const events = JSON.parse(localStorage.getItem('pending_analytics_events') || '[]');
    events.push({
      ...event,
      timestamp: new Date().toISOString(),
      sessionId: this.getSessionId(),
    });
    localStorage.setItem('pending_analytics_events', JSON.stringify(events));
  }

  // Sync locally stored events when connection is restored
  async syncPendingEvents(): Promise<void> {
    const events = JSON.parse(localStorage.getItem('pending_analytics_events') || '[]');
    if (events.length === 0) return;

    try {
      await this.apiClient.post('/analytics/events/batch', { events });
      localStorage.removeItem('pending_analytics_events');
    } catch (error) {
      console.error('Failed to sync pending events', error);
    }
  }

  // Check if user needs onboarding
  async checkOnboardingStatus(userId: string): Promise<boolean> {
    try {
      const response = await this.apiClient.get(`/users/${userId}/onboarding-status`);
      return response.data.needsOnboarding;
    } catch (error) {
      console.error('Failed to check onboarding status', error);
      return true; // Default to showing onboarding if check fails
    }
  }
}

export const onboardingService = new OnboardingService();