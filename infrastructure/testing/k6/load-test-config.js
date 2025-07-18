import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';
import { SharedArray } from 'k6/data';

// Custom metrics
const errorRate = new Rate('errors');

// Test data
const testUsers = new SharedArray('users', function() {
  return JSON.parse(open('./test-users.json'));
});

// Test configuration
export const options = {
  // Scenarios define different workload patterns
  scenarios: {
    // Smoke test
    smoke: {
      executor: 'constant-vus',
      vus: 2,
      duration: '1m',
      tags: { test_type: 'smoke' },
    },
    
    // Load test - ramp up to 1000 users
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '5m', target: 100 },
        { duration: '10m', target: 500 },
        { duration: '10m', target: 1000 },
        { duration: '5m', target: 0 },
      ],
      gracefulRampDown: '30s',
      tags: { test_type: 'load' },
    },
    
    // Stress test - push beyond normal capacity
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 200 },
        { duration: '5m', target: 200 },
        { duration: '2m', target: 300 },
        { duration: '5m', target: 300 },
        { duration: '2m', target: 400 },
        { duration: '5m', target: 400 },
        { duration: '10m', target: 0 },
      ],
      gracefulRampDown: '5m',
      tags: { test_type: 'stress' },
    },
    
    // Spike test - sudden traffic increase
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },
        { duration: '1m', target: 100 },
        { duration: '10s', target: 1500 },
        { duration: '3m', target: 1500 },
        { duration: '10s', target: 100 },
        { duration: '3m', target: 100 },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '10s',
      tags: { test_type: 'spike' },
    },
    
    // Soak test - sustained load over extended period
    soak: {
      executor: 'constant-vus',
      vus: 500,
      duration: '2h',
      tags: { test_type: 'soak' },
    },
  },
  
  // Thresholds for pass/fail criteria
  thresholds: {
    http_req_failed: ['rate<0.1'], // Error rate < 10%
    http_req_duration: ['p(95)<500'], // 95% of requests must be < 500ms
    'http_req_duration{test_type:load}': ['p(95)<1000'], // Load test specific
    'http_req_duration{test_type:stress}': ['p(95)<2000'], // Stress test allows higher latency
    errors: ['rate<0.1'], // Custom error rate
  },
  
  // Disable default output during the test
  discardResponseBodies: true,
  
  // Setup and teardown functions
  setupTimeout: '60s',
  teardownTimeout: '60s',
};

// API base URL
const BASE_URL = __ENV.BASE_URL || 'https://api.llmoptimizer.com';

// Test setup
export function setup() {
  // Verify API is accessible
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`API health check failed: ${res.status}`);
  }
  
  // Return data for use in default function and teardown
  return { startTime: new Date().toISOString() };
}

// Main test function
export default function(data) {
  const user = testUsers[__VU % testUsers.length];
  
  // Authentication
  const authRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    email: user.email,
    password: user.password,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  
  check(authRes, {
    'login successful': (r) => r.status === 200,
    'token returned': (r) => r.json('token') !== '',
  });
  
  errorRate.add(authRes.status !== 200);
  
  if (authRes.status !== 200) {
    return;
  }
  
  const token = authRes.json('token');
  const authHeaders = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
  
  // Content submission
  const contentRes = http.post(`${BASE_URL}/content/analyze`, JSON.stringify({
    title: 'Test Content',
    content: 'This is a test content for load testing the LLM optimization platform.',
    url: 'https://example.com/test-content',
    contentType: 'article',
  }), {
    headers: authHeaders,
  });
  
  check(contentRes, {
    'content submitted': (r) => r.status === 201,
    'content id returned': (r) => r.json('contentId') !== '',
  });
  
  errorRate.add(contentRes.status !== 201);
  
  if (contentRes.status === 201) {
    const contentId = contentRes.json('contentId');
    
    // Get optimization results
    sleep(1); // Wait for processing
    
    const resultsRes = http.get(`${BASE_URL}/content/${contentId}/optimization`, {
      headers: authHeaders,
    });
    
    check(resultsRes, {
      'results retrieved': (r) => r.status === 200,
      'optimization score exists': (r) => r.json('optimizationScore') !== undefined,
    });
    
    errorRate.add(resultsRes.status !== 200);
  }
  
  // Analytics query
  const analyticsRes = http.get(`${BASE_URL}/analytics/dashboard`, {
    headers: authHeaders,
  });
  
  check(analyticsRes, {
    'analytics retrieved': (r) => r.status === 200,
  });
  
  errorRate.add(analyticsRes.status !== 200);
  
  // ML model query
  const mlRes = http.post(`${BASE_URL}/ml/predict`, JSON.stringify({
    text: 'Sample text for ML prediction',
    model: 'semantic-saturation',
  }), {
    headers: authHeaders,
  });
  
  check(mlRes, {
    'ml prediction successful': (r) => r.status === 200,
    'prediction result exists': (r) => r.json('prediction') !== undefined,
  });
  
  errorRate.add(mlRes.status !== 200);
  
  // Random sleep between requests (0.5 - 2 seconds)
  sleep(Math.random() * 1.5 + 0.5);
}

// Test teardown
export function teardown(data) {
  console.log(`Test completed. Started at: ${data.startTime}`);
  
  // Could send notification or cleanup here
  const summaryRes = http.post(`${BASE_URL}/admin/test-complete`, JSON.stringify({
    testType: 'k6-load-test',
    startTime: data.startTime,
    endTime: new Date().toISOString(),
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
}