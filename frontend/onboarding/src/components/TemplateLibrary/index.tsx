import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  TextField,
  InputAdornment,
  Tabs,
  Tab,
  Chip,
  Button,
  IconButton,
  Drawer,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import { motion, AnimatePresence } from 'framer-motion';
import { useTemplates } from '../../hooks/useTemplates';
import { TemplateCard } from './TemplateCard';
import { TemplateFilters } from './TemplateFilters';
import { TemplatePreview } from './TemplatePreview';
import { ContentType } from '../../types';

export const TemplateLibrary: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [activeTab, setActiveTab] = useState<ContentType | 'all'>('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);

  const {
    templates,
    selectedTemplate,
    loading,
    filters,
    filterOptions,
    recommendedTemplates,
    select,
    clearSelection,
    updateFilter,
    resetFilters,
  } = useTemplates();

  const handleTabChange = (_: React.SyntheticEvent, newValue: ContentType | 'all') => {
    setActiveTab(newValue);
    if (newValue === 'all') {
      updateFilter({ category: null });
    } else {
      updateFilter({ category: newValue });
    }
  };

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    updateFilter({ searchQuery: event.target.value });
  };

  const handleTemplateClick = (template: any) => {
    select(template);
    setPreviewOpen(true);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Header */}
        <Box mb={4}>
          <Typography variant="h4" gutterBottom>
            Template Library
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Choose from our collection of optimized templates to get started quickly
          </Typography>
        </Box>

        {/* Search and Filters Bar */}
        <Box mb={3}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                variant="outlined"
                placeholder="Search templates..."
                value={filters.searchQuery}
                onChange={handleSearch}
                className="template-search"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Box display="flex" justifyContent="flex-end" gap={1}>
                <Button
                  startIcon={<FilterListIcon />}
                  onClick={() => setFilterDrawerOpen(true)}
                  variant="outlined"
                >
                  Filters
                  {Object.values(filters).filter(v => v && v !== 'popularity').length > 0 && (
                    <Chip
                      size="small"
                      label={Object.values(filters).filter(v => v && v !== 'popularity').length}
                      color="primary"
                      sx={{ ml: 1 }}
                    />
                  )}
                </Button>
                <IconButton
                  onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
                  color={viewMode === 'grid' ? 'primary' : 'default'}
                >
                  {viewMode === 'grid' ? <ViewModuleIcon /> : <ViewListIcon />}
                </IconButton>
              </Box>
            </Grid>
          </Grid>
        </Box>

        {/* Category Tabs */}
        <Box mb={3} className="template-categories">
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            variant="scrollable"
            scrollButtons="auto"
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab label="All Templates" value="all" />
            {Object.values(ContentType).map((type) => (
              <Tab
                key={type}
                label={type.charAt(0).toUpperCase() + type.slice(1)}
                value={type}
              />
            ))}
          </Tabs>
        </Box>

        {/* Recommended Section */}
        {activeTab === 'all' && recommendedTemplates.length > 0 && (
          <Box mb={4}>
            <Typography variant="h6" gutterBottom>
              Recommended for You
            </Typography>
            <Grid container spacing={2}>
              {recommendedTemplates.slice(0, 3).map((template) => (
                <Grid item xs={12} md={4} key={template.id}>
                  <TemplateCard
                    template={template}
                    onClick={() => handleTemplateClick(template)}
                    viewMode="grid"
                    isRecommended
                  />
                </Grid>
              ))}
            </Grid>
          </Box>
        )}

        {/* Templates Grid/List */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab + viewMode}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            {loading ? (
              <Box display="flex" justifyContent="center" py={8}>
                <Typography color="text.secondary">Loading templates...</Typography>
              </Box>
            ) : templates.length === 0 ? (
              <Box display="flex" justifyContent="center" py={8}>
                <Typography color="text.secondary">
                  No templates found. Try adjusting your filters.
                </Typography>
              </Box>
            ) : (
              <Grid container spacing={viewMode === 'grid' ? 3 : 1}>
                {templates.map((template) => (
                  <Grid
                    item
                    xs={12}
                    sm={viewMode === 'grid' ? 6 : 12}
                    md={viewMode === 'grid' ? 4 : 12}
                    key={template.id}
                  >
                    <TemplateCard
                      template={template}
                      onClick={() => handleTemplateClick(template)}
                      viewMode={viewMode}
                    />
                  </Grid>
                ))}
              </Grid>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Filters Drawer */}
        <Drawer
          anchor="right"
          open={filterDrawerOpen}
          onClose={() => setFilterDrawerOpen(false)}
          PaperProps={{ sx: { width: isMobile ? '100%' : 400 } }}
        >
          <TemplateFilters
            filters={filters}
            filterOptions={filterOptions}
            onUpdateFilter={updateFilter}
            onResetFilters={resetFilters}
            onClose={() => setFilterDrawerOpen(false)}
          />
        </Drawer>

        {/* Template Preview */}
        <TemplatePreview
          open={previewOpen}
          template={selectedTemplate}
          onClose={() => {
            setPreviewOpen(false);
            clearSelection();
          }}
        />
      </motion.div>
    </Container>
  );
};