import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit';
import { Suggestion } from '../../types';
import { applySuggestion } from '../../services/api';

interface SuggestionsState {
  items: Suggestion[];
  selectedIds: string[];
  sortBy: 'priority' | 'impact' | 'category';
  sortOrder: 'asc' | 'desc';
  searchQuery: string;
  applyingIds: string[];
  appliedIds: string[];
  error: string | null;
}

const initialState: SuggestionsState = {
  items: [],
  selectedIds: [],
  sortBy: 'priority',
  sortOrder: 'desc',
  searchQuery: '',
  applyingIds: [],
  appliedIds: [],
  error: null,
};

// Async thunk for applying a suggestion
export const applySuggestionAsync = createAsyncThunk(
  'suggestions/apply',
  async ({ suggestionId, contentId }: { suggestionId: string; contentId: string }) => {
    const response = await applySuggestion(suggestionId, contentId);
    return { suggestionId, response };
  }
);

const suggestionsSlice = createSlice({
  name: 'suggestions',
  initialState,
  reducers: {
    setSuggestions: (state, action: PayloadAction<Suggestion[]>) => {
      state.items = action.payload;
    },
    toggleSuggestionSelection: (state, action: PayloadAction<string>) => {
      const id = action.payload;
      const index = state.selectedIds.indexOf(id);
      if (index > -1) {
        state.selectedIds.splice(index, 1);
      } else {
        state.selectedIds.push(id);
      }
    },
    selectAllSuggestions: (state) => {
      state.selectedIds = state.items.map(s => s.id);
    },
    clearSelection: (state) => {
      state.selectedIds = [];
    },
    setSortBy: (state, action: PayloadAction<SuggestionsState['sortBy']>) => {
      state.sortBy = action.payload;
    },
    setSortOrder: (state, action: PayloadAction<SuggestionsState['sortOrder']>) => {
      state.sortOrder = action.payload;
    },
    setSearchQuery: (state, action: PayloadAction<string>) => {
      state.searchQuery = action.payload;
    },
    updateSuggestionStatus: (state, action: PayloadAction<{ id: string; status: Suggestion['status'] }>) => {
      const suggestion = state.items.find(s => s.id === action.payload.id);
      if (suggestion) {
        suggestion.status = action.payload.status;
      }
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(applySuggestionAsync.pending, (state, action) => {
        state.applyingIds.push(action.meta.arg.suggestionId);
        state.error = null;
      })
      .addCase(applySuggestionAsync.fulfilled, (state, action) => {
        const { suggestionId } = action.payload;
        state.applyingIds = state.applyingIds.filter(id => id !== suggestionId);
        state.appliedIds.push(suggestionId);
        // Update suggestion status
        const suggestion = state.items.find(s => s.id === suggestionId);
        if (suggestion) {
          suggestion.status = 'applied';
        }
      })
      .addCase(applySuggestionAsync.rejected, (state, action) => {
        state.applyingIds = state.applyingIds.filter(
          id => id !== action.meta.arg.suggestionId
        );
        state.error = action.error.message || 'Failed to apply suggestion';
      });
  },
});

export const {
  setSuggestions,
  toggleSuggestionSelection,
  selectAllSuggestions,
  clearSelection,
  setSortBy,
  setSortOrder,
  setSearchQuery,
  updateSuggestionStatus,
  clearError,
} = suggestionsSlice.actions;

export default suggestionsSlice.reducer;