import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { OnboardingState, WizardData } from '../../types';

const initialState: OnboardingState = {
  currentStep: 0,
  totalSteps: 6,
  completedSteps: [],
  skippedSteps: [],
  progress: 0,
  tourActive: false,
  wizardData: {},
};

const onboardingSlice = createSlice({
  name: 'onboarding',
  initialState,
  reducers: {
    startOnboarding: (state) => {
      state.startedAt = new Date();
      state.currentStep = 0;
      state.progress = 0;
    },
    completeStep: (state, action: PayloadAction<string>) => {
      if (!state.completedSteps.includes(action.payload)) {
        state.completedSteps.push(action.payload);
        state.progress = (state.completedSteps.length / state.totalSteps) * 100;
      }
    },
    skipStep: (state, action: PayloadAction<string>) => {
      if (!state.skippedSteps.includes(action.payload)) {
        state.skippedSteps.push(action.payload);
      }
    },
    nextStep: (state) => {
      if (state.currentStep < state.totalSteps - 1) {
        state.currentStep += 1;
      }
    },
    previousStep: (state) => {
      if (state.currentStep > 0) {
        state.currentStep -= 1;
      }
    },
    goToStep: (state, action: PayloadAction<number>) => {
      if (action.payload >= 0 && action.payload < state.totalSteps) {
        state.currentStep = action.payload;
      }
    },
    updateWizardData: (state, action: PayloadAction<Partial<WizardData>>) => {
      state.wizardData = { ...state.wizardData, ...action.payload };
    },
    completeOnboarding: (state) => {
      state.completedAt = new Date();
      state.progress = 100;
    },
    resetOnboarding: () => initialState,
    setTourActive: (state, action: PayloadAction<boolean>) => {
      state.tourActive = action.payload;
    },
    saveProgress: (state) => {
      // This would trigger a side effect to save to localStorage or API
      localStorage.setItem('onboarding_progress', JSON.stringify({
        currentStep: state.currentStep,
        completedSteps: state.completedSteps,
        skippedSteps: state.skippedSteps,
        wizardData: state.wizardData,
        progress: state.progress,
      }));
    },
    loadProgress: (state) => {
      const saved = localStorage.getItem('onboarding_progress');
      if (saved) {
        const data = JSON.parse(saved);
        return { ...state, ...data };
      }
    },
  },
});

export const {
  startOnboarding,
  completeStep,
  skipStep,
  nextStep,
  previousStep,
  goToStep,
  updateWizardData,
  completeOnboarding,
  resetOnboarding,
  setTourActive,
  saveProgress,
  loadProgress,
} = onboardingSlice.actions;

export default onboardingSlice.reducer;