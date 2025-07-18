import { DashboardLayout } from '../store/slices/dashboardSlice';
import { AnalyticsMetric, TimeSeriesData, HeatmapData } from '../store/slices/analyticsSlice';
import { PredictionData, TrendData, AnomalyData } from '../store/slices/predictionsSlice';

export const generateSampleLayout = (): DashboardLayout => ({
  id: 'default',
  name: 'Default Dashboard',
  widgets: [
    {
      id: 'kpi-1',
      type: 'kpi',
      title: 'Total Visibility Score',
      x: 0,
      y: 0,
      w: 3,
      h: 2,
      config: {
        metricId: 'visibility-score',
        title: 'Visibility Score',
        format: 'number',
        decimals: 1,
        showTrend: true,
        showChange: true,
      },
    },
    {
      id: 'kpi-2',
      type: 'kpi',
      title: 'Content Performance',
      x: 3,
      y: 0,
      w: 3,
      h: 2,
      config: {
        metricId: 'content-performance',
        title: 'Content Performance',
        format: 'percentage',
        decimals: 1,
        showTrend: true,
        showChange: true,
      },
    },
    {
      id: 'kpi-3',
      type: 'kpi',
      title: 'Engagement Rate',
      x: 6,
      y: 0,
      w: 3,
      h: 2,
      config: {
        metricId: 'engagement-rate',
        title: 'Engagement Rate',
        format: 'percentage',
        decimals: 2,
        showTrend: true,
        showChange: true,
      },
    },
    {
      id: 'kpi-4',
      type: 'kpi',
      title: 'AI Optimization Score',
      x: 9,
      y: 0,
      w: 3,
      h: 2,
      config: {
        metricId: 'ai-optimization',
        title: 'AI Optimization',
        format: 'percentage',
        decimals: 0,
        showTrend: true,
        showChange: true,
      },
    },
    {
      id: 'chart-1',
      type: 'chart',
      title: 'Visibility Trend',
      x: 0,
      y: 2,
      w: 6,
      h: 3,
      config: {
        title: 'Visibility Score Over Time',
        dataKey: 'visibility-trend',
        chartType: 'area',
        showGrid: true,
        showLegend: false,
        showTooltip: true,
      },
    },
    {
      id: 'prediction-1',
      type: 'prediction',
      title: 'Visibility Forecast',
      x: 6,
      y: 2,
      w: 6,
      h: 3,
      config: {
        title: 'Visibility Forecast',
        metric: 'visibility-score',
        showConfidenceInterval: true,
        showAnomalies: true,
        showTrend: true,
        timeframe: 'hour',
      },
    },
    {
      id: 'heatmap-1',
      type: 'heatmap',
      title: 'Content Performance Heatmap',
      x: 0,
      y: 5,
      w: 4,
      h: 3,
      config: {
        title: 'Content Performance by Day/Hour',
        xLabel: 'Hour of Day',
        yLabel: 'Day of Week',
        showValues: true,
        cellSize: 35,
      },
    },
    {
      id: 'funnel-1',
      type: 'funnel',
      title: 'User Journey',
      x: 4,
      y: 5,
      w: 4,
      h: 3,
      config: {
        title: 'Content Optimization Funnel',
        showPercentages: true,
        showValues: true,
        orientation: 'vertical',
      },
    },
    {
      id: 'comparison-1',
      type: 'comparison',
      title: 'Performance Metrics',
      x: 8,
      y: 5,
      w: 4,
      h: 3,
      config: {
        title: 'Key Performance Indicators',
        showProgress: true,
        showChange: true,
        showTarget: true,
      },
    },
    {
      id: '3d-network-1',
      type: '3d-network',
      title: 'Semantic Network',
      x: 0,
      y: 8,
      w: 12,
      h: 4,
      config: {
        title: 'Content Semantic Network',
        viewMode: '3d',
        showLabels: true,
        animationSpeed: 0.5,
      },
    },
  ],
});

export const generateSampleMetrics = (): AnalyticsMetric[] => [
  {
    id: 'visibility-score',
    name: 'Visibility Score',
    value: 87.5,
    change: 12.3,
    timestamp: new Date().toISOString(),
    unit: 'points',
  },
  {
    id: 'content-performance',
    name: 'Content Performance',
    value: 78.2,
    change: 5.7,
    timestamp: new Date().toISOString(),
    unit: '%',
  },
  {
    id: 'engagement-rate',
    name: 'Engagement Rate',
    value: 4.85,
    change: -2.1,
    timestamp: new Date().toISOString(),
    unit: '%',
  },
  {
    id: 'ai-optimization',
    name: 'AI Optimization Score',
    value: 92,
    change: 8.5,
    timestamp: new Date().toISOString(),
    unit: '%',
  },
];

export const generateTimeSeriesData = (): { [key: string]: TimeSeriesData[] } => {
  const now = Date.now();
  const data: { [key: string]: TimeSeriesData[] } = {
    'visibility-trend': [],
  };

  // Generate visibility trend data for the last 24 hours
  for (let i = 24; i >= 0; i--) {
    data['visibility-trend'].push({
      timestamp: new Date(now - i * 60 * 60 * 1000).toISOString(),
      value: 75 + Math.random() * 20 + (24 - i) * 0.5,
      label: 'Visibility Score',
    });
  }

  return data;
};

export const generateHeatmapData = (): HeatmapData[] => {
  const daysOfWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const hoursOfDay = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0'));
  const data: HeatmapData[] = [];

  daysOfWeek.forEach((day) => {
    hoursOfDay.forEach((hour) => {
      data.push({
        x: hour,
        y: day,
        value: Math.random() * 100,
      });
    });
  });

  return data;
};

export const generatePredictions = (): PredictionData[] => {
  const now = Date.now();
  const predictions: PredictionData[] = [];

  // Generate predictions for the next 6 hours
  for (let i = 0; i < 12; i++) {
    const baseValue = 85 + Math.random() * 10;
    const confidence = 0.95 - i * 0.05;
    const uncertainty = 5 + i * 2;

    predictions.push({
      id: `pred-${i}`,
      metric: 'visibility-score',
      timestamp: new Date(now + i * 30 * 60 * 1000).toISOString(),
      predicted: baseValue,
      actual: i < 3 ? baseValue + (Math.random() - 0.5) * 5 : undefined,
      confidence,
      lowerBound: baseValue - uncertainty,
      upperBound: baseValue + uncertainty,
    });
  }

  return predictions;
};

export const generateTrends = (): TrendData[] => [
  {
    metric: 'visibility-score',
    trend: 'increasing',
    changeRate: 12.5,
    confidence: 0.87,
  },
  {
    metric: 'engagement-rate',
    trend: 'stable',
    changeRate: 0.3,
    confidence: 0.92,
  },
];

export const generateAnomalies = (): AnomalyData[] => [
  {
    id: 'anomaly-1',
    metric: 'visibility-score',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    value: 65.3,
    severity: 'medium',
    description: 'Sudden drop in visibility score detected',
  },
  {
    id: 'anomaly-2',
    metric: 'engagement-rate',
    timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    value: 8.9,
    severity: 'low',
    description: 'Unusual spike in engagement rate',
  },
];