import { useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from './index';
import {
  startOnboarding,
  completeStep,
  skipStep,
  nextStep,
  previousStep,
  goToStep,
  updateWizardData,
  completeOnboarding,
  saveProgress,
  loadProgress,
} from '../store/slices/onboardingSlice';
import { logEvent, incrementStepsCompleted, incrementStepsSkipped } from '../store/slices/analyticsSlice';
import { markOnboardingComplete } from '../store/slices/userSlice';
import { WizardData } from '../types';

export const useOnboarding = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const onboarding = useAppSelector((state) => state.onboarding);
  const user = useAppSelector((state) => state.user.currentUser);

  // Load saved progress on mount
  useEffect(() => {
    dispatch(loadProgress());
  }, [dispatch]);

  // Auto-save progress on changes
  useEffect(() => {
    if (onboarding.currentStep > 0) {
      dispatch(saveProgress());
    }
  }, [dispatch, onboarding.currentStep, onboarding.completedSteps]);

  const start = useCallback(() => {
    dispatch(startOnboarding());
    dispatch(logEvent({
      event: {
        name: 'onboarding_started',
        category: 'onboarding',
        properties: { userId: user?.id },
      },
    }));
    navigate('/onboarding/welcome');
  }, [dispatch, navigate, user?.id]);

  const complete = useCallback(() => {
    dispatch(completeOnboarding());
    dispatch(markOnboardingComplete());
    dispatch(logEvent({
      event: {
        name: 'onboarding_completed',
        category: 'onboarding',
        properties: {
          userId: user?.id,
          totalTime: Date.now() - (onboarding.startedAt?.getTime() || Date.now()),
          stepsCompleted: onboarding.completedSteps.length,
          stepsSkipped: onboarding.skippedSteps.length,
        },
      },
    }));
    navigate('/dashboard');
  }, [dispatch, navigate, user?.id, onboarding]);

  const completeCurrentStep = useCallback((stepId: string) => {
    dispatch(completeStep(stepId));
    dispatch(incrementStepsCompleted());
    dispatch(logEvent({
      event: {
        name: 'step_completed',
        category: 'onboarding',
        properties: { stepId, userId: user?.id },
      },
    }));
  }, [dispatch, user?.id]);

  const skipCurrentStep = useCallback((stepId: string) => {
    dispatch(skipStep(stepId));
    dispatch(incrementStepsSkipped());
    dispatch(logEvent({
      event: {
        name: 'step_skipped',
        category: 'onboarding',
        properties: { stepId, userId: user?.id },
      },
    }));
  }, [dispatch, user?.id]);

  const goNext = useCallback(() => {
    dispatch(nextStep());
  }, [dispatch]);

  const goPrevious = useCallback(() => {
    dispatch(previousStep());
  }, [dispatch]);

  const goTo = useCallback((step: number) => {
    dispatch(goToStep(step));
  }, [dispatch]);

  const updateWizard = useCallback((data: Partial<WizardData>) => {
    dispatch(updateWizardData(data));
  }, [dispatch]);

  const canProceed = useCallback((requiredFields: string[] = []): boolean => {
    // Check if required wizard data fields are filled
    for (const field of requiredFields) {
      if (!onboarding.wizardData[field as keyof WizardData]) {
        return false;
      }
    }
    return true;
  }, [onboarding.wizardData]);

  return {
    ...onboarding,
    start,
    complete,
    completeCurrentStep,
    skipCurrentStep,
    goNext,
    goPrevious,
    goTo,
    updateWizard,
    canProceed,
    isFirstTime: !user?.onboardingCompleted,
  };
};