import { io, Socket } from 'socket.io-client';
import { store } from '../store';
import {
  setConnectionStatus,
  setError,
  incrementReconnectAttempts,
  setLastMessage,
  ConnectionStatus,
} from '../store/slices/websocketSlice';
import {
  updateMetric,
  appendTimeSeriesData,
  setHeatmapData,
} from '../store/slices/analyticsSlice';
import {
  addPrediction,
  addAnomaly,
  setTrends,
} from '../store/slices/predictionsSlice';

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectDelay = 3000;

  connect(url: string = process.env.REACT_APP_WS_URL || 'http://localhost:3001') {
    if (this.socket?.connected) {
      console.log('WebSocket already connected');
      return;
    }

    store.dispatch(setConnectionStatus(ConnectionStatus.CONNECTING));

    this.socket = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      store.dispatch(setConnectionStatus(ConnectionStatus.CONNECTED));
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      store.dispatch(setConnectionStatus(ConnectionStatus.DISCONNECTED));
      this.handleReconnect();
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      store.dispatch(setError(error.message));
    });

    // Analytics events
    this.socket.on('metric:update', (data) => {
      store.dispatch(updateMetric(data));
      store.dispatch(setLastMessage({ type: 'metric:update', data }));
    });

    this.socket.on('timeseries:update', (data) => {
      store.dispatch(appendTimeSeriesData(data));
      store.dispatch(setLastMessage({ type: 'timeseries:update', data }));
    });

    this.socket.on('heatmap:update', (data) => {
      store.dispatch(setHeatmapData(data));
      store.dispatch(setLastMessage({ type: 'heatmap:update', data }));
    });

    // Prediction events
    this.socket.on('prediction:new', (data) => {
      store.dispatch(addPrediction(data));
      store.dispatch(setLastMessage({ type: 'prediction:new', data }));
    });

    this.socket.on('anomaly:detected', (data) => {
      store.dispatch(addAnomaly(data));
      store.dispatch(setLastMessage({ type: 'anomaly:detected', data }));
    });

    this.socket.on('trends:update', (data) => {
      store.dispatch(setTrends(data));
      store.dispatch(setLastMessage({ type: 'trends:update', data }));
    });

    // Custom event handler for any other events
    this.socket.onAny((event, ...args) => {
      console.log('WebSocket event:', event, args);
    });
  }

  private handleReconnect() {
    const state = store.getState();
    const reconnectAttempts = state.websocket.reconnectAttempts;

    if (reconnectAttempts >= this.maxReconnectAttempts) {
      store.dispatch(setError('Max reconnection attempts reached'));
      return;
    }

    store.dispatch(incrementReconnectAttempts());

    this.reconnectTimer = setTimeout(() => {
      console.log(`Reconnection attempt ${reconnectAttempts + 1}`);
      this.connect();
    }, this.reconnectDelay * (reconnectAttempts + 1));
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }

    store.dispatch(setConnectionStatus(ConnectionStatus.DISCONNECTED));
  }

  emit(event: string, data: any) {
    if (!this.socket?.connected) {
      console.error('WebSocket not connected');
      return;
    }

    this.socket.emit(event, data);
  }

  on(event: string, callback: (...args: any[]) => void) {
    if (!this.socket) {
      console.error('WebSocket not initialized');
      return;
    }

    this.socket.on(event, callback);
  }

  off(event: string, callback?: (...args: any[]) => void) {
    if (!this.socket) {
      console.error('WebSocket not initialized');
      return;
    }

    if (callback) {
      this.socket.off(event, callback);
    } else {
      this.socket.off(event);
    }
  }

  // Utility methods for common operations
  subscribeToMetric(metricId: string) {
    this.emit('subscribe:metric', { metricId });
  }

  unsubscribeFromMetric(metricId: string) {
    this.emit('unsubscribe:metric', { metricId });
  }

  subscribeToChannel(channel: string) {
    this.emit('subscribe:channel', { channel });
  }

  unsubscribeFromChannel(channel: string) {
    this.emit('unsubscribe:channel', { channel });
  }

  requestHistoricalData(metric: string, startTime: string, endTime: string) {
    this.emit('request:historical', { metric, startTime, endTime });
  }

  requestPrediction(metric: string, timeframe: string) {
    this.emit('request:prediction', { metric, timeframe });
  }
}

const websocketService = new WebSocketService();
export default websocketService;