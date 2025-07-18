import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface PredictionData {
  id: string;
  metric: string;
  timestamp: string;
  predicted: number;
  actual?: number;
  confidence: number;
  lowerBound: number;
  upperBound: number;
}

export interface TrendData {
  metric: string;
  trend: 'increasing' | 'decreasing' | 'stable';
  changeRate: number;
  confidence: number;
}

export interface AnomalyData {
  id: string;
  metric: string;
  timestamp: string;
  value: number;
  severity: 'low' | 'medium' | 'high';
  description: string;
}

export interface ScenarioData {
  id: string;
  name: string;
  parameters: { [key: string]: any };
  predictions: PredictionData[];
}

interface PredictionsState {
  predictions: PredictionData[];
  trends: TrendData[];
  anomalies: AnomalyData[];
  scenarios: ScenarioData[];
  activeScenario: string | null;
  loading: boolean;
  error: string | null;
}

const initialState: PredictionsState = {
  predictions: [],
  trends: [],
  anomalies: [],
  scenarios: [],
  activeScenario: null,
  loading: false,
  error: null,
};

const predictionsSlice = createSlice({
  name: 'predictions',
  initialState,
  reducers: {
    setPredictions: (state, action: PayloadAction<PredictionData[]>) => {
      state.predictions = action.payload;
    },
    addPrediction: (state, action: PayloadAction<PredictionData>) => {
      state.predictions.push(action.payload);
      // Keep only last 500 predictions for performance
      if (state.predictions.length > 500) {
        state.predictions = state.predictions.slice(-500);
      }
    },
    updatePredictionActual: (
      state,
      action: PayloadAction<{ id: string; actual: number }>
    ) => {
      const prediction = state.predictions.find(p => p.id === action.payload.id);
      if (prediction) {
        prediction.actual = action.payload.actual;
      }
    },
    setTrends: (state, action: PayloadAction<TrendData[]>) => {
      state.trends = action.payload;
    },
    setAnomalies: (state, action: PayloadAction<AnomalyData[]>) => {
      state.anomalies = action.payload;
    },
    addAnomaly: (state, action: PayloadAction<AnomalyData>) => {
      state.anomalies.unshift(action.payload);
      // Keep only last 50 anomalies
      if (state.anomalies.length > 50) {
        state.anomalies = state.anomalies.slice(0, 50);
      }
    },
    clearAnomaly: (state, action: PayloadAction<string>) => {
      state.anomalies = state.anomalies.filter(a => a.id !== action.payload);
    },
    addScenario: (state, action: PayloadAction<ScenarioData>) => {
      state.scenarios.push(action.payload);
    },
    updateScenario: (state, action: PayloadAction<ScenarioData>) => {
      const index = state.scenarios.findIndex(s => s.id === action.payload.id);
      if (index !== -1) {
        state.scenarios[index] = action.payload;
      }
    },
    deleteScenario: (state, action: PayloadAction<string>) => {
      state.scenarios = state.scenarios.filter(s => s.id !== action.payload);
      if (state.activeScenario === action.payload) {
        state.activeScenario = null;
      }
    },
    setActiveScenario: (state, action: PayloadAction<string | null>) => {
      state.activeScenario = action.payload;
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
  setPredictions,
  addPrediction,
  updatePredictionActual,
  setTrends,
  setAnomalies,
  addAnomaly,
  clearAnomaly,
  addScenario,
  updateScenario,
  deleteScenario,
  setActiveScenario,
  setLoading,
  setError,
} = predictionsSlice.actions;

export default predictionsSlice.reducer;