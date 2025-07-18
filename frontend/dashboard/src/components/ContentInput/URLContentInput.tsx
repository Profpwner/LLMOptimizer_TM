import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  Chip,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  LinearProgress
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddLinkIcon from '@mui/icons-material/AddLink';
import SendIcon from '@mui/icons-material/Send';
import { useSubmitURLsMutation } from '../../services/contentApi';
import { contentWebSocket, JobUpdate } from '../../services/contentWebSocket';

interface URLItem {
  id: string;
  url: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error?: string;
}

export default function URLContentInput() {
  const [urls, setUrls] = useState<URLItem[]>([]);
  const [currentUrl, setCurrentUrl] = useState('');
  const [contentType, setContentType] = useState('article');
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<number>(0);

  const [submitURLs, { isLoading }] = useSubmitURLsMutation();

  // Subscribe to WebSocket job updates
  useEffect(() => {
    if (!activeJobId) return;

    // Subscribe to job updates
    contentWebSocket.subscribeToJob(activeJobId);

    const unsubscribe = contentWebSocket.subscribe('job_update', (message) => {
      const update = message as JobUpdate;
      
      if (update.job_id === activeJobId) {
        if (update.progress !== undefined) {
          setJobProgress(update.progress * 100);
        }

        // Update URL statuses based on job update
        if (update.data?.results) {
          setUrls(prev => prev.map(url => {
            const result = update.data.results.find((r: any) => r.url === url.url);
            if (result) {
              return {
                ...url,
                status: result.success ? 'completed' : 'failed',
                error: result.error
              };
            }
            return url;
          }));
        }

        // Handle job completion
        if (update.status === 'completed') {
          setActiveJobId(null);
          setJobProgress(0);
          
          // Clear successful URLs after a delay
          setTimeout(() => {
            setUrls(prev => prev.filter(u => u.status === 'failed'));
          }, 3000);
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, [activeJobId]);

  const validateURL = (url: string): boolean => {
    try {
      const urlObj = new URL(url);
      return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
    } catch {
      return false;
    }
  };

  const handleAddURL = () => {
    setValidationError(null);
    
    if (!currentUrl) return;
    
    if (!validateURL(currentUrl)) {
      setValidationError('Please enter a valid URL');
      return;
    }

    if (urls.some(u => u.url === currentUrl)) {
      setValidationError('This URL has already been added');
      return;
    }

    const newUrl: URLItem = {
      id: Date.now().toString(),
      url: currentUrl,
      status: 'pending'
    };

    setUrls(prev => [...prev, newUrl]);
    setCurrentUrl('');
  };

  const handleRemoveURL = (id: string) => {
    setUrls(prev => prev.filter(u => u.id !== id));
  };

  const handleSubmit = async () => {
    setError(null);

    if (urls.length === 0) {
      setError('Please add at least one URL');
      return;
    }

    try {
      // Update all URLs to processing status
      setUrls(prev => prev.map(u => ({ ...u, status: 'processing' })));

      const response = await submitURLs({
        urls: urls.map(u => u.url),
        content_type: contentType,
        metadata: {
          source: 'url_input',
          batch_size: urls.length
        }
      }).unwrap();

      // Set the active job ID to track progress via WebSocket
      if (response.job_id) {
        setActiveJobId(response.job_id);
      }

    } catch (err: any) {
      setError(err.data?.detail || 'Failed to submit URLs');
      // Reset all URLs to pending on error
      setUrls(prev => prev.map(u => ({ ...u, status: 'pending' })));
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddURL();
    }
  };

  const getStatusColor = (status: URLItem['status']) => {
    switch (status) {
      case 'pending': return 'default';
      case 'processing': return 'primary';
      case 'completed': return 'success';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  const completedCount = urls.filter(u => u.status === 'completed').length;
  const processingCount = urls.filter(u => u.status === 'processing').length;

  return (
    <Box>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Extract content from web pages by providing their URLs. The system will automatically
            scrape and process the content for optimization.
          </Typography>
        </Grid>

        <Grid item xs={12} md={8}>
          <TextField
            fullWidth
            label="Enter URL"
            variant="outlined"
            value={currentUrl}
            onChange={(e) => setCurrentUrl(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="https://example.com/article"
            error={!!validationError}
            helperText={validationError}
          />
        </Grid>

        <Grid item xs={12} md={4}>
          <FormControl fullWidth>
            <InputLabel>Content Type</InputLabel>
            <Select
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
              label="Content Type"
            >
              <MenuItem value="article">Article</MenuItem>
              <MenuItem value="blog_post">Blog Post</MenuItem>
              <MenuItem value="product_description">Product Description</MenuItem>
              <MenuItem value="landing_page">Landing Page</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12}>
          <Button
            variant="outlined"
            startIcon={<AddLinkIcon />}
            onClick={handleAddURL}
            disabled={!currentUrl}
          >
            Add URL
          </Button>
        </Grid>

        {urls.length > 0 && (
          <Grid item xs={12}>
            <Paper variant="outlined">
              <Box sx={{ p: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  URLs to Process ({urls.length})
                </Typography>
                {(processingCount > 0 || activeJobId) && (
                  <Box sx={{ mb: 2 }}>
                    <LinearProgress 
                      variant={activeJobId ? "determinate" : "indeterminate"} 
                      value={jobProgress} 
                    />
                    <Typography variant="caption" color="text.secondary">
                      {activeJobId 
                        ? `Processing URLs... ${Math.round(jobProgress)}% complete`
                        : `Processing ${processingCount} of {urls.length} URLs...`
                      }
                    </Typography>
                  </Box>
                )}
                <List>
                  {urls.map((urlItem) => (
                    <ListItem key={urlItem.id}>
                      <ListItemText
                        primary={urlItem.url}
                        secondary={urlItem.error}
                      />
                      <Chip
                        label={urlItem.status}
                        color={getStatusColor(urlItem.status)}
                        size="small"
                        sx={{ mr: 2 }}
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          edge="end"
                          onClick={() => handleRemoveURL(urlItem.id)}
                          disabled={urlItem.status === 'processing'}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </Box>
            </Paper>
          </Grid>
        )}

        {error && (
          <Grid item xs={12}>
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          </Grid>
        )}

        {completedCount > 0 && (
          <Grid item xs={12}>
            <Alert severity="success">
              Successfully processed {completedCount} URL{completedCount > 1 ? 's' : ''}!
            </Alert>
          </Grid>
        )}

        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              startIcon={isLoading ? <CircularProgress size={20} /> : <SendIcon />}
              onClick={handleSubmit}
              disabled={isLoading || urls.length === 0}
            >
              {isLoading ? 'Processing...' : `Process ${urls.length} URL${urls.length !== 1 ? 's' : ''}`}
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}