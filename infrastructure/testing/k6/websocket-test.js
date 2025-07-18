import ws from 'k6/ws';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 }, // Ramp up to 100 WebSocket connections
    { duration: '5m', target: 500 }, // Ramp up to 500 connections
    { duration: '10m', target: 1000 }, // Stay at 1000 connections
    { duration: '2m', target: 0 }, // Ramp down
  ],
  thresholds: {
    ws_connecting: ['p(95)<1000'], // 95% of WebSocket connections should be < 1s
    ws_msgs_received: ['rate>100'], // Receive at least 100 messages per second
  },
};

const WS_URL = __ENV.WS_URL || 'wss://api.llmoptimizer.com/ws';

export default function () {
  const url = WS_URL;
  const params = {
    headers: {
      'Authorization': 'Bearer ' + getAuthToken(),
    },
    tags: { my_tag: 'websocket' },
  };

  const res = ws.connect(url, params, function (socket) {
    socket.on('open', () => {
      console.log('WebSocket connected');
      
      // Subscribe to real-time updates
      socket.send(JSON.stringify({
        type: 'subscribe',
        channels: ['optimization-updates', 'analytics-live', 'system-notifications'],
      }));
      
      // Send periodic ping to keep connection alive
      socket.setInterval(() => {
        socket.send(JSON.stringify({ type: 'ping' }));
      }, 30000);
    });

    socket.on('message', (data) => {
      const message = JSON.parse(data);
      
      check(message, {
        'message has type': (msg) => msg.type !== undefined,
        'message has timestamp': (msg) => msg.timestamp !== undefined,
      });
      
      // Handle different message types
      switch (message.type) {
        case 'optimization-update':
          // Verify optimization update structure
          check(message, {
            'has contentId': (msg) => msg.contentId !== undefined,
            'has progress': (msg) => msg.progress >= 0 && msg.progress <= 100,
          });
          break;
          
        case 'analytics-update':
          // Verify analytics update
          check(message, {
            'has metrics': (msg) => msg.metrics !== undefined,
          });
          break;
          
        case 'pong':
          // Ping response received
          break;
      }
    });

    socket.on('error', (e) => {
      console.log('WebSocket error:', e);
    });

    socket.on('close', () => {
      console.log('WebSocket closed');
    });

    // Simulate user activity
    socket.setTimeout(() => {
      // Request optimization status
      socket.send(JSON.stringify({
        type: 'get-optimization-status',
        contentId: Math.floor(Math.random() * 1000),
      }));
    }, 5000);

    // Keep connection open for duration
    socket.setTimeout(() => {
      socket.close();
    }, 60000);
  });

  check(res, { 'WebSocket connection successful': (r) => r && r.status === 101 });
}

function getAuthToken() {
  // In real scenario, this would authenticate and return a token
  return 'mock-jwt-token-for-testing';
}