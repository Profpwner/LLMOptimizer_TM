import React, { useMemo, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  InputAdornment,
  IconButton,
  Chip,
  Button,
  Menu,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Divider,
  CircularProgress,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import SortIcon from '@mui/icons-material/Sort';
import ClearIcon from '@mui/icons-material/Clear';
import { useAppSelector } from '../../hooks/useAppSelector';
import { useAppDispatch } from '../../hooks/useAppDispatch';
import { 
  setSearchQuery, 
  setSortBy, 
  setSortOrder,
  selectAllSuggestions,
  clearSelection,
} from '../../store/slices/suggestionsSlice';
import { updateFilters } from '../../store/slices/dashboardSlice';
import SuggestionCard from './SuggestionCard';

const Suggestions: React.FC = () => {
  const dispatch = useAppDispatch();
  const { items, searchQuery, sortBy, sortOrder, selectedIds, applyingIds } = useAppSelector((state) => state.suggestions);
  const { filters } = useAppSelector((state) => state.dashboard);
  
  const [filterAnchor, setFilterAnchor] = useState<null | HTMLElement>(null);
  const [sortAnchor, setSortAnchor] = useState<null | HTMLElement>(null);

  // Filter and sort suggestions
  const filteredSuggestions = useMemo(() => {
    let filtered = items;

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (s) =>
          s.title.toLowerCase().includes(query) ||
          s.description.toLowerCase().includes(query) ||
          s.category.toLowerCase().includes(query)
      );
    }

    // Apply category filter
    if (filters.suggestionCategories.length > 0) {
      filtered = filtered.filter((s) => filters.suggestionCategories.includes(s.category));
    }

    // Apply priority filter
    if (filters.suggestionPriorities.length > 0) {
      filtered = filtered.filter((s) => filters.suggestionPriorities.includes(s.priority));
    }

    // Apply status filter
    if (filters.suggestionStatus.length > 0) {
      filtered = filtered.filter((s) => filters.suggestionStatus.includes(s.status));
    }

    // Sort
    const sorted = [...filtered].sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case 'priority':
          const priorityOrder = { high: 3, medium: 2, low: 1 };
          comparison = priorityOrder[b.priority] - priorityOrder[a.priority];
          break;
        case 'impact':
          comparison = b.impact - a.impact;
          break;
        case 'category':
          comparison = a.category.localeCompare(b.category);
          break;
      }
      return sortOrder === 'asc' ? -comparison : comparison;
    });

    return sorted;
  }, [items, searchQuery, filters, sortBy, sortOrder]);

  const handleCategoryToggle = (category: string) => {
    const newCategories = filters.suggestionCategories.includes(category)
      ? filters.suggestionCategories.filter((c) => c !== category)
      : [...filters.suggestionCategories, category];
    dispatch(updateFilters({ suggestionCategories: newCategories }));
  };

  const handlePriorityToggle = (priority: string) => {
    const newPriorities = filters.suggestionPriorities.includes(priority)
      ? filters.suggestionPriorities.filter((p) => p !== priority)
      : [...filters.suggestionPriorities, priority];
    dispatch(updateFilters({ suggestionPriorities: newPriorities }));
  };

  const handleStatusToggle = (status: string) => {
    const newStatus = filters.suggestionStatus.includes(status)
      ? filters.suggestionStatus.filter((s) => s !== status)
      : [...filters.suggestionStatus, status];
    dispatch(updateFilters({ suggestionStatus: newStatus }));
  };

  const categories = ['keyword', 'structure', 'readability', 'technical', 'engagement'];
  const priorities = ['high', 'medium', 'low'];
  const statuses = ['pending', 'applied', 'rejected'];

  return (
    <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          Optimization Suggestions
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search suggestions..."
            value={searchQuery}
            onChange={(e) => dispatch(setSearchQuery(e.target.value))}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
              endAdornment: searchQuery && (
                <InputAdornment position="end">
                  <IconButton size="small" onClick={() => dispatch(setSearchQuery(''))}>
                    <ClearIcon />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          
          <IconButton onClick={(e) => setFilterAnchor(e.currentTarget)}>
            <FilterListIcon />
          </IconButton>
          
          <IconButton onClick={(e) => setSortAnchor(e.currentTarget)}>
            <SortIcon />
          </IconButton>
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {filteredSuggestions.length} suggestions found
            {selectedIds.length > 0 && ` • ${selectedIds.length} selected`}
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1 }}>
            {selectedIds.length > 0 && (
              <>
                <Button size="small" onClick={() => dispatch(clearSelection())}>
                  Clear Selection
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  disabled={applyingIds.length > 0}
                >
                  Apply Selected ({selectedIds.length})
                </Button>
              </>
            )}
            {selectedIds.length === 0 && filteredSuggestions.length > 0 && (
              <Button size="small" onClick={() => dispatch(selectAllSuggestions())}>
                Select All
              </Button>
            )}
          </Box>
        </Box>

        {/* Active filters display */}
        {(filters.suggestionCategories.length > 0 ||
          filters.suggestionPriorities.length > 0 ||
          filters.suggestionStatus.length > 0) && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {filters.suggestionCategories.map((cat) => (
              <Chip
                key={cat}
                label={cat}
                size="small"
                onDelete={() => handleCategoryToggle(cat)}
              />
            ))}
            {filters.suggestionPriorities.map((pri) => (
              <Chip
                key={pri}
                label={pri}
                size="small"
                color="primary"
                onDelete={() => handlePriorityToggle(pri)}
              />
            ))}
            {filters.suggestionStatus.map((status) => (
              <Chip
                key={status}
                label={status}
                size="small"
                color="secondary"
                onDelete={() => handleStatusToggle(status)}
              />
            ))}
          </Box>
        )}
      </Box>

      <Divider />

      <Box sx={{ flex: 1, overflow: 'auto', mt: 2 }}>
        {filteredSuggestions.length === 0 ? (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
            }}
          >
            <Typography color="text.secondary">
              No suggestions match your filters
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {filteredSuggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                isSelected={selectedIds.includes(suggestion.id)}
                isApplying={applyingIds.includes(suggestion.id)}
              />
            ))}
          </Box>
        )}
      </Box>

      {/* Filter Menu */}
      <Menu
        anchorEl={filterAnchor}
        open={Boolean(filterAnchor)}
        onClose={() => setFilterAnchor(null)}
      >
        <Box sx={{ p: 2, minWidth: 250 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Categories
          </Typography>
          {categories.map((category) => (
            <FormControlLabel
              key={category}
              control={
                <Checkbox
                  checked={filters.suggestionCategories.includes(category)}
                  onChange={() => handleCategoryToggle(category)}
                  size="small"
                />
              }
              label={category}
              sx={{ display: 'block' }}
            />
          ))}
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Priority
          </Typography>
          {priorities.map((priority) => (
            <FormControlLabel
              key={priority}
              control={
                <Checkbox
                  checked={filters.suggestionPriorities.includes(priority)}
                  onChange={() => handlePriorityToggle(priority)}
                  size="small"
                />
              }
              label={priority}
              sx={{ display: 'block' }}
            />
          ))}
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Status
          </Typography>
          {statuses.map((status) => (
            <FormControlLabel
              key={status}
              control={
                <Checkbox
                  checked={filters.suggestionStatus.includes(status)}
                  onChange={() => handleStatusToggle(status)}
                  size="small"
                />
              }
              label={status}
              sx={{ display: 'block' }}
            />
          ))}
        </Box>
      </Menu>

      {/* Sort Menu */}
      <Menu
        anchorEl={sortAnchor}
        open={Boolean(sortAnchor)}
        onClose={() => setSortAnchor(null)}
      >
        <MenuItem
          onClick={() => {
            dispatch(setSortBy('priority'));
            setSortAnchor(null);
          }}
          selected={sortBy === 'priority'}
        >
          Sort by Priority
        </MenuItem>
        <MenuItem
          onClick={() => {
            dispatch(setSortBy('impact'));
            setSortAnchor(null);
          }}
          selected={sortBy === 'impact'}
        >
          Sort by Impact
        </MenuItem>
        <MenuItem
          onClick={() => {
            dispatch(setSortBy('category'));
            setSortAnchor(null);
          }}
          selected={sortBy === 'category'}
        >
          Sort by Category
        </MenuItem>
        <Divider />
        <MenuItem
          onClick={() => {
            dispatch(setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'));
            setSortAnchor(null);
          }}
        >
          {sortOrder === 'asc' ? 'Descending' : 'Ascending'}
        </MenuItem>
      </Menu>
    </Paper>
  );
};

export default Suggestions;