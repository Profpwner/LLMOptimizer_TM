import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Switch,
  FormControlLabel,
} from '@mui/material';
import { useAppSelector } from '../../hooks/useAppSelector';
import { useAppDispatch } from '../../hooks/useAppDispatch';
import { toggleShowTargets, toggleAnimations } from '../../store/slices/metricsSlice';
import MetricCard from './MetricCard';
import MetricsChart from './MetricsChart';

const ImpactMetrics: React.FC = () => {
  const dispatch = useAppDispatch();
  const { current: metrics, showTargets, animationsEnabled } = useAppSelector((state) => state.metrics);

  if (!metrics) {
    return (
      <Paper sx={{ p: 3, height: '100%' }}>
        <Typography variant="h6">Impact Metrics</Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 'calc(100% - 40px)',
          }}
        >
          <Typography color="text.secondary">No metrics data available</Typography>
        </Box>
      </Paper>
    );
  }

  const metricsList = [
    { key: 'visibility', metric: metrics.visibility, icon: '👁️' },
    { key: 'engagement', metric: metrics.engagement, icon: '💬' },
    { key: 'conversion', metric: metrics.conversion, icon: '🎯' },
    { key: 'reach', metric: metrics.reach, icon: '📡' },
    { key: 'performance', metric: metrics.performance, icon: '⚡' },
  ];

  return (
    <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Impact Metrics</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <FormControlLabel
            control={
              <Switch
                checked={showTargets}
                onChange={() => dispatch(toggleShowTargets())}
                size="small"
              />
            }
            label="Show Targets"
          />
          <FormControlLabel
            control={
              <Switch
                checked={animationsEnabled}
                onChange={() => dispatch(toggleAnimations())}
                size="small"
              />
            }
            label="Animations"
          />
        </Box>
      </Box>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {metricsList.map(({ key, metric, icon }) => (
          <Grid item xs={12} sm={6} md={4} lg={2.4} key={key}>
            <MetricCard
              metric={metric}
              icon={icon}
              showTarget={showTargets}
              animated={animationsEnabled}
            />
          </Grid>
        ))}
      </Grid>

      <Box sx={{ flex: 1, minHeight: 300 }}>
        <MetricsChart metrics={metricsList.map(m => m.metric)} />
      </Box>

      {metrics.custom && metrics.custom.length > 0 && (
        <>
          <Typography variant="subtitle1" sx={{ mt: 3, mb: 2 }}>
            Custom Metrics
          </Typography>
          <Grid container spacing={2}>
            {metrics.custom.map((metric) => (
              <Grid item xs={12} sm={6} md={4} key={metric.id}>
                <MetricCard
                  metric={metric}
                  icon="📊"
                  showTarget={showTargets}
                  animated={animationsEnabled}
                />
              </Grid>
            ))}
          </Grid>
        </>
      )}
    </Paper>
  );
};

export default ImpactMetrics;