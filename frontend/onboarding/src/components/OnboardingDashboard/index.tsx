import React from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  Button,
  Card,
  CardContent,
  CardActions,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Chip,
  Avatar,
  IconButton,
  Tooltip,
} from '@mui/material';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAppSelector } from '../../hooks';
import { useOnboarding } from '../../hooks/useOnboarding';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import SchoolIcon from '@mui/icons-material/School';
import TemplateIcon from '@mui/icons-material/Description';
import SettingsIcon from '@mui/icons-material/Settings';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { WelcomeSection } from './WelcomeSection';
import { ProgressOverview } from './ProgressOverview';
import { QuickActions } from './QuickActions';
import { ResourceLinks } from './ResourceLinks';
import { AchievementBadges } from './AchievementBadges';

export const OnboardingDashboard: React.FC = () => {
  const navigate = useNavigate();
  const user = useAppSelector((state) => state.user.currentUser);
  const onboarding = useOnboarding();

  const quickActions = [
    {
      id: 'tour',
      title: 'Take Product Tour',
      description: 'Learn the basics in 5 minutes',
      icon: <PlayCircleOutlineIcon />,
      action: () => navigate('/onboarding/tour'),
      color: 'primary',
    },
    {
      id: 'wizard',
      title: 'Setup Wizard',
      description: 'Personalize your experience',
      icon: <SettingsIcon />,
      action: () => navigate('/onboarding/wizard'),
      color: 'secondary',
    },
    {
      id: 'templates',
      title: 'Browse Templates',
      description: 'Start with proven formats',
      icon: <TemplateIcon />,
      action: () => navigate('/onboarding/templates'),
      color: 'info',
    },
    {
      id: 'tutorial',
      title: 'Interactive Tutorial',
      description: 'Learn by doing',
      icon: <SchoolIcon />,
      action: () => navigate('/onboarding/tutorial'),
      color: 'success',
    },
  ];

  const onboardingSteps = [
    {
      id: 'account',
      label: 'Create Account',
      completed: true,
    },
    {
      id: 'profile',
      label: 'Complete Profile',
      completed: onboarding.completedSteps.includes('wizard_step_0'),
    },
    {
      id: 'goals',
      label: 'Set Goals',
      completed: onboarding.completedSteps.includes('wizard_step_2'),
    },
    {
      id: 'tour',
      label: 'Take Product Tour',
      completed: onboarding.completedSteps.includes('tour_completed'),
    },
    {
      id: 'first_content',
      label: 'Create First Content',
      completed: onboarding.completedSteps.includes('first_content'),
    },
  ];

  const completedStepsCount = onboardingSteps.filter(step => step.completed).length;
  const progressPercentage = (completedStepsCount / onboardingSteps.length) * 100;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }} className="onboarding-welcome">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Welcome Section */}
        <WelcomeSection userName={user?.name || 'there'} />

        {/* Main Grid */}
        <Grid container spacing={3} sx={{ mt: 2 }}>
          {/* Progress Overview */}
          <Grid item xs={12} md={8}>
            <ProgressOverview
              steps={onboardingSteps}
              completedCount={completedStepsCount}
              progressPercentage={progressPercentage}
            />
          </Grid>

          {/* Achievement Badges */}
          <Grid item xs={12} md={4}>
            <AchievementBadges />
          </Grid>

          {/* Quick Actions */}
          <Grid item xs={12}>
            <QuickActions actions={quickActions} />
          </Grid>

          {/* Resource Links */}
          <Grid item xs={12} md={6}>
            <ResourceLinks />
          </Grid>

          {/* Getting Started Tips */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, height: '100%' }}>
              <Box display="flex" alignItems="center" mb={2}>
                <TrendingUpIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Pro Tips</Typography>
              </Box>
              <List dense>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircleIcon fontSize="small" color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Start with templates"
                    secondary="Save time by using our optimized templates"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircleIcon fontSize="small" color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Set clear goals"
                    secondary="Define what you want to achieve with your content"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircleIcon fontSize="small" color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Use the wizard"
                    secondary="Get personalized recommendations based on your needs"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircleIcon fontSize="small" color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Enable integrations"
                    secondary="Connect your favorite tools for seamless workflow"
                  />
                </ListItem>
              </List>
            </Paper>
          </Grid>
        </Grid>

        {/* Call to Action */}
        {!onboarding.tourActive && progressPercentage < 100 && (
          <Box mt={4} textAlign="center">
            <Paper sx={{ p: 4, backgroundColor: 'primary.light' }}>
              <Typography variant="h5" gutterBottom>
                Ready to optimize your content?
              </Typography>
              <Typography variant="body1" paragraph color="text.secondary">
                Complete the onboarding to unlock all features and start creating better content.
              </Typography>
              <Button
                variant="contained"
                size="large"
                onClick={() => {
                  if (!onboarding.completedSteps.includes('wizard_completed')) {
                    navigate('/onboarding/wizard');
                  } else if (!onboarding.completedSteps.includes('tour_completed')) {
                    navigate('/onboarding/tour');
                  } else {
                    navigate('/dashboard');
                  }
                }}
              >
                Continue Onboarding
              </Button>
            </Paper>
          </Box>
        )}
      </motion.div>
    </Container>
  );
};