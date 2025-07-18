import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  Tabs,
  Tab,
  Chip,
  Stack,
  IconButton,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Grid,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import PreviewIcon from '@mui/icons-material/Preview';
import CodeIcon from '@mui/icons-material/Code';
import SettingsIcon from '@mui/icons-material/Settings';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { Template } from '../../types';
import { useAppDispatch } from '../../hooks';
import { applyTemplate } from '../../store/slices/templateSlice';
import { logEvent } from '../../store/slices/analyticsSlice';
import { motion } from 'framer-motion';

interface TemplatePreviewProps {
  open: boolean;
  template: Template | null;
  onClose: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`template-tabpanel-${index}`}
      aria-labelledby={`template-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

export const TemplatePreview: React.FC<TemplatePreviewProps> = ({
  open,
  template,
  onClose,
}) => {
  const dispatch = useAppDispatch();
  const [activeTab, setActiveTab] = useState(0);
  const [copied, setCopied] = useState(false);

  if (!template) return null;

  const handleApplyTemplate = () => {
    dispatch(applyTemplate(template.id));
    dispatch(logEvent({
      event: {
        name: 'template_applied_from_preview',
        category: 'template',
        properties: {
          templateId: template.id,
          templateName: template.name,
        },
      },
    }));
    onClose();
  };

  const handleCopyStructure = () => {
    navigator.clipboard.writeText(JSON.stringify(template.content.structure, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const difficultyColors = {
    beginner: 'success',
    intermediate: 'warning',
    advanced: 'error',
  } as const;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      className="template-preview"
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box>
            <Typography variant="h6">{template.name}</Typography>
            <Stack direction="row" spacing={1} mt={1}>
              <Chip label={template.category} size="small" />
              <Chip
                label={template.difficulty}
                size="small"
                color={difficultyColors[template.difficulty]}
              />
              {template.industry && (
                <Chip label={template.industry} size="small" variant="outlined" />
              )}
            </Stack>
          </Box>
          <IconButton onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        <Tabs
          value={activeTab}
          onChange={(_, newValue) => setActiveTab(newValue)}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab icon={<PreviewIcon />} label="Preview" />
          <Tab icon={<CodeIcon />} label="Structure" />
          <Tab icon={<SettingsIcon />} label="Customization" />
        </Tabs>

        <TabPanel value={activeTab} index={0}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <Typography variant="body1" paragraph>
              {template.description}
            </Typography>

            <Box mb={3}>
              <Typography variant="subtitle1" gutterBottom fontWeight="bold">
                Key Features
              </Typography>
              <List dense>
                {template.features.map((feature, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <CheckCircleIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary={feature} />
                  </ListItem>
                ))}
              </List>
            </Box>

            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Estimated Time
                  </Typography>
                  <Typography variant="h6" color="primary">
                    {template.estimatedTime}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Popularity Score
                  </Typography>
                  <Typography variant="h6" color="success.main">
                    {template.popularity}%
                  </Typography>
                </Paper>
              </Grid>
            </Grid>

            {template.previewUrl && (
              <Box mt={3}>
                <Typography variant="subtitle1" gutterBottom fontWeight="bold">
                  Live Preview
                </Typography>
                <Box
                  component="iframe"
                  src={template.previewUrl}
                  sx={{
                    width: '100%',
                    height: 400,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                  }}
                />
              </Box>
            )}
          </motion.div>
        </TabPanel>

        <TabPanel value={activeTab} index={1}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="subtitle1" fontWeight="bold">
              Template Structure
            </Typography>
            <Button
              size="small"
              startIcon={<ContentCopyIcon />}
              onClick={handleCopyStructure}
              disabled={copied}
            >
              {copied ? 'Copied!' : 'Copy Structure'}
            </Button>
          </Box>
          <Paper variant="outlined" sx={{ p: 2, backgroundColor: 'grey.50' }}>
            <pre style={{ margin: 0, overflow: 'auto' }}>
              <code>{JSON.stringify(template.content.structure, null, 2)}</code>
            </pre>
          </Paper>
        </TabPanel>

        <TabPanel value={activeTab} index={2}>
          <Typography variant="subtitle1" gutterBottom fontWeight="bold">
            Available Customizations
          </Typography>
          <Stack spacing={2}>
            {template.content.customizations.map((customization) => (
              <Paper key={customization.id} variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  {customization.label}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Type: {customization.type} | Default: {customization.defaultValue}
                </Typography>
                {customization.options && (
                  <Box mt={1}>
                    <Typography variant="caption" color="text.secondary">
                      Options: {customization.options.join(', ')}
                    </Typography>
                  </Box>
                )}
              </Paper>
            ))}
          </Stack>
        </TabPanel>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleApplyTemplate}
          className="template-customize"
        >
          Use This Template
        </Button>
      </DialogActions>
    </Dialog>
  );
};