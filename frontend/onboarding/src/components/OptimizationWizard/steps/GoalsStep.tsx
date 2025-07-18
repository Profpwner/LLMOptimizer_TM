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
  RadioGroup,
  Radio,
  Typography,
  Chip,
  Paper,
  FormHelperText,
} from '@mui/material';
import { WizardData, OptimizationGoal, ContentType } from '../../../types';

interface GoalsStepProps {
  data: WizardData;
  onUpdate: (data: Partial<WizardData>) => void;
  showHelp: boolean;
}

const monthlyVolumes = [
  { value: '1-10', label: '1-10 pieces' },
  { value: '11-50', label: '11-50 pieces' },
  { value: '51-100', label: '51-100 pieces' },
  { value: '100+', label: '100+ pieces' },
];

const schema = yup.object().shape({
  primaryGoals: yup
    .array()
    .of(yup.string().oneOf(Object.values(OptimizationGoal)))
    .min(1, 'Please select at least one goal')
    .required('Goals are required'),
  contentTypes: yup
    .array()
    .of(yup.string().oneOf(Object.values(ContentType)))
    .min(1, 'Please select at least one content type')
    .required('Content types are required'),
  monthlyVolume: yup.string().required('Please select your content volume'),
});

export const GoalsStep: React.FC<GoalsStepProps> = ({ data, onUpdate, showHelp }) => {
  const {
    control,
    formState: { errors },
    watch,
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: data.goals || {
      primaryGoals: [],
      contentTypes: [],
      monthlyVolume: '',
    },
  });

  React.useEffect(() => {
    const subscription = watch((value) => {
      onUpdate({ goals: value as any });
    });
    return () => subscription.unsubscribe();
  }, [watch, onUpdate]);

  const goalDescriptions = {
    [OptimizationGoal.SEO_RANKING]: 'Improve search engine visibility and rankings',
    [OptimizationGoal.ENGAGEMENT]: 'Increase user interaction and time on page',
    [OptimizationGoal.CONVERSION]: 'Drive more conversions and sales',
    [OptimizationGoal.READABILITY]: 'Make content easier to read and understand',
    [OptimizationGoal.BRAND_VOICE]: 'Maintain consistent brand messaging',
  };

  const contentTypeDescriptions = {
    [ContentType.BLOG]: 'Blog posts and articles',
    [ContentType.PRODUCT]: 'Product descriptions and features',
    [ContentType.LANDING]: 'Landing pages and campaigns',
    [ContentType.FAQ]: 'FAQs and help content',
    [ContentType.SOCIAL]: 'Social media posts',
    [ContentType.EMAIL]: 'Email newsletters and campaigns',
  };

  return (
    <Box>
      {showHelp && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Select your optimization goals and the types of content you create. This helps us 
          prioritize the right features and suggestions for your needs.
        </Alert>
      )}

      <FormControl component="fieldset" margin="normal" error={!!errors.primaryGoals}>
        <FormLabel component="legend">
          What are your primary optimization goals? (Select all that apply)
        </FormLabel>
        <Controller
          name="primaryGoals"
          control={control}
          render={({ field }) => (
            <FormGroup>
              {Object.entries(goalDescriptions).map(([value, description]) => (
                <Paper key={value} elevation={0} sx={{ p: 1, mb: 1, border: '1px solid', borderColor: 'divider' }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={field.value?.includes(value) || false}
                        onChange={(e) => {
                          const newValue = e.target.checked
                            ? [...(field.value || []), value]
                            : field.value?.filter((v) => v !== value) || [];
                          field.onChange(newValue);
                        }}
                      />
                    }
                    label={
                      <Box>
                        <Typography variant="body2" fontWeight="medium">
                          {value.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {description}
                        </Typography>
                      </Box>
                    }
                  />
                </Paper>
              ))}
            </FormGroup>
          )}
        />
        {errors.primaryGoals && <FormHelperText>{errors.primaryGoals.message}</FormHelperText>}
      </FormControl>

      <FormControl component="fieldset" margin="normal" error={!!errors.contentTypes}>
        <FormLabel component="legend">
          What types of content do you create? (Select all that apply)
        </FormLabel>
        <Controller
          name="contentTypes"
          control={control}
          render={({ field }) => (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
              {Object.entries(contentTypeDescriptions).map(([value, description]) => (
                <Chip
                  key={value}
                  label={value.charAt(0).toUpperCase() + value.slice(1)}
                  onClick={() => {
                    const isSelected = field.value?.includes(value);
                    const newValue = isSelected
                      ? field.value?.filter((v) => v !== value) || []
                      : [...(field.value || []), value];
                    field.onChange(newValue);
                  }}
                  color={field.value?.includes(value) ? 'primary' : 'default'}
                  variant={field.value?.includes(value) ? 'filled' : 'outlined'}
                />
              ))}
            </Box>
          )}
        />
        {errors.contentTypes && <FormHelperText>{errors.contentTypes.message}</FormHelperText>}
      </FormControl>

      <FormControl component="fieldset" margin="normal" error={!!errors.monthlyVolume}>
        <FormLabel component="legend">
          How much content do you typically create per month?
        </FormLabel>
        <Controller
          name="monthlyVolume"
          control={control}
          render={({ field }) => (
            <RadioGroup {...field}>
              {monthlyVolumes.map((volume) => (
                <FormControlLabel
                  key={volume.value}
                  value={volume.value}
                  control={<Radio />}
                  label={volume.label}
                />
              ))}
            </RadioGroup>
          )}
        />
        {errors.monthlyVolume && <FormHelperText>{errors.monthlyVolume.message}</FormHelperText>}
      </FormControl>
    </Box>
  );
};