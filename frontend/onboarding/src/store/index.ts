import { configureStore } from '@reduxjs/toolkit';
import onboardingReducer from './slices/onboardingSlice';
import tourReducer from './slices/tourSlice';
import templateReducer from './slices/templateSlice';
import userReducer from './slices/userSlice';
import analyticsReducer from './slices/analyticsSlice';

export const store = configureStore({
  reducer: {
    onboarding: onboardingReducer,
    tour: tourReducer,
    template: templateReducer,
    user: userReducer,
    analytics: analyticsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['analytics/logEvent'],
        // Ignore these field paths in all actions
        ignoredActionPaths: ['payload.timestamp', 'payload.date'],
        // Ignore these paths in the state
        ignoredPaths: ['onboarding.startedAt', 'onboarding.completedAt'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;