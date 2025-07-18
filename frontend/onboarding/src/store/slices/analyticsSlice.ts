import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { AnalyticsEvent, AnalyticsEventLog, OnboardingMetrics } from '../../types';

interface AnalyticsState {
  sessionId: string;
  events: AnalyticsEventLog[];
  metrics: OnboardingMetrics;
}

const generateSessionId = () => {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

const initialState: AnalyticsState = {
  sessionId: generateSessionId(),
  events: [],
  metrics: {
    totalTime: 0,
    completionRate: 0,
    stepsCompleted: 0,
    stepsSkipped: 0,
    tourCompleted: false,
    wizardCompleted: false,
    templateSelected: false,
  },
};

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    logEvent: (state, action: PayloadAction<{ event: AnalyticsEvent; context?: Record<string, any> }>) => {
      state.events.push({
        event: action.payload.event,
        timestamp: new Date(),
        context: action.payload.context,
      });
      
      // Send to analytics service (would be implemented in middleware)
      console.log('Analytics Event:', action.payload.event.name, action.payload);
    },
    updateMetrics: (state, action: PayloadAction<Partial<OnboardingMetrics>>) => {
      state.metrics = { ...state.metrics, ...action.payload };
    },
    incrementStepsCompleted: (state) => {
      state.metrics.stepsCompleted += 1;
    },
    incrementStepsSkipped: (state) => {
      state.metrics.stepsSkipped += 1;
    },
    setTourCompleted: (state) => {
      state.metrics.tourCompleted = true;
    },
    setWizardCompleted: (state) => {
      state.metrics.wizardCompleted = true;
    },
    setTemplateSelected: (state) => {
      state.metrics.templateSelected = true;
    },
    calculateCompletionRate: (state, action: PayloadAction<{ completed: number; total: number }>) => {
      state.metrics.completionRate = (action.payload.completed / action.payload.total) * 100;
    },
    setDropoffStep: (state, action: PayloadAction<string>) => {
      state.metrics.dropoffStep = action.payload;
    },
    resetAnalytics: () => initialState,
    exportAnalytics: (state) => {
      // This would export analytics data
      const data = {
        sessionId: state.sessionId,
        events: state.events,
        metrics: state.metrics,
        exportedAt: new Date(),
      };
      console.log('Exporting analytics:', data);
      // In production, this would send to an analytics service
    },
  },
});

export const {
  logEvent,
  updateMetrics,
  incrementStepsCompleted,
  incrementStepsSkipped,
  setTourCompleted,
  setWizardCompleted,
  setTemplateSelected,
  calculateCompletionRate,
  setDropoffStep,
  resetAnalytics,
  exportAnalytics,
} = analyticsSlice.actions;

export default analyticsSlice.reducer;