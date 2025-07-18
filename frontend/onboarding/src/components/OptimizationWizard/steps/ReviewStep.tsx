import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Button,
  Alert,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import BusinessIcon from '@mui/icons-material/Business';
import TargetIcon from '@mui/icons-material/TrackChanges';
import SettingsIcon from '@mui/icons-material/Settings';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import EditIcon from '@mui/icons-material/Edit';
import { WizardData } from '../../../types';
import { useNavigate } from 'react-router-dom';
import Confetti from 'react-confetti';
import { motion } from 'framer-motion';

interface ReviewStepProps {
  data: WizardData;
  onUpdate: (data: Partial<WizardData>) => void;
  showHelp: boolean;
}

export const ReviewStep: React.FC<ReviewStepProps> = ({ data, showHelp }) => {
  const navigate = useNavigate();
  const [showConfetti, setShowConfetti] = React.useState(false);

  const handleComplete = () => {
    setShowConfetti(true);
    setTimeout(() => {
      navigate('/onboarding/complete');
    }, 3000);
  };

  const sections = [
    {
      title: 'Personal Information',
      icon: <PersonIcon />,
      items: [
        { label: 'Name', value: data.userInfo?.name },
        { label: 'Role', value: data.userInfo?.role?.replace(/_/g, ' ') },
        { label: 'Experience', value: data.userInfo?.experience },
      ],
    },
    {
      title: 'Business Details',
      icon: <BusinessIcon />,
      items: [
        { label: 'Industry', value: data.businessInfo?.industry },
        { label: 'Company Size', value: data.businessInfo?.companySize },
        { label: 'Website', value: data.businessInfo?.website || 'Not provided' },
      ],
    },
    {
      title: 'Optimization Goals',
      icon: <TargetIcon />,
      items: [
        {
          label: 'Primary Goals',
          value: data.goals?.primaryGoals?.map(g => g.replace(/_/g, ' ')).join(', '),
        },
        {
          label: 'Content Types',
          value: data.goals?.contentTypes?.join(', '),
        },
        {
          label: 'Monthly Volume',
          value: data.goals?.monthlyVolume,
        },
      ],
    },
    {
      title: 'Preferences',
      icon: <SettingsIcon />,
      items: [
        {
          label: 'Features',
          value: data.preferences?.features?.length + ' features selected',
        },
        {
          label: 'Integrations',
          value: data.preferences?.integrations?.length + ' integrations selected',
        },
        {
          label: 'Notifications',
          value: data.preferences?.notifications ? 'Enabled' : 'Disabled',
        },
      ],
    },
  ];

  return (
    <Box>
      {showConfetti && (
        <Confetti
          width={window.innerWidth}
          height={window.innerHeight}
          recycle={false}
          numberOfPieces={200}
        />
      )}

      {showHelp && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Review your settings before completing the setup. You can always change these later
          in your profile settings.
        </Alert>
      )}

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <Typography variant="h6" gutterBottom>
          Great! Let's review your settings
        </Typography>

        <Grid container spacing={2} sx={{ mt: 1 }}>
          {sections.map((section, index) => (
            <Grid item xs={12} md={6} key={section.title}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card>
                  <CardContent>
                    <Box display="flex" alignItems="center" mb={2}>
                      {section.icon}
                      <Typography variant="subtitle1" fontWeight="bold" sx={{ ml: 1 }}>
                        {section.title}
                      </Typography>
                    </Box>
                    <List dense>
                      {section.items.map((item) => (
                        <ListItem key={item.label} sx={{ px: 0 }}>
                          <ListItemText
                            primary={item.label}
                            secondary={item.value || 'Not set'}
                            secondaryTypographyProps={{
                              style: { 
                                fontWeight: 500,
                                color: item.value ? 'inherit' : 'text.disabled',
                              },
                            }}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          ))}
        </Grid>

        <Box sx={{ mt: 4, p: 3, bgcolor: 'success.light', borderRadius: 2 }}>
          <Box display="flex" alignItems="center" mb={2}>
            <CheckCircleIcon color="success" sx={{ mr: 1 }} />
            <Typography variant="h6" color="success.dark">
              You're all set!
            </Typography>
          </Box>
          <Typography variant="body2" color="success.dark" gutterBottom>
            Your personalized optimization experience is ready. Based on your settings, we've:
          </Typography>
          <List dense>
            <ListItem>
              <ListItemIcon>
                <CheckCircleIcon color="success" fontSize="small" />
              </ListItemIcon>
              <ListItemText primary="Configured role-specific features and tools" />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <CheckCircleIcon color="success" fontSize="small" />
              </ListItemIcon>
              <ListItemText primary="Selected industry-relevant templates" />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <CheckCircleIcon color="success" fontSize="small" />
              </ListItemIcon>
              <ListItemText primary="Set up your optimization preferences" />
            </ListItem>
          </List>
        </Box>
      </motion.div>
    </Box>
  );
};