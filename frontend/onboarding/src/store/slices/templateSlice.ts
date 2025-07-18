import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit';
import { Template, ContentType } from '../../types';
import { fetchTemplates } from '../../services/templateService';

interface TemplateState {
  templates: Template[];
  selectedTemplate: Template | null;
  loading: boolean;
  error: string | null;
  filters: {
    category: ContentType | null;
    industry: string | null;
    searchQuery: string;
    sortBy: 'popularity' | 'name' | 'difficulty';
  };
}

const initialState: TemplateState = {
  templates: [],
  selectedTemplate: null,
  loading: false,
  error: null,
  filters: {
    category: null,
    industry: null,
    searchQuery: '',
    sortBy: 'popularity',
  },
};

// Async thunk for fetching templates
export const loadTemplates = createAsyncThunk(
  'template/loadTemplates',
  async () => {
    const templates = await fetchTemplates();
    return templates;
  }
);

const templateSlice = createSlice({
  name: 'template',
  initialState,
  reducers: {
    selectTemplate: (state, action: PayloadAction<Template>) => {
      state.selectedTemplate = action.payload;
    },
    clearSelectedTemplate: (state) => {
      state.selectedTemplate = null;
    },
    setFilter: (state, action: PayloadAction<Partial<TemplateState['filters']>>) => {
      state.filters = { ...state.filters, ...action.payload };
    },
    clearFilters: (state) => {
      state.filters = initialState.filters;
    },
    applyTemplate: (state, action: PayloadAction<string>) => {
      // This would trigger a side effect to apply the template
      const template = state.templates.find(t => t.id === action.payload);
      if (template) {
        state.selectedTemplate = template;
        // Save to localStorage for persistence
        localStorage.setItem('applied_template', JSON.stringify(template));
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadTemplates.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(loadTemplates.fulfilled, (state, action) => {
        state.loading = false;
        state.templates = action.payload;
      })
      .addCase(loadTemplates.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to load templates';
      });
  },
});

export const {
  selectTemplate,
  clearSelectedTemplate,
  setFilter,
  clearFilters,
  applyTemplate,
} = templateSlice.actions;

export default templateSlice.reducer;