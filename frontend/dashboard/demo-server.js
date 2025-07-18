const express = require('express');
const http = require('http');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: "http://localhost:3002",
    methods: ["GET", "POST"]
  }
});

// Sample data generators
function generateMetricUpdate() {
  const metrics = ['visibility-score', 'content-performance', 'engagement-rate', 'ai-optimization'];
  const metric = metrics[Math.floor(Math.random() * metrics.length)];
  
  return {
    id: metric,
    name: metric.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
    value: Math.random() * 100,
    change: (Math.random() - 0.5) * 20,
    timestamp: new Date().toISOString(),
    unit: metric.includes('rate') || metric.includes('performance') ? '%' : 'points'
  };
}

function generateTimeSeriesUpdate() {
  return {
    key: 'visibility-trend',
    data: {
      timestamp: new Date().toISOString(),
      value: 75 + Math.random() * 20,
      label: 'Visibility Score'
    }
  };
}

function generatePrediction() {
  const baseValue = 85 + Math.random() * 10;
  const confidence = 0.8 + Math.random() * 0.2;
  const uncertainty = 5 + Math.random() * 5;
  
  return {
    id: `pred-${Date.now()}`,
    metric: 'visibility-score',
    timestamp: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
    predicted: baseValue,
    confidence,
    lowerBound: baseValue - uncertainty,
    upperBound: baseValue + uncertainty
  };
}

function generateAnomaly() {
  const severities = ['low', 'medium', 'high'];
  const metrics = ['visibility-score', 'engagement-rate', 'content-performance'];
  
  return {
    id: `anomaly-${Date.now()}`,
    metric: metrics[Math.floor(Math.random() * metrics.length)],
    timestamp: new Date().toISOString(),
    value: Math.random() * 100,
    severity: severities[Math.floor(Math.random() * severities.length)],
    description: `Unusual ${Math.random() > 0.5 ? 'spike' : 'drop'} detected in metric`
  };
}

// Socket.io connection handling
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);
  
  // Handle subscriptions
  socket.on('subscribe:channel', ({ channel }) => {
    console.log(`Client ${socket.id} subscribed to channel: ${channel}`);
    socket.join(channel);
  });
  
  socket.on('unsubscribe:channel', ({ channel }) => {
    console.log(`Client ${socket.id} unsubscribed from channel: ${channel}`);
    socket.leave(channel);
  });
  
  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

// Start sending demo data
setInterval(() => {
  // Send metric updates
  io.to('analytics').emit('metric:update', generateMetricUpdate());
  
  // Send time series data
  io.to('analytics').emit('timeseries:update', generateTimeSeriesUpdate());
}, 2000);

// Send predictions less frequently
setInterval(() => {
  io.to('predictions').emit('prediction:new', generatePrediction());
}, 10000);

// Occasionally send anomalies
setInterval(() => {
  if (Math.random() > 0.7) {
    io.to('predictions').emit('anomaly:detected', generateAnomaly());
  }
}, 15000);

// Update trends
setInterval(() => {
  const trends = [
    {
      metric: 'visibility-score',
      trend: Math.random() > 0.5 ? 'increasing' : 'decreasing',
      changeRate: (Math.random() - 0.5) * 20,
      confidence: 0.7 + Math.random() * 0.3
    },
    {
      metric: 'engagement-rate',
      trend: 'stable',
      changeRate: (Math.random() - 0.5) * 2,
      confidence: 0.8 + Math.random() * 0.2
    }
  ];
  
  io.to('predictions').emit('trends:update', trends);
}, 30000);

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`WebSocket demo server running on port ${PORT}`);
  console.log(`Dashboard should connect to ws://localhost:${PORT}`);
});