import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface DashboardWidget {
  id: string;
  type: 'kpi' | 'chart' | 'heatmap' | 'funnel' | 'comparison' | '3d-network' | 'prediction';
  title: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
  config?: any;
}

export interface DashboardLayout {
  id: string;
  name: string;
  widgets: DashboardWidget[];
}

interface DashboardState {
  currentLayout: DashboardLayout | null;
  layouts: DashboardLayout[];
  theme: 'light' | 'dark';
  dateRange: {
    start: string;
    end: string;
  };
  autoRefresh: boolean;
  refreshInterval: number; // in seconds
  fullscreenWidget: string | null;
}

const initialState: DashboardState = {
  currentLayout: null,
  layouts: [],
  theme: 'light',
  dateRange: {
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    end: new Date().toISOString(),
  },
  autoRefresh: true,
  refreshInterval: 30,
  fullscreenWidget: null,
};

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    setCurrentLayout: (state, action: PayloadAction<DashboardLayout>) => {
      state.currentLayout = action.payload;
    },
    addLayout: (state, action: PayloadAction<DashboardLayout>) => {
      state.layouts.push(action.payload);
    },
    updateLayout: (state, action: PayloadAction<DashboardLayout>) => {
      const index = state.layouts.findIndex(l => l.id === action.payload.id);
      if (index !== -1) {
        state.layouts[index] = action.payload;
      }
      if (state.currentLayout?.id === action.payload.id) {
        state.currentLayout = action.payload;
      }
    },
    deleteLayout: (state, action: PayloadAction<string>) => {
      state.layouts = state.layouts.filter(l => l.id !== action.payload);
      if (state.currentLayout?.id === action.payload) {
        state.currentLayout = state.layouts[0] || null;
      }
    },
    updateWidget: (state, action: PayloadAction<DashboardWidget>) => {
      if (state.currentLayout) {
        const index = state.currentLayout.widgets.findIndex(w => w.id === action.payload.id);
        if (index !== -1) {
          state.currentLayout.widgets[index] = action.payload;
        }
      }
    },
    addWidget: (state, action: PayloadAction<DashboardWidget>) => {
      if (state.currentLayout) {
        state.currentLayout.widgets.push(action.payload);
      }
    },
    removeWidget: (state, action: PayloadAction<string>) => {
      if (state.currentLayout) {
        state.currentLayout.widgets = state.currentLayout.widgets.filter(
          w => w.id !== action.payload
        );
      }
    },
    setTheme: (state, action: PayloadAction<'light' | 'dark'>) => {
      state.theme = action.payload;
    },
    setDateRange: (state, action: PayloadAction<{ start: string; end: string }>) => {
      state.dateRange = action.payload;
    },
    setAutoRefresh: (state, action: PayloadAction<boolean>) => {
      state.autoRefresh = action.payload;
    },
    setRefreshInterval: (state, action: PayloadAction<number>) => {
      state.refreshInterval = action.payload;
    },
    setFullscreenWidget: (state, action: PayloadAction<string | null>) => {
      state.fullscreenWidget = action.payload;
    },
  },
});

export const {
  setCurrentLayout,
  addLayout,
  updateLayout,
  deleteLayout,
  updateWidget,
  addWidget,
  removeWidget,
  setTheme,
  setDateRange,
  setAutoRefresh,
  setRefreshInterval,
  setFullscreenWidget,
} = dashboardSlice.actions;

export default dashboardSlice.reducer;