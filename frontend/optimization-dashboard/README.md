# Optimization Results Dashboard

A comprehensive React/TypeScript dashboard for displaying LLM content optimization results with real-time updates.

## Features

### 1. Visibility Score Panel
- Bar chart visualization using Chart.js
- Platform-specific scores (ChatGPT, Claude, Gemini, Perplexity)
- Color-coded score ranges
- Animated transitions
- Detailed tooltips with metric breakdowns

### 2. Content Comparison Panel
- Side-by-side diff view
- Unified diff view toggle
- Syntax highlighting
- Character/word count comparison
- Change statistics

### 3. Suggestions Panel
- Sortable by priority/impact/category
- Advanced filtering options
- Search functionality
- One-click implementation
- Batch operations

### 4. Impact Metrics Panel
- Animated metric cards
- Trend indicators
- Progress bars for targets
- Historical data charts
- Custom metrics support

### 5. Real-time Updates
- WebSocket integration
- Live data synchronization
- Connection status indicator
- Auto-reconnection

## Technology Stack

- **React 18** with TypeScript
- **Redux Toolkit** for state management
- **Material-UI v5** for components
- **Chart.js** with react-chartjs-2 for visualizations
- **Socket.io-client** for WebSocket
- **diff-match-patch** for content comparison
- **react-syntax-highlighter** for code highlighting

## Project Structure

```
src/
├── components/
│   ├── common/          # Shared components
│   ├── ContentComparison/
│   ├── ImpactMetrics/
│   ├── Suggestions/
│   ├── VisibilityScore/
│   └── Dashboard.tsx    # Main container
├── hooks/               # Custom React hooks
├── services/            # API and WebSocket services
├── store/              # Redux store and slices
├── types/              # TypeScript type definitions
└── utils/              # Utility functions
```

## Installation

```bash
npm install
```

## Development

```bash
npm start
```

## Build

```bash
npm build
```

## Environment Variables

Create a `.env` file:

```env
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_WS_URL=ws://localhost:8000/ws
```

## Usage

The dashboard accepts a `contentId` parameter via URL:

```
http://localhost:3000/?contentId=your-content-id
```

## API Integration

The dashboard integrates with the following endpoints:

- `GET /optimization/results/:contentId` - Fetch optimization results
- `POST /optimization/suggestions/:id/apply` - Apply a suggestion
- `GET /optimization/results/:contentId/export` - Export results
- WebSocket events for real-time updates

## Responsive Design

- Mobile-first approach
- Adaptive layouts for different screen sizes
- Touch-friendly interactions
- Print-optimized styles

## Performance Optimizations

- React.memo for component memoization
- Lazy loading for heavy components
- Virtualized lists for large datasets
- Debounced search inputs
- Efficient Redux selectors

## Testing

```bash
npm test
```

## License

MIT