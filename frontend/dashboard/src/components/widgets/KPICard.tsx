import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  IconButton,
  Skeleton,
  useTheme,
  alpha,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  TrendingFlat as TrendingFlatIcon,
  MoreVert as MoreVertIcon,
  Fullscreen as FullscreenIcon,
} from '@mui/icons-material';
import { useAppSelector, useAppDispatch } from '../../hooks/redux';
import { setFullscreenWidget } from '../../store/slices/dashboardSlice';

interface KPICardProps {
  widgetId: string;
  config: {
    metricId?: string;
    title?: string;
    format?: 'number' | 'percentage' | 'currency';
    decimals?: number;
    showTrend?: boolean;
    showChange?: boolean;
  };
}

const KPICard: React.FC<KPICardProps> = ({ widgetId, config }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const metrics = useAppSelector((state) => state.analytics.metrics);
  const loading = useAppSelector((state) => state.analytics.loading);

  const metric = useMemo(() => {
    if (!config.metricId) return null;
    return metrics.find((m) => m.id === config.metricId);
  }, [metrics, config.metricId]);

  const formatValue = (value: number) => {
    const decimals = config.decimals ?? 2;
    switch (config.format) {
      case 'percentage':
        return `${value.toFixed(decimals)}%`;
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        }).format(value);
      default:
        return new Intl.NumberFormat('en-US', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        }).format(value);
    }
  };

  const getTrendIcon = (change: number) => {
    if (change > 0) return <TrendingUpIcon />;
    if (change < 0) return <TrendingDownIcon />;
    return <TrendingFlatIcon />;
  };

  const getTrendColor = (change: number) => {
    if (change > 0) return theme.palette.success.main;
    if (change < 0) return theme.palette.error.main;
    return theme.palette.text.secondary;
  };

  const handleFullscreen = () => {
    dispatch(setFullscreenWidget(widgetId));
  };

  if (loading && !metric) {
    return (
      <Card sx={{ height: '100%' }}>
        <CardContent>
          <Skeleton variant="text" width="60%" height={32} />
          <Skeleton variant="text" width="80%" height={48} />
          <Skeleton variant="text" width="40%" height={24} />
        </CardContent>
      </Card>
    );
  }

  if (!metric) {
    return (
      <Card sx={{ height: '100%' }}>
        <CardContent>
          <Typography color="textSecondary">
            No metric configured
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: theme.palette.mode === 'dark'
          ? `linear-gradient(135deg, ${alpha(theme.palette.primary.dark, 0.1)} 0%, ${alpha(
              theme.palette.background.paper,
              0.9
            )} 100%)`
          : undefined,
      }}
    >
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
        <Typography variant="subtitle1" color="textSecondary">
          {config.title || metric.name}
        </Typography>
        <Box>
          <IconButton size="small" onClick={handleFullscreen}>
            <FullscreenIcon fontSize="small" />
          </IconButton>
          <IconButton size="small">
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <Typography
          variant="h3"
          component="div"
          sx={{
            fontWeight: 'bold',
            color: theme.palette.text.primary,
            mb: 1,
          }}
        >
          {formatValue(metric.value)}
        </Typography>
        {metric.unit && (
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            {metric.unit}
          </Typography>
        )}
        {config.showTrend !== false && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ color: getTrendColor(metric.change) }}>
              {getTrendIcon(metric.change)}
            </Box>
            {config.showChange !== false && (
              <Typography
                variant="body2"
                sx={{
                  color: getTrendColor(metric.change),
                  fontWeight: 'medium',
                }}
              >
                {metric.change > 0 ? '+' : ''}{metric.change.toFixed(1)}%
              </Typography>
            )}
            <Typography variant="body2" color="textSecondary">
              vs last period
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default KPICard;