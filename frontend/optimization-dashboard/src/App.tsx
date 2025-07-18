import React from 'react';
import { Provider } from 'react-redux';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { store } from './store';
import Dashboard from './components/Dashboard';
import ErrorBoundary from './components/common/ErrorBoundary';

// Create Material-UI theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
  },
});

function App() {
  // In a real app, you'd get the contentId from URL params or props
  const contentId = new URLSearchParams(window.location.search).get('contentId') || 'demo-content';

  return (
    <Provider store={store}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <ErrorBoundary>
          <Dashboard contentId={contentId} />
        </ErrorBoundary>
      </ThemeProvider>
    </Provider>
  );
}

export default App;