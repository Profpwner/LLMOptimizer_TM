import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { ImpactMetrics, Metric } from '../../types';

interface MetricsState {
  current: ImpactMetrics | null;
  history: {
    timestamp: string;
    metrics: ImpactMetrics;
  }[];
  selectedMetrics: string[];
  timeframe: '1h' | '24h' | '7d' | '30d';
  showTargets: boolean;
  animationsEnabled: boolean;
}

const initialState: MetricsState = {
  current: null,
  history: [],
  selectedMetrics: ['visibility', 'engagement', 'conversion', 'reach', 'performance'],
  timeframe: '24h',
  showTargets: true,
  animationsEnabled: true,
};

const metricsSlice = createSlice({
  name: 'metrics',
  initialState,
  reducers: {
    setMetrics: (state, action: PayloadAction<ImpactMetrics>) => {
      state.current = action.payload;
      // Add to history
      state.history.push({
        timestamp: new Date().toISOString(),
        metrics: action.payload,
      });
      // Keep only last 100 entries
      if (state.history.length > 100) {
        state.history = state.history.slice(-100);
      }
    },
    updateMetric: (state, action: PayloadAction<{ key: keyof ImpactMetrics; metric: Metric }>) => {
      if (state.current) {
        (state.current[action.payload.key] as any) = action.payload.metric;
      }
    },
    toggleMetricSelection: (state, action: PayloadAction<string>) => {
      const index = state.selectedMetrics.indexOf(action.payload);
      if (index > -1) {
        state.selectedMetrics.splice(index, 1);
      } else {
        state.selectedMetrics.push(action.payload);
      }
    },
    setTimeframe: (state, action: PayloadAction<MetricsState['timeframe']>) => {
      state.timeframe = action.payload;
    },
    toggleShowTargets: (state) => {
      state.showTargets = !state.showTargets;
    },
    toggleAnimations: (state) => {
      state.animationsEnabled = !state.animationsEnabled;
    },
    clearHistory: (state) => {
      state.history = [];
    },
  },
});

export const {
  setMetrics,
  updateMetric,
  toggleMetricSelection,
  setTimeframe,
  toggleShowTargets,
  toggleAnimations,
  clearHistory,
} = metricsSlice.actions;

export default metricsSlice.reducer;