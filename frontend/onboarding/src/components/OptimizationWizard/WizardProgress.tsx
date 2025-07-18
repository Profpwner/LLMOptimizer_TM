import React from 'react';
import { Box, LinearProgress, Typography, Chip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { motion } from 'framer-motion';

interface WizardProgressProps {
  totalSteps: number;
  currentStep: number;
  completedSteps: boolean[];
}

export const WizardProgress: React.FC<WizardProgressProps> = ({
  totalSteps,
  currentStep,
  completedSteps,
}) => {
  const progress = ((currentStep + 1) / totalSteps) * 100;
  const completedCount = completedSteps.filter(Boolean).length;

  return (
    <Box sx={{ width: '100%' }} className="wizard-progress">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="body2" color="text.secondary">
          Step {currentStep + 1} of {totalSteps}
        </Typography>
        <Chip
          label={`${completedCount} completed`}
          size="small"
          color={completedCount === totalSteps ? 'success' : 'default'}
          icon={completedCount === totalSteps ? <CheckCircleIcon /> : undefined}
        />
      </Box>
      
      <Box position="relative">
        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{
            height: 8,
            borderRadius: 4,
            backgroundColor: 'grey.200',
            '& .MuiLinearProgress-bar': {
              borderRadius: 4,
              backgroundColor: 'primary.main',
            },
          }}
        />
        
        <Box
          display="flex"
          justifyContent="space-between"
          position="absolute"
          width="100%"
          top="50%"
          sx={{ transform: 'translateY(-50%)' }}
        >
          {Array.from({ length: totalSteps }).map((_, index) => (
            <motion.div
              key={index}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: index * 0.1 }}
            >
              <Box
                sx={{
                  backgroundColor: 'background.paper',
                  borderRadius: '50%',
                  p: 0.25,
                }}
              >
                {completedSteps[index] ? (
                  <CheckCircleIcon
                    sx={{
                      fontSize: 20,
                      color: 'success.main',
                    }}
                  />
                ) : index === currentStep ? (
                  <RadioButtonUncheckedIcon
                    sx={{
                      fontSize: 20,
                      color: 'primary.main',
                    }}
                  />
                ) : (
                  <RadioButtonUncheckedIcon
                    sx={{
                      fontSize: 20,
                      color: 'grey.400',
                    }}
                  />
                )}
              </Box>
            </motion.div>
          ))}
        </Box>
      </Box>
    </Box>
  );
};