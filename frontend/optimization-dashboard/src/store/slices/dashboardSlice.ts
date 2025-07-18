import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit';
import { DashboardState, OptimizationResult, Platform } from '../../types';
import { fetchOptimizationResults } from '../../services/api';

const initialState: DashboardState = {
  results: null,
  loading: false,
  error: null,
  selectedPlatform: 'all',
  filters: {
    suggestionCategories: [],
    suggestionPriorities: [],
    suggestionStatus: ['pending'],
  },
  viewMode: 'split',
};

// Async thunk for fetching optimization results
export const loadOptimizationResults = createAsyncThunk(
  'dashboard/loadResults',
  async (contentId: string) => {
    const response = await fetchOptimizationResults(contentId);
    return response;
  }
);

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    setSelectedPlatform: (state, action: PayloadAction<Platform | 'all'>) => {
      state.selectedPlatform = action.payload;
    },
    setViewMode: (state, action: PayloadAction<'split' | 'unified'>) => {
      state.viewMode = action.payload;
    },
    updateFilters: (state, action: PayloadAction<Partial<DashboardState['filters']>>) => {
      state.filters = { ...state.filters, ...action.payload };
    },
    clearError: (state) => {
      state.error = null;
    },
    updateResults: (state, action: PayloadAction<Partial<OptimizationResult>>) => {
      if (state.results) {
        state.results = { ...state.results, ...action.payload };
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadOptimizationResults.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(loadOptimizationResults.fulfilled, (state, action) => {
        state.loading = false;
        state.results = action.payload;
      })
      .addCase(loadOptimizationResults.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to load optimization results';
      });
  },
});

export const {
  setSelectedPlatform,
  setViewMode,
  updateFilters,
  clearError,
  updateResults,
} = dashboardSlice.actions;

export default dashboardSlice.reducer;