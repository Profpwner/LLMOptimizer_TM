import React from 'react';
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
import { useAppDispatch } from '../../hooks/redux';
import { setFullscreenWidget } from '../../store/slices/dashboardSlice';

interface FunnelChartProps {
  widgetId: string;
  config: {
    title?: string;
    data?: Array<{
      name: string;
      value: number;
      color?: string;
    }>;
    showPercentages?: boolean;
    showValues?: boolean;
    orientation?: 'vertical' | 'horizontal';
  };
}

const FunnelChart: React.FC<FunnelChartProps> = ({ widgetId, config }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();

  const handleFullscreen = () => {
    dispatch(setFullscreenWidget(widgetId));
  };

  const data = config.data || [
    { name: 'Visitors', value: 10000 },
    { name: 'Signups', value: 6500 },
    { name: 'Active Users', value: 4000 },
    { name: 'Paid Users', value: 2000 },
    { name: 'Premium Users', value: 500 },
  ];

  const maxValue = Math.max(...data.map((d) => d.value));
  const isVertical = config.orientation !== 'horizontal';

  const defaultColors = [
    theme.palette.primary.main,
    theme.palette.secondary.main,
    theme.palette.success.main,
    theme.palette.warning.main,
    theme.palette.info.main,
  ];

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
        <Typography variant="h6">{config.title || 'Funnel Chart'}</Typography>
        <Box>
          <IconButton size="small" onClick={handleFullscreen}>
            <FullscreenIcon fontSize="small" />
          </IconButton>
          <IconButton size="small">
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Box
          sx={{
            width: '100%',
            maxWidth: isVertical ? 400 : '100%',
            display: 'flex',
            flexDirection: isVertical ? 'column' : 'row',
            gap: 2,
            alignItems: 'center',
          }}
        >
          {data.map((item, index) => {
            const widthPercent = (item.value / maxValue) * 100;
            const color = item.color || defaultColors[index % defaultColors.length];
            const conversionRate = index > 0 
              ? ((item.value / data[index - 1].value) * 100).toFixed(1)
              : '100';

            return (
              <Box
                key={index}
                sx={{
                  width: isVertical ? `${widthPercent}%` : '100%',
                  height: isVertical ? 60 : `${widthPercent}%`,
                  minWidth: isVertical ? undefined : 100,
                  minHeight: isVertical ? undefined : 40,
                  display: 'flex',
                  flexDirection: isVertical ? 'column' : 'row',
                  alignItems: 'center',
                  position: 'relative',
                }}
              >
                <Box
                  sx={{
                    width: '100%',
                    height: '100%',
                    backgroundColor: alpha(color, 0.8),
                    clipPath: isVertical
                      ? `polygon(${10 + index * 5}% 0%, ${90 - index * 5}% 0%, ${95 - index * 5}% 100%, ${5 + index * 5}% 100%)`
                      : 'none',
                    borderRadius: isVertical ? 0 : theme.shape.borderRadius,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    transition: 'all 0.3s ease',
                    cursor: 'pointer',
                    '&:hover': {
                      backgroundColor: color,
                      transform: 'scale(1.02)',
                    },
                  }}
                >
                  <Box sx={{ textAlign: 'center', p: 2 }}>
                    <Typography
                      variant="subtitle2"
                      sx={{
                        color: theme.palette.getContrastText(color),
                        fontWeight: 'bold',
                      }}
                    >
                      {item.name}
                    </Typography>
                    {config.showValues !== false && (
                      <Typography
                        variant="h6"
                        sx={{
                          color: theme.palette.getContrastText(color),
                        }}
                      >
                        {item.value.toLocaleString()}
                      </Typography>
                    )}
                    {config.showPercentages !== false && index > 0 && (
                      <Typography
                        variant="caption"
                        sx={{
                          color: theme.palette.getContrastText(color),
                          opacity: 0.9,
                        }}
                      >
                        {conversionRate}% conversion
                      </Typography>
                    )}
                  </Box>
                </Box>
                {index < data.length - 1 && isVertical && (
                  <Box
                    sx={{
                      position: 'absolute',
                      bottom: -16,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      zIndex: 1,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        backgroundColor: theme.palette.background.paper,
                        px: 1,
                        py: 0.5,
                        borderRadius: 1,
                        border: `1px solid ${theme.palette.divider}`,
                      }}
                    >
                      {conversionRate}%
                    </Typography>
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>
      </CardContent>
    </Card>
  );
};

export default FunnelChart;