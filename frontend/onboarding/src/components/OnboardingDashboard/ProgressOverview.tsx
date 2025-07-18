import React from 'react';
import {
  Paper,
  Typography,
  Box,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { motion } from 'framer-motion';

interface ProgressOverviewProps {
  steps: Array<{
    id: string;
    label: string;
    completed: boolean;
  }>;
  completedCount: number;
  progressPercentage: number;
}

export const ProgressOverview: React.FC<ProgressOverviewProps> = ({
  steps,
  completedCount,
  progressPercentage,
}) => {
  return (
    <Paper sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Your Progress</Typography>
        <Chip
          label={`${completedCount}/${steps.length} completed`}
          color={progressPercentage === 100 ? 'success' : 'primary'}
          size="small"
        />
      </Box>
      
      <Box mb={3}>
        <LinearProgress
          variant="determinate"
          value={progressPercentage}
          sx={{
            height: 10,
            borderRadius: 5,
            backgroundColor: 'grey.200',
            '& .MuiLinearProgress-bar': {
              borderRadius: 5,
              background: progressPercentage === 100
                ? 'linear-gradient(45deg, #4caf50 30%, #81c784 90%)'
                : 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
            },
          }}
        />
        <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
          {progressPercentage}% Complete
        </Typography>
      </Box>

      <List>
        {steps.map((step, index) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <ListItem>
              <ListItemIcon>
                {step.completed ? (
                  <CheckCircleIcon color="success" />
                ) : (
                  <RadioButtonUncheckedIcon color="action" />
                )}
              </ListItemIcon>
              <ListItemText
                primary={step.label}
                primaryTypographyProps={{
                  style: {
                    textDecoration: step.completed ? 'line-through' : 'none',
                    color: step.completed ? 'text.secondary' : 'text.primary',
                  },
                }}
              />
              {step.completed && (
                <Chip label="Done" size="small" color="success" />
              )}
            </ListItem>
          </motion.div>
        ))}
      </List>
    </Paper>
  );
};