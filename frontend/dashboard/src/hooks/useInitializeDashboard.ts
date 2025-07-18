import { useEffect } from 'react';
import { useAppDispatch } from './redux';
import { setCurrentLayout } from '../store/slices/dashboardSlice';
import { setMetrics, setTimeSeriesData, appendTimeSeriesData, setHeatmapData } from '../store/slices/analyticsSlice';
import { setPredictions, setTrends, setAnomalies } from '../store/slices/predictionsSlice';
import {
  generateSampleLayout,
  generateSampleMetrics,
  generateTimeSeriesData,
  generateHeatmapData,
  generatePredictions,
  generateTrends,
  generateAnomalies,
} from '../utils/sampleData';
import WebSocketService from '../services/websocket.service';

export const useInitializeDashboard = () => {
  const dispatch = useAppDispatch();

  useEffect(() => {
    // Initialize with sample data
    dispatch(setCurrentLayout(generateSampleLayout()));
    dispatch(setMetrics(generateSampleMetrics()));
    
    const timeSeriesData = generateTimeSeriesData();
    Object.entries(timeSeriesData).forEach(([key, data]) => {
      dispatch(setTimeSeriesData({ key, data }));
    });
    
    dispatch(setHeatmapData(generateHeatmapData()));
    dispatch(setPredictions(generatePredictions()));
    dispatch(setTrends(generateTrends()));
    dispatch(setAnomalies(generateAnomalies()));

    // Simulate real-time updates
    const interval = setInterval(() => {
      // Update metrics
      const metrics = generateSampleMetrics();
      metrics.forEach(metric => {
        metric.value = metric.value + (Math.random() - 0.5) * 2;
        metric.change = metric.change + (Math.random() - 0.5);
      });
      dispatch(setMetrics(metrics));

      // Add new time series data point
      dispatch(appendTimeSeriesData({
        key: 'visibility-trend',
        data: {
          timestamp: new Date().toISOString(),
          value: 75 + Math.random() * 20,
          label: 'Visibility Score',
        },
      }));

      // Update predictions
      const predictions = generatePredictions();
      dispatch(setPredictions(predictions));
    }, 5000); // Update every 5 seconds

    // Subscribe to WebSocket channels
    WebSocketService.subscribeToChannel('analytics');
    WebSocketService.subscribeToChannel('predictions');

    return () => {
      clearInterval(interval);
      WebSocketService.unsubscribeFromChannel('analytics');
      WebSocketService.unsubscribeFromChannel('predictions');
    };
  }, [dispatch]);
};