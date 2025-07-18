import { configureStore } from '@reduxjs/toolkit';
import dashboardReducer from './slices/dashboardSlice';
import visibilityReducer from './slices/visibilitySlice';
import suggestionsReducer from './slices/suggestionsSlice';
import metricsReducer from './slices/metricsSlice';
import websocketReducer from './slices/websocketSlice';

export const store = configureStore({
  reducer: {
    dashboard: dashboardReducer,
    visibility: visibilityReducer,
    suggestions: suggestionsReducer,
    metrics: metricsReducer,
    websocket: websocketReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['websocket/connected', 'websocket/disconnected'],
        // Ignore these field paths in all actions
        ignoredActionPaths: ['payload.timestamp'],
        // Ignore these paths in the state
        ignoredPaths: ['websocket.socket'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;