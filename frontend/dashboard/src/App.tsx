import React, { useEffect } from 'react';
import { Provider } from 'react-redux';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { store } from './store';
import { useAppSelector } from './hooks/redux';
import Dashboard from './components/Dashboard';
import WebSocketService from './services/websocket.service';
import { contentWebSocket } from './services/contentWebSocket';
import './App.css';

function AppContent() {
  const theme = useAppSelector((state) => state.dashboard.theme);

  const muiTheme = createTheme({
    palette: {
      mode: theme,
      primary: {
        main: theme === 'light' ? '#1976d2' : '#90caf9',
      },
      secondary: {
        main: theme === 'light' ? '#dc004e' : '#f48fb1',
      },
      background: {
        default: theme === 'light' ? '#f5f5f5' : '#121212',
        paper: theme === 'light' ? '#ffffff' : '#1e1e1e',
      },
    },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontSize: '2.5rem',
        fontWeight: 500,
      },
      h2: {
        fontSize: '2rem',
        fontWeight: 500,
      },
      h3: {
        fontSize: '1.75rem',
        fontWeight: 500,
      },
    },
    components: {
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            boxShadow: theme === 'light' 
              ? '0 2px 8px rgba(0,0,0,0.1)' 
              : '0 2px 8px rgba(0,0,0,0.3)',
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            textTransform: 'none',
          },
        },
      },
    },
  });

  useEffect(() => {
    // Connect to WebSocket services on app load
    WebSocketService.connect();
    contentWebSocket.connect();

    // Cleanup on unmount
    return () => {
      WebSocketService.disconnect();
      contentWebSocket.disconnect();
    };
  }, []);

  return (
    <ThemeProvider theme={muiTheme}>
      <CssBaseline />
      <Dashboard />
    </ThemeProvider>
  );
}

function App() {
  return (
    <Provider store={store}>
      <AppContent />
    </Provider>
  );
}

export default App;
