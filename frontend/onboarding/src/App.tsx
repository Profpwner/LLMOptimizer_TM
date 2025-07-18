import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Provider } from 'react-redux';
import { ThemeProvider, createTheme, CssBaseline, Box, Typography, CircularProgress } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { SnackbarProvider } from 'notistack';
import { motion } from 'framer-motion';
import { store } from './store';
import { OnboardingDashboard } from './components/OnboardingDashboard';
import { OptimizationWizard } from './components/OptimizationWizard';
import { TemplateLibrary } from './components/TemplateLibrary';
import { ProductTour } from './components/ProductTour';
import { OnboardingLayout } from './components/OnboardingLayout';
import { useAppDispatch, useAppSelector } from './hooks';
import { setUser, markOnboardingComplete } from './store/slices/userSlice';
import { loadProgress } from './store/slices/onboardingSlice';

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

// App content component that uses hooks
const AppContent: React.FC = () => {
  const dispatch = useAppDispatch();
  const user = useAppSelector((state) => state.user.currentUser);

  useEffect(() => {
    // Simulate loading user data (in real app, this would be from auth)
    const mockUser = {
      id: 'user-123',
      email: 'user@example.com',
      name: 'John Doe',
      role: 'content_creator' as const,
      createdAt: new Date(),
      onboardingCompleted: false,
    };
    dispatch(setUser(mockUser));

    // Load saved progress
    dispatch(loadProgress());
  }, [dispatch]);

  // Redirect to main app if onboarding is completed
  if (user?.onboardingCompleted) {
    window.location.href = '/dashboard';
    return null;
  }

  return (
    <OnboardingLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/onboarding/dashboard" replace />} />
        <Route path="/onboarding">
          <Route path="dashboard" element={<OnboardingDashboard />} />
          <Route path="wizard" element={<OptimizationWizard />} />
          <Route path="templates" element={<TemplateLibrary />} />
          <Route
            path="tour"
            element={
              <>
                <OnboardingDashboard />
                <ProductTour autoStart tourId="default" />
              </>
            }
          />
          <Route path="complete" element={<OnboardingComplete />} />
          <Route path="" element={<Navigate to="/onboarding/dashboard" replace />} />
        </Route>
      </Routes>
    </OnboardingLayout>
  );
};

// Completion page component
const OnboardingComplete: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  useEffect(() => {
    dispatch(markOnboardingComplete());
    setTimeout(() => {
      window.location.href = '/dashboard';
    }, 3000);
  }, [dispatch]);

  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      minHeight="100vh"
      textAlign="center"
    >
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', duration: 0.5 }}
      >
        <CheckCircleIcon sx={{ fontSize: 100, color: 'success.main', mb: 2 }} />
      </motion.div>
      <Typography variant="h4" gutterBottom>
        Congratulations! 🎉
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        You've completed the onboarding process. Redirecting to your dashboard...
      </Typography>
      <CircularProgress />
    </Box>
  );
};

// Main App component
function App() {
  return (
    <Provider store={store}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <SnackbarProvider
          maxSnack={3}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
        >
          <Router>
            <AppContent />
          </Router>
        </SnackbarProvider>
      </ThemeProvider>
    </Provider>
  );
}

export default App;