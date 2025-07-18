import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
  IconButton,
  Button,
  Checkbox,
  Collapse,
  LinearProgress,
  Tooltip,
  useTheme,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import BuildIcon from '@mui/icons-material/Build';
import InfoIcon from '@mui/icons-material/Info';
import { useAppDispatch } from '../../hooks/useAppSelector';
import { toggleSuggestionSelection, applySuggestionAsync } from '../../store/slices/suggestionsSlice';
import { Suggestion } from '../../types';

interface SuggestionCardProps {
  suggestion: Suggestion;
  isSelected: boolean;
  isApplying: boolean;
}

const SuggestionCard: React.FC<SuggestionCardProps> = ({ suggestion, isSelected, isApplying }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const [expanded, setExpanded] = useState(false);

  const handleApply = () => {
    // In a real app, you'd get the contentId from context or props
    const contentId = 'current-content-id';
    dispatch(applySuggestionAsync({ suggestionId: suggestion.id, contentId }));
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'error';
      case 'medium':
        return 'warning';
      case 'low':
        return 'info';
      default:
        return 'default';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'keyword':
        return '🔍';
      case 'structure':
        return '🏗️';
      case 'readability':
        return '📖';
      case 'technical':
        return '⚙️';
      case 'engagement':
        return '💡';
      default:
        return '📝';
    }
  };

  const getStatusIcon = () => {
    switch (suggestion.status) {
      case 'applied':
        return <CheckCircleIcon color="success" fontSize="small" />;
      case 'rejected':
        return <ErrorIcon color="error" fontSize="small" />;
      default:
        return null;
    }
  };

  return (
    <Card
      sx={{
        position: 'relative',
        transition: 'all 0.3s ease',
        opacity: suggestion.status === 'applied' ? 0.7 : 1,
        borderLeft: 4,
        borderLeftColor: `${getPriorityColor(suggestion.priority)}.main`,
        '&:hover': {
          boxShadow: 3,
          transform: 'translateY(-2px)',
        },
      }}
    >
      {isApplying && <LinearProgress sx={{ position: 'absolute', top: 0, left: 0, right: 0 }} />}
      
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <Checkbox
            checked={isSelected}
            onChange={() => dispatch(toggleSuggestionSelection(suggestion.id))}
            disabled={suggestion.status !== 'pending' || isApplying}
          />
          
          <Box sx={{ flex: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
                    {suggestion.title}
                  </Typography>
                  {getStatusIcon()}
                </Box>
                
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip
                    label={`${getCategoryIcon(suggestion.category)} ${suggestion.category}`}
                    size="small"
                    variant="outlined"
                  />
                  <Chip
                    label={suggestion.priority}
                    size="small"
                    color={getPriorityColor(suggestion.priority) as any}
                  />
                  <Chip
                    label={`Impact: ${suggestion.impact}%`}
                    size="small"
                    variant="outlined"
                    color="primary"
                  />
                  {suggestion.platform && (
                    <Chip
                      label={suggestion.platform}
                      size="small"
                      variant="outlined"
                    />
                  )}
                </Box>
              </Box>
              
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {suggestion.status === 'pending' && (
                  <Button
                    size="small"
                    variant="contained"
                    onClick={handleApply}
                    disabled={isApplying}
                    startIcon={
                      suggestion.implementation?.type === 'automatic' ? (
                        <AutoFixHighIcon />
                      ) : (
                        <BuildIcon />
                      )
                    }
                  >
                    {suggestion.implementation?.type === 'automatic' ? 'Auto Apply' : 'Apply'}
                  </Button>
                )}
                
                <IconButton
                  size="small"
                  onClick={() => setExpanded(!expanded)}
                >
                  {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>
            </Box>
            
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {suggestion.description}
            </Typography>
            
            <Collapse in={expanded}>
              <Box sx={{ mt: 2, p: 2, bgcolor: theme.palette.action.hover, borderRadius: 1 }}>
                {suggestion.implementation && (
                  <>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <InfoIcon fontSize="small" color="primary" />
                      <Typography variant="subtitle2">
                        Implementation Details
                      </Typography>
                    </Box>
                    
                    {suggestion.implementation.code && (
                      <Box
                        sx={{
                          mt: 1,
                          p: 2,
                          bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.100',
                          borderRadius: 1,
                          fontFamily: 'monospace',
                          fontSize: '0.875rem',
                          overflow: 'auto',
                        }}
                      >
                        <pre style={{ margin: 0 }}>{suggestion.implementation.code}</pre>
                      </Box>
                    )}
                    
                    {suggestion.implementation.instructions && (
                      <Typography variant="body2" sx={{ mt: 1 }}>
                        {suggestion.implementation.instructions}
                      </Typography>
                    )}
                  </>
                )}
              </Box>
            </Collapse>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default SuggestionCard;