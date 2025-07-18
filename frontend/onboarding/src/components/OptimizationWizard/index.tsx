import React, { useState, useEffect } from 'react';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Button,
  Paper,
  Typography,
  Container,
  Fade,
  IconButton,
  Tooltip,
} from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { useOnboarding } from '../../hooks/useOnboarding';
import { useAnalytics } from '../../hooks/useAnalytics';
import { UserInfoStep } from './steps/UserInfoStep';
import { BusinessInfoStep } from './steps/BusinessInfoStep';
import { GoalsStep } from './steps/GoalsStep';
import { PreferencesStep } from './steps/PreferencesStep';
import { ReviewStep } from './steps/ReviewStep';
import { WizardProgress } from './WizardProgress';
import { WizardData } from '../../types';

const steps = [
  {
    label: 'Personal Information',
    description: 'Tell us about yourself',
    component: UserInfoStep,
    requiredFields: ['userInfo'],
  },
  {
    label: 'Business Details',
    description: 'Share your business information',
    component: BusinessInfoStep,
    requiredFields: ['businessInfo'],
  },
  {
    label: 'Optimization Goals',
    description: 'What do you want to achieve?',
    component: GoalsStep,
    requiredFields: ['goals'],
  },
  {
    label: 'Preferences',
    description: 'Customize your experience',
    component: PreferencesStep,
    requiredFields: ['preferences'],
  },
  {
    label: 'Review & Confirm',
    description: 'Review your settings',
    component: ReviewStep,
    requiredFields: [],
  },
];

export const OptimizationWizard: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [showHelp, setShowHelp] = useState(false);
  const { wizardData, updateWizard, canProceed, completeCurrentStep } = useOnboarding();
  const { logEvent, trackTiming } = useAnalytics();
  const [stepStartTime, setStepStartTime] = useState(Date.now());

  useEffect(() => {
    setStepStartTime(Date.now());
  }, [activeStep]);

  const handleNext = () => {
    const stepTime = Date.now() - stepStartTime;
    trackTiming('wizard_step', steps[activeStep].label, stepTime);
    
    completeCurrentStep(`wizard_step_${activeStep}`);
    logEvent('wizard_step_completed', 'wizard', {
      step: activeStep,
      stepName: steps[activeStep].label,
      timeSpent: stepTime,
    });

    if (activeStep === steps.length - 1) {
      logEvent('wizard_completed', 'wizard', {
        totalSteps: steps.length,
        wizardData,
      });
    } else {
      setActiveStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
    logEvent('wizard_step_back', 'wizard', {
      fromStep: activeStep,
      toStep: activeStep - 1,
    });
  };

  const handleUpdateData = (data: Partial<WizardData>) => {
    updateWizard(data);
  };

  const isStepComplete = (stepIndex: number): boolean => {
    const step = steps[stepIndex];
    return canProceed(step.requiredFields);
  };

  const CurrentStepComponent = steps[activeStep].component;

  return (
    <Container maxWidth="md" className="wizard-container">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Box sx={{ mt: 4, mb: 4 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
            <div>
              <Typography variant="h4" gutterBottom>
                Optimization Setup Wizard
              </Typography>
              <Typography variant="body1" color="text.secondary">
                Let's personalize your experience in just a few steps
              </Typography>
            </div>
            <Tooltip title="Get help with this wizard">
              <IconButton
                onClick={() => setShowHelp(!showHelp)}
                className="wizard-help"
                color={showHelp ? 'primary' : 'default'}
              >
                <HelpOutlineIcon />
              </IconButton>
            </Tooltip>
          </Box>

          <WizardProgress
            totalSteps={steps.length}
            currentStep={activeStep}
            completedSteps={steps.map((_, index) => isStepComplete(index))}
          />

          <Paper elevation={3} sx={{ mt: 3, p: 3 }}>
            <Stepper activeStep={activeStep} orientation="vertical">
              {steps.map((step, index) => (
                <Step key={step.label}>
                  <StepLabel
                    optional={
                      index === steps.length - 1 ? (
                        <Typography variant="caption">Last step</Typography>
                      ) : null
                    }
                  >
                    {step.label}
                  </StepLabel>
                  <StepContent>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      {step.description}
                    </Typography>
                    
                    <Box sx={{ mt: 2, mb: 2 }} className="wizard-form">
                      <AnimatePresence mode="wait">
                        <motion.div
                          key={activeStep}
                          initial={{ opacity: 0, x: 20 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -20 }}
                          transition={{ duration: 0.3 }}
                        >
                          <CurrentStepComponent
                            data={wizardData}
                            onUpdate={handleUpdateData}
                            showHelp={showHelp}
                          />
                        </motion.div>
                      </AnimatePresence>
                    </Box>

                    <Box sx={{ mb: 2 }}>
                      <Button
                        variant="contained"
                        onClick={handleNext}
                        sx={{ mt: 1, mr: 1 }}
                        disabled={!isStepComplete(index)}
                      >
                        {index === steps.length - 1 ? 'Complete Setup' : 'Continue'}
                      </Button>
                      <Button
                        disabled={index === 0}
                        onClick={handleBack}
                        sx={{ mt: 1, mr: 1 }}
                      >
                        Back
                      </Button>
                      {index < steps.length - 2 && (
                        <Button
                          onClick={() => {
                            logEvent('wizard_step_skipped', 'wizard', {
                              step: index,
                              stepName: step.label,
                            });
                            setActiveStep((prev) => prev + 1);
                          }}
                          sx={{ mt: 1 }}
                        >
                          Skip for now
                        </Button>
                      )}
                    </Box>
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          </Paper>

          {showHelp && (
            <Fade in={showHelp}>
              <Paper sx={{ mt: 2, p: 2, backgroundColor: 'info.light' }}>
                <Typography variant="body2">
                  <strong>Need help?</strong> This wizard helps you set up LLM Optimizer 
                  according to your specific needs. Each step is optional except the last one. 
                  You can always update these settings later in your profile.
                </Typography>
              </Paper>
            </Fade>
          )}
        </Box>
      </motion.div>
    </Container>
  );
};