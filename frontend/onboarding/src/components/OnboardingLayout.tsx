import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Box,
  LinearProgress,
  IconButton,
  Menu,
  MenuItem,
  Avatar,
  Chip,
} from '@mui/material';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import { useAppSelector } from '../hooks';
import { motion } from 'framer-motion';

interface OnboardingLayoutProps {
  children: React.ReactNode;
}

export const OnboardingLayout: React.FC<OnboardingLayoutProps> = ({ children }) => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const user = useAppSelector((state) => state.user.currentUser);
  const onboarding = useAppSelector((state) => state.onboarding);

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleSkipOnboarding = () => {
    if (window.confirm('Are you sure you want to skip onboarding? You can always come back later.')) {
      window.location.href = '/dashboard';
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            LLM Optimizer - Getting Started
          </Typography>
          
          {onboarding.progress > 0 && (
            <Chip
              label={`${Math.round(onboarding.progress)}% Complete`}
              color="secondary"
              size="small"
              sx={{ mr: 2 }}
            />
          )}

          <IconButton
            color="inherit"
            onClick={() => window.open('/help', '_blank')}
            sx={{ mr: 1 }}
          >
            <HelpOutlineIcon />
          </IconButton>

          <IconButton
            size="large"
            aria-label="account of current user"
            aria-controls="menu-appbar"
            aria-haspopup="true"
            onClick={handleMenu}
            color="inherit"
          >
            <Avatar sx={{ width: 32, height: 32 }}>
              {user?.name?.charAt(0).toUpperCase() || <AccountCircleIcon />}
            </Avatar>
          </IconButton>
          
          <Menu
            id="menu-appbar"
            anchorEl={anchorEl}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            keepMounted
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            open={Boolean(anchorEl)}
            onClose={handleClose}
          >
            <MenuItem disabled>
              <Typography variant="body2">{user?.email}</Typography>
            </MenuItem>
            <MenuItem onClick={handleSkipOnboarding}>
              <ExitToAppIcon fontSize="small" sx={{ mr: 1 }} />
              Skip Onboarding
            </MenuItem>
          </Menu>
        </Toolbar>
        
        {onboarding.progress > 0 && onboarding.progress < 100 && (
          <LinearProgress
            variant="determinate"
            value={onboarding.progress}
            sx={{
              height: 2,
              backgroundColor: 'rgba(255, 255, 255, 0.3)',
              '& .MuiLinearProgress-bar': {
                backgroundColor: 'white',
              },
            }}
          />
        )}
      </AppBar>

      <Box component="main" sx={{ flexGrow: 1, bgcolor: 'background.default' }}>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          {children}
        </motion.div>
      </Box>

      <Box
        component="footer"
        sx={{
          py: 2,
          px: 2,
          mt: 'auto',
          backgroundColor: 'background.paper',
          borderTop: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Container maxWidth="lg">
          <Typography variant="body2" color="text.secondary" align="center">
            Need help? Contact support@llmoptimizer.com or use the help button above.
          </Typography>
        </Container>
      </Box>
    </Box>
  );
};