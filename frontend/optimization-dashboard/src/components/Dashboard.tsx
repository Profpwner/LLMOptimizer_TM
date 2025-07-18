import React, { useEffect } from 'react';
import {
  Box,
  Grid,
  Container,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Button,
  CircularProgress,
  Alert,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import DownloadIcon from '@mui/icons-material/Download';
import PrintIcon from '@mui/icons-material/Print';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import { useAppSelector } from '../hooks/useAppSelector';
import { useAppDispatch } from '../hooks/useAppDispatch';
import { useWebSocket } from '../hooks/useWebSocket';
import { loadOptimizationResults, clearError } from '../store/slices/dashboardSlice';
import VisibilityScore from './VisibilityScore';
import ContentComparison from './ContentComparison';
import Suggestions from './Suggestions';
import ImpactMetrics from './ImpactMetrics';
import { exportOptimizationResults } from '../services/api';

interface DashboardProps {
  contentId: string;
}

const Dashboard: React.FC<DashboardProps> = ({ contentId }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const { results, loading, error } = useAppSelector((state) => state.dashboard);
  const { connected } = useWebSocket(contentId);
  
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  useEffect(() => {
    // Load initial data
    dispatch(loadOptimizationResults(contentId));
  }, [contentId, dispatch]);

  const handleRefresh = () => {
    dispatch(loadOptimizationResults(contentId));
  };

  const handleExport = async (format: 'pdf' | 'csv' | 'json') => {
    try {
      const blob = await exportOptimizationResults(contentId, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `optimization-results-${contentId}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleFullscreen = () => {
    if (document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen();
    }
  };

  if (loading && !results) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress size={60} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Optimization Results Dashboard
          </Typography>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color={connected ? 'success.light' : 'error.light'}>
              {connected ? '● Live' : '● Offline'}
            </Typography>
            
            <IconButton color="inherit" onClick={handleRefresh}>
              <RefreshIcon />
            </IconButton>
            
            <Button
              color="inherit"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('pdf')}
            >
              Export
            </Button>
            
            {!isMobile && (
              <>
                <IconButton color="inherit" onClick={handlePrint}>
                  <PrintIcon />
                </IconButton>
                <IconButton color="inherit" onClick={handleFullscreen}>
                  <FullscreenIcon />
                </IconButton>
              </>
            )}
          </Box>
        </Toolbar>
      </AppBar>

      <Container maxWidth={false} sx={{ flex: 1, py: 3, overflow: 'auto' }}>
        {error && (
          <Alert
            severity="error"
            onClose={() => dispatch(clearError())}
            sx={{ mb: 2 }}
          >
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* Visibility Score - Full width on mobile, half on desktop */}
          <Grid item xs={12} lg={6}>
            <Box sx={{ height: isMobile ? 400 : 500 }}>
              <VisibilityScore />
            </Box>
          </Grid>

          {/* Impact Metrics - Full width on mobile, half on desktop */}
          <Grid item xs={12} lg={6}>
            <Box sx={{ height: isMobile ? 400 : 500 }}>
              <ImpactMetrics />
            </Box>
          </Grid>

          {/* Content Comparison - Full width */}
          <Grid item xs={12}>
            <Box sx={{ height: isMobile ? 400 : 600 }}>
              <ContentComparison />
            </Box>
          </Grid>

          {/* Suggestions - Full width */}
          <Grid item xs={12}>
            <Box sx={{ height: isMobile ? 500 : 700 }}>
              <Suggestions />
            </Box>
          </Grid>
        </Grid>
      </Container>

      {/* Print-specific styles */}
      <style>
        {`
          @media print {
            .MuiAppBar-root {
              display: none;
            }
            .MuiContainer-root {
              padding: 0;
            }
            .MuiGrid-container {
              page-break-inside: avoid;
            }
            .MuiPaper-root {
              box-shadow: none !important;
              border: 1px solid #ddd;
            }
          }
        `}
      </style>
    </Box>
  );
};

export default Dashboard;