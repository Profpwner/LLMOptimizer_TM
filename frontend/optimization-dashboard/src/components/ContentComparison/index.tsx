import React, { useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
  Divider,
} from '@mui/material';
import { useAppSelector } from '../../hooks/useAppSelector';
import { useAppDispatch } from '../../hooks/useAppDispatch';
import { setViewMode } from '../../store/slices/dashboardSlice';
import DiffViewer from './DiffViewer';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import VisibilityIcon from '@mui/icons-material/Visibility';

const ContentComparison: React.FC = () => {
  const dispatch = useAppDispatch();
  const { results, viewMode } = useAppSelector((state) => state.dashboard);

  const comparison = results?.comparison;

  const stats = useMemo(() => {
    if (!comparison) return null;
    
    const stats = comparison.stats;
    const totalCharChange = stats.charactersAdded - stats.charactersRemoved;
    const totalWordChange = stats.wordsAdded - stats.wordsRemoved;
    
    return {
      ...stats,
      totalCharChange,
      totalWordChange,
      charChangePercent: comparison.original.length > 0
        ? Math.round((Math.abs(totalCharChange) / comparison.original.length) * 100)
        : 0,
    };
  }, [comparison]);

  if (!comparison) {
    return (
      <Paper sx={{ p: 3, height: '100%' }}>
        <Typography variant="h6">Content Comparison</Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 'calc(100% - 40px)',
          }}
        >
          <Typography color="text.secondary">No comparison data available</Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Content Comparison</Typography>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, value) => value && dispatch(setViewMode(value))}
            size="small"
          >
            <ToggleButton value="split">
              <CompareArrowsIcon sx={{ mr: 1 }} />
              Split View
            </ToggleButton>
            <ToggleButton value="unified">
              <VisibilityIcon sx={{ mr: 1 }} />
              Unified View
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {stats && (
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Chip
              label={`Characters: ${stats.totalCharChange > 0 ? '+' : ''}${stats.totalCharChange}`}
              color={stats.totalCharChange > 0 ? 'success' : 'error'}
              size="small"
              variant="outlined"
            />
            <Chip
              label={`Words: ${stats.totalWordChange > 0 ? '+' : ''}${stats.totalWordChange}`}
              color={stats.totalWordChange > 0 ? 'success' : 'error'}
              size="small"
              variant="outlined"
            />
            <Chip
              label={`Change: ${stats.charChangePercent}%`}
              size="small"
              variant="outlined"
            />
            <Chip
              label={`Added: ${stats.charactersAdded} chars`}
              color="success"
              size="small"
              variant="outlined"
            />
            <Chip
              label={`Removed: ${stats.charactersRemoved} chars`}
              color="error"
              size="small"
              variant="outlined"
            />
          </Box>
        )}
      </Box>

      <Divider sx={{ mb: 2 }} />

      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        <DiffViewer
          original={comparison.original}
          optimized={comparison.optimized}
          changes={comparison.changes}
          viewMode={viewMode}
        />
      </Box>
    </Paper>
  );
};

export default ContentComparison;