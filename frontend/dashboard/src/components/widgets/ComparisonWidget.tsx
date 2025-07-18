import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  IconButton,
  useTheme,
  LinearProgress,
  Chip,
  Stack,
} from '@mui/material';
import {
  MoreVert as MoreVertIcon,
  Fullscreen as FullscreenIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { useAppDispatch } from '../../hooks/redux';
import { setFullscreenWidget } from '../../store/slices/dashboardSlice';

interface ComparisonWidgetProps {
  widgetId: string;
  config: {
    title?: string;
    items?: Array<{
      name: string;
      current: number;
      previous: number;
      target?: number;
      unit?: string;
    }>;
    showProgress?: boolean;
    showChange?: boolean;
    showTarget?: boolean;
  };
}

const ComparisonWidget: React.FC<ComparisonWidgetProps> = ({ widgetId, config }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();

  const handleFullscreen = () => {
    dispatch(setFullscreenWidget(widgetId));
  };

  const items = config.items || [
    { name: 'Revenue', current: 125000, previous: 100000, target: 150000, unit: '$' },
    { name: 'Users', current: 5420, previous: 4800, target: 6000 },
    { name: 'Conversion Rate', current: 3.2, previous: 2.8, target: 4.0, unit: '%' },
    { name: 'Avg. Order Value', current: 85, previous: 78, target: 100, unit: '$' },
  ];

  const formatValue = (value: number, unit?: string) => {
    if (unit === '$') {
      return `$${value.toLocaleString()}`;
    }
    if (unit === '%') {
      return `${value.toFixed(1)}%`;
    }
    return value.toLocaleString();
  };

  const calculateChange = (current: number, previous: number) => {
    return ((current - previous) / previous) * 100;
  };

  const calculateProgress = (current: number, target: number) => {
    return Math.min((current / target) * 100, 100);
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box
        className="widget-header"
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          pb: 0,
          cursor: 'move',
        }}
      >
        <Typography variant="h6">{config.title || 'Performance Comparison'}</Typography>
        <Box>
          <IconButton size="small" onClick={handleFullscreen}>
            <FullscreenIcon fontSize="small" />
          </IconButton>
          <IconButton size="small">
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <CardContent sx={{ flexGrow: 1 }}>
        <Stack spacing={3}>
          {items.map((item, index) => {
            const change = calculateChange(item.current, item.previous);
            const progress = item.target ? calculateProgress(item.current, item.target) : 0;
            const isPositive = change >= 0;

            return (
              <Box key={index}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="subtitle1" fontWeight="medium">
                    {item.name}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="h6" fontWeight="bold">
                      {formatValue(item.current, item.unit)}
                    </Typography>
                    {config.showChange !== false && (
                      <Chip
                        size="small"
                        icon={isPositive ? <TrendingUpIcon /> : <TrendingDownIcon />}
                        label={`${isPositive ? '+' : ''}${change.toFixed(1)}%`}
                        color={isPositive ? 'success' : 'error'}
                        sx={{ ml: 1 }}
                      />
                    )}
                  </Box>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                  <Typography variant="caption" color="textSecondary" sx={{ minWidth: 80 }}>
                    Previous: {formatValue(item.previous, item.unit)}
                  </Typography>
                  {config.showTarget !== false && item.target && (
                    <Typography variant="caption" color="textSecondary">
                      Target: {formatValue(item.target, item.unit)}
                    </Typography>
                  )}
                </Box>

                {config.showProgress !== false && item.target && (
                  <Box sx={{ position: 'relative' }}>
                    <LinearProgress
                      variant="determinate"
                      value={progress}
                      sx={{
                        height: 8,
                        borderRadius: 4,
                        backgroundColor: theme.palette.action.hover,
                        '& .MuiLinearProgress-bar': {
                          borderRadius: 4,
                          backgroundColor:
                            progress >= 100
                              ? theme.palette.success.main
                              : progress >= 75
                              ? theme.palette.warning.main
                              : theme.palette.primary.main,
                        },
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        position: 'absolute',
                        right: 0,
                        top: -20,
                        color: theme.palette.text.secondary,
                      }}
                    >
                      {progress.toFixed(0)}% of target
                    </Typography>
                  </Box>
                )}
              </Box>
            );
          })}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default ComparisonWidget;