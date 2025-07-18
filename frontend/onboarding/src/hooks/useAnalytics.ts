import { useCallback } from 'react';
import { useAppDispatch, useAppSelector } from './index';
import {
  logEvent as logAnalyticsEvent,
  updateMetrics,
  exportAnalytics,
} from '../store/slices/analyticsSlice';
import { AnalyticsEvent } from '../types';

export const useAnalytics = () => {
  const dispatch = useAppDispatch();
  const analytics = useAppSelector((state) => state.analytics);
  const user = useAppSelector((state) => state.user.currentUser);

  const logEvent = useCallback((
    name: string,
    category: AnalyticsEvent['category'],
    properties?: Record<string, any>
  ) => {
    dispatch(logAnalyticsEvent({
      event: {
        name,
        category,
        properties: {
          ...properties,
          userId: user?.id,
          sessionId: analytics.sessionId,
          timestamp: new Date().toISOString(),
        },
      },
    }));
  }, [dispatch, user?.id, analytics.sessionId]);

  const logInteraction = useCallback((
    element: string,
    action: string,
    value?: any
  ) => {
    logEvent('user_interaction', 'onboarding', {
      element,
      action,
      value,
    });
  }, [logEvent]);

  const logPageView = useCallback((
    pageName: string,
    pageCategory: string
  ) => {
    logEvent('page_view', 'onboarding', {
      pageName,
      pageCategory,
      referrer: document.referrer,
      url: window.location.href,
    });
  }, [logEvent]);

  const logError = useCallback((
    error: Error,
    context?: Record<string, any>
  ) => {
    logEvent('error_occurred', 'onboarding', {
      errorMessage: error.message,
      errorStack: error.stack,
      ...context,
    });
  }, [logEvent]);

  const updateMetric = useCallback((
    metric: keyof typeof analytics.metrics,
    value: any
  ) => {
    dispatch(updateMetrics({ [metric]: value }));
  }, [dispatch]);

  const trackTiming = useCallback((
    category: string,
    variable: string,
    value: number
  ) => {
    logEvent('timing_complete', 'onboarding', {
      timingCategory: category,
      timingVariable: variable,
      timingValue: value,
    });
  }, [logEvent]);

  const exportData = useCallback(() => {
    dispatch(exportAnalytics());
  }, [dispatch]);

  // Helper to track feature usage
  const trackFeatureUsage = useCallback((
    featureName: string,
    metadata?: Record<string, any>
  ) => {
    logEvent('feature_used', 'onboarding', {
      featureName,
      ...metadata,
    });
  }, [logEvent]);

  // Helper to track goal completion
  const trackGoal = useCallback((
    goalName: string,
    goalValue?: number
  ) => {
    logEvent('goal_completed', 'onboarding', {
      goalName,
      goalValue,
    });
  }, [logEvent]);

  return {
    ...analytics,
    logEvent,
    logInteraction,
    logPageView,
    logError,
    updateMetric,
    trackTiming,
    trackFeatureUsage,
    trackGoal,
    exportData,
  };
};