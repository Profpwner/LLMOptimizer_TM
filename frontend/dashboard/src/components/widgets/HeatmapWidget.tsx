import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  IconButton,
  useTheme,
  Tooltip,
} from '@mui/material';
import {
  MoreVert as MoreVertIcon,
  Fullscreen as FullscreenIcon,
} from '@mui/icons-material';
import { useAppSelector, useAppDispatch } from '../../hooks/redux';
import { setFullscreenWidget } from '../../store/slices/dashboardSlice';

interface HeatmapWidgetProps {
  widgetId: string;
  config: {
    title?: string;
    xLabel?: string;
    yLabel?: string;
    colorScale?: string[];
    showValues?: boolean;
    cellSize?: number;
  };
}

const HeatmapWidget: React.FC<HeatmapWidgetProps> = ({ widgetId, config }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const heatmapData = useAppSelector((state) => state.analytics.heatmapData);

  const { minValue, maxValue, xLabels, yLabels, matrix } = useMemo(() => {
    if (!heatmapData || heatmapData.length === 0) {
      return { minValue: 0, maxValue: 1, xLabels: [], yLabels: [], matrix: [] };
    }

    const xLabels = Array.from(new Set(heatmapData.map((d) => d.x)));
    const yLabels = Array.from(new Set(heatmapData.map((d) => d.y)));
    const values = heatmapData.map((d) => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);

    const matrix: (number | null)[][] = [];
    for (let y = 0; y < yLabels.length; y++) {
      matrix[y] = [];
      for (let x = 0; x < xLabels.length; x++) {
        const cell = heatmapData.find(
          (d) => d.x === xLabels[x] && d.y === yLabels[y]
        );
        matrix[y][x] = cell ? cell.value : null;
      }
    }

    return { minValue, maxValue, xLabels, yLabels, matrix };
  }, [heatmapData]);

  const handleFullscreen = () => {
    dispatch(setFullscreenWidget(widgetId));
  };

  const getColor = (value: number | null) => {
    if (value === null) return theme.palette.action.disabledBackground;

    const colorScale = config.colorScale || [
      theme.palette.primary.light,
      theme.palette.primary.main,
      theme.palette.primary.dark,
    ];

    const normalized = (value - minValue) / (maxValue - minValue);
    const index = Math.floor(normalized * (colorScale.length - 1));
    return colorScale[Math.min(index, colorScale.length - 1)];
  };

  const cellSize = config.cellSize || 40;

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
        <Typography variant="h6">{config.title || 'Heatmap'}</Typography>
        <Box>
          <IconButton size="small" onClick={handleFullscreen}>
            <FullscreenIcon fontSize="small" />
          </IconButton>
          <IconButton size="small">
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <CardContent sx={{ flexGrow: 1, overflow: 'auto' }}>
        {matrix.length > 0 ? (
          <Box sx={{ display: 'inline-block' }}>
            {/* Y-axis label */}
            {config.yLabel && (
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    writingMode: 'vertical-rl',
                    transform: 'rotate(180deg)',
                    mr: 2,
                  }}
                >
                  {config.yLabel}
                </Typography>
              </Box>
            )}

            <Box sx={{ display: 'flex' }}>
              {/* Y-axis labels */}
              <Box sx={{ mr: 1 }}>
                {yLabels.map((label, i) => (
                  <Box
                    key={i}
                    sx={{
                      height: cellSize,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      pr: 1,
                    }}
                  >
                    <Typography variant="caption" noWrap>
                      {label}
                    </Typography>
                  </Box>
                ))}
              </Box>

              {/* Heatmap grid */}
              <Box>
                {/* X-axis labels */}
                <Box sx={{ display: 'flex', mb: 1 }}>
                  {xLabels.map((label, i) => (
                    <Box
                      key={i}
                      sx={{
                        width: cellSize,
                        textAlign: 'center',
                        overflow: 'hidden',
                      }}
                    >
                      <Typography
                        variant="caption"
                        noWrap
                        sx={{
                          transform: 'rotate(-45deg)',
                          transformOrigin: 'center',
                          display: 'block',
                        }}
                      >
                        {label}
                      </Typography>
                    </Box>
                  ))}
                </Box>

                {/* Cells */}
                {matrix.map((row, y) => (
                  <Box key={y} sx={{ display: 'flex' }}>
                    {row.map((value, x) => (
                      <Tooltip
                        key={x}
                        title={`${xLabels[x]}, ${yLabels[y]}: ${
                          value !== null ? value.toFixed(2) : 'N/A'
                        }`}
                      >
                        <Box
                          sx={{
                            width: cellSize,
                            height: cellSize,
                            backgroundColor: getColor(value),
                            border: `1px solid ${theme.palette.divider}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer',
                            transition: 'transform 0.2s',
                            '&:hover': {
                              transform: 'scale(1.1)',
                              zIndex: 1,
                              boxShadow: theme.shadows[4],
                            },
                          }}
                        >
                          {config.showValues && value !== null && (
                            <Typography
                              variant="caption"
                              sx={{
                                color: theme.palette.getContrastText(
                                  getColor(value)
                                ),
                                fontWeight: 'bold',
                              }}
                            >
                              {value.toFixed(0)}
                            </Typography>
                          )}
                        </Box>
                      </Tooltip>
                    ))}
                  </Box>
                ))}
              </Box>
            </Box>

            {/* X-axis label */}
            {config.xLabel && (
              <Box sx={{ textAlign: 'center', mt: 2 }}>
                <Typography variant="caption">{config.xLabel}</Typography>
              </Box>
            )}
          </Box>
        ) : (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
            }}
          >
            <Typography color="textSecondary">No data available</Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default HeatmapWidget;