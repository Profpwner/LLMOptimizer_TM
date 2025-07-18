import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  LinearProgress,
  Tooltip,
  useTheme,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat';
import { Metric } from '../../types';

interface MetricCardProps {
  metric: Metric;
  icon: string;
  showTarget: boolean;
  animated: boolean;
}

const MetricCard: React.FC<MetricCardProps> = ({ metric, icon, showTarget, animated }) => {
  const theme = useTheme();
  const [displayValue, setDisplayValue] = useState(animated ? 0 : metric.value);

  useEffect(() => {
    if (animated) {
      const duration = 1000; // 1 second animation
      const steps = 60;
      const increment = metric.value / steps;
      let current = 0;
      let step = 0;

      const timer = setInterval(() => {
        step++;
        current = Math.min(increment * step, metric.value);
        setDisplayValue(Math.round(current * 10) / 10);

        if (step >= steps) {
          clearInterval(timer);
          setDisplayValue(metric.value);
        }
      }, duration / steps);

      return () => clearInterval(timer);
    } else {
      setDisplayValue(metric.value);
    }
  }, [metric.value, animated]);

  const getTrendIcon = () => {
    switch (metric.trend) {
      case 'up':
        return <TrendingUpIcon fontSize="small" color="success" />;
      case 'down':
        return <TrendingDownIcon fontSize="small" color="error" />;
      default:
        return <TrendingFlatIcon fontSize="small" color="disabled" />;
    }
  };

  const getChangeColor = () => {
    if (metric.change > 0) return theme.palette.success.main;
    if (metric.change < 0) return theme.palette.error.main;
    return theme.palette.text.secondary;
  };

  const progressValue = metric.target
    ? Math.min((metric.value / metric.target) * 100, 100)
    : 0;

  const progressColor = progressValue >= 100
    ? 'success'
    : progressValue >= 75
    ? 'primary'
    : progressValue >= 50
    ? 'warning'
    : 'error';

  return (
    <Card
      sx={{
        height: '100%',
        transition: 'all 0.3s ease',
        '&:hover': {
          boxShadow: 3,
          transform: 'translateY(-2px)',
        },
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="h4" component="span">
            {icon}
          </Typography>
          {getTrendIcon()}
        </Box>

        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          {metric.name}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, mb: 1 }}>
          <Typography variant="h4" component="div">
            {displayValue}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {metric.unit}
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography
            variant="caption"
            sx={{ color: getChangeColor() }}
          >
            {metric.change > 0 ? '+' : ''}{metric.change} ({metric.changePercent}%)
          </Typography>
          <Typography variant="caption" color="text.secondary">
            from {metric.previousValue}
          </Typography>
        </Box>

        {showTarget && metric.target && (
          <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                Target
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {metric.target} {metric.unit}
              </Typography>
            </Box>
            <Tooltip title={`${progressValue.toFixed(1)}% of target`}>
              <LinearProgress
                variant="determinate"
                value={progressValue}
                color={progressColor as any}
                sx={{
                  height: 6,
                  borderRadius: 3,
                  bgcolor: theme.palette.action.hover,
                }}
              />
            </Tooltip>
          </Box>
        )}

        {metric.description && (
          <Tooltip title={metric.description}>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                display: 'block',
                mt: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {metric.description}
            </Typography>
          </Tooltip>
        )}
      </CardContent>
    </Card>
  );
};

export default MetricCard;