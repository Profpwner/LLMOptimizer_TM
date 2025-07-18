import React from 'react';
import { TourStep } from '../types';
import { Box, Typography, List, ListItem, ListItemIcon, ListItemText } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import TextFieldsIcon from '@mui/icons-material/TextFields';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import TuneIcon from '@mui/icons-material/Tune';
import SaveIcon from '@mui/icons-material/Save';

// Default tour for first-time users
const defaultTourSteps: TourStep[] = [
  {
    target: '.onboarding-welcome',
    content: (
      <Box>
        <Typography variant="body2" gutterBottom>
          Welcome to LLM Optimizer! Let's take a quick tour to help you get started with optimizing your content.
        </Typography>
        <Typography variant="body2" color="text.secondary">
          This tour will show you the key features and how to use them effectively.
        </Typography>
      </Box>
    ),
    placement: 'center',
    disableBeacon: true,
    title: 'Welcome to LLM Optimizer!',
  },
  {
    target: '.content-input-area',
    content: (
      <Box>
        <Typography variant="body2" gutterBottom>
          This is where you'll input your content for optimization. You can:
        </Typography>
        <List dense>
          <ListItem>
            <ListItemIcon><TextFieldsIcon fontSize="small" /></ListItemIcon>
            <ListItemText primary="Type or paste your content" />
          </ListItem>
          <ListItem>
            <ListItemIcon><SaveIcon fontSize="small" /></ListItemIcon>
            <ListItemText primary="Upload documents" />
          </ListItem>
        </List>
      </Box>
    ),
    placement: 'bottom',
    title: 'Input Your Content',
    spotlightClicks: true,
  },
  {
    target: '.optimization-settings',
    content: (
      <Box>
        <Typography variant="body2" gutterBottom>
          Customize your optimization settings here:
        </Typography>
        <List dense>
          <ListItem>
            <ListItemText primary="• Choose optimization goals (SEO, engagement, etc.)" />
          </ListItem>
          <ListItem>
            <ListItemText primary="• Set target audience" />
          </ListItem>
          <ListItem>
            <ListItemText primary="• Configure tone and style" />
          </ListItem>
        </List>
      </Box>
    ),
    placement: 'left',
    title: 'Optimization Settings',
  },
  {
    target: '.analyze-button',
    content: (
      <Typography variant="body2">
        Click this button to start the AI-powered analysis. Our system will process your content and provide optimization suggestions in seconds.
      </Typography>
    ),
    placement: 'bottom',
    title: 'Start Analysis',
    spotlightClicks: true,
  },
  {
    target: '.results-dashboard',
    content: (
      <Box>
        <Typography variant="body2" gutterBottom>
          After analysis, you'll see:
        </Typography>
        <List dense>
          <ListItem>
            <ListItemIcon><AnalyticsIcon fontSize="small" /></ListItemIcon>
            <ListItemText primary="Visibility score" />
          </ListItem>
          <ListItem>
            <ListItemIcon><TuneIcon fontSize="small" /></ListItemIcon>
            <ListItemText primary="Optimization suggestions" />
          </ListItem>
          <ListItem>
            <ListItemIcon><DashboardIcon fontSize="small" /></ListItemIcon>
            <ListItemText primary="Performance metrics" />
          </ListItem>
        </List>
      </Box>
    ),
    placement: 'top',
    title: 'View Results',
  },
  {
    target: '.suggestion-cards',
    content: (
      <Typography variant="body2">
        Each suggestion card shows a specific improvement. You can apply suggestions individually or all at once. Click on a card to see more details.
      </Typography>
    ),
    placement: 'right',
    title: 'Apply Suggestions',
    spotlightClicks: true,
  },
  {
    target: '.export-options',
    content: (
      <Typography variant="body2">
        Export your optimized content in various formats, or copy it directly to your clipboard. You can also save it as a template for future use.
      </Typography>
    ),
    placement: 'left',
    title: 'Export Your Content',
  },
  {
    target: '.help-center',
    content: (
      <Box>
        <Typography variant="body2" gutterBottom>
          Need help? Access our resources anytime:
        </Typography>
        <Typography variant="body2" color="text.secondary">
          • Knowledge base<br />
          • Video tutorials<br />
          • Live chat support
        </Typography>
      </Box>
    ),
    placement: 'bottom',
    title: 'Get Help Anytime',
  },
];

// Dashboard-specific tour
const dashboardTourSteps: TourStep[] = [
  {
    target: '.dashboard-overview',
    content: 'This is your optimization dashboard. Here you can see all your recent content and their performance metrics.',
    placement: 'bottom',
    title: 'Dashboard Overview',
  },
  {
    target: '.content-list',
    content: 'View all your optimized content here. Click on any item to see detailed analytics and make further improvements.',
    placement: 'right',
    title: 'Content Library',
  },
  {
    target: '.performance-chart',
    content: 'Track your content performance over time. See how optimizations impact engagement, visibility, and conversions.',
    placement: 'left',
    title: 'Performance Analytics',
  },
  {
    target: '.quick-actions',
    content: 'Quick access to common actions: create new content, use templates, or start a new optimization.',
    placement: 'bottom',
    title: 'Quick Actions',
  },
];

// Template library tour
const templateTourSteps: TourStep[] = [
  {
    target: '.template-categories',
    content: 'Browse templates by category: Blog posts, Product descriptions, FAQs, Social media, and more.',
    placement: 'right',
    title: 'Template Categories',
  },
  {
    target: '.template-search',
    content: 'Search for specific templates or filter by industry, goal, or content type.',
    placement: 'bottom',
    title: 'Find Templates',
  },
  {
    target: '.template-preview',
    content: 'Preview any template before using it. See the structure and example content.',
    placement: 'left',
    title: 'Preview Templates',
  },
  {
    target: '.template-customize',
    content: 'Customize templates to match your brand voice and specific needs.',
    placement: 'top',
    title: 'Customize Templates',
  },
];

// Wizard-specific tour
const wizardTourSteps: TourStep[] = [
  {
    target: '.wizard-progress',
    content: 'Track your progress through the setup wizard. You can go back to any step at any time.',
    placement: 'bottom',
    title: 'Setup Progress',
  },
  {
    target: '.wizard-form',
    content: 'Fill out each step to customize LLM Optimizer for your specific needs.',
    placement: 'center',
    title: 'Personalize Your Experience',
  },
  {
    target: '.wizard-help',
    content: 'Get contextual help for each step. Click the help icon for more information.',
    placement: 'right',
    title: 'Get Help',
  },
];

export const TOUR_STEPS: Record<string, TourStep[]> = {
  default: defaultTourSteps,
  dashboard: dashboardTourSteps,
  templates: templateTourSteps,
  wizard: wizardTourSteps,
};

// Helper function to get role-specific tour steps
export const getRoleSpecificTour = (role: string): TourStep[] => {
  const baseSteps = [...defaultTourSteps];
  
  switch (role) {
    case 'marketer':
      baseSteps.splice(3, 0, {
        target: '.campaign-tools',
        content: 'Access marketing-specific tools like A/B testing, campaign tracking, and ROI analysis.',
        placement: 'bottom',
        title: 'Marketing Tools',
      });
      break;
    case 'seo_specialist':
      baseSteps.splice(3, 0, {
        target: '.seo-tools',
        content: 'Advanced SEO features: keyword density analysis, meta tag optimization, and SERP preview.',
        placement: 'bottom',
        title: 'SEO Tools',
      });
      break;
    case 'content_creator':
      baseSteps.splice(3, 0, {
        target: '.writing-assistant',
        content: 'AI-powered writing suggestions, tone adjustments, and readability improvements.',
        placement: 'bottom',
        title: 'Writing Assistant',
      });
      break;
  }
  
  return baseSteps;
};