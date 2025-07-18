import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import {
  Box,
  Alert,
  FormControl,
  FormLabel,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Switch,
  Typography,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/Notifications';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SpeedIcon from '@mui/icons-material/Speed';
import SecurityIcon from '@mui/icons-material/Security';
import IntegrationInstructionsIcon from '@mui/icons-material/IntegrationInstructions';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import GroupIcon from '@mui/icons-material/Group';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
import { WizardData } from '../../../types';

interface PreferencesStepProps {
  data: WizardData;
  onUpdate: (data: Partial<WizardData>) => void;
  showHelp: boolean;
}

const features = [
  {
    id: 'auto_optimize',
    label: 'Auto-Optimization',
    description: 'Automatically optimize content as you type',
    icon: <AutoAwesomeIcon />,
  },
  {
    id: 'real_time_preview',
    label: 'Real-time Preview',
    description: 'See optimization results instantly',
    icon: <SpeedIcon />,
  },
  {
    id: 'advanced_analytics',
    label: 'Advanced Analytics',
    description: 'Detailed performance tracking and insights',
    icon: <AnalyticsIcon />,
  },
  {
    id: 'team_collaboration',
    label: 'Team Collaboration',
    description: 'Share and collaborate with team members',
    icon: <GroupIcon />,
  },
  {
    id: 'api_access',
    label: 'API Access',
    description: 'Integrate with your existing tools',
    icon: <IntegrationInstructionsIcon />,
  },
  {
    id: 'data_encryption',
    label: 'Enhanced Security',
    description: 'End-to-end encryption for your content',
    icon: <SecurityIcon />,
  },
];

const integrations = [
  { id: 'wordpress', label: 'WordPress' },
  { id: 'shopify', label: 'Shopify' },
  { id: 'hubspot', label: 'HubSpot' },
  { id: 'google_analytics', label: 'Google Analytics' },
  { id: 'mailchimp', label: 'Mailchimp' },
  { id: 'slack', label: 'Slack' },
];

const schema = yup.object().shape({
  features: yup.array().of(yup.string()),
  integrations: yup.array().of(yup.string()),
  notifications: yup.boolean(),
});

export const PreferencesStep: React.FC<PreferencesStepProps> = ({ data, onUpdate, showHelp }) => {
  const {
    control,
    watch,
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: data.preferences || {
      features: ['auto_optimize', 'real_time_preview'],
      integrations: [],
      notifications: true,
    },
  });

  React.useEffect(() => {
    const subscription = watch((value) => {
      onUpdate({ preferences: value as any });
    });
    return () => subscription.unsubscribe();
  }, [watch, onUpdate]);

  return (
    <Box>
      {showHelp && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Customize your experience by selecting the features and integrations you'd like to use. 
          You can always change these settings later.
        </Alert>
      )}

      <FormControl component="fieldset" fullWidth>
        <FormLabel component="legend" sx={{ mb: 2 }}>
          Select the features you'd like to enable
        </FormLabel>
        <Controller
          name="features"
          control={control}
          render={({ field }) => (
            <List>
              {features.map((feature) => (
                <ListItem key={feature.id} sx={{ px: 0 }}>
                  <ListItemIcon>{feature.icon}</ListItemIcon>
                  <ListItemText
                    primary={feature.label}
                    secondary={feature.description}
                  />
                  <ListItemSecondaryAction>
                    <Checkbox
                      edge="end"
                      checked={field.value?.includes(feature.id) || false}
                      onChange={(e) => {
                        const newValue = e.target.checked
                          ? [...(field.value || []), feature.id]
                          : field.value?.filter((v) => v !== feature.id) || [];
                        field.onChange(newValue);
                      }}
                    />
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          )}
        />
      </FormControl>

      <Divider sx={{ my: 3 }} />

      <FormControl component="fieldset" fullWidth>
        <FormLabel component="legend" sx={{ mb: 2 }}>
          Select integrations to connect
        </FormLabel>
        <Controller
          name="integrations"
          control={control}
          render={({ field }) => (
            <FormGroup row>
              {integrations.map((integration) => (
                <FormControlLabel
                  key={integration.id}
                  control={
                    <Checkbox
                      checked={field.value?.includes(integration.id) || false}
                      onChange={(e) => {
                        const newValue = e.target.checked
                          ? [...(field.value || []), integration.id]
                          : field.value?.filter((v) => v !== integration.id) || [];
                        field.onChange(newValue);
                      }}
                    />
                  }
                  label={integration.label}
                  sx={{ width: '45%', mb: 1 }}
                />
              ))}
            </FormGroup>
          )}
        />
      </FormControl>

      <Divider sx={{ my: 3 }} />

      <Controller
        name="notifications"
        control={control}
        render={({ field }) => (
          <FormControlLabel
            control={
              <Switch
                {...field}
                checked={field.value}
                icon={<NotificationsIcon />}
                checkedIcon={<NotificationsIcon />}
              />
            }
            label={
              <Box>
                <Typography variant="body1">Enable notifications</Typography>
                <Typography variant="caption" color="text.secondary">
                  Get notified about optimization opportunities and updates
                </Typography>
              </Box>
            }
          />
        )}
      />
    </Box>
  );
};