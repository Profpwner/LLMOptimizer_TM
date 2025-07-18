import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import {
  TextField,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Box,
  Alert,
  FormHelperText,
} from '@mui/material';
import { WizardData, UserRole, ExperienceLevel } from '../../../types';

interface UserInfoStepProps {
  data: WizardData;
  onUpdate: (data: Partial<WizardData>) => void;
  showHelp: boolean;
}

const schema = yup.object().shape({
  name: yup.string().required('Name is required').min(2, 'Name must be at least 2 characters'),
  role: yup.string().oneOf(Object.values(UserRole)).required('Please select your role'),
  experience: yup.string().oneOf(Object.values(ExperienceLevel)).required('Please select your experience level'),
});

export const UserInfoStep: React.FC<UserInfoStepProps> = ({ data, onUpdate, showHelp }) => {
  const {
    control,
    formState: { errors },
    watch,
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: data.userInfo || {
      name: '',
      role: UserRole.CONTENT_CREATOR,
      experience: ExperienceLevel.BEGINNER,
    },
  });

  // Watch for changes and update parent
  React.useEffect(() => {
    const subscription = watch((value) => {
      onUpdate({ userInfo: value as any });
    });
    return () => subscription.unsubscribe();
  }, [watch, onUpdate]);

  return (
    <Box>
      {showHelp && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Tell us about yourself so we can customize your experience. Your role and experience 
          level help us show you the most relevant features and suggestions.
        </Alert>
      )}

      <Controller
        name="name"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            fullWidth
            label="Your Name"
            variant="outlined"
            margin="normal"
            error={!!errors.name}
            helperText={errors.name?.message}
            placeholder="John Doe"
          />
        )}
      />

      <FormControl component="fieldset" margin="normal" error={!!errors.role}>
        <FormLabel component="legend">What's your primary role?</FormLabel>
        <Controller
          name="role"
          control={control}
          render={({ field }) => (
            <RadioGroup {...field} row>
              <FormControlLabel
                value={UserRole.CONTENT_CREATOR}
                control={<Radio />}
                label="Content Creator"
              />
              <FormControlLabel
                value={UserRole.MARKETER}
                control={<Radio />}
                label="Marketer"
              />
              <FormControlLabel
                value={UserRole.SEO_SPECIALIST}
                control={<Radio />}
                label="SEO Specialist"
              />
              <FormControlLabel
                value={UserRole.BUSINESS_OWNER}
                control={<Radio />}
                label="Business Owner"
              />
              <FormControlLabel
                value={UserRole.DEVELOPER}
                control={<Radio />}
                label="Developer"
              />
            </RadioGroup>
          )}
        />
        {errors.role && <FormHelperText>{errors.role.message}</FormHelperText>}
      </FormControl>

      <FormControl component="fieldset" margin="normal" error={!!errors.experience}>
        <FormLabel component="legend">What's your experience level with content optimization?</FormLabel>
        <Controller
          name="experience"
          control={control}
          render={({ field }) => (
            <RadioGroup {...field}>
              <FormControlLabel
                value={ExperienceLevel.BEGINNER}
                control={<Radio />}
                label="Beginner - I'm just getting started"
              />
              <FormControlLabel
                value={ExperienceLevel.INTERMEDIATE}
                control={<Radio />}
                label="Intermediate - I have some experience"
              />
              <FormControlLabel
                value={ExperienceLevel.ADVANCED}
                control={<Radio />}
                label="Advanced - I'm very experienced"
              />
            </RadioGroup>
          )}
        />
        {errors.experience && <FormHelperText>{errors.experience.message}</FormHelperText>}
      </FormControl>
    </Box>
  );
};