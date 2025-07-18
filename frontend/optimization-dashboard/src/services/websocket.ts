import { io, Socket } from 'socket.io-client';
import { store } from '../store';
import { connected, disconnected, error, ping } from '../store/slices/websocketSlice';
import { updateResults } from '../store/slices/dashboardSlice';
import { setVisibilityData } from '../store/slices/visibilitySlice';
import { setSuggestions } from '../store/slices/suggestionsSlice';
import { setMetrics } from '../store/slices/metricsSlice';
import { WS_URL } from './api';

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectInterval: NodeJS.Timeout | null = null;

  connect() {
    if (this.socket?.connected) return;

    this.socket = io(WS_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      store.dispatch(connected(this.socket!.id));
    });

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      store.dispatch(disconnected());
    });

    this.socket.on('error', (err) => {
      console.error('WebSocket error:', err);
      store.dispatch(error(err.message || 'WebSocket error'));
    });

    this.socket.on('ping', () => {
      store.dispatch(ping());
    });

    // Handle optimization updates
    this.socket.on('optimization:update', (data) => {
      store.dispatch(updateResults(data));
    });

    this.socket.on('visibility:update', (data) => {
      store.dispatch(setVisibilityData(data));
    });

    this.socket.on('suggestions:update', (data) => {
      store.dispatch(setSuggestions(data));
    });

    this.socket.on('metrics:update', (data) => {
      store.dispatch(setMetrics(data));
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    if (this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
      this.reconnectInterval = null;
    }
  }

  emit(event: string, data: any) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn('WebSocket not connected. Cannot emit event:', event);
    }
  }

  on(event: string, callback: (data: any) => void) {
    if (this.socket) {
      this.socket.on(event, callback);
    }
  }

  off(event: string, callback?: (data: any) => void) {
    if (this.socket) {
      this.socket.off(event, callback);
    }
  }

  subscribeToContent(contentId: string) {
    this.emit('subscribe:content', { contentId });
  }

  unsubscribeFromContent(contentId: string) {
    this.emit('unsubscribe:content', { contentId });
  }
}

export const websocketService = new WebSocketService();
export default websocketService;