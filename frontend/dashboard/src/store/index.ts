import { configureStore } from '@reduxjs/toolkit';
import analyticsReducer from './slices/analyticsSlice';
import websocketReducer from './slices/websocketSlice';
import dashboardReducer from './slices/dashboardSlice';
import predictionsReducer from './slices/predictionsSlice';
import { contentApi } from '../services/contentApi';

export const store = configureStore({
  reducer: {
    analytics: analyticsReducer,
    websocket: websocketReducer,
    dashboard: dashboardReducer,
    predictions: predictionsReducer,
    [contentApi.reducerPath]: contentApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(contentApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;