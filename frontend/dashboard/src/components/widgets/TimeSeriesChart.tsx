import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  IconButton,
  useTheme,
  alpha,
} from '@mui/material';
import {
  MoreVert as MoreVertIcon,
  Fullscreen as FullscreenIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
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

interface TimeSeriesChartProps {
  widgetId: string;
  config: {
    title?: string;
    dataKey?: string;
    chartType?: 'line' | 'area' | 'bar';
    showGrid?: boolean;
    showLegend?: boolean;
    showTooltip?: boolean;
    yAxisDomain?: [number | 'auto', number | 'auto'];
    referenceLines?: Array<{
      y: number;
      label: string;
      color: string;
    }>;
    colors?: string[];
  };
}

const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({ widgetId, config }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const timeSeriesData = useAppSelector((state) => state.analytics.timeSeriesData);

  const data = useMemo(() => {
    if (!config.dataKey || !timeSeriesData[config.dataKey]) return [];
    return timeSeriesData[config.dataKey].map((item) => ({
      ...item,
      timestamp: format(new Date(item.timestamp), 'HH:mm:ss'),
    }));
  }, [timeSeriesData, config.dataKey]);

  const handleFullscreen = () => {
    dispatch(setFullscreenWidget(widgetId));
  };

  const chartColors = config.colors || [
    theme.palette.primary.main,
    theme.palette.secondary.main,
    theme.palette.success.main,
    theme.palette.warning.main,
  ];

  const renderChart = () => {
    const commonProps = {
      data,
      margin: { top: 5, right: 30, left: 20, bottom: 5 },
    };

    const axisStyle = {
      fontSize: 12,
      fill: theme.palette.text.secondary,
    };

    const gridStyle = {
      stroke: alpha(theme.palette.divider, 0.3),
      strokeDasharray: '3 3',
    };

    switch (config.chartType) {
      case 'area':
        return (
          <AreaChart {...commonProps}>
            {config.showGrid !== false && <CartesianGrid {...gridStyle} />}
            <XAxis dataKey="timestamp" tick={axisStyle} />
            <YAxis tick={axisStyle} domain={config.yAxisDomain} />
            {config.showTooltip !== false && (
              <Tooltip
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              />
            )}
            {config.showLegend && <Legend />}
            <Area
              type="monotone"
              dataKey="value"
              stroke={chartColors[0]}
              fill={alpha(chartColors[0], 0.3)}
              strokeWidth={2}
            />
            {config.referenceLines?.map((line, index) => (
              <ReferenceLine
                key={index}
                y={line.y}
                label={line.label}
                stroke={line.color}
                strokeDasharray="5 5"
              />
            ))}
          </AreaChart>
        );

      case 'bar':
        return (
          <BarChart {...commonProps}>
            {config.showGrid !== false && <CartesianGrid {...gridStyle} />}
            <XAxis dataKey="timestamp" tick={axisStyle} />
            <YAxis tick={axisStyle} domain={config.yAxisDomain} />
            {config.showTooltip !== false && (
              <Tooltip
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              />
            )}
            {config.showLegend && <Legend />}
            <Bar dataKey="value" fill={chartColors[0]} radius={[4, 4, 0, 0]} />
            {config.referenceLines?.map((line, index) => (
              <ReferenceLine
                key={index}
                y={line.y}
                label={line.label}
                stroke={line.color}
                strokeDasharray="5 5"
              />
            ))}
          </BarChart>
        );

      case 'line':
      default:
        return (
          <LineChart {...commonProps}>
            {config.showGrid !== false && <CartesianGrid {...gridStyle} />}
            <XAxis dataKey="timestamp" tick={axisStyle} />
            <YAxis tick={axisStyle} domain={config.yAxisDomain} />
            {config.showTooltip !== false && (
              <Tooltip
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              />
            )}
            {config.showLegend && <Legend />}
            <Line
              type="monotone"
              dataKey="value"
              stroke={chartColors[0]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
            />
            {config.referenceLines?.map((line, index) => (
              <ReferenceLine
                key={index}
                y={line.y}
                label={line.label}
                stroke={line.color}
                strokeDasharray="5 5"
              />
            ))}
          </LineChart>
        );
    }
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
        <Typography variant="h6">
          {config.title || 'Time Series Chart'}
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
      <CardContent sx={{ flexGrow: 1, p: 2 }}>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            {renderChart()}
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
              No data available
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default TimeSeriesChart;