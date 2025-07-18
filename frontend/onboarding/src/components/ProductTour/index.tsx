import React, { useEffect, useCallback } from 'react';
import Joyride, { CallBackProps, STATUS, EVENTS, Step } from 'react-joyride';
import { Box, Button, Typography } from '@mui/material';
import { useProductTour } from '../../hooks/useProductTour';
import { TourTooltip } from './TourTooltip';
import { tourStyles } from './tourStyles';

interface ProductTourProps {
  tourId?: string;
  onComplete?: () => void;
  autoStart?: boolean;
}

export const ProductTour: React.FC<ProductTourProps> = ({
  tourId = 'default',
  onComplete,
  autoStart = false,
}) => {
  const {
    run,
    stepIndex,
    steps,
    start,
    stop,
    next,
    previous,
    complete,
    isReady,
  } = useProductTour(tourId);

  useEffect(() => {
    if (autoStart && isReady) {
      start();
    }
  }, [autoStart, isReady, start]);

  const handleJoyrideCallback = useCallback((data: CallBackProps) => {
    const { status, type, index, action } = data;

    if ([EVENTS.STEP_AFTER, EVENTS.TARGET_NOT_FOUND].includes(type)) {
      // Update step index in our state
      if (action === 'next') {
        next();
      } else if (action === 'prev') {
        previous();
      }
    } else if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
      // Tour ended
      if (status === STATUS.FINISHED) {
        complete();
        onComplete?.();
      } else {
        stop();
      }
    }
  }, [next, previous, complete, stop, onComplete]);

  // Convert our custom steps to Joyride steps
  const joyrideSteps: Step[] = steps.map((step) => ({
    target: step.target,
    content: step.content,
    placement: step.placement || 'bottom',
    disableBeacon: step.disableBeacon ?? true,
    disableOverlay: step.disableOverlay ?? false,
    spotlightClicks: step.spotlightClicks ?? true,
    styles: step.styles || {},
    title: step.title,
    hideCloseButton: step.hideCloseButton ?? false,
    hideFooter: step.hideFooter ?? false,
    showProgress: step.showProgress ?? true,
    showSkipButton: step.showSkipButton ?? true,
  }));

  if (!run || steps.length === 0) {
    return null;
  }

  return (
    <Joyride
      steps={joyrideSteps}
      run={run}
      stepIndex={stepIndex}
      continuous
      showProgress
      showSkipButton
      callback={handleJoyrideCallback}
      styles={tourStyles}
      tooltipComponent={TourTooltip}
      floaterProps={{
        disableAnimation: false,
      }}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Finish',
        next: 'Next',
        skip: 'Skip Tour',
      }}
    />
  );
};