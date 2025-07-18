import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Alert,
  FormHelperText,
  Autocomplete,
} from '@mui/material';
import { WizardData } from '../../../types';

interface BusinessInfoStepProps {
  data: WizardData;
  onUpdate: (data: Partial<WizardData>) => void;
  showHelp: boolean;
}

const industries = [
  'Technology',
  'Healthcare',
  'Finance',
  'E-commerce',
  'Education',
  'Real Estate',
  'Travel & Tourism',
  'Food & Beverage',
  'Entertainment',
  'Fashion & Beauty',
  'Automotive',
  'Legal Services',
  'Marketing & Advertising',
  'Non-profit',
  'Other',
];

const companySizes = [
  { value: 'solo', label: 'Solo/Freelancer' },
  { value: 'small', label: 'Small (2-10 employees)' },
  { value: 'medium', label: 'Medium (11-50 employees)' },
  { value: 'large', label: 'Large (51-200 employees)' },
  { value: 'enterprise', label: 'Enterprise (200+ employees)' },
];

const schema = yup.object().shape({
  industry: yup.string().required('Please select your industry'),
  companySize: yup.string().required('Please select company size'),
  website: yup.string().url('Please enter a valid URL').nullable(),
});

export const BusinessInfoStep: React.FC<BusinessInfoStepProps> = ({ data, onUpdate, showHelp }) => {
  const {
    control,
    formState: { errors },
    watch,
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: data.businessInfo || {
      industry: '',
      companySize: '',
      website: '',
    },
  });

  React.useEffect(() => {
    const subscription = watch((value) => {
      onUpdate({ businessInfo: value as any });
    });
    return () => subscription.unsubscribe();
  }, [watch, onUpdate]);

  return (
    <Box>
      {showHelp && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Your business information helps us provide industry-specific templates and suggestions 
          tailored to your company size and sector.
        </Alert>
      )}

      <Controller
        name="industry"
        control={control}
        render={({ field }) => (
          <Autocomplete
            {...field}
            options={industries}
            value={field.value || null}
            onChange={(_, value) => field.onChange(value)}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Industry"
                variant="outlined"
                margin="normal"
                error={!!errors.industry}
                helperText={errors.industry?.message}
                fullWidth
              />
            )}
          />
        )}
      />

      <FormControl fullWidth margin="normal" error={!!errors.companySize}>
        <InputLabel>Company Size</InputLabel>
        <Controller
          name="companySize"
          control={control}
          render={({ field }) => (
            <Select {...field} label="Company Size">
              {companySizes.map((size) => (
                <MenuItem key={size.value} value={size.value}>
                  {size.label}
                </MenuItem>
              ))}
            </Select>
          )}
        />
        {errors.companySize && <FormHelperText>{errors.companySize.message}</FormHelperText>}
      </FormControl>

      <Controller
        name="website"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            fullWidth
            label="Company Website (Optional)"
            variant="outlined"
            margin="normal"
            error={!!errors.website}
            helperText={errors.website?.message || 'We\'ll analyze your website to provide better suggestions'}
            placeholder="https://example.com"
            type="url"
          />
        )}
      />
    </Box>
  );
};