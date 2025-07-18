import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { VisibilityData, PlatformScore } from '../../types';

interface VisibilityState {
  data: VisibilityData | null;
  history: VisibilityData[];
  selectedTimeRange: '1h' | '24h' | '7d' | '30d';
  comparisonMode: boolean;
  comparisonData: VisibilityData | null;
}

const initialState: VisibilityState = {
  data: null,
  history: [],
  selectedTimeRange: '24h',
  comparisonMode: false,
  comparisonData: null,
};

const visibilitySlice = createSlice({
  name: 'visibility',
  initialState,
  reducers: {
    setVisibilityData: (state, action: PayloadAction<VisibilityData>) => {
      state.data = action.payload;
      // Add to history
      state.history.push(action.payload);
      // Keep only last 100 entries
      if (state.history.length > 100) {
        state.history = state.history.slice(-100);
      }
    },
    updatePlatformScore: (state, action: PayloadAction<PlatformScore>) => {
      if (state.data) {
        const index = state.data.platforms.findIndex(
          p => p.platform === action.payload.platform
        );
        if (index !== -1) {
          state.data.platforms[index] = action.payload;
        }
      }
    },
    setTimeRange: (state, action: PayloadAction<VisibilityState['selectedTimeRange']>) => {
      state.selectedTimeRange = action.payload;
    },
    toggleComparisonMode: (state) => {
      state.comparisonMode = !state.comparisonMode;
    },
    setComparisonData: (state, action: PayloadAction<VisibilityData | null>) => {
      state.comparisonData = action.payload;
    },
    clearHistory: (state) => {
      state.history = [];
    },
  },
});

export const {
  setVisibilityData,
  updatePlatformScore,
  setTimeRange,
  toggleComparisonMode,
  setComparisonData,
  clearHistory,
} = visibilitySlice.actions;

export default visibilitySlice.reducer;