import { store } from '../store';

export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export interface ContentUpdate {
  type: 'content_update';
  content_id: string;
  update_type: string;
  data: any;
  timestamp: string;
}

export interface JobUpdate {
  type: 'job_update';
  job_id: string;
  status: string;
  progress?: number;
  data?: any;
  timestamp: string;
}

class ContentWebSocketService {
  private ws: WebSocket | null = null;
  private reconnectInterval: number = 5000;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private messageHandlers: Map<string, Set<(message: WebSocketMessage) => void>> = new Map();
  private userId: string | null = null;

  constructor() {
    // Get user ID from auth token or session
    this.userId = this.getUserId();
  }

  private getUserId(): string {
    // In a real app, extract this from JWT token or auth state
    return 'user123';
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = process.env.REACT_APP_CONTENT_WS_URL || 'ws://localhost:8002';
    this.ws = new WebSocket(`${wsUrl}/ws/${this.userId}`);

    this.ws.onopen = () => {
      console.log('Content WebSocket connected');
      this.clearReconnectTimer();
      
      // Send initial ping
      this.send({ type: 'ping' });
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;
        this.handleMessage(message);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.scheduleReconnect();
    };
  }

  disconnect() {
    this.clearReconnectTimer();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private scheduleReconnect() {
    this.clearReconnectTimer();
    this.reconnectTimer = setTimeout(() => {
      console.log('Attempting to reconnect WebSocket...');
      this.connect();
    }, this.reconnectInterval);
  }

  private clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private handleMessage(message: WebSocketMessage) {
    // Handle specific message types
    switch (message.type) {
      case 'connection':
        console.log('WebSocket connection confirmed:', message);
        break;
      
      case 'pong':
        // Server responded to ping
        break;
      
      case 'content_update':
        this.notifyHandlers('content_update', message);
        break;
      
      case 'job_update':
        this.notifyHandlers('job_update', message);
        break;
      
      case 'error':
        console.error('WebSocket error message:', message);
        break;
      
      default:
        console.log('Unknown WebSocket message type:', message);
    }
  }

  private notifyHandlers(type: string, message: WebSocketMessage) {
    const handlers = this.messageHandlers.get(type);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in message handler:', error);
        }
      });
    }
  }

  send(message: WebSocketMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }

  // Subscribe to specific message types
  subscribe(type: string, handler: (message: WebSocketMessage) => void) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.messageHandlers.delete(type);
        }
      }
    };
  }

  // Subscribe to updates for a specific content item
  subscribeToContent(contentId: string) {
    this.send({
      type: 'subscribe',
      subscription_type: 'content',
      target_id: contentId
    });
  }

  // Subscribe to updates for a specific job
  subscribeToJob(jobId: string) {
    this.send({
      type: 'subscribe',
      subscription_type: 'job',
      target_id: jobId
    });
  }
}

// Export singleton instance
export const contentWebSocket = new ContentWebSocketService();