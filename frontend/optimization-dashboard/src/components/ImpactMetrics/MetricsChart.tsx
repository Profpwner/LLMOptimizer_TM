import React, { useMemo } from 'react';
import { Box, useTheme } from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { useAppSelector } from '../../hooks/useAppSelector';
import { Metric } from '../../types';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface MetricsChartProps {
  metrics: Metric[];
}

const MetricsChart: React.FC<MetricsChartProps> = ({ metrics }) => {
  const theme = useTheme();
  const { history, timeframe } = useAppSelector((state) => state.metrics);

  // Filter history based on timeframe
  const filteredHistory = useMemo(() => {
    const now = new Date();
    const cutoff = new Date();
    
    switch (timeframe) {
      case '1h':
        cutoff.setHours(now.getHours() - 1);
        break;
      case '24h':
        cutoff.setDate(now.getDate() - 1);
        break;
      case '7d':
        cutoff.setDate(now.getDate() - 7);
        break;
      case '30d':
        cutoff.setDate(now.getDate() - 30);
        break;
    }

    return history.filter(h => new Date(h.timestamp) >= cutoff);
  }, [history, timeframe]);

  const chartData = useMemo(() => {
    const labels = filteredHistory.map(h => {
      const date = new Date(h.timestamp);
      if (timeframe === '1h') {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (timeframe === '24h') {
        return date.toLocaleTimeString([], { hour: '2-digit' });
      } else {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }
    });

    const datasets = [
      {
        label: 'Visibility',
        data: filteredHistory.map(h => h.metrics.visibility.value),
        borderColor: theme.palette.primary.main,
        backgroundColor: theme.palette.primary.main + '20',
        tension: 0.4,
      },
      {
        label: 'Engagement',
        data: filteredHistory.map(h => h.metrics.engagement.value),
        borderColor: theme.palette.secondary.main,
        backgroundColor: theme.palette.secondary.main + '20',
        tension: 0.4,
      },
      {
        label: 'Conversion',
        data: filteredHistory.map(h => h.metrics.conversion.value),
        borderColor: theme.palette.success.main,
        backgroundColor: theme.palette.success.main + '20',
        tension: 0.4,
      },
      {
        label: 'Reach',
        data: filteredHistory.map(h => h.metrics.reach.value),
        borderColor: theme.palette.warning.main,
        backgroundColor: theme.palette.warning.main + '20',
        tension: 0.4,
      },
      {
        label: 'Performance',
        data: filteredHistory.map(h => h.metrics.performance.value),
        borderColor: theme.palette.info.main,
        backgroundColor: theme.palette.info.main + '20',
        tension: 0.4,
      },
    ];

    return { labels, datasets };
  }, [filteredHistory, theme, timeframe]);

  const chartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        mode: 'index',
        intersect: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          callback: (value) => `${value}%`,
        },
      },
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false,
    },
  };

  if (filteredHistory.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
        }}
      >
        No historical data available for the selected timeframe
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%' }}>
      <Line data={chartData} options={chartOptions} />
    </Box>
  );
};

export default MetricsChart;