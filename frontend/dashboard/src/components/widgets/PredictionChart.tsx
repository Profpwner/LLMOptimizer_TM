import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  IconButton,
  useTheme,
  alpha,
  Chip,
  Stack,
  Alert,
} from '@mui/material';
import {
  MoreVert as MoreVertIcon,
  Fullscreen as FullscreenIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { format } from 'date-fns';
import { useAppSelector, useAppDispatch } from '../../hooks/redux';
import { setFullscreenWidget } from '../../store/slices/dashboardSlice';

interface PredictionChartProps {
  widgetId: string;
  config: {
    title?: string;
    metric?: string;
    showConfidenceInterval?: boolean;
    showAnomalies?: boolean;
    showTrend?: boolean;
    timeframe?: 'hour' | 'day' | 'week' | 'month';
  };
}

const PredictionChart: React.FC<PredictionChartProps> = ({ widgetId, config }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const predictions = useAppSelector((state) => state.predictions.predictions);
  const anomalies = useAppSelector((state) => state.predictions.anomalies);
  const trends = useAppSelector((state) => state.predictions.trends);

  const handleFullscreen = () => {
    dispatch(setFullscreenWidget(widgetId));
  };

  const chartData = useMemo(() => {
    const metricPredictions = predictions.filter(
      (p) => !config.metric || p.metric === config.metric
    );

    return metricPredictions.map((pred) => ({
      timestamp: format(new Date(pred.timestamp), 'HH:mm'),
      predicted: pred.predicted,
      actual: pred.actual,
      lowerBound: pred.lowerBound,
      upperBound: pred.upperBound,
      confidence: pred.confidence,
    }));
  }, [predictions, config.metric]);

  const currentTrend = useMemo(() => {
    if (!config.metric || !trends.length) return null;
    return trends.find((t) => t.metric === config.metric);
  }, [trends, config.metric]);

  const recentAnomalies = useMemo(() => {
    if (!config.metric || !anomalies.length) return [];
    return anomalies
      .filter((a) => a.metric === config.metric)
      .slice(0, 3);
  }, [anomalies, config.metric]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Box
          sx={{
            backgroundColor: theme.palette.background.paper,
            p: 2,
            borderRadius: 1,
            boxShadow: theme.shadows[4],
            border: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Typography variant="subtitle2" gutterBottom>
            {label}
          </Typography>
          <Stack spacing={1}>
            <Box>
              <Typography variant="caption" color="textSecondary">
                Predicted:
              </Typography>
              <Typography variant="body2" fontWeight="bold">
                {data.predicted?.toFixed(2)}
              </Typography>
            </Box>
            {data.actual !== undefined && (
              <Box>
                <Typography variant="caption" color="textSecondary">
                  Actual:
                </Typography>
                <Typography variant="body2" fontWeight="bold">
                  {data.actual.toFixed(2)}
                </Typography>
              </Box>
            )}
            <Box>
              <Typography variant="caption" color="textSecondary">
                Confidence:
              </Typography>
              <Typography variant="body2">
                {(data.confidence * 100).toFixed(0)}%
              </Typography>
            </Box>
          </Stack>
        </Box>
      );
    }
    return null;
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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6">
            {config.title || 'Visibility Forecast'}
          </Typography>
          {currentTrend && (
            <Chip
              size="small"
              icon={<TrendingUpIcon />}
              label={`${currentTrend.trend} (${currentTrend.changeRate > 0 ? '+' : ''}${currentTrend.changeRate.toFixed(1)}%)`}
              color={
                currentTrend.trend === 'increasing' ? 'success' :
                currentTrend.trend === 'decreasing' ? 'error' : 'default'
              }
            />
          )}
        </Box>
        <Box>
          <IconButton size="small" onClick={handleFullscreen}>
            <FullscreenIcon fontSize="small" />
          </IconButton>
          <IconButton size="small">
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        {config.showAnomalies !== false && recentAnomalies.length > 0 && (
          <Alert
            severity="warning"
            icon={<WarningIcon />}
            sx={{ mb: 2 }}
          >
            <Typography variant="subtitle2" gutterBottom>
              Recent Anomalies Detected
            </Typography>
            {recentAnomalies.map((anomaly, index) => (
              <Typography key={index} variant="caption" display="block">
                • {anomaly.description} ({format(new Date(anomaly.timestamp), 'HH:mm')})
              </Typography>
            ))}
          </Alert>
        )}
        
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={alpha(theme.palette.divider, 0.3)}
              />
              <XAxis
                dataKey="timestamp"
                tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              
              {/* Confidence interval */}
              {config.showConfidenceInterval !== false && (
                <Area
                  dataKey="upperBound"
                  stackId="1"
                  stroke="none"
                  fill={alpha(theme.palette.primary.light, 0.2)}
                  name="Upper bound"
                />
              )}
              
              {/* Prediction line */}
              <Line
                type="monotone"
                dataKey="predicted"
                stroke={theme.palette.primary.main}
                strokeWidth={3}
                dot={false}
                name="Predicted"
              />
              
              {/* Actual values line */}
              <Line
                type="monotone"
                dataKey="actual"
                stroke={theme.palette.success.main}
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={{ r: 4 }}
                name="Actual"
              />
              
              {/* Lower confidence bound */}
              {config.showConfidenceInterval !== false && (
                <Area
                  dataKey="lowerBound"
                  stackId="2"
                  stroke="none"
                  fill={alpha(theme.palette.primary.light, 0.2)}
                  name="Lower bound"
                />
              )}
              
              {/* Reference line for current time */}
              <ReferenceLine
                x={chartData[chartData.length - 1]?.timestamp}
                stroke={theme.palette.text.secondary}
                strokeDasharray="3 3"
                label="Now"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
            }}
          >
            <Typography color="textSecondary">
              No prediction data available
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default PredictionChart;