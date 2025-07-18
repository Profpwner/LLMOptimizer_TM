import { useCallback, useEffect, useState } from 'react';
import { useAppDispatch, useAppSelector } from './index';
import {
  startTour,
  stopTour,
  resetTour,
  nextTourStep,
  previousTourStep,
  goToTourStep,
  completeTour,
} from '../store/slices/tourSlice';
import { logEvent, setTourCompleted } from '../store/slices/analyticsSlice';
import { TourStep } from '../types';
import { TOUR_STEPS } from '../utils/tourSteps';

export const useProductTour = (tourId: string = 'default') => {
  const dispatch = useAppDispatch();
  const tour = useAppSelector((state) => state.tour);
  const user = useAppSelector((state) => state.user.currentUser);
  const [isReady, setIsReady] = useState(false);

  // Check if tour should auto-start
  useEffect(() => {
    const completedTours = JSON.parse(localStorage.getItem('completed_tours') || '[]');
    const shouldAutoStart = !completedTours.includes(tourId) && user && !user.onboardingCompleted;
    
    if (shouldAutoStart) {
      // Small delay to ensure DOM is ready
      setTimeout(() => {
        setIsReady(true);
      }, 500);
    }
  }, [tourId, user]);

  const start = useCallback((customSteps?: TourStep[]) => {
    const steps = customSteps || TOUR_STEPS[tourId] || TOUR_STEPS.default;
    dispatch(startTour({ tourId, steps }));
    dispatch(logEvent({
      event: {
        name: 'tour_started',
        category: 'tour',
        properties: { tourId, userId: user?.id, stepCount: steps.length },
      },
    }));
  }, [dispatch, tourId, user?.id]);

  const stop = useCallback(() => {
    dispatch(stopTour());
    dispatch(logEvent({
      event: {
        name: 'tour_stopped',
        category: 'tour',
        properties: {
          tourId,
          userId: user?.id,
          stoppedAtStep: tour.stepIndex,
          completed: false,
        },
      },
    }));
  }, [dispatch, tourId, user?.id, tour.stepIndex]);

  const reset = useCallback(() => {
    dispatch(resetTour());
  }, [dispatch]);

  const next = useCallback(() => {
    const isLastStep = tour.stepIndex === tour.steps.length - 1;
    
    if (isLastStep) {
      complete();
    } else {
      dispatch(nextTourStep());
      dispatch(logEvent({
        event: {
          name: 'tour_step_completed',
          category: 'tour',
          properties: {
            tourId,
            userId: user?.id,
            stepIndex: tour.stepIndex,
            stepTarget: tour.steps[tour.stepIndex]?.target,
          },
        },
      }));
    }
  }, [dispatch, tour, tourId, user?.id]);

  const previous = useCallback(() => {
    dispatch(previousTourStep());
  }, [dispatch]);

  const goToStep = useCallback((stepIndex: number) => {
    dispatch(goToTourStep(stepIndex));
    dispatch(logEvent({
      event: {
        name: 'tour_step_jumped',
        category: 'tour',
        properties: {
          tourId,
          userId: user?.id,
          fromStep: tour.stepIndex,
          toStep: stepIndex,
        },
      },
    }));
  }, [dispatch, tourId, user?.id, tour.stepIndex]);

  const complete = useCallback(() => {
    dispatch(completeTour());
    dispatch(setTourCompleted());
    dispatch(logEvent({
      event: {
        name: 'tour_completed',
        category: 'tour',
        properties: {
          tourId,
          userId: user?.id,
          totalSteps: tour.steps.length,
        },
      },
    }));
  }, [dispatch, tourId, user?.id, tour.steps.length]);

  // Helper to check if a specific element is available
  const isElementReady = useCallback((selector: string): boolean => {
    return !!document.querySelector(selector);
  }, []);

  // Wait for all tour targets to be available
  const waitForElements = useCallback(async (selectors: string[]): Promise<boolean> => {
    const maxAttempts = 20;
    let attempts = 0;

    while (attempts < maxAttempts) {
      const allReady = selectors.every(isElementReady);
      if (allReady) return true;

      await new Promise(resolve => setTimeout(resolve, 100));
      attempts++;
    }

    return false;
  }, [isElementReady]);

  return {
    ...tour,
    isReady,
    start,
    stop,
    reset,
    next,
    previous,
    goToStep,
    complete,
    isElementReady,
    waitForElements,
  };
};