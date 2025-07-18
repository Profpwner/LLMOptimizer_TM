import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { TourState, TourStep } from '../../types';

const initialState: TourState = {
  run: false,
  stepIndex: 0,
  steps: [],
  tourId: '',
  completed: false,
};

const tourSlice = createSlice({
  name: 'tour',
  initialState,
  reducers: {
    startTour: (state, action: PayloadAction<{ tourId: string; steps: TourStep[] }>) => {
      state.run = true;
      state.tourId = action.payload.tourId;
      state.steps = action.payload.steps;
      state.stepIndex = 0;
      state.completed = false;
    },
    stopTour: (state) => {
      state.run = false;
    },
    resetTour: (state) => {
      state.run = false;
      state.stepIndex = 0;
      state.completed = false;
    },
    nextTourStep: (state) => {
      if (state.stepIndex < state.steps.length - 1) {
        state.stepIndex += 1;
      } else {
        state.completed = true;
        state.run = false;
      }
    },
    previousTourStep: (state) => {
      if (state.stepIndex > 0) {
        state.stepIndex -= 1;
      }
    },
    goToTourStep: (state, action: PayloadAction<number>) => {
      if (action.payload >= 0 && action.payload < state.steps.length) {
        state.stepIndex = action.payload;
      }
    },
    completeTour: (state) => {
      state.completed = true;
      state.run = false;
      // Save completed tour to localStorage
      const completedTours = JSON.parse(localStorage.getItem('completed_tours') || '[]');
      if (!completedTours.includes(state.tourId)) {
        completedTours.push(state.tourId);
        localStorage.setItem('completed_tours', JSON.stringify(completedTours));
      }
    },
    updateTourSteps: (state, action: PayloadAction<TourStep[]>) => {
      state.steps = action.payload;
    },
  },
});

export const {
  startTour,
  stopTour,
  resetTour,
  nextTourStep,
  previousTourStep,
  goToTourStep,
  completeTour,
  updateTourSteps,
} = tourSlice.actions;

export default tourSlice.reducer;