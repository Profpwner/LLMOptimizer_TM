import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface AnalyticsMetric {
  id: string;
  name: string;
  value: number;
  change: number;
  timestamp: string;
  unit?: string;
}

export interface TimeSeriesData {
  timestamp: string;
  value: number;
  label?: string;
}

export interface HeatmapData {
  x: string;
  y: string;
  value: number;
}

interface AnalyticsState {
  metrics: AnalyticsMetric[];
  timeSeriesData: { [key: string]: TimeSeriesData[] };
  heatmapData: HeatmapData[];
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
}

const initialState: AnalyticsState = {
  metrics: [],
  timeSeriesData: {},
  heatmapData: [],
  loading: false,
  error: null,
  lastUpdated: null,
};

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    setMetrics: (state, action: PayloadAction<AnalyticsMetric[]>) => {
      state.metrics = action.payload;
      state.lastUpdated = new Date().toISOString();
    },
    updateMetric: (state, action: PayloadAction<AnalyticsMetric>) => {
      const index = state.metrics.findIndex(m => m.id === action.payload.id);
      if (index !== -1) {
        state.metrics[index] = action.payload;
      } else {
        state.metrics.push(action.payload);
      }
      state.lastUpdated = new Date().toISOString();
    },
    setTimeSeriesData: (state, action: PayloadAction<{ key: string; data: TimeSeriesData[] }>) => {
      state.timeSeriesData[action.payload.key] = action.payload.data;
    },
    appendTimeSeriesData: (state, action: PayloadAction<{ key: string; data: TimeSeriesData }>) => {
      if (!state.timeSeriesData[action.payload.key]) {
        state.timeSeriesData[action.payload.key] = [];
      }
      state.timeSeriesData[action.payload.key].push(action.payload.data);
      // Keep only last 100 data points for performance
      if (state.timeSeriesData[action.payload.key].length > 100) {
        state.timeSeriesData[action.payload.key].shift();
      }
    },
    setHeatmapData: (state, action: PayloadAction<HeatmapData[]>) => {
      state.heatmapData = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const {
  setMetrics,
  updateMetric,
  setTimeSeriesData,
  appendTimeSeriesData,
  setHeatmapData,
  setLoading,
  setError,
} = analyticsSlice.actions;

export default analyticsSlice.reducer;