import React from 'react';
import { Box, Paper, Typography, Tooltip, useTheme } from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip as ChartTooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { useAppSelector } from '../../hooks/useAppSelector';
import { Platform } from '../../types';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  ChartTooltip,
  Legend
);

const VisibilityScore: React.FC = () => {
  const theme = useTheme();
  const { data: visibilityData } = useAppSelector((state) => state.visibility);
  const { selectedPlatform } = useAppSelector((state) => state.dashboard);

  if (!visibilityData) {
    return (
      <Paper sx={{ p: 3, height: '100%' }}>
        <Typography variant="h6">Visibility Score</Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 'calc(100% - 40px)',
          }}
        >
          <Typography color="text.secondary">No data available</Typography>
        </Box>
      </Paper>
    );
  }

  // Filter platforms based on selection
  const displayPlatforms = selectedPlatform === 'all'
    ? visibilityData.platforms
    : visibilityData.platforms.filter(p => p.platform === selectedPlatform);

  // Prepare chart data
  const chartData = {
    labels: displayPlatforms.map(p => p.platform),
    datasets: [
      {
        label: 'Current Score',
        data: displayPlatforms.map(p => p.score),
        backgroundColor: displayPlatforms.map(p => {
          if (p.score >= 80) return theme.palette.success.main;
          if (p.score >= 60) return theme.palette.warning.main;
          return theme.palette.error.main;
        }),
        borderColor: displayPlatforms.map(p => {
          if (p.score >= 80) return theme.palette.success.dark;
          if (p.score >= 60) return theme.palette.warning.dark;
          return theme.palette.error.dark;
        }),
        borderWidth: 2,
        borderRadius: 8,
      },
    ],
  };

  const chartOptions: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const platform = displayPlatforms[context.dataIndex];
            return [
              `Score: ${platform.score}%`,
              `Keywords: ${platform.details.keywords}%`,
              `Structure: ${platform.details.structure}%`,
              `Readability: ${platform.details.readability}%`,
              `Engagement: ${platform.details.engagement}%`,
            ];
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        ticks: {
          callback: (value) => `${value}%`,
        },
      },
    },
    animation: {
      duration: 1000,
      easing: 'easeInOutQuart',
    },
  };

  const getTrendIcon = (change: number) => {
    if (change > 0) return <TrendingUpIcon color="success" fontSize="small" />;
    if (change < 0) return <TrendingDownIcon color="error" fontSize="small" />;
    return <TrendingFlatIcon color="disabled" fontSize="small" />;
  };

  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Visibility Score
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h3" component="div" color="primary">
            {visibilityData.overall}%
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Overall Score
          </Typography>
        </Box>
      </Box>

      <Box sx={{ height: 300, mb: 3 }}>
        <Bar data={chartData} options={chartOptions} />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2 }}>
        {displayPlatforms.map((platform) => (
          <Box
            key={platform.platform}
            sx={{
              p: 2,
              border: 1,
              borderColor: 'divider',
              borderRadius: 1,
              transition: 'all 0.3s ease',
              '&:hover': {
                boxShadow: 2,
                transform: 'translateY(-2px)',
              },
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle2">{platform.platform}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {getTrendIcon(platform.change)}
                <Typography
                  variant="caption"
                  color={platform.change > 0 ? 'success.main' : platform.change < 0 ? 'error.main' : 'text.secondary'}
                >
                  {platform.change > 0 ? '+' : ''}{platform.change}%
                </Typography>
              </Box>
            </Box>
            <Tooltip
              title={
                <Box>
                  <Typography variant="caption">Keywords: {platform.details.keywords}%</Typography><br />
                  <Typography variant="caption">Structure: {platform.details.structure}%</Typography><br />
                  <Typography variant="caption">Readability: {platform.details.readability}%</Typography><br />
                  <Typography variant="caption">Engagement: {platform.details.engagement}%</Typography>
                </Box>
              }
            >
              <Box>
                <Typography variant="h4" component="div">
                  {platform.score}%
                </Typography>
                <Box
                  sx={{
                    width: '100%',
                    height: 4,
                    bgcolor: 'grey.300',
                    borderRadius: 2,
                    overflow: 'hidden',
                    mt: 1,
                  }}
                >
                  <Box
                    sx={{
                      width: `${platform.score}%`,
                      height: '100%',
                      bgcolor: platform.score >= 80 ? 'success.main' : platform.score >= 60 ? 'warning.main' : 'error.main',
                      transition: 'width 1s ease-in-out',
                    }}
                  />
                </Box>
              </Box>
            </Tooltip>
          </Box>
        ))}
      </Box>
    </Paper>
  );
};

export default VisibilityScore;