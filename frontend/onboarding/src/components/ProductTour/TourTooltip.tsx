import React from 'react';
import { TooltipRenderProps } from 'react-joyride';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  LinearProgress,
  Stack,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { motion } from 'framer-motion';

export const TourTooltip: React.FC<TooltipRenderProps> = ({
  continuous,
  index,
  step,
  backProps,
  closeProps,
  primaryProps,
  skipProps,
  tooltipProps,
  isLastStep,
  size,
}) => {
  const progress = ((index + 1) / size) * 100;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      transition={{ duration: 0.3 }}
    >
      <Card
        {...tooltipProps}
        sx={{
          maxWidth: 400,
          boxShadow: 6,
          borderRadius: 2,
          overflow: 'visible',
          '&::before': {
            content: '""',
            position: 'absolute',
            width: 0,
            height: 0,
            borderStyle: 'solid',
            // Arrow positioning will be handled by Joyride
          },
        }}
      >
        {/* Progress Bar */}
        {step.showProgress !== false && (
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              height: 4,
              backgroundColor: 'grey.200',
              '& .MuiLinearProgress-bar': {
                backgroundColor: 'primary.main',
              },
            }}
          />
        )}

        <CardContent sx={{ p: 3 }}>
          {/* Header */}
          <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
            {step.title && (
              <Typography variant="h6" component="h3" fontWeight="bold">
                {step.title}
              </Typography>
            )}
            {!step.hideCloseButton && (
              <IconButton
                {...closeProps}
                size="small"
                sx={{ ml: 1, mt: -1, mr: -1 }}
                aria-label="Close tour"
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            )}
          </Box>

          {/* Content */}
          <Box mb={3}>
            {typeof step.content === 'string' ? (
              <Typography variant="body2" color="text.secondary">
                {step.content}
              </Typography>
            ) : (
              step.content
            )}
          </Box>

          {/* Actions */}
          {!step.hideFooter && (
            <Stack direction="row" spacing={1} justifyContent="space-between" alignItems="center">
              <Box>
                {step.showSkipButton && !isLastStep && (
                  <Button
                    {...skipProps}
                    size="small"
                    color="inherit"
                    sx={{ textTransform: 'none' }}
                  >
                    Skip tour
                  </Button>
                )}
              </Box>
              
              <Stack direction="row" spacing={1}>
                {index > 0 && (
                  <Button
                    {...backProps}
                    size="small"
                    variant="outlined"
                    startIcon={<ChevronLeftIcon />}
                    sx={{ textTransform: 'none' }}
                  >
                    Back
                  </Button>
                )}
                
                <Button
                  {...primaryProps}
                  size="small"
                  variant="contained"
                  endIcon={!isLastStep && <ChevronRightIcon />}
                  sx={{ textTransform: 'none' }}
                >
                  {isLastStep ? 'Finish' : 'Next'}
                </Button>
              </Stack>
            </Stack>
          )}

          {/* Step counter */}
          {step.showProgress !== false && (
            <Typography
              variant="caption"
              color="text.disabled"
              align="center"
              display="block"
              mt={2}
            >
              {index + 1} of {size}
            </Typography>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};