import React from 'react';
import {
  Box,
  Typography,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Button,
  Divider,
  Stack,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { ContentType, ExperienceLevel } from '../../types';

interface TemplateFiltersProps {
  filters: any;
  filterOptions: {
    categories: ContentType[];
    industries: string[];
    tags: string[];
  };
  onUpdateFilter: (filter: any) => void;
  onResetFilters: () => void;
  onClose: () => void;
}

export const TemplateFilters: React.FC<TemplateFiltersProps> = ({
  filters,
  filterOptions,
  onUpdateFilter,
  onResetFilters,
  onClose,
}) => {
  const activeFilterCount = Object.values(filters).filter(v => v && v !== 'popularity').length;

  return (
    <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h6">Filters</Typography>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Active Filters */}
      {activeFilterCount > 0 && (
        <Box mb={2}>
          <Typography variant="subtitle2" gutterBottom>
            Active Filters ({activeFilterCount})
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {filters.category && (
              <Chip
                label={`Category: ${filters.category}`}
                onDelete={() => onUpdateFilter({ category: null })}
                size="small"
              />
            )}
            {filters.industry && (
              <Chip
                label={`Industry: ${filters.industry}`}
                onDelete={() => onUpdateFilter({ industry: null })}
                size="small"
              />
            )}
          </Stack>
        </Box>
      )}

      <Divider sx={{ mb: 3 }} />

      {/* Filter Options */}
      <Box sx={{ flex: 1, overflowY: 'auto' }}>
        {/* Industry Filter */}
        <FormControl fullWidth sx={{ mb: 3 }}>
          <InputLabel>Industry</InputLabel>
          <Select
            value={filters.industry || ''}
            onChange={(e) => onUpdateFilter({ industry: e.target.value || null })}
            label="Industry"
          >
            <MenuItem value="">All Industries</MenuItem>
            {filterOptions.industries.map((industry) => (
              <MenuItem key={industry} value={industry}>
                {industry}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Difficulty Filter */}
        <FormControl component="fieldset" sx={{ mb: 3 }}>
          <FormLabel component="legend">Difficulty Level</FormLabel>
          <RadioGroup
            value={filters.difficulty || 'all'}
            onChange={(e) => onUpdateFilter({ 
              difficulty: e.target.value === 'all' ? null : e.target.value 
            })}
          >
            <FormControlLabel value="all" control={<Radio />} label="All Levels" />
            <FormControlLabel 
              value={ExperienceLevel.BEGINNER} 
              control={<Radio />} 
              label="Beginner" 
            />
            <FormControlLabel 
              value={ExperienceLevel.INTERMEDIATE} 
              control={<Radio />} 
              label="Intermediate" 
            />
            <FormControlLabel 
              value={ExperienceLevel.ADVANCED} 
              control={<Radio />} 
              label="Advanced" 
            />
          </RadioGroup>
        </FormControl>

        {/* Sort By */}
        <FormControl component="fieldset" sx={{ mb: 3 }}>
          <FormLabel component="legend">Sort By</FormLabel>
          <RadioGroup
            value={filters.sortBy}
            onChange={(e) => onUpdateFilter({ sortBy: e.target.value })}
          >
            <FormControlLabel value="popularity" control={<Radio />} label="Most Popular" />
            <FormControlLabel value="name" control={<Radio />} label="Name (A-Z)" />
            <FormControlLabel value="difficulty" control={<Radio />} label="Difficulty" />
          </RadioGroup>
        </FormControl>

        {/* Tags */}
        {filterOptions.tags.length > 0 && (
          <Box mb={3}>
            <Typography variant="subtitle2" gutterBottom>
              Tags
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {filterOptions.tags.slice(0, 10).map((tag) => (
                <Chip
                  key={tag}
                  label={tag}
                  onClick={() => {
                    const currentTags = filters.tags || [];
                    const newTags = currentTags.includes(tag)
                      ? currentTags.filter((t: string) => t !== tag)
                      : [...currentTags, tag];
                    onUpdateFilter({ tags: newTags });
                  }}
                  color={filters.tags?.includes(tag) ? 'primary' : 'default'}
                  variant={filters.tags?.includes(tag) ? 'filled' : 'outlined'}
                  size="small"
                />
              ))}
            </Stack>
          </Box>
        )}
      </Box>

      {/* Actions */}
      <Box>
        <Divider sx={{ mb: 2 }} />
        <Stack direction="row" spacing={2}>
          <Button
            fullWidth
            variant="outlined"
            onClick={onResetFilters}
            disabled={activeFilterCount === 0}
          >
            Clear All
          </Button>
          <Button fullWidth variant="contained" onClick={onClose}>
            Apply Filters
          </Button>
        </Stack>
      </Box>
    </Box>
  );
};